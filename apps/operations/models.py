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


class BackupExecution(OrganizationOwnedModel):
    class Result(models.TextChoices):
        SUCCESS = "SUCCESS", "Correcto"
        WARNING = "WARNING", "Advertencia"
        ERROR = "ERROR", "Error"
        NO_REPORT = "NO_REPORT", "Sin reporte"
        UNKNOWN = "UNKNOWN", "Desconocido"
        JUSTIFIED = "JUSTIFIED", "Justificado"
        CANCELLED = "CANCELLED", "Cancelado"

    class MatchStatus(models.TextChoices):
        NEEDS_REVIEW = "NEEDS_REVIEW", "Requiere revisión"
        MANUAL_MATCHED = "MANUAL_MATCHED", "Asociado manualmente"
        AUTO_MATCHED = "AUTO_MATCHED", "Asociado automáticamente"
        REJECTED = "REJECTED", "Rechazado"

    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.PROTECT,
        related_name="backup_executions",
    )
    expected_execution = models.ForeignKey(
        ExpectedExecution,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="backup_executions",
    )
    parsed_item = models.OneToOneField(
        "parsers.ParsedReportItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="backup_execution",
    )
    service_date = models.DateField()
    occurred_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=20, choices=Result.choices)
    match_status = models.CharField(
        max_length=30,
        choices=MatchStatus.choices,
        default=MatchStatus.NEEDS_REVIEW,
    )
    confidence = models.FloatField(default=0.0)
    parser_summary = models.TextField(blank=True)
    operator_note = models.TextField(blank=True)
    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matched_backup_executions",
    )
    matched_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-service_date", "backup_job__name", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "parsed_item"],
                condition=models.Q(parsed_item__isnull=False),
                name="uq_backup_execution_parsed_item_per_org",
            )
        ]

    def clean(self):
        if self.expected_execution_id:
            self.organization = self.expected_execution.organization
            self.backup_job = self.expected_execution.backup_job
            if not self.service_date:
                self.service_date = self.expected_execution.service_date
        elif self.backup_job_id:
            self.organization = self.backup_job.organization

        if self.backup_job_id and self.organization_id:
            if self.backup_job.organization_id != self.organization_id:
                raise ValidationError("Backup job must belong to the same organization.")
        if self.expected_execution_id and self.backup_job_id:
            if self.expected_execution.organization_id != self.organization_id:
                raise ValidationError(
                    "Expected execution must belong to the same organization."
                )
            if self.expected_execution.backup_job_id != self.backup_job_id:
                raise ValidationError(
                    "Expected execution must belong to the selected backup job."
                )
        if self.parsed_item_id and self.organization_id:
            if self.parsed_item.organization_id != self.organization_id:
                raise ValidationError("Parsed item must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.service_date} - {self.backup_job} - {self.result}"


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
