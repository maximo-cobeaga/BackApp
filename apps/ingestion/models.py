"""Read-only mailbox ingestion models."""
from django.conf import settings
from django.db import models

from apps.tenancy.models import OrganizationOwnedModel


class MailConnector(OrganizationOwnedModel):
    class ProviderType(models.TextChoices):
        MICROSOFT_GRAPH = "MICROSOFT_GRAPH", "Microsoft 365 Outlook"
        IMAP = "IMAP", "IMAP"
        GMAIL_API = "GMAIL_API", "Gmail API"

    class AuthMode(models.TextChoices):
        OAUTH_CLIENT_CREDENTIALS = "OAUTH_CLIENT_CREDENTIALS", "OAuth client credentials"
        OAUTH_REFRESH_TOKEN = "OAUTH_REFRESH_TOKEN", "OAuth refresh token"
        BASIC_ENV = "BASIC_ENV", "Basic credentials from environment"

    name = models.CharField(max_length=160)
    provider_type = models.CharField(max_length=30, choices=ProviderType.choices)
    auth_mode = models.CharField(max_length=40, choices=AuthMode.choices)
    mailbox_address = models.EmailField()
    folder = models.CharField(max_length=160, default="Inbox")
    config = models.JSONField(default=dict, blank=True)
    read_only = models.BooleanField(default=True)
    poll_interval_seconds = models.PositiveIntegerField(default=300)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mail_connectors",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uq_mail_connector_name_per_organization",
            ),
            models.CheckConstraint(
                condition=models.Q(read_only=True),
                name="ck_mail_connector_read_only",
            ),
        ]

    def clean(self):
        self.read_only = True

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_provider_type_display()})"


class InboundMessage(OrganizationOwnedModel):
    connector = models.ForeignKey(
        MailConnector,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    external_message_id = models.CharField(max_length=512)
    internet_message_id = models.CharField(max_length=512, blank=True)
    conversation_id = models.CharField(max_length=512, blank=True)
    subject = models.CharField(max_length=998, blank=True)
    sender = models.EmailField(blank=True)
    recipients = models.JSONField(default=list, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    body_preview = models.TextField(blank=True)
    raw_headers = models.JSONField(default=dict, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    has_attachments = models.BooleanField(default=False)
    parser_status = models.CharField(max_length=40, default="UNPROCESSED")

    class Meta:
        ordering = ["-received_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "connector", "external_message_id"],
                name="uq_inbound_message_external_id_per_connector_org",
            )
        ]

    def clean(self):
        if self.connector_id:
            self.organization = self.connector.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.subject or self.external_message_id


class MessageAttachment(OrganizationOwnedModel):
    message = models.ForeignKey(
        InboundMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=160, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    storage_path = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["filename"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "message", "sha256", "filename"],
                name="uq_message_attachment_hash_name_per_org",
            )
        ]

    def clean(self):
        if self.message_id:
            self.organization = self.message.organization

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.filename
