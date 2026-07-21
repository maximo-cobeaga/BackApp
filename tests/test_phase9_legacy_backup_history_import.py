import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.imports.legacy_history import (
    LegacyStatus,
    parse_legacy_backup_history,
    normalize_legacy_status,
)
from apps.imports.models import (
    ImportBatch,
    LegacyBackupConfiguration,
    LegacyDailyRecord,
    LegacyImportIssue,
    LegacyTicketReference,
)
from apps.backups.models import BackupJob, BackupJobTarget, BackupSchedule, BackupTechnology
from apps.customers.models import ManagedCustomer, Site
from apps.inventory.models import ProtectedObject
from apps.operations.models import ExpectedExecution
from apps.tenancy.models import Membership, Organization


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
            [*FIXED_HEADERS, "Responsable de verificacion de backup", "Estado", "Ticket", "Observaciones", "Responsable de verificacion de backup", "Estado", "Ticket", "Observaciones", "Responsable de verificacion de backup", "Estado", "Ticket", "Observaciones", "", ""],
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
        assert summary.legacy_status_cells == 6
        assert summary.legacy_daily_records == 5
        assert summary.observations == 5
        assert summary.ticket_references == 2
        assert summary.unique_ticket_ids == 2
        assert summary.imported_execution_candidates == 3
        assert summary.status_counts[LegacyStatus.SUCCESS] == 1
        assert summary.status_counts[LegacyStatus.WARNING] == 1
        assert summary.status_counts[LegacyStatus.ERROR] == 1
        assert summary.status_counts[LegacyStatus.NOT_APPLICABLE] == 1
        assert summary.status_counts[LegacyStatus.UNKNOWN] == 1
        assert summary.status_counts[LegacyStatus.PLACEHOLDER] == 1
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

    def test_management_command_writes_dry_run_json_to_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            output_path = Path(directory) / "reports" / "legacy-dry-run.json"
            self._legacy_csv(path)
            stdout = StringIO()

            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(output_path),
                stdout=stdout,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        assert "Wrote report" in stdout.getvalue()
        assert payload["tenant"] == "pilot"
        assert payload["dry_run"] is True
        assert payload["configuration_rows"] == 2
        assert ImportBatch.objects.count() == 0

    def test_management_command_commits_after_matching_dry_run_report(self):
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            report_path = Path(directory) / "legacy-dry-run.json"
            commit_report_path = Path(directory) / "legacy-commit.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(report_path),
                stdout=StringIO(),
            )

            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(report_path),
                commit=True,
                output=str(commit_report_path),
                stdout=StringIO(),
            )
            payload = json.loads(commit_report_path.read_text(encoding="utf-8"))

            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(report_path),
                commit=True,
                stdout=StringIO(),
            )

        assert payload["dry_run"] is False
        assert payload["batch_created"] is True
        assert payload["managed_customers_created"] == 1
        assert payload["configurations_created"] == 2
        assert payload["daily_records_created"] == 5
        assert payload["issues_created"] == 2
        assert payload["ticket_references_created"] == 2
        assert ImportBatch.objects.filter(organization=organization).count() == 1
        assert ManagedCustomer.objects.filter(organization=organization).count() == 1
        assert LegacyBackupConfiguration.objects.filter(organization=organization).count() == 2
        assert LegacyDailyRecord.objects.filter(organization=organization).count() == 5
        assert LegacyImportIssue.objects.filter(organization=organization).count() == 2
        assert LegacyTicketReference.objects.filter(organization=organization).count() == 2

    def test_legacy_import_review_views_are_tenant_scoped(self):
        User = get_user_model()
        user = User.objects.create_user(username="admin", password="pass")
        other_user = User.objects.create_user(username="other", password="pass")
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        other_organization = Organization.objects.create(name="Other", slug="other")
        Membership.objects.create(
            organization=organization,
            user=user,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=other_organization,
            user=other_user,
            role=Membership.Role.ADMIN,
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            report_path = Path(directory) / "legacy-dry-run.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(report_path),
                stdout=StringIO(),
            )
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(report_path),
                commit=True,
                stdout=StringIO(),
            )

        hidden_customer = ManagedCustomer.objects.create(
            organization=other_organization,
            name="Cliente oculto",
        )
        hidden_batch = ImportBatch.objects.create(
            organization=other_organization,
            original_filename="hidden.csv",
            source_sha256="h" * 64,
        )
        LegacyBackupConfiguration.objects.create(
            organization=other_organization,
            import_batch=hidden_batch,
            managed_customer=hidden_customer,
            source_sha256="h" * 64,
            source_row=99,
            legacy_fingerprint="f" * 64,
            legacy_customer_name="Cliente oculto",
            legacy_backup_name="Oculto",
        )

        self.client.force_login(user)
        summary = self.client.get(reverse("legacy_import_summary"))
        configs = self.client.get(reverse("legacy_import_configuration_list"))
        records = self.client.get(reverse("legacy_import_daily_record_list"))
        issues = self.client.get(reverse("legacy_import_issue_list"))

        assert summary.status_code == 200
        assert configs.status_code == 200
        assert records.status_code == 200
        assert issues.status_code == 200
        summary_content = summary.content.decode()
        configs_content = configs.content.decode()
        records_content = records.content.decode()
        issues_content = issues.content.decode()
        assert "498" not in summary_content
        assert "Cliente A" in configs_content
        assert "Oculto" not in configs_content
        assert "Correcto" in records_content
        assert "STATUS_OBSERVATION_CONFLICT" in issues_content

    def test_legacy_configuration_detail_shows_records_and_issues(self):
        User = get_user_model()
        user = User.objects.create_user(username="admin", password="pass")
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        Membership.objects.create(
            organization=organization,
            user=user,
            role=Membership.Role.ADMIN,
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            report_path = Path(directory) / "legacy-dry-run.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(report_path),
                stdout=StringIO(),
            )
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(report_path),
                commit=True,
                stdout=StringIO(),
            )

        config = LegacyBackupConfiguration.objects.get(
            organization=organization,
            source_row=9,
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("legacy_import_configuration_detail", args=[config.id])
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Cliente A" in content
        assert "Veeam Backup" in content
        assert "Correcto" in content
        assert "STATUS_OBSERVATION_CONFLICT" in content

    def test_bootstrap_legacy_backups_creates_provisional_operational_records(self):
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            dry_run_report = Path(directory) / "legacy-dry-run.json"
            commit_report = Path(directory) / "legacy-commit.json"
            bootstrap_report = Path(directory) / "legacy-bootstrap.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(dry_run_report),
                stdout=StringIO(),
            )
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(dry_run_report),
                commit=True,
                output=str(commit_report),
                stdout=StringIO(),
            )

            call_command(
                "bootstrap_legacy_backups",
                tenant="pilot",
                source=str(commit_report),
                output=str(bootstrap_report),
                stdout=StringIO(),
            )
            first_payload = json.loads(bootstrap_report.read_text(encoding="utf-8"))

            call_command(
                "bootstrap_legacy_backups",
                tenant="pilot",
                source=str(commit_report),
                stdout=StringIO(),
            )

        assert first_payload["processed"] == 2
        assert first_payload["sites_created"] == 1
        assert first_payload["technologies_created"] == 2
        assert first_payload["protected_objects_created"] == 2
        assert first_payload["backup_jobs_created"] == 2
        assert first_payload["targets_created"] == 2
        assert Site.objects.filter(organization=organization).count() == 1
        assert ProtectedObject.objects.filter(organization=organization).count() == 2
        assert BackupTechnology.objects.filter(organization=organization).count() == 2
        assert BackupJob.objects.filter(organization=organization).count() == 2
        assert BackupJobTarget.objects.filter(organization=organization).count() == 2
        assert LegacyBackupConfiguration.objects.filter(
            organization=organization,
            reconciled_backup_job__isnull=False,
        ).count() == 2

    def test_bootstrap_legacy_schedules_creates_assisted_schedules(self):
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            dry_run_report = Path(directory) / "legacy-dry-run.json"
            commit_report = Path(directory) / "legacy-commit.json"
            schedule_report = Path(directory) / "legacy-schedules.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(dry_run_report),
                stdout=StringIO(),
            )
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(dry_run_report),
                commit=True,
                output=str(commit_report),
                stdout=StringIO(),
            )
            call_command(
                "bootstrap_legacy_backups",
                tenant="pilot",
                source=str(commit_report),
                stdout=StringIO(),
            )

            call_command(
                "bootstrap_legacy_schedules",
                tenant="pilot",
                frequency="DAILY",
                weekdays="1,2,3,4,5",
                scheduled_time="23:00",
                deadline_time="08:00",
                deadline_offset_days=1,
                mode="ASSISTED",
                output=str(schedule_report),
                stdout=StringIO(),
            )
            payload = json.loads(schedule_report.read_text(encoding="utf-8"))
            call_command(
                "bootstrap_legacy_schedules",
                tenant="pilot",
                frequency="DAILY",
                weekdays="1,2,3,4,5",
                scheduled_time="23:00",
                deadline_time="08:00",
                deadline_offset_days=1,
                mode="ASSISTED",
                stdout=StringIO(),
            )

        assert payload["created"] == 2
        assert payload["skipped_existing"] == 0
        assert payload["creates_expected_executions"] is False
        assert BackupSchedule.objects.filter(organization=organization).count() == 2
        schedule = BackupSchedule.objects.filter(organization=organization).first()
        assert schedule.frequency == BackupSchedule.Frequency.DAILY
        assert schedule.weekdays == "1,2,3,4,5"
        assert schedule.scheduled_time.isoformat() == "23:00:00"
        assert schedule.report_deadline_time.isoformat() == "08:00:00"
        assert schedule.mode == BackupSchedule.Mode.ASSISTED
        assert "Provisional schedule" in schedule.notes

    def test_generate_legacy_expected_executions_uses_recorded_range(self):
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            dry_run_report = Path(directory) / "legacy-dry-run.json"
            commit_report = Path(directory) / "legacy-commit.json"
            output_report = Path(directory) / "legacy-expected.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(dry_run_report),
                stdout=StringIO(),
            )
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(dry_run_report),
                commit=True,
                output=str(commit_report),
                stdout=StringIO(),
            )
            call_command(
                "bootstrap_legacy_backups",
                tenant="pilot",
                source=str(commit_report),
                stdout=StringIO(),
            )
            call_command(
                "bootstrap_legacy_schedules",
                tenant="pilot",
                frequency="DAILY",
                weekdays="1,2,3,4,5",
                scheduled_time="23:00",
                deadline_time="08:00",
                deadline_offset_days=1,
                mode="ASSISTED",
                stdout=StringIO(),
            )

            call_command(
                "generate_legacy_expected_executions",
                tenant="pilot",
                source=str(commit_report),
                output=str(output_report),
                stdout=StringIO(),
            )
            payload = json.loads(output_report.read_text(encoding="utf-8"))
            call_command(
                "generate_legacy_expected_executions",
                tenant="pilot",
                source=str(commit_report),
                stdout=StringIO(),
            )

        assert payload["start_date"] == "2026-01-01"
        assert payload["end_date"] == "2026-01-03"
        assert payload["dates_considered"] == 3
        assert payload["expected_executions_created"] == 4
        assert payload["creates_backup_executions"] is False
        assert ExpectedExecution.objects.filter(organization=organization).count() == 4

    def test_legacy_configuration_detail_reconciles_operational_records(self):
        User = get_user_model()
        user = User.objects.create_user(username="admin", password="pass")
        organization = Organization.objects.create(name="Pilot", slug="pilot")
        Membership.objects.create(
            organization=organization,
            user=user,
            role=Membership.Role.ADMIN,
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            report_path = Path(directory) / "legacy-dry-run.json"
            self._legacy_csv(path)
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run=True,
                output=str(report_path),
                stdout=StringIO(),
            )
            call_command(
                "import_backup_history",
                str(path),
                tenant="pilot",
                encoding="cp1252",
                delimiter=";",
                dry_run_report=str(report_path),
                commit=True,
                stdout=StringIO(),
            )

        config = LegacyBackupConfiguration.objects.get(
            organization=organization,
            source_row=9,
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("legacy_import_configuration_detail", args=[config.id]),
            {
                "site_name": "MDP",
                "object_name": "YA01V",
                "technology_name": "Veeam",
                "job_name": "SQL",
                "note": "Confirmed from legacy row",
            },
        )

        assert response.status_code == 302
        config.refresh_from_db()
        assert Site.objects.filter(organization=organization, name="MDP").exists()
        assert BackupTechnology.objects.filter(organization=organization, name="Veeam").exists()
        assert ProtectedObject.objects.filter(organization=organization, name="YA01V").exists()
        job = BackupJob.objects.get(organization=organization, name="SQL")
        assert BackupJobTarget.objects.filter(organization=organization, backup_job=job).exists()
        assert config.reconciled_backup_job == job
        assert config.reconciled_by == user
        assert config.reconciliation_note == "Confirmed from legacy row"
