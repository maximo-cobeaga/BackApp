"""Normalized parser output models."""
from django.conf import settings
from django.db import models

from apps.ingestion.models import InboundMessage
from apps.tenancy.models import OrganizationOwnedModel


class ParsedReportItem(OrganizationOwnedModel):
    class ParserStatus(models.TextChoices):
        SUCCESS = "SUCCESS", "Correcto"
        WARNING = "WARNING", "Warning"
        FAILED = "FAILED", "Fallido"
        PARTIAL = "PARTIAL", "Parcial"
        RUNNING = "RUNNING", "En curso"
        CANCELED = "CANCELED", "Cancelado"
        UNKNOWN = "UNKNOWN", "Desconocido"

    class ReviewStatus(models.TextChoices):
        AUTO_VALIDATED = "AUTO_VALIDATED", "Validado automáticamente"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Requiere revisión"
        REVIEWED = "REVIEWED", "Revisado"
        REJECTED = "REJECTED", "Rechazado"

    message = models.ForeignKey(
        InboundMessage,
        on_delete=models.CASCADE,
        related_name="parsed_items",
    )
    item_index = models.PositiveSmallIntegerField(default=0)
    parser_name = models.CharField(max_length=120)
    parser_version = models.CharField(max_length=40)
    parser_status = models.CharField(max_length=20, choices=ParserStatus.choices)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NEEDS_REVIEW,
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    customer_hints = models.JSONField(default=list, blank=True)
    object_hints = models.JSONField(default=list, blank=True)
    job_hints = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    error_code = models.CharField(max_length=120, blank=True)
    error_details = models.TextField(blank=True)
    warning_details = models.TextField(blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=0.0)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_parsed_report_items",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "message__received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "message", "parser_name", "parser_version", "item_index"],
                name="uq_parsed_report_item_parser_index_per_message_org",
            )
        ]

    def clean(self):
        if self.message_id:
            self.organization = self.message.organization
        if self.parser_status == self.ParserStatus.UNKNOWN:
            if self.review_status == self.ReviewStatus.AUTO_VALIDATED:
                self.review_status = self.ReviewStatus.NEEDS_REVIEW
            self.confidence = 0.0

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.parser_name} {self.parser_status}: {self.summary[:60]}"
