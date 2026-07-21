"""Spreadsheet import preview and confirmation models."""
from django.conf import settings
from django.db import models

from apps.backups.models import BackupJob
from apps.customers.models import ManagedCustomer, Site
from apps.inventory.models import ProtectedObject
from apps.tenancy.models import OrganizationOwnedModel


class ImportBatch(OrganizationOwnedModel):
    class Status(models.TextChoices):
        PREVIEW = "PREVIEW", "En previsualización"
        IMPORTED = "IMPORTED", "Importado"
        ROLLED_BACK = "ROLLED_BACK", "Revertido"
        FAILED = "FAILED", "Fallido"

    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVIEW)
    column_mapping = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    source_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    encoding = models.CharField(max_length=40, blank=True)
    delimiter = models.CharField(max_length=10, blank=True)
    dry_run = models.BooleanField(default=False)
    summary_json = models.JSONField(default=dict, blank=True)
    imported_customer_ids = models.JSONField(default=list, blank=True)
    imported_site_ids = models.JSONField(default=list, blank=True)
    imported_object_ids = models.JSONField(default=list, blank=True)
    imported_technology_ids = models.JSONField(default=list, blank=True)
    imported_job_ids = models.JSONField(default=list, blank=True)
    imported_target_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_batches",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_import_batches",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rolled_back_import_batches",
    )
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.status})"


class ImportRow(OrganizationOwnedModel):
    class Status(models.TextChoices):
        NEW = "NEW", "Nuevo"
        MATCHED = "MATCHED", "Coincidencia"
        INCOMPLETE = "INCOMPLETE", "Incompleto"
        CONFLICT = "CONFLICT", "Conflicto"
        IMPORTED = "IMPORTED", "Importado"
        SKIPPED = "SKIPPED", "Omitido"

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    raw_data = models.JSONField(default=dict)
    normalized_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices)
    messages = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "batch", "row_number"],
                name="uq_import_row_number_per_batch_organization",
            )
        ]

    def clean(self):
        if self.batch_id:
            self.organization = self.batch.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Row {self.row_number}: {self.status}"


class LegacyBackupConfiguration(OrganizationOwnedModel):
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.PROTECT,
        related_name="legacy_backup_configurations",
    )
    managed_customer = models.ForeignKey(
        ManagedCustomer,
        on_delete=models.PROTECT,
        related_name="legacy_backup_configurations",
    )
    source_sha256 = models.CharField(max_length=64)
    source_row = models.PositiveIntegerField()
    legacy_fingerprint = models.CharField(max_length=64)
    legacy_customer_name = models.CharField(max_length=255)
    legacy_site_label = models.CharField(max_length=255, blank=True)
    source_asset_label = models.CharField(max_length=255, blank=True)
    legacy_backup_name = models.CharField(max_length=255, blank=True)
    legacy_method = models.CharField(max_length=160, blank=True)
    provider = models.CharField(max_length=80, blank=True)
    provider_requires_confirmation = models.BooleanField(default=False)
    external_responsible = models.TextField(blank=True)
    is_external = models.BooleanField(default=False)
    schedule_hint = models.TextField(blank=True)
    schedule_requires_confirmation = models.BooleanField(default=False)
    quality_flags = models.JSONField(default=list, blank=True)
    reconciled_site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciled_legacy_backup_configurations",
    )
    reconciled_protected_object = models.ForeignKey(
        ProtectedObject,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciled_legacy_backup_configurations",
    )
    reconciled_backup_job = models.ForeignKey(
        BackupJob,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciled_legacy_backup_configurations",
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciled_legacy_backup_configurations",
    )
    reconciliation_note = models.TextField(blank=True)

    class Meta:
        ordering = ["legacy_customer_name", "source_row"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_sha256", "legacy_fingerprint"],
                name="uq_legacy_backup_config_fingerprint_per_source_org",
            )
        ]

    def clean(self):
        if self.import_batch_id:
            self.organization = self.import_batch.organization
        if self.managed_customer_id and self.organization_id:
            self.legacy_customer_name = self.legacy_customer_name or self.managed_customer.name

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.legacy_customer_name} - {self.legacy_backup_name}"


class LegacyDailyRecord(OrganizationOwnedModel):
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.PROTECT,
        related_name="legacy_daily_records",
    )
    backup_configuration = models.ForeignKey(
        LegacyBackupConfiguration,
        on_delete=models.PROTECT,
        related_name="daily_records",
    )
    source_sha256 = models.CharField(max_length=64)
    source_row = models.PositiveIntegerField()
    source_date = models.DateField()
    raw_responsible = models.TextField(blank=True)
    raw_status = models.CharField(max_length=80, blank=True)
    raw_ticket = models.CharField(max_length=120, blank=True)
    raw_observation = models.TextField(blank=True)
    normalized_status = models.CharField(max_length=40)
    normalization_rule = models.CharField(max_length=120, blank=True)
    quality_flags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["source_date", "source_row"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_sha256", "source_row", "source_date"],
                name="uq_legacy_daily_record_source_row_date_per_org",
            )
        ]

    def clean(self):
        if self.import_batch_id:
            self.organization = self.import_batch.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.source_date} row {self.source_row}: {self.normalized_status}"


class LegacyImportIssue(OrganizationOwnedModel):
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.PROTECT,
        related_name="legacy_import_issues",
    )
    source_sha256 = models.CharField(max_length=64)
    source_row = models.PositiveIntegerField()
    source_date = models.DateField(null=True, blank=True)
    issue_code = models.CharField(max_length=80)
    severity = models.CharField(max_length=20)
    details = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_legacy_import_issues",
    )

    class Meta:
        ordering = ["source_row", "source_date", "issue_code"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "source_sha256",
                    "source_row",
                    "source_date",
                    "issue_code",
                ],
                name="uq_legacy_import_issue_source_row_date_code_per_org",
            )
        ]

    def clean(self):
        if self.import_batch_id:
            self.organization = self.import_batch.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.issue_code} at row {self.source_row}"


class LegacyTicketReference(OrganizationOwnedModel):
    class ExternalSystem(models.TextChoices):
        MANAGEENGINE = "MANAGEENGINE", "ManageEngine"

    external_system = models.CharField(
        max_length=40,
        choices=ExternalSystem.choices,
        default=ExternalSystem.MANAGEENGINE,
    )
    external_id = models.CharField(max_length=120)

    class Meta:
        ordering = ["external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "external_system", "external_id"],
                name="uq_legacy_ticket_reference_external_id_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"{self.external_system}:{self.external_id}"
