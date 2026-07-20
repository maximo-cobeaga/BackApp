"""Safe generic parser for unknown report formats."""
from apps.ingestion.models import InboundMessage
from apps.parsers.models import ParsedReportItem
from apps.parsers.providers.base import ParsedBackupResult


class GenericUnknownParser:
    name = "generic-unknown"
    version = "1"

    def parse(self, message: InboundMessage) -> list[ParsedBackupResult]:
        summary_parts = []
        if message.subject:
            summary_parts.append(f"Subject: {message.subject}")
        if message.sender:
            summary_parts.append(f"From: {message.sender}")
        if message.body_preview:
            summary_parts.append(f"Preview: {message.body_preview[:240]}")
        summary = " | ".join(summary_parts) or "Message format is unknown."
        return [
            ParsedBackupResult(
                parser_status=ParsedReportItem.ParserStatus.UNKNOWN,
                summary=summary,
                occurred_at=message.received_at,
                confidence=0.0,
            )
        ]
