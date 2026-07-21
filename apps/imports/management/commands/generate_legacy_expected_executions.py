"""Generate expected executions across the legacy recorded date range."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from apps.operations.models import ExpectedExecution
from apps.operations.services import generate_expected_executions
from apps.tenancy.models import Organization


class Command(BaseCommand):
    help = "Generate expected executions for the date range recorded in a legacy report."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant slug for the import scope.")
        parser.add_argument(
            "--source",
            required=True,
            help="Path to the legacy commit JSON report.",
        )
        parser.add_argument(
            "--output",
            help="Optional path to write the generation report.",
        )

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(slug=options["tenant"])
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Tenant not found: {options['tenant']}") from exc

        source_report_path = Path(options["source"])
        try:
            source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CommandError(f"Source report not found: {source_report_path}") from exc
        summary = source_report.get("summary") or {}
        start_date = parse_date(summary.get("first_recorded_date") or "")
        end_date = parse_date(summary.get("last_recorded_date") or "")
        if start_date is None or end_date is None:
            raise CommandError("Source report does not include a valid recorded date range.")
        if end_date < start_date:
            raise CommandError("Source report recorded date range is invalid.")

        before_count = ExpectedExecution.objects.filter(
            organization=organization,
            service_date__gte=start_date,
            service_date__lte=end_date,
        ).count()
        dates_considered = 0
        current_date = start_date
        while current_date <= end_date:
            dates_considered += 1
            generate_expected_executions(
                organization=organization,
                service_date=current_date,
            )
            current_date += timedelta(days=1)
        after_count = ExpectedExecution.objects.filter(
            organization=organization,
            service_date__gte=start_date,
            service_date__lte=end_date,
        ).count()
        payload = json.dumps(
            {
                "tenant": organization.slug,
                "source_sha256": source_report.get("source_sha256"),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "dates_considered": dates_considered,
                "expected_executions_created": after_count - before_count,
                "expected_executions_total_in_range": after_count,
                "creates_backup_executions": False,
                "creates_tickets": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        output_path = options.get("output")
        if output_path:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(payload + "\n", encoding="utf-8")
            self.stdout.write(f"Wrote expected execution report to {destination}")
            return
        self.stdout.write(payload)
