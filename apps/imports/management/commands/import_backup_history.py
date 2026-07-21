"""Import or dry-run the legacy backup history CSV."""
from django.core.management.base import BaseCommand, CommandError

from apps.imports.legacy_history import LegacyImportError, parse_legacy_backup_history


class Command(BaseCommand):
    help = "Dry-run or import the legacy backup history CSV matrix."

    def add_arguments(self, parser):
        parser.add_argument("source_file", help="Path to the legacy CSV file.")
        parser.add_argument("--tenant", required=True, help="Tenant slug for the import scope.")
        parser.add_argument("--encoding", default="cp1252", help="CSV encoding.")
        parser.add_argument("--delimiter", default=";", help="CSV delimiter.")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true", help="Parse without DB writes.")
        mode.add_argument("--commit", action="store_true", help="Commit after review.")

    def handle(self, *args, **options):
        if options["commit"]:
            raise CommandError("Commit mode is not implemented in this slice. Run --dry-run.")
        try:
            summary = parse_legacy_backup_history(
                options["source_file"],
                encoding=options["encoding"],
                delimiter=options["delimiter"],
            )
        except LegacyImportError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            summary.to_json(
                tenant=options["tenant"],
                dry_run=True,
            )
        )
