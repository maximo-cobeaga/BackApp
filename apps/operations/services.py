"""Daily-control export and expected-execution services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from openpyxl import Workbook

from apps.backups.models import BackupJob, BackupSchedule
from apps.operations.models import BackupExecution, DailyControlEntry, ExpectedExecution
from apps.parsers.models import ParsedReportItem
from apps.tenancy.models import Organization


@dataclass(frozen=True)
class BackupExecutionCandidate:
    expected_execution: ExpectedExecution
    confidence: float
    reasons: list[str]


DAILY_CONTROL_HEADERS = [
    "Fecha",
    "Cliente",
    "Sede",
    "Tarea",
    "Tecnología",
    "Objeto",
    "Resultado",
    "Observación",
    "Ticket",
]


def build_daily_control_workbook(*, organization: Organization, control_date: date) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Control diario"
    sheet.append(DAILY_CONTROL_HEADERS)

    entries = DailyControlEntry.objects.select_related(
        "backup_job__managed_customer",
        "backup_job__site",
        "backup_job__technology",
        "protected_object",
    ).filter(organization=organization, control_date=control_date)

    for entry in entries:
        sheet.append(
            [
                entry.control_date.isoformat(),
                entry.backup_job.managed_customer.name,
                entry.backup_job.site.name,
                entry.backup_job.name,
                entry.backup_job.technology.name,
                entry.protected_object.name if entry.protected_object else "",
                entry.get_result_display(),
                entry.manual_observation,
                entry.ticket_reference,
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def parse_weekdays(raw_weekdays: str) -> set[int]:
    weekdays: set[int] = set()
    for item in raw_weekdays.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        weekday = int(stripped)
        if weekday < 1 or weekday > 7:
            raise ValueError("Weekdays must use ISO values from 1 to 7.")
        weekdays.add(weekday)
    return weekdays


def schedule_runs_on(schedule: BackupSchedule, service_date: date) -> bool:
    configured_weekdays = parse_weekdays(schedule.weekdays)
    if configured_weekdays and service_date.isoweekday() not in configured_weekdays:
        return False

    if schedule.frequency == BackupSchedule.Frequency.DAILY:
        return True
    if schedule.frequency == BackupSchedule.Frequency.WEEKLY:
        return bool(configured_weekdays) or service_date.isoweekday() == 1
    if schedule.frequency == BackupSchedule.Frequency.MONTHLY:
        return service_date.day == 1
    if schedule.frequency == BackupSchedule.Frequency.CUSTOM:
        return bool(configured_weekdays)
    return False


def local_datetime_for(
    *,
    service_date: date,
    local_time: time,
    timezone_name: str,
    offset_days: int = 0,
) -> datetime:
    local_zone = ZoneInfo(timezone_name)
    local_date = service_date + timedelta(days=offset_days)
    local_value = datetime.combine(local_date, local_time, tzinfo=local_zone)
    return local_value.astimezone(UTC)


@transaction.atomic
def generate_expected_executions(
    *,
    organization: Organization,
    service_date: date,
) -> list[ExpectedExecution]:
    schedules = BackupSchedule.objects.select_related("backup_job").filter(
        organization=organization,
        is_active=True,
        backup_job__status=BackupJob.Status.ACTIVE,
    )
    executions: list[ExpectedExecution] = []
    for schedule in schedules:
        if not schedule_runs_on(schedule, service_date):
            continue
        scheduled_start_at = local_datetime_for(
            service_date=service_date,
            local_time=schedule.scheduled_time,
            timezone_name=schedule.timezone,
        )
        report_deadline_at = local_datetime_for(
            service_date=service_date,
            local_time=schedule.report_deadline_time,
            timezone_name=schedule.timezone,
            offset_days=schedule.report_deadline_offset_days,
        )
        execution, _created = ExpectedExecution.objects.get_or_create(
            organization=organization,
            schedule=schedule,
            service_date=service_date,
            defaults={
                "backup_job": schedule.backup_job,
                "scheduled_start_at": scheduled_start_at,
                "report_deadline_at": report_deadline_at,
                "status": ExpectedExecution.Status.WAITING_REPORT,
            },
        )
        executions.append(execution)
    return executions


@transaction.atomic
def mark_missing_reports(*, organization: Organization, now: datetime | None = None) -> int:
    current_time = now or timezone.now()
    overdue = ExpectedExecution.objects.select_for_update().filter(
        organization=organization,
        status=ExpectedExecution.Status.WAITING_REPORT,
        report_deadline_at__lt=current_time,
    )
    updated = overdue.update(
        status=ExpectedExecution.Status.NO_REPORT,
        system_summary="No report was recorded before the configured deadline.",
    )
    return updated


def backup_execution_result_from_parsed_item(parsed_item: ParsedReportItem) -> str:
    if parsed_item.parser_status == ParsedReportItem.ParserStatus.SUCCESS:
        return BackupExecution.Result.SUCCESS
    if parsed_item.parser_status == ParsedReportItem.ParserStatus.WARNING:
        return BackupExecution.Result.WARNING
    if parsed_item.parser_status == ParsedReportItem.ParserStatus.FAILED:
        return BackupExecution.Result.ERROR
    if parsed_item.parser_status == ParsedReportItem.ParserStatus.PARTIAL:
        return BackupExecution.Result.WARNING
    if parsed_item.parser_status == ParsedReportItem.ParserStatus.CANCELED:
        return BackupExecution.Result.CANCELLED
    if parsed_item.parser_status == ParsedReportItem.ParserStatus.RUNNING:
        return BackupExecution.Result.UNKNOWN
    return BackupExecution.Result.UNKNOWN


def backup_execution_candidates_for_parsed_item(
    *,
    parsed_item: ParsedReportItem,
    limit: int = 10,
) -> list[BackupExecutionCandidate]:
    provider = str((parsed_item.metrics or {}).get("provider") or "").casefold()
    job_hints = {hint.casefold() for hint in parsed_item.job_hints if hint}
    received_at = parsed_item.message.received_at
    queryset = ExpectedExecution.objects.select_related(
        "backup_job__managed_customer",
        "backup_job__site",
        "backup_job__technology",
    ).filter(organization=parsed_item.organization)

    if received_at is not None:
        received_date = received_at.date()
        queryset = queryset.filter(
            service_date__gte=received_date - timedelta(days=2),
            service_date__lte=received_date + timedelta(days=1),
        )

    candidates: list[BackupExecutionCandidate] = []
    for expected in queryset:
        score = 0
        reasons: list[str] = []
        job = expected.backup_job
        if job.name.casefold() in job_hints:
            score += 60
            reasons.append("Coincide la tarea detectada")
        elif job_hints:
            aliases = [
                alias.strip().casefold()
                for alias in job.matching_aliases.replace(";", "\n")
                .replace(",", "\n")
                .splitlines()
                if alias.strip()
            ]
            if any(alias in job_hints for alias in aliases):
                score += 55
                reasons.append("Coincide un alias de la tarea")

        technology_name = job.technology.name.casefold()
        if provider and (provider in technology_name or technology_name in provider):
            score += 20
            reasons.append("Coincide la tecnología detectada")

        if received_at is not None:
            deadline_margin = expected.report_deadline_at + timedelta(hours=12)
            if expected.scheduled_start_at <= received_at <= deadline_margin:
                score += 20
                reasons.append("El correo llegó dentro de la ventana esperada")
            elif expected.service_date <= received_at.date() <= expected.service_date + timedelta(days=1):
                score += 10
                reasons.append("La fecha del correo es cercana a la ejecución")

        if score > 0:
            candidates.append(
                BackupExecutionCandidate(
                    expected_execution=expected,
                    confidence=round(min(score / 100, 1.0), 2),
                    reasons=reasons,
                )
            )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.confidence,
            candidate.expected_execution.service_date,
            candidate.expected_execution.scheduled_start_at,
        ),
        reverse=True,
    )[:limit]


@transaction.atomic
def create_backup_execution_from_parsed_item(
    *,
    parsed_item: ParsedReportItem,
    expected_execution: ExpectedExecution,
    result: str | None = None,
    user=None,
    operator_note: str = "",
) -> tuple[BackupExecution, bool]:
    if parsed_item.organization_id != expected_execution.organization_id:
        raise ValueError("Parsed item and expected execution must belong to the same organization.")

    selected_result = result or backup_execution_result_from_parsed_item(parsed_item)
    execution, created = BackupExecution.objects.get_or_create(
        organization=expected_execution.organization,
        parsed_item=parsed_item,
        defaults={
            "backup_job": expected_execution.backup_job,
            "expected_execution": expected_execution,
            "service_date": expected_execution.service_date,
            "occurred_at": parsed_item.occurred_at,
            "result": selected_result,
            "match_status": BackupExecution.MatchStatus.MANUAL_MATCHED,
            "confidence": parsed_item.confidence,
            "parser_summary": parsed_item.summary,
            "operator_note": operator_note,
            "matched_by": user if getattr(user, "is_authenticated", False) else None,
            "matched_at": timezone.now(),
        },
    )
    if not created:
        return execution, False

    parsed_item.review_status = ParsedReportItem.ReviewStatus.REVIEWED
    parsed_item.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    parsed_item.reviewed_at = timezone.now()
    parsed_item.review_note = operator_note
    parsed_item.save(
        update_fields=[
            "review_status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "updated_at",
        ]
    )

    if not parsed_item.message.parsed_items.filter(
        review_status=ParsedReportItem.ReviewStatus.NEEDS_REVIEW
    ).exists():
        parsed_item.message.parser_status = "REVIEWED"
        parsed_item.message.save(update_fields=["parser_status", "updated_at"])

    return execution, True


def dashboard_metrics(*, organization: Organization, service_date: date) -> dict[str, int]:
    execution_counts = ExpectedExecution.objects.filter(
        organization=organization,
        service_date=service_date,
    ).aggregate(
        expected=Count("id"),
        waiting=Count("id", filter=Q(status=ExpectedExecution.Status.WAITING_REPORT)),
        no_report=Count("id", filter=Q(status=ExpectedExecution.Status.NO_REPORT)),
    )
    manual_counts = DailyControlEntry.objects.filter(
        organization=organization,
        control_date=service_date,
    ).aggregate(
        manual_total=Count("id"),
        manual_success=Count("id", filter=Q(result=DailyControlEntry.Result.SUCCESS)),
        manual_warning=Count("id", filter=Q(result=DailyControlEntry.Result.WARNING)),
        manual_error=Count("id", filter=Q(result=DailyControlEntry.Result.ERROR)),
    )
    return {**execution_counts, **manual_counts}
