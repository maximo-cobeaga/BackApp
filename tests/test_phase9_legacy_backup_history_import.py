import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from apps.imports.legacy_history import (
    LegacyStatus,
    parse_legacy_backup_history,
    normalize_legacy_status,
)
from apps.imports.models import ImportBatch


FIXED_HEADERS = [
    "Cliente",
    "Fecha de Alta del Cliente",
    "Fecha de Baja del Cliente",
    "Sucursal",
    "Servidor",
    "Tipo de Backup",
    "Método de Backup",
    "Responsable de Disco Externo",
]


class PhaseNineLegacyBackupHistoryImportTest(TestCase):
    def _legacy_csv(self, path: Path):
        rows = [
            ["Si el cliente está suspendido", *([""] * 21)],
            ["Si el cliente se da de baja", *([""] * 21)],
            ["Correctos", *([""] * 21)],
            ["Errores", *([""] * 21)],
            ["Responsables", *([""] * 21)],
            [*([""] * 8), "01/01/2026", "", "", "", "02/01/2026", "", "", "", "03/01/2026", "", "", "", "", ""],
            [*FIXED_HEADERS, "Responsable", "Estado", "Ticket", "Observaciones", "Responsable", "Estado", "Ticket", "Observaciones", "Responsable", "Estado", "Ticket", "Observaciones", "", ""],
            [".", *([""] * 21)],
            ["Cliente A", "", "", "MDP", "YA01V", "SQL", "Veeam Backup", "", "Ana", "Correcto", "", "OK", "Ana", "Error", "123", "se realizó correctamente pero no llegó reporte", "", "", "", "", "", ""],
            ["", "", "", "MDP", "YA02V", "NAKIVO externo viernes", "", "Juan <juan@example.com>", "..", "Warning", "124", "sin modificaciones 7 días", "", "N/A", "", "No aplica", "", ",", "", "valor raro", "", ""],
            [".", "", "", "", "", "", "", "", ".", ".", "", "", "", "", "", "", "", "", "", "", "", ""],
        ]
        with path.open("w", encoding="cp1252", newline="") as handle:
            writer = csv.writer(handle, delimiter=";", lineterminator="\r\n")
            writer.writerows(rows)

    def test_normalizes_legacy_status_values_explicitly(self):
        assert normalize_legacy_status("Correcto") == LegacyStatus.SUCCESS
        assert normalize_legacy_status("Correctos") == LegacyStatus.SUCCESS
        assert normalize_legacy_status("Warning") == LegacyStatus.WARNING
        assert normalize_legacy_status("Warnings") == LegacyStatus.WARNING
        assert normalize_legacy_status("Error") == LegacyStatus.ERROR
        assert normalize_legacy_status("N/A") == LegacyStatus.NOT_APPLICABLE
        assert normalize_legacy_status("NA") == LegacyStatus.NOT_APPLICABLE
        assert normalize_legacy_status(".") == LegacyStatus.PLACEHOLDER
        assert normalize_legacy_status(",") == LegacyStatus.UNKNOWN
        assert normalize_legacy_status("N") == LegacyStatus.UNKNOWN
        assert normalize_legacy_status("") == LegacyStatus.UNRECORDED

    def test_dry_run_parses_matrix_without_database_writes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "Gestion de Backups 2026(Control Backups).csv"
            self._legacy_csv(path)

            summary = parse_legacy_backup_history(
                path,
                encoding="cp1252",
                delimiter=";",
            )

        assert ImportBatch.objects.count() == 0
        assert summary.source_file == path.name
        assert summary.rows == 11
        assert summary.columns == 22
        assert summary.effective_columns == 20
        assert summary.ignored_trailing_empty_columns == 2
        assert summary.date_groups == 3
        assert summary.managed_customers == 1
        assert summary.configuration_rows == 2
        assert summary.separator_rows == 1
        assert summary.first_recorded_date == "2026-01-01"
        assert summary.last_recorded_date == "2026-01-03"
        assert summary.legacy_status_cells == 5
        assert summary.observations == 5
        assert summary.ticket_references == 2
        assert summary.unique_ticket_ids == 2
        assert summary.imported_execution_candidates == 3
        assert summary.status_counts[LegacyStatus.SUCCESS] == 1
        assert summary.status_counts[LegacyStatus.WARNING] == 1
        assert summary.status_counts[LegacyStatus.ERROR] == 1
        assert summary.status_counts[LegacyStatus.NOT_APPLICABLE] == 1
        assert summary.status_counts[LegacyStatus.UNKNOWN] == 1
        assert summary.provider_counts["VEEAM"] == 1
        assert summary.provider_confirmation_required == 1
        issue_codes = {issue["issue_code"] for issue in summary.issues}
        assert "STATUS_OBSERVATION_CONFLICT" in issue_codes
        assert "UNKNOWN_STATUS" in issue_codes

    def test_management_command_outputs_dry_run_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            self._legacy_csv(path)
            output = StringIO()

            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                stdout=output,
            )

        payload = json.loads(output.getvalue())
        assert payload["tenant"] == "pilot"
        assert payload["dry_run"] is True
        assert payload["configuration_rows"] == 2
        assert payload["date_groups"] == 3
        assert ImportBatch.objects.count() == 0
