from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.ingestion.models import InboundMessage, MailConnector, MessageAttachment
from apps.ingestion.providers.base import FetchedAttachment, FetchedMessage, ProviderConfigurationError, ProviderNotImplemented
from apps.ingestion.providers.graph import MicrosoftGraphMailboxProvider
from apps.ingestion.providers.registry import provider_for
from apps.ingestion.services import sync_mailbox
from apps.tenancy.models import Membership, Organization


class FakeMailProvider:
    def __init__(self, messages):
        self.messages = messages

    def fetch_recent(self, *, connector, limit=25):
        return self.messages[:limit]


class PhaseFiveMailConnectorTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="admin", password="pass")
        self.other_user = User.objects.create_user(username="other", password="pass")
        self.org = Organization.objects.create(name="Org", slug="org")
        self.other_org = Organization.objects.create(name="Other", slug="other")
        Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.ADMIN,
        )
        Membership.objects.create(
            organization=self.other_org,
            user=self.other_user,
            role=Membership.Role.ADMIN,
        )
        self.connector = MailConnector.objects.create(
            organization=self.org,
            name="Backups M365",
            provider_type=MailConnector.ProviderType.MICROSOFT_GRAPH,
            auth_mode=MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
            mailbox_address="backups@example.com",
            folder="Inbox",
            config={
                "tenant_id_env": "M365_TENANT_ID",
                "client_id_env": "M365_CLIENT_ID",
                "client_secret_env": "M365_CLIENT_SECRET",
            },
            created_by=self.user,
        )
        self.other_connector = MailConnector.objects.create(
            organization=self.other_org,
            name="Other M365",
            provider_type=MailConnector.ProviderType.MICROSOFT_GRAPH,
            auth_mode=MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
            mailbox_address="other@example.com",
            folder="Inbox",
            config={
                "tenant_id_env": "M365_TENANT_ID",
                "client_id_env": "M365_CLIENT_ID",
                "client_secret_env": "M365_CLIENT_SECRET",
            },
        )
        self.client.force_login(self.user)

    def test_provider_registry_selects_microsoft_graph_and_registers_future_types(self):
        assert isinstance(provider_for(self.connector), MicrosoftGraphMailboxProvider)
        imap_connector = MailConnector(
            organization=self.org,
            name="IMAP future",
            provider_type=MailConnector.ProviderType.IMAP,
            auth_mode=MailConnector.AuthMode.BASIC_ENV,
            mailbox_address="imap@example.com",
        )
        with self.assertRaises(ProviderNotImplemented):
            provider_for(imap_connector).fetch_recent(connector=imap_connector)

    def test_connector_never_persists_secret_values_from_form(self):
        response = self.client.post(
            reverse("mail_connector_create"),
            {
                "name": "M365 Soporte",
                "provider_type": MailConnector.ProviderType.MICROSOFT_GRAPH,
                "auth_mode": MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
                "mailbox_address": "soporte@example.com",
                "folder": "Inbox",
                "poll_interval_seconds": "300",
                "is_active": "on",
                "notes": "",
                "tenant_id_env": "M365_TENANT_ID",
                "client_id_env": "M365_CLIENT_ID",
                "client_secret_env": "M365_CLIENT_SECRET",
            },
        )
        assert response.status_code == 302
        connector = MailConnector.objects.get(organization=self.org, name="M365 Soporte")
        assert connector.read_only is True
        assert connector.config == {
            "tenant_id_env": "M365_TENANT_ID",
            "client_id_env": "M365_CLIENT_ID",
            "client_secret_env": "M365_CLIENT_SECRET",
        }
        assert "super-secret-value" not in str(connector.config)

    def test_sync_mailbox_stores_full_body_and_attachment_text(self):
        fetched = FetchedMessage(
            external_message_id="graph-body",
            subject="Backup body",
            sender="reports@example.com",
            body_preview="Preview only",
            text_body="Status: Success\nErrors: 0",
            html_body="<p>Status: <strong>Success</strong></p>",
            html_as_text="Status: Success",
            attachments=[
                FetchedAttachment(
                    filename="report.txt",
                    content_type="text/plain",
                    size_bytes=120,
                    sha256="b" * 64,
                    extracted_text="Warnings: 0\nErrors: 0",
                )
            ],
            has_attachments=True,
        )

        sync_mailbox(connector=self.connector, provider=FakeMailProvider([fetched]))

        message = InboundMessage.objects.get(
            organization=self.org,
            connector=self.connector,
            external_message_id="graph-body",
        )
        attachment = message.attachments.get()
        assert message.text_body == "Status: Success\nErrors: 0"
        assert message.html_body == "<p>Status: <strong>Success</strong></p>"
        assert message.html_as_text == "Status: Success"
        assert attachment.extracted_text == "Warnings: 0\nErrors: 0"

    def test_sync_mailbox_stores_messages_idempotently_with_attachment_metadata(self):
        fetched = FetchedMessage(
            external_message_id="graph-1",
            internet_message_id="<internet-1@example.com>",
            conversation_id="conversation-1",
            subject="Backup OK",
            sender="reports@example.com",
            recipients=["backups@example.com"],
            received_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            body_preview="Backup completed",
            has_attachments=True,
            attachments=[
                FetchedAttachment(
                    filename="report.txt",
                    content_type="text/plain",
                    size_bytes=120,
                    sha256="a" * 64,
                )
            ],
        )
        provider = FakeMailProvider([fetched])
        first = sync_mailbox(connector=self.connector, provider=provider)
        second = sync_mailbox(connector=self.connector, provider=provider)

        assert first.fetched == 1
        assert first.created == 1
        assert first.skipped == 0
        assert second.fetched == 1
        assert second.created == 0
        assert second.skipped == 1
        assert InboundMessage.objects.filter(
            organization=self.org,
            connector=self.connector,
            external_message_id="graph-1",
        ).count() == 1
        assert MessageAttachment.objects.filter(organization=self.org).count() == 1

    def test_message_list_hides_other_organization_records(self):
        InboundMessage.objects.create(
            organization=self.org,
            connector=self.connector,
            external_message_id="visible",
            subject="Visible",
            sender="reports@example.com",
        )
        InboundMessage.objects.create(
            organization=self.other_org,
            connector=self.other_connector,
            external_message_id="hidden",
            subject="Hidden",
            sender="other@example.com",
        )
        response = self.client.get(reverse("inbound_message_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Visible" in content
        assert "Hidden" not in content

    def test_graph_provider_requires_environment_references(self):
        provider = MicrosoftGraphMailboxProvider()
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ProviderConfigurationError):
                provider.fetch_recent(connector=self.connector)

    def test_graph_provider_maps_message_payload(self):
        provider = MicrosoftGraphMailboxProvider()
        item = {
            "id": "graph-id",
            "internetMessageId": "<msg@example.com>",
            "conversationId": "conversation",
            "subject": "Backup report",
            "from": {"emailAddress": {"address": "sender@example.com"}},
            "toRecipients": [
                {"emailAddress": {"address": "backups@example.com"}},
            ],
            "receivedDateTime": "2026-07-20T08:00:00Z",
            "bodyPreview": "Done",
            "body": {
                "contentType": "html",
                "content": "<p>Status: <strong>Success</strong></p>",
            },
            "hasAttachments": False,
        }
        message = provider._message_from_graph(item)
        assert message.external_message_id == "graph-id"
        assert message.sender == "sender@example.com"
        assert message.recipients == ["backups@example.com"]
        assert message.received_at == datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
        assert message.html_body == "<p>Status: <strong>Success</strong></p>"
        assert message.html_as_text == "Status: Success"
