"""Read-only mailbox synchronization services."""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.ingestion.models import InboundMessage, MailConnector, MessageAttachment
from apps.ingestion.providers.base import FetchedMessage, MailProvider
from apps.ingestion.providers.registry import provider_for


@dataclass(frozen=True)
class MailboxSyncResult:
    fetched: int
    created: int
    skipped: int


@transaction.atomic
def store_fetched_message(*, connector: MailConnector, message: FetchedMessage) -> tuple[InboundMessage, bool]:
    inbound, created = InboundMessage.objects.get_or_create(
        organization=connector.organization,
        connector=connector,
        external_message_id=message.external_message_id,
        defaults={
            "internet_message_id": message.internet_message_id,
            "conversation_id": message.conversation_id,
            "subject": message.subject,
            "sender": message.sender,
            "recipients": message.recipients,
            "received_at": message.received_at,
            "body_preview": message.body_preview,
            "text_body": message.text_body,
            "html_body": message.html_body,
            "html_as_text": message.html_as_text,
            "raw_headers": message.raw_headers,
            "provider_payload": message.provider_payload,
            "content_hash": message.content_hash,
            "has_attachments": message.has_attachments,
        },
    )
    if not created:
        return inbound, False

    attachments = [
        MessageAttachment(
            organization=connector.organization,
            message=inbound,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
            sha256=attachment.sha256,
            storage_path=attachment.storage_path,
            extracted_text=attachment.extracted_text,
        )
        for attachment in message.attachments
        if attachment.sha256
    ]
    if attachments:
        MessageAttachment.objects.bulk_create(attachments)
    return inbound, True


@transaction.atomic
def sync_mailbox(
    *,
    connector: MailConnector,
    provider: MailProvider | None = None,
    limit: int = 25,
) -> MailboxSyncResult:
    if not connector.read_only:
        raise ValueError("Mailbox synchronization requires a read-only connector.")
    selected_provider = provider or provider_for(connector)
    fetched_messages = selected_provider.fetch_recent(connector=connector, limit=limit)
    created_count = 0
    skipped_count = 0
    for fetched_message in fetched_messages:
        if not fetched_message.external_message_id:
            skipped_count += 1
            continue
        _message, created = store_fetched_message(
            connector=connector,
            message=fetched_message,
        )
        if created:
            created_count += 1
        else:
            skipped_count += 1
    connector.last_synced_at = timezone.now()
    connector.save(update_fields=["last_synced_at", "updated_at"])
    return MailboxSyncResult(
        fetched=len(fetched_messages),
        created=created_count,
        skipped=skipped_count,
    )
