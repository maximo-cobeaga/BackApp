"""Bootstrap provisional schedules for legacy-created backup jobs."""
from __future__ import annotations

import json
from datetime import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.backups.models import BackupSchedule
from apps.imports.services import bootstrap_legacy_schedules
from apps.tenancy.models import Organization


class Command(BaseCommand):
    help = "Create provisional assisted schedules for legacy bootstrapped backup jobs."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant slug for the import scope.")
        parser.add_argument(
            "--frequency",
            default=BackupSchedule.Frequency.DAILY,
            choices=[choice[0] for choice in BackupSchedule.Frequency.choices],
        )
        parser.add_argument("--weekdays", default="1,2,3,4,5")
        parser.add_argument("--scheduled-time", default="23:00")
        parser.add_argument("--deadline-time", default="08:00")
        parser.add_argument("--deadline-offset-days", type=int, default=1)
        parser.add_argument(
            "--mode",
            default=BackupSchedule.Mode.ASSISTED,
            choices=[choice[0] for choice in BackupSchedule.Mode.choices],
        )
        parser.add_argument("--timezone", default="America/Argentina/Buenos_Aires")
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing provisional schedules instead of skipping them.",
        )
        parser.add_argument("--output", help="Optional path to write the schedule report.")

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(slug=options["tenant"])
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Tenant not found: {options['tenant']}") from exc

        try:
            scheduled_time = _parse_time(options["scheduled_time"], "scheduled-time")
            deadline_time = _parse_time(options["deadline_time"], "deadline-time")
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        result = bootstrap_legacy_schedules(
            organization=organization,
            frequency=options["frequency"],
            weekdays=options["weekdays"],
            scheduled_time=scheduled_time,
            report_deadline_time=deadline_time,
            report_deadline_offset_days=options["deadline_offset_days"],
            mode=options["mode"],
            timezone_name=options["timezone"],
            update_existing=options["update_existing"],
        )
        payload = json.dumps(
            result.to_dict(tenant=organization.slug),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        output_path = options.get("output")
        if output_path:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(payload + "\n", encoding="utf-8")
            self.stdout.write(f"Wrote schedule bootstrap report to {destination}")
            return
        self.stdout.write(payload)


def _parse_time(value: str, option_name: str) -> time:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"--{option_name} must use HH:MM format.")
    hour, minute = [int(part) for part in parts]
    return time(hour=hour, minute=minute)
