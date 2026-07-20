from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.ingestion.models import InboundMessage, MailConnector
from apps.parsers.models import ParsedReportItem
from apps.parsers.providers.generic import GenericUnknownParser
from apps.parsers.services import mark_parsed_item_reviewed, parse_message, parse_unprocessed_messages
from apps.tenancy.models import Membership, Organization


class PhaseSixParserRegistryReviewTest(TestCase):
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
            name="M365",
            provider_type=MailConnector.ProviderType.MICROSOFT_GRAPH,
            auth_mode=MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
            mailbox_address="backups@example.com",
            config={
                "tenant_id_env": "M365_TENANT_ID",
                "client_id_env": "M365_CLIENT_ID",
                "client_secret_env": "M365_CLIENT_SECRET",
            },
        )
        self.other_connector = MailConnector.objects.create(
            organization=self.other_org,
            name="Other M365",
            provider_type=MailConnector.ProviderType.MICROSOFT_GRAPH,
            auth_mode=MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS,
            mailbox_address="other@example.com",
            config={
                "tenant_id_env": "M365_TENANT_ID",
                "client_id_env": "M365_CLIENT_ID",
                "client_secret_env": "M365_CLIENT_SECRET",
            },
        )
        self.message = InboundMessage.objects.create(
            organization=self.org,
            connector=self.connector,
            external_message_id="m1",
            subject="Backup report",
            sender="reports@example.com",
            received_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            body_preview="Backup result in an unknown format",
        )
        self.other_message = InboundMessage.objects.create(
            organization=self.other_org,
            connector=self.other_connector,
            external_message_id="m2",
            subject="Hidden report",
            sender="other@example.com",
        )
        self.client.force_login(self.user)

    def test_generic_parser_returns_unknown_low_confidence_review_required(self):
        result = GenericUnknownParser().parse(self.message)[0]
        assert result.parser_status == ParsedReportItem.ParserStatus.UNKNOWN
        assert result.confidence == 0.0
        assert "Backup report" in result.summary

    def test_parse_message_creates_unknown_item_and_needs_review(self):
        items, created = parse_message(message=self.message)
        self.message.refresh_from_db()
        assert created == 1
        assert len(items) == 1
        item = items[0]
        assert item.parser_status == ParsedReportItem.ParserStatus.UNKNOWN
        assert item.review_status == ParsedReportItem.ReviewStatus.NEEDS_REVIEW
        assert item.confidence == 0.0
        assert self.message.parser_status == "NEEDS_REVIEW"

    def test_parse_message_is_idempotent(self):
        parse_message(message=self.message)
        _items, created = parse_message(message=self.message)
        assert created == 0
        assert ParsedReportItem.objects.filter(
            organization=self.org,
            message=self.message,
        ).count() == 1

    def test_parse_unprocessed_messages_is_tenant_scoped(self):
        result = parse_unprocessed_messages(organization=self.org)
        assert result.processed_messages == 1
        assert result.created_items == 1
        assert ParsedReportItem.objects.filter(organization=self.org).count() == 1
        assert ParsedReportItem.objects.filter(organization=self.other_org).count() == 0
        self.other_message.refresh_from_db()
        assert self.other_message.parser_status == "UNPROCESSED"

    def test_review_queue_hides_other_organization_items(self):
        parse_message(message=self.message)
        parse_message(message=self.other_message)
        response = self.client.get(reverse("parser_review_queue"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Backup report" in content
        assert "Hidden report" not in content

    def test_review_action_marks_item_reviewed_without_changing_technical_status(self):
        item = parse_message(message=self.message)[0][0]
        response = self.client.post(
            reverse("parsed_item_review", args=[item.id]),
            {"review_note": "Checked manually; needs a provider-specific parser later."},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        self.message.refresh_from_db()
        assert item.parser_status == ParsedReportItem.ParserStatus.UNKNOWN
        assert item.review_status == ParsedReportItem.ReviewStatus.REVIEWED
        assert item.reviewed_by == self.user
        assert self.message.parser_status == "REVIEWED"

    def test_mark_reviewed_service_updates_review_metadata(self):
        item = parse_message(message=self.message)[0][0]
        mark_parsed_item_reviewed(item=item, user=self.user, note="Reviewed")
        item.refresh_from_db()
        assert item.review_status == ParsedReportItem.ReviewStatus.REVIEWED
        assert item.review_note == "Reviewed"
        assert item.reviewed_at is not None
