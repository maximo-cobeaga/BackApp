"""Import or dry-run the legacy backup history CSV."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.imports.legacy_history import (
    LegacyImportError,
    commit_legacy_backup_history,
    parse_legacy_backup_history,
)
from apps.tenancy.models import Organization


class Command(BaseCommand):
    help = "Dry-run or import the legacy backup history CSV matrix."

    def add_arguments(self, parser):
        parser.add_argument("source_file", help="Path to the legacy CSV file.")
        parser.add_argument("--tenant", required=True, help="Tenant slug for the import scope.")
        parser.add_argument("--encoding", default="cp1252", help="CSV encoding.")
        parser.add_argument("--delimiter", default=";", help="CSV delimiter.")
        parser.add_argument(
            "--output",
            help="Optional path to write the JSON report.",
        )
        parser.add_argument(
            "--dry-run-report",
            help="Dry-run JSON report required before commit.",
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true", help="Parse without DB writes.")
        mode.add_argument("--commit", action="store_true", help="Commit after review.")

    def handle(self, *args, **options):
        try:
            if options["commit"]:
                report_json = self._commit(options)
            else:
                report_json = self._dry_run(options)
        except LegacyImportError as exc:
            raise CommandError(str(exc)) from exc

        self._write_report(report_json, options.get("output"))

    def _dry_run(self, options) -> str:
        summary = parse_legacy_backup_history(
            options["source_file"],
            encoding=options["encoding"],
            delimiter=options["delimiter"],
        )
        return summary.to_json(
            tenant=options["tenant"],
            dry_run=True,
        )

    def _commit(self, options) -> str:
        dry_run_report = options.get("dry_run_report")
        if not dry_run_report:
            raise LegacyImportError("Commit requires --dry-run-report.")
        try:
            organization = Organization.objects.get(slug=options["tenant"])
        except Organization.DoesNotExist as exc:
            raise LegacyImportError(f"Tenant not found: {options['tenant']}") from exc
        result = commit_legacy_backup_history(
            options["source_file"],
            organization=organization,
            dry_run_report_path=dry_run_report,
            encoding=options["encoding"],
            delimiter=options["delimiter"],
        )
        return result.to_json(tenant=organization.slug)

    def _write_report(self, report_json: str, output_path: str | None) -> None:
        if output_path:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(report_json + "\n", encoding="utf-8")
            self.stdout.write(f"Wrote report to {destination}")
            return

        self.stdout.write(report_json)
