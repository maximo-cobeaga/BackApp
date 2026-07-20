"""Spreadsheet import preview and confirmation models."""
from django.conf import settings
from django.db import models

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
