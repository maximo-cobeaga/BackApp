from datetime import UTC, date, datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.backups.models import BackupJob, BackupSchedule, BackupTechnology
from apps.customers.models import ManagedCustomer, Site
from apps.imports.models import ImportBatch, LegacyBackupConfiguration
from apps.ingestion.models import InboundMessage, MailConnector
from apps.operations.models import BackupExecution, ExpectedExecution
from apps.operations.services import (
    backup_execution_candidates_for_parsed_item,
    create_backup_execution_from_parsed_item,
)
from apps.parsers.models import ParsedReportItem
from apps.parsers.services import parse_message
from apps.tenancy.models import Membership, Organization


class PhaseSevenBackupExecutionMatchingTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="admin", password="pass")
        self.other_user = User.objects.create_user(username="other", password="pass")
        self.org = Organization.objects.create(name="Org", slug="org")
        self.other_org = Organization.objects.create(name="Other", slug="other")
        Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.other_org,
            user=self.other_user,
            role=Membership.Role.ADMIN,
        )
        self.customer = ManagedCustomer.objects.create(organization=self.org, name="Cliente")
        self.site = Site.objects.create(
            organization=self.org,
            managed_customer=self.customer,
            name="MDP",
        )
        self.technology = BackupTechnology.objects.create(organization=self.org, name="Veeam")
        self.job = BackupJob.objects.create(
            organization=self.org,
            managed_customer=self.customer,
            site=self.site,
            technology=self.technology,
            name="Veeam diario",
        )
        self.schedule = BackupSchedule.objects.create(
            organization=self.org,
            backup_job=self.job,
            frequency=BackupSchedule.Frequency.DAILY,
            weekdays="1,2,3,4,5",
            scheduled_time=time(23, 0),
            report_deadline_time=time(6, 0),
            report_deadline_offset_days=1,
        )
        self.expected = ExpectedExecution.objects.create(
            organization=self.org,
            backup_job=self.job,
            schedule=self.schedule,
            service_date=date(2026, 7, 20),
            scheduled_start_at=datetime(2026, 7, 21, 2, 0, tzinfo=UTC),
            report_deadline_at=datetime(2026, 7, 21, 9, 0, tzinfo=UTC),
        )
        self.other_customer = ManagedCustomer.objects.create(
            organization=self.other_org,
            name="Cliente ajeno",
        )
        self.other_site = Site.objects.create(
            organization=self.other_org,
            managed_customer=self.other_customer,
            name="BA",
        )
        self.other_technology = BackupTechnology.objects.create(
            organization=self.other_org,
            name="Iperius",
        )
        self.other_job = BackupJob.objects.create(
            organization=self.other_org,
            managed_customer=self.other_customer,
            site=self.other_site,
            technology=self.other_technology,
            name="Oculta",
        )
        self.other_schedule = BackupSchedule.objects.create(
            organization=self.other_org,
            backup_job=self.other_job,
            frequency=BackupSchedule.Frequency.DAILY,
            weekdays="1,2,3,4,5",
            scheduled_time=time(23, 0),
            report_deadline_time=time(6, 0),
            report_deadline_offset_days=1,
        )
        self.other_expected = ExpectedExecution.objects.create(
            organization=self.other_org,
            backup_job=self.other_job,
            schedule=self.other_schedule,
            service_date=date(2026, 7, 20),
            scheduled_start_at=datetime(2026, 7, 21, 2, 0, tzinfo=UTC),
            report_deadline_at=datetime(2026, 7, 21, 9, 0, tzinfo=UTC),
        )
        self.connector = MailConnector.objects.create(
            organization=self.org,
            name="M365",
            provider_type=MailConnector.ProviderType.MICROSOFT_GRAPH,
            auth_mode=MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
            mailbox_address="backups@example.com",
            config={
                "tenant_id_env": "M365_TENANT_ID",
                "client_id_env": "M365_CLIENT_ID",
                "client_secret_env": "M365_CLIENT_SECRET",
            },
        )
        self.message = InboundMessage.objects.create(
            organization=self.org,
            connector=self.connector,
            external_message_id="m1",
            subject="Backup report",
            sender="reports@example.com",
            received_at=datetime(2026, 7, 21, 5, 30, tzinfo=UTC),
            body_preview="Backup result in an unknown format",
        )
        self.item = parse_message(message=self.message)[0][0]
        self.client.force_login(self.user)

    def test_manual_matching_creates_backup_execution_from_parsed_item(self):
        execution, created = create_backup_execution_from_parsed_item(
            parsed_item=self.item,
            expected_execution=self.expected,
            result=BackupExecution.Result.UNKNOWN,
            user=self.user,
            operator_note="Matched manually from review.",
        )
        self.item.refresh_from_db()
        self.message.refresh_from_db()

        assert created is True
        assert execution.organization == self.org
        assert execution.backup_job == self.job
        assert execution.expected_execution == self.expected
        assert execution.parsed_item == self.item
        assert execution.result == BackupExecution.Result.UNKNOWN
        assert execution.match_status == BackupExecution.MatchStatus.MANUAL_MATCHED
        assert execution.matched_by == self.user
        assert self.item.review_status == ParsedReportItem.ReviewStatus.REVIEWED
        assert self.message.parser_status == "REVIEWED"

    def test_manual_matching_is_idempotent_by_parsed_item(self):
        first, first_created = create_backup_execution_from_parsed_item(
            parsed_item=self.item,
            expected_execution=self.expected,
            result=BackupExecution.Result.UNKNOWN,
            user=self.user,
        )
        second, second_created = create_backup_execution_from_parsed_item(
            parsed_item=self.item,
            expected_execution=self.expected,
            result=BackupExecution.Result.ERROR,
            user=self.user,
        )

        assert first_created is True
        assert second_created is False
        assert first == second
        assert BackupExecution.objects.filter(organization=self.org).count() == 1
        second.refresh_from_db()
        assert second.result == BackupExecution.Result.UNKNOWN

    def test_matching_candidates_rank_job_provider_and_window(self):
        self.item.job_hints = [self.job.name]
        self.item.metrics = {"provider": "VEEAM"}
        self.item.save(update_fields=["job_hints", "metrics", "updated_at"])

        candidates = backup_execution_candidates_for_parsed_item(parsed_item=self.item)

        assert len(candidates) == 1
        assert candidates[0].expected_execution == self.expected
        assert candidates[0].confidence == 1.0
        assert "Coincide la tarea detectada" in candidates[0].reasons
        assert "Coincide la tecnología detectada" in candidates[0].reasons
        assert "El correo llegó dentro de la ventana esperada" in candidates[0].reasons

    def test_matching_candidates_use_legacy_bootstrap_evidence(self):
        batch = ImportBatch.objects.create(
            organization=self.org,
            original_filename="legacy.csv",
            source_sha256="a" * 64,
        )
        LegacyBackupConfiguration.objects.create(
            organization=self.org,
            import_batch=batch,
            managed_customer=self.customer,
            source_sha256="a" * 64,
            source_row=9,
            legacy_fingerprint="b" * 64,
            legacy_customer_name=self.customer.name,
            legacy_site_label=self.site.name,
            source_asset_label="YA01V",
            legacy_backup_name="SQL Produccion",
            legacy_method="Veeam Backup",
            provider="VEEAM",
            reconciled_site=self.site,
            reconciled_backup_job=self.job,
        )
        self.item.customer_hints = [self.customer.name]
        self.item.object_hints = ["YA01V"]
        self.item.job_hints = ["SQL Produccion"]
        self.item.metrics = {"provider": "VEEAM"}
        self.item.save(
            update_fields=["customer_hints", "object_hints", "job_hints", "metrics", "updated_at"]
        )

        candidates = backup_execution_candidates_for_parsed_item(parsed_item=self.item)

        assert candidates[0].expected_execution == self.expected
        assert candidates[0].confidence == 1.0
        assert "Coincide una configuración histórica reconciliada" in candidates[0].reasons
        assert "Coincide el objeto protegido o activo histórico" in candidates[0].reasons
        assert "Coincide el cliente detectado" in candidates[0].reasons

    def test_review_form_prefills_single_strong_matching_candidate(self):
        self.item.job_hints = [self.job.name]
        self.item.metrics = {"provider": "VEEAM"}
        self.item.save(update_fields=["job_hints", "metrics", "updated_at"])

        response = self.client.get(reverse("parsed_item_review", args=[self.item.id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Sugerencias de matching" in content
        assert "Sugerida 100%" in content
        assert f'value="{self.expected.id}" selected' in content

    def test_review_form_only_lists_same_organization_expected_executions(self):
        response = self.client.get(reverse("parsed_item_review", args=[self.item.id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Veeam diario" in content
        assert "Oculta" not in content

    def test_review_action_rejects_cross_tenant_expected_execution(self):
        response = self.client.post(
            reverse("parsed_item_review", args=[self.item.id]),
            {
                "expected_execution": str(self.other_expected.id),
                "result": BackupExecution.Result.UNKNOWN,
                "review_note": "Should not be accepted.",
            },
        )

        assert response.status_code == 200
        assert BackupExecution.objects.filter(organization=self.org).count() == 0
        self.item.refresh_from_db()
        assert self.item.review_status == ParsedReportItem.ReviewStatus.NEEDS_REVIEW

    def test_backup_execution_list_is_tenant_scoped(self):
        create_backup_execution_from_parsed_item(
            parsed_item=self.item,
            expected_execution=self.expected,
            result=BackupExecution.Result.UNKNOWN,
            user=self.user,
        )
        BackupExecution.objects.create(
            organization=self.other_org,
            backup_job=self.other_job,
            expected_execution=self.other_expected,
            service_date=date(2026, 7, 20),
            result=BackupExecution.Result.ERROR,
            match_status=BackupExecution.MatchStatus.MANUAL_MATCHED,
        )

        response = self.client.get(
            reverse("backup_execution_list"),
            {"date": "2026-07-20"},
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Veeam diario" in content
        assert "Oculta" not in content

    def test_review_action_creates_backup_execution_and_removes_item_from_queue(self):
        response = self.client.post(
            reverse("parsed_item_review", args=[self.item.id]),
            {
                "expected_execution": str(self.expected.id),
                "result": BackupExecution.Result.UNKNOWN,
                "review_note": "Confirmed manually.",
            },
        )

        assert response.status_code == 302
        execution = BackupExecution.objects.get(organization=self.org)
        assert execution.expected_execution == self.expected
        assert execution.operator_note == "Confirmed manually."
        queue = self.client.get(reverse("parser_review_queue"))
        assert "Backup report" not in queue.content.decode()
