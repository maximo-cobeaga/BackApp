from datetime import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.backups.forms import BackupJobForm, BackupJobTargetForm
from apps.backups.models import (
    BackupDestination,
    BackupJob,
    BackupJobTarget,
    BackupSchedule,
    BackupTechnology,
    RetentionPolicy,
)
from apps.customers.models import ManagedCustomer, Site
from apps.inventory.models import ProtectedObject
from apps.tenancy.models import Membership, Organization


class BackupInventoryTest(TestCase):
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
        self.customer = ManagedCustomer.objects.create(
            organization=self.org,
            name="Cliente",
        )
        self.other_customer = ManagedCustomer.objects.create(
            organization=self.other_org,
            name="Cliente ajeno",
        )
        self.site = Site.objects.create(
            organization=self.org,
            managed_customer=self.customer,
            name="MDP",
        )
        self.other_site = Site.objects.create(
            organization=self.other_org,
            managed_customer=self.other_customer,
            name="BA",
        )
        self.server = ProtectedObject.objects.create(
            organization=self.org,
            managed_customer=self.customer,
            site=self.site,
            name="YAPP",
            object_type=ProtectedObject.ObjectType.PHYSICAL_SERVER,
        )
        self.database = ProtectedObject.objects.create(
            organization=self.org,
            managed_customer=self.customer,
            site=self.site,
            name="SQL Server",
            object_type=ProtectedObject.ObjectType.DATABASE,
        )
        self.other_object = ProtectedObject.objects.create(
            organization=self.other_org,
            managed_customer=self.other_customer,
            site=self.other_site,
            name="Other",
            object_type=ProtectedObject.ObjectType.PHYSICAL_SERVER,
        )
        self.technology = BackupTechnology.objects.create(
            organization=self.org,
            name="Veeam",
        )
        self.other_technology = BackupTechnology.objects.create(
            organization=self.other_org,
            name="Iperius",
        )
        self.client.force_login(self.user)

    def _create_job(self, name="Veeam diario"):
        return BackupJob.objects.create(
            organization=self.org,
            managed_customer=self.customer,
            site=self.site,
            technology=self.technology,
            name=name,
        )

    def test_job_supports_multiple_targets(self):
        job = self._create_job()
        BackupJobTarget.objects.create(
            organization=self.org,
            backup_job=job,
            protected_object=self.server,
            role=BackupJobTarget.TargetRole.PRIMARY,
        )
        BackupJobTarget.objects.create(
            organization=self.org,
            backup_job=job,
            protected_object=self.database,
            role=BackupJobTarget.TargetRole.INCLUDED,
        )
        assert set(job.targets.values_list("protected_object", flat=True)) == {
            self.server.id,
            self.database.id,
        }

    def test_protected_object_supports_multiple_jobs(self):
        daily = self._create_job("Veeam diario")
        weekly = self._create_job("Veeam semanal")
        BackupJobTarget.objects.create(
            organization=self.org,
            backup_job=daily,
            protected_object=self.server,
        )
        BackupJobTarget.objects.create(
            organization=self.org,
            backup_job=weekly,
            protected_object=self.server,
        )
        assert set(self.server.backup_targets.values_list("backup_job", flat=True)) == {
            daily.id,
            weekly.id,
        }

    def test_job_rejects_foreign_technology(self):
        job = BackupJob(
            organization=self.org,
            managed_customer=self.customer,
            site=self.site,
            technology=self.other_technology,
            name="Cruce inválido",
        )
        with self.assertRaises(ValidationError):
            job.clean()

    def test_target_rejects_foreign_object(self):
        job = self._create_job()
        target = BackupJobTarget(
            organization=self.org,
            backup_job=job,
            protected_object=self.other_object,
        )
        with self.assertRaises(ValidationError):
            target.clean()

    def test_forms_only_expose_active_organization_records(self):
        job = self._create_job()
        job_form = BackupJobForm(organization=self.org)
        target_form = BackupJobTargetForm(organization=self.org)
        assert list(job_form.fields["site"].queryset) == [self.site]
        assert list(job_form.fields["technology"].queryset) == [self.technology]
        assert list(target_form.fields["backup_job"].queryset) == [job]
        assert set(target_form.fields["protected_object"].queryset) == {
            self.server,
            self.database,
        }

    def test_schedule_destination_retention_use_job_organization(self):
        job = self._create_job()
        schedule = BackupSchedule.objects.create(
            organization=self.org,
            backup_job=job,
            frequency=BackupSchedule.Frequency.DAILY,
            weekdays="1,2,3,4,5",
            scheduled_time=time(23, 0),
            report_deadline_time=time(6, 0),
        )
        destination = BackupDestination.objects.create(
            organization=self.org,
            backup_job=job,
            repository_type="NAS",
            name="Repositorio local",
        )
        retention = RetentionPolicy.objects.create(
            organization=self.org,
            backup_job=job,
            daily_copies=7,
            weekly_copies=4,
            total_days=30,
        )
        assert schedule.organization == self.org
        assert destination.organization == self.org
        assert retention.organization == self.org

    def test_admin_can_create_phase2_inventory_through_views(self):
        tech_response = self.client.post(
            reverse("backup_technology_create"),
            {"name": "Iperius", "vendor": "Enter", "notes": "", "is_active": "on"},
        )
        assert tech_response.status_code == 302
        technology = BackupTechnology.objects.get(organization=self.org, name="Iperius")

        job_response = self.client.post(
            reverse("backup_job_create"),
            {
                "site": str(self.site.id),
                "technology": str(technology.id),
                "name": "Iperius diario",
                "external_identifier": "IP-001",
                "matching_aliases": "YAPP Iperius",
                "status": BackupJob.Status.ACTIVE,
                "criticality": BackupJob.Criticality.HIGH,
                "internal_owner": "Soporte",
                "notes": "",
            },
        )
        assert job_response.status_code == 302
        job = BackupJob.objects.get(organization=self.org, name="Iperius diario")

        target_response = self.client.post(
            reverse("backup_target_create"),
            {
                "backup_job": str(job.id),
                "protected_object": str(self.server.id),
                "role": BackupJobTarget.TargetRole.PRIMARY,
                "inclusions": "",
                "exclusions": "",
                "notes": "",
                "is_active": "on",
            },
        )
        assert target_response.status_code == 302
        assert BackupJobTarget.objects.filter(
            organization=self.org,
            backup_job=job,
            protected_object=self.server,
        ).exists()

    def test_job_list_hides_other_organization_records(self):
        visible_job = self._create_job("Visible")
        BackupJob.objects.create(
            organization=self.other_org,
            managed_customer=self.other_customer,
            site=self.other_site,
            technology=self.other_technology,
            name="Oculta",
        )
        response = self.client.get(reverse("backup_job_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert visible_job.name in content
        assert "Oculta" not in content
