"""Manual daily-control and expected-execution operation models."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.backups.models import BackupJob, BackupJobTarget, BackupSchedule
from apps.inventory.models import ProtectedObject
from apps.tenancy.models import OrganizationOwnedModel


class ExpectedExecution(OrganizationOwnedModel):
    class Status(models.TextChoices):
        WAITING_REPORT = "WAITING_REPORT", "Esperando reporte"
        SUCCESS = "SUCCESS", "Correcto"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"
        NO_REPORT = "NO_REPORT", "Sin reporte"
        JUSTIFIED = "JUSTIFIED", "Justificado"
        CANCELLED = "CANCELLED", "Cancelado"

    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.PROTECT,
        related_name="expected_executions",
    )
    schedule = models.ForeignKey(
        BackupSchedule,
        on_delete=models.PROTECT,
        related_name="expected_executions",
    )
    service_date = models.DateField()
    scheduled_start_at = models.DateTimeField()
    report_deadline_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING_REPORT,
    )
    system_summary = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["service_date", "scheduled_start_at", "backup_job__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "schedule", "service_date"],
                name="uq_expected_execution_schedule_date_per_organization",
            )
        ]

    def clean(self):
        if self.schedule_id:
            self.organization = self.schedule.organization
            self.backup_job = self.schedule.backup_job
        if self.backup_job_id and self.schedule_id:
            if self.backup_job.organization_id != self.schedule.organization_id:
                raise ValidationError("Job and schedule must belong to the same organization.")
            if self.schedule.backup_job_id != self.backup_job_id:
                raise ValidationError("Schedule must belong to the selected backup job.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.service_date} - {self.backup_job} - {self.status}"


class DailyControlEntry(OrganizationOwnedModel):
    class Result(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        SUCCESS = "SUCCESS", "Correcto"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"
        NO_REPORT = "NO_REPORT", "Sin reporte"
        JUSTIFIED = "JUSTIFIED", "Justificado"

    control_date = models.DateField()
    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.PROTECT,
        related_name="daily_control_entries",
    )
    expected_execution = models.ForeignKey(
        ExpectedExecution,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="daily_control_entries",
    )
    backup_job_target = models.ForeignKey(
        BackupJobTarget,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="daily_control_entries",
    )
    protected_object = models.ForeignKey(
        ProtectedObject,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="daily_control_entries",
    )
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.PENDING)
    observed_at = models.DateTimeField(null=True, blank=True)
    system_summary = models.TextField(blank=True)
    manual_observation = models.TextField(blank=True)
    ticket_reference = models.CharField(max_length=120, blank=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="daily_control_entries",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-control_date", "backup_job__name", "protected_object__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "control_date", "backup_job", "protected_object"],
                name="uq_daily_control_job_object_date_per_organization",
            )
        ]

    def clean(self):
        if self.backup_job_id:
            self.organization = self.backup_job.organization
        if self.expected_execution_id:
            if self.expected_execution.organization_id != self.organization_id:
                raise ValidationError(
                    "Expected execution must belong to the same organization."
                )
            if self.expected_execution.backup_job_id != self.backup_job_id:
                raise ValidationError(
                    "Expected execution must belong to the selected backup job."
                )
        if self.backup_job_target_id:
            if self.backup_job_target.organization_id != self.organization_id:
                raise ValidationError("Target must belong to the same organization.")
            if self.backup_job_target.backup_job_id != self.backup_job_id:
                raise ValidationError("Target must belong to the selected backup job.")
            self.protected_object = self.backup_job_target.protected_object
        if self.protected_object_id and self.organization_id:
            if self.protected_object.organization_id != self.organization_id:
                raise ValidationError("Protected object must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.control_date} - {self.backup_job} - {self.result}"
