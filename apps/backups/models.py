"""Backup inventory and configuration models."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.customers.models import ManagedCustomer, Site
from apps.inventory.models import ProtectedObject
from apps.tenancy.models import OrganizationOwnedModel


class BackupTechnology(OrganizationOwnedModel):
    name = models.CharField(max_length=120)
    vendor = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uq_backup_technology_name_per_organization",
            )
        ]

    def __str__(self) -> str:
        return self.name


class BackupJob(OrganizationOwnedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activa"
        PAUSED = "PAUSED", "Pausada"
        RETIRED = "RETIRED", "Retirada"

    class Criticality(models.TextChoices):
        LOW = "LOW", "Baja"
        MEDIUM = "MEDIUM", "Media"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"

    managed_customer = models.ForeignKey(
        ManagedCustomer,
        on_delete=models.PROTECT,
        related_name="backup_jobs",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="backup_jobs",
    )
    technology = models.ForeignKey(
        BackupTechnology,
        on_delete=models.PROTECT,
        related_name="backup_jobs",
    )
    name = models.CharField(max_length=255)
    external_identifier = models.CharField(max_length=160, blank=True)
    matching_aliases = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    criticality = models.CharField(
        max_length=20,
        choices=Criticality.choices,
        default=Criticality.MEDIUM,
    )
    internal_owner = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["managed_customer__name", "site__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "managed_customer", "site", "name"],
                name="uq_backup_job_name_per_site_organization",
            ),
            models.UniqueConstraint(
                fields=["organization", "external_identifier"],
                condition=~models.Q(external_identifier=""),
                name="uq_backup_job_external_identifier_per_organization",
            ),
        ]

    def clean(self):
        if self.site_id:
            self.organization = self.site.organization
            self.managed_customer = self.site.managed_customer
        if self.managed_customer_id and self.site_id:
            if self.managed_customer.organization_id != self.site.organization_id:
                raise ValidationError("Customer and site must belong to the same organization.")
            if self.site.managed_customer_id != self.managed_customer_id:
                raise ValidationError("Site must belong to the selected customer.")
        if self.technology_id and self.organization_id:
            if self.technology.organization_id != self.organization_id:
                raise ValidationError("Technology must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class BackupJobTarget(OrganizationOwnedModel):
    class TargetRole(models.TextChoices):
        PRIMARY = "PRIMARY", "Principal"
        INCLUDED = "INCLUDED", "Incluido"
        EXCLUDED = "EXCLUDED", "Excluido"
        DEPENDENCY = "DEPENDENCY", "Dependencia"
        OTHER = "OTHER", "Otro"

    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    protected_object = models.ForeignKey(
        ProtectedObject,
        on_delete=models.PROTECT,
        related_name="backup_targets",
    )
    role = models.CharField(
        max_length=20,
        choices=TargetRole.choices,
        default=TargetRole.PRIMARY,
    )
    inclusions = models.TextField(blank=True)
    exclusions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["backup_job__name", "protected_object__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "backup_job", "protected_object"],
                name="uq_backup_job_target_per_organization",
            )
        ]

    def clean(self):
        if self.backup_job_id:
            self.organization = self.backup_job.organization
        if self.backup_job_id and self.protected_object_id:
            if self.backup_job.organization_id != self.protected_object.organization_id:
                raise ValidationError("Backup job and target must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.backup_job} -> {self.protected_object}"


class BackupSchedule(OrganizationOwnedModel):
    class Frequency(models.TextChoices):
        DAILY = "DAILY", "Diaria"
        WEEKLY = "WEEKLY", "Semanal"
        MONTHLY = "MONTHLY", "Mensual"
        CUSTOM = "CUSTOM", "Personalizada"

    class Mode(models.TextChoices):
        AUTOMATIC = "AUTOMATIC", "Automática"
        MANUAL = "MANUAL", "Manual"
        ASSISTED = "ASSISTED", "Asistida"

    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    frequency = models.CharField(max_length=20, choices=Frequency.choices)
    weekdays = models.CharField(
        max_length=80,
        blank=True,
        help_text="Comma-separated ISO weekdays, 1=Monday through 7=Sunday.",
    )
    scheduled_time = models.TimeField()
    timezone = models.CharField(max_length=64, default="America/Argentina/Buenos_Aires")
    cron_expression = models.CharField(max_length=120, blank=True)
    expected_duration_minutes = models.PositiveIntegerField(default=60)
    report_deadline_time = models.TimeField()
    report_deadline_offset_days = models.PositiveSmallIntegerField(default=1)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.AUTOMATIC)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["backup_job__name", "scheduled_time"]

    def clean(self):
        if self.backup_job_id:
            self.organization = self.backup_job.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.backup_job} @ {self.scheduled_time}"


class BackupDestination(OrganizationOwnedModel):
    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.CASCADE,
        related_name="destinations",
    )
    repository_type = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    location = models.CharField(max_length=255, blank=True)
    capacity_gb = models.PositiveIntegerField(null=True, blank=True)
    free_space_threshold_gb = models.PositiveIntegerField(null=True, blank=True)
    is_offsite = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["backup_job__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "backup_job", "name"],
                name="uq_backup_destination_name_per_job_organization",
            )
        ]

    def clean(self):
        if self.backup_job_id:
            self.organization = self.backup_job.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class RetentionPolicy(OrganizationOwnedModel):
    backup_job = models.OneToOneField(
        BackupJob,
        on_delete=models.CASCADE,
        related_name="retention_policy",
    )
    daily_copies = models.PositiveSmallIntegerField(default=0)
    weekly_copies = models.PositiveSmallIntegerField(default=0)
    monthly_copies = models.PositiveSmallIntegerField(default=0)
    annual_copies = models.PositiveSmallIntegerField(default=0)
    total_days = models.PositiveIntegerField(default=0)
    uses_gfs = models.BooleanField(default=False)
    deleted_item_retention_days = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Retention policies"

    def clean(self):
        if self.backup_job_id:
            self.organization = self.backup_job.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Retention for {self.backup_job}"


class BackupConfigurationChange(OrganizationOwnedModel):
    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.CASCADE,
        related_name="configuration_changes",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backup_configuration_changes",
    )
    summary = models.CharField(max_length=255)
    reason = models.TextField(blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.backup_job_id:
            self.organization = self.backup_job.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.summary
