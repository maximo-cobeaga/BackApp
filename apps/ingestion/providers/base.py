"""Mailbox provider contract for read-only ingestion."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from apps.ingestion.models import MailConnector


class MailProviderError(RuntimeError):
    """Base provider error."""


class ProviderNotImplemented(MailProviderError):
    """Raised when a provider type is registered but not implemented yet."""


class ProviderConfigurationError(MailProviderError):
    """Raised when required connector configuration is missing."""


@dataclass(frozen=True)
class FetchedAttachment:
    filename: str
    content_type: str = ""
    size_bytes: int = 0
    sha256: str = ""
    storage_path: str = ""
    extracted_text: str = ""


@dataclass(frozen=True)
class FetchedMessage:
    external_message_id: str
    internet_message_id: str = ""
    conversation_id: str = ""
    subject: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    received_at: datetime | None = None
    body_preview: str = ""
    text_body: str = ""
    html_body: str = ""
    html_as_text: str = ""
    raw_headers: dict[str, str] = field(default_factory=dict)
    provider_payload: dict = field(default_factory=dict)
    content_hash: str = ""
    has_attachments: bool = False
    attachments: list[FetchedAttachment] = field(default_factory=list)


class MailProvider(Protocol):
    def fetch_recent(self, *, connector: MailConnector, limit: int = 25) -> list[FetchedMessage]:
        """Fetch recent read-only messages from the configured mailbox."""
