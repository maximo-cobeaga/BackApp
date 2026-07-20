"""Mailbox provider registry."""
from apps.ingestion.models import MailConnector
from apps.ingestion.providers.base import MailProvider, ProviderNotImplemented
from apps.ingestion.providers.graph import MicrosoftGraphMailboxProvider


class NotImplementedMailboxProvider:
    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    def fetch_recent(self, *, connector: MailConnector, limit: int = 25):
        raise ProviderNotImplemented(
            f"{self.provider_name} is registered but not implemented in this phase."
        )


def provider_for(connector: MailConnector) -> MailProvider:
    if connector.provider_type == MailConnector.ProviderType.MICROSOFT_GRAPH:
        return MicrosoftGraphMailboxProvider()
    if connector.provider_type == MailConnector.ProviderType.IMAP:
        return NotImplementedMailboxProvider("IMAP")
    if connector.provider_type == MailConnector.ProviderType.GMAIL_API:
        return NotImplementedMailboxProvider("Gmail API")
    raise ProviderNotImplemented(f"Unknown provider type: {connector.provider_type}")
