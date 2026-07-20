"""Parser execution and review services."""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.ingestion.models import InboundMessage
from apps.parsers.models import ParsedReportItem
from apps.parsers.providers.registry import ParserRegistry, default_parser_registry
from apps.tenancy.models import Organization


@dataclass(frozen=True)
class ParseBatchResult:
    processed_messages: int
    created_items: int
    skipped_messages: int


@transaction.atomic
def parse_message(
    *,
    message: InboundMessage,
    registry: ParserRegistry | None = None,
) -> tuple[list[ParsedReportItem], int]:
    selected_registry = registry or default_parser_registry()
    parser = selected_registry.parser_for(message)
    results = parser.parse(message)
    parsed_items: list[ParsedReportItem] = []
    created_count = 0

    for index, result in enumerate(results):
        item, created = ParsedReportItem.objects.get_or_create(
            organization=message.organization,
            message=message,
            parser_name=parser.name,
            parser_version=parser.version,
            item_index=index,
            defaults={
                "parser_status": result.parser_status,
                "review_status": ParsedReportItem.ReviewStatus.NEEDS_REVIEW,
                "occurred_at": result.occurred_at,
                "customer_hints": result.customer_hints,
                "object_hints": result.object_hints,
                "job_hints": result.job_hints,
                "summary": result.summary,
                "error_code": result.error_code,
                "error_details": result.error_details,
                "warning_details": result.warning_details,
                "metrics": result.metrics,
                "confidence": result.confidence,
            },
        )
        parsed_items.append(item)
        if created:
            created_count += 1

    message.parser_status = "NEEDS_REVIEW" if created_count else message.parser_status
    if parsed_items and all(
        item.review_status == ParsedReportItem.ReviewStatus.REVIEWED for item in parsed_items
    ):
        message.parser_status = "REVIEWED"
    message.save(update_fields=["parser_status", "updated_at"])
    return parsed_items, created_count


@transaction.atomic
def parse_unprocessed_messages(
    *,
    organization: Organization,
    registry: ParserRegistry | None = None,
    limit: int = 50,
) -> ParseBatchResult:
    messages = list(
        InboundMessage.objects.select_for_update()
        .filter(organization=organization, parser_status="UNPROCESSED")
        .order_by("received_at", "created_at")[:limit]
    )
    processed = 0
    created_items = 0
    skipped = 0
    for message in messages:
        _items, created = parse_message(message=message, registry=registry)
        processed += 1
        created_items += created
        if created == 0:
            skipped += 1
    return ParseBatchResult(
        processed_messages=processed,
        created_items=created_items,
        skipped_messages=skipped,
    )


@transaction.atomic
def mark_parsed_item_reviewed(*, item: ParsedReportItem, user, note: str = "") -> ParsedReportItem:
    item.review_status = ParsedReportItem.ReviewStatus.REVIEWED
    item.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    item.reviewed_at = timezone.now()
    item.review_note = note
    item.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    if not item.message.parsed_items.filter(
        review_status=ParsedReportItem.ReviewStatus.NEEDS_REVIEW
    ).exists():
        item.message.parser_status = "REVIEWED"
        item.message.save(update_fields=["parser_status", "updated_at"])
    return item
