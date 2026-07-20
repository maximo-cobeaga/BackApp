from datetime import UTC, date, datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.backups.models import BackupJob, BackupSchedule, BackupTechnology
from apps.customers.models import ManagedCustomer, Site
from apps.operations.models import DailyControlEntry, ExpectedExecution
from apps.operations.services import (
    dashboard_metrics,
    generate_expected_executions,
    mark_missing_reports,
)
from apps.tenancy.models import Membership, Organization


class PhaseFourExpectedExecutionTest(TestCase):
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
        self.client.force_login(self.user)

    def test_generate_expected_executions_from_active_schedules(self):
        executions = generate_expected_executions(
            organization=self.org,
            service_date=date(2026, 7, 20),
        )
        assert len(executions) == 1
        execution = executions[0]
        assert execution.organization == self.org
        assert execution.backup_job == self.job
        assert execution.schedule == self.schedule
        assert execution.status == ExpectedExecution.Status.WAITING_REPORT
        assert execution.scheduled_start_at == datetime(2026, 7, 21, 2, 0, tzinfo=UTC)
        assert execution.report_deadline_at == datetime(2026, 7, 21, 9, 0, tzinfo=UTC)

    def test_generation_is_idempotent_by_schedule_and_service_date(self):
        generate_expected_executions(organization=self.org, service_date=date(2026, 7, 20))
        generate_expected_executions(organization=self.org, service_date=date(2026, 7, 20))
        assert ExpectedExecution.objects.filter(
            organization=self.org,
            schedule=self.schedule,
            service_date=date(2026, 7, 20),
        ).count() == 1

    def test_schedule_weekdays_are_respected(self):
        executions = generate_expected_executions(
            organization=self.org,
            service_date=date(2026, 7, 19),
        )
        assert executions == []
        assert not ExpectedExecution.objects.filter(
            organization=self.org,
            service_date=date(2026, 7, 19),
        ).exists()

    def test_mark_missing_reports_updates_only_overdue_waiting_records(self):
        execution = generate_expected_executions(
            organization=self.org,
            service_date=date(2026, 7, 20),
        )[0]
        updated = mark_missing_reports(
            organization=self.org,
            now=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        )
        execution.refresh_from_db()
        assert updated == 1
        assert execution.status == ExpectedExecution.Status.NO_REPORT
        assert "No report" in execution.system_summary

    def test_expected_execution_list_hides_other_organization_records(self):
        visible = generate_expected_executions(
            organization=self.org,
            service_date=date(2026, 7, 20),
        )[0]
        ExpectedExecution.objects.create(
            organization=self.other_org,
            backup_job=self.other_job,
            schedule=self.other_schedule,
            service_date=date(2026, 7, 20),
            scheduled_start_at=datetime(2026, 7, 21, 2, 0, tzinfo=UTC),
            report_deadline_at=datetime(2026, 7, 21, 9, 0, tzinfo=UTC),
        )
        response = self.client.get(
            reverse("expected_execution_list"),
            {"date": "2026-07-20"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert visible.backup_job.name in content
        assert "Oculta" not in content

    def test_generate_view_creates_expected_execution(self):
        response = self.client.post(
            reverse("expected_execution_generate"),
            {"service_date": "2026-07-20"},
        )
        assert response.status_code == 302
        assert ExpectedExecution.objects.filter(
            organization=self.org,
            schedule=self.schedule,
            service_date=date(2026, 7, 20),
        ).exists()

    def test_dashboard_metrics_include_expected_and_manual_counts(self):
        execution = generate_expected_executions(
            organization=self.org,
            service_date=date(2026, 7, 20),
        )[0]
        mark_missing_reports(
            organization=self.org,
            now=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        )
        DailyControlEntry.objects.create(
            organization=self.org,
            control_date=date(2026, 7, 20),
            backup_job=self.job,
            expected_execution=execution,
            result=DailyControlEntry.Result.ERROR,
        )
        metrics = dashboard_metrics(
            organization=self.org,
            service_date=date(2026, 7, 20),
        )
        assert metrics["expected"] == 1
        assert metrics["waiting"] == 0
        assert metrics["no_report"] == 1
        assert metrics["manual_total"] == 1
        assert metrics["manual_error"] == 1

    def test_dashboard_view_is_tenant_scoped(self):
        generate_expected_executions(organization=self.org, service_date=date(2026, 7, 20))
        ExpectedExecution.objects.create(
            organization=self.other_org,
            backup_job=self.other_job,
            schedule=self.other_schedule,
            service_date=date(2026, 7, 20),
            scheduled_start_at=datetime(2026, 7, 21, 2, 0, tzinfo=UTC),
            report_deadline_at=datetime(2026, 7, 21, 9, 0, tzinfo=UTC),
            status=ExpectedExecution.Status.NO_REPORT,
        )
        response = self.client.get(reverse("dashboard"), {"date": "2026-07-20"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Total esperadas: 1" in content
        assert "Sin reporte: 0" in content
