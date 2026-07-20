"""Daily-control export and expected-execution services."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from openpyxl import Workbook

from apps.backups.models import BackupJob, BackupSchedule
from apps.operations.models import DailyControlEntry, ExpectedExecution
from apps.tenancy.models import Organization


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
