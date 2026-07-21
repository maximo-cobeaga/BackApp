"""Bootstrap operational backup records from imported legacy configurations."""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.imports.services import bootstrap_legacy_backups
from apps.tenancy.models import Organization


class Command(BaseCommand):
    help = "Create provisional operational backup records from legacy import staging data."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant slug for the import scope.")
        parser.add_argument(
            "--source",
            required=True,
            help="Path to the legacy commit JSON report.",
        )
        parser.add_argument(
            "--output",
            help="Optional path to write the bootstrap JSON report.",
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
        source_sha256 = source_report.get("source_sha256")
        if not source_sha256:
            raise CommandError("Source report does not include source_sha256.")

        result = bootstrap_legacy_backups(
            organization=organization,
            source_sha256=source_sha256,
        )
        payload = json.dumps(
            result.to_dict(
                tenant=organization.slug,
                source_sha256=source_sha256,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        output_path = options.get("output")
        if output_path:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(payload + "\n", encoding="utf-8")
            self.stdout.write(f"Wrote bootstrap report to {destination}")
            return
        self.stdout.write(payload)
