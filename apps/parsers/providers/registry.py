"""Parser registry.

Provider-specific backup parsers must be added only after anonymized samples are
available. Until then, the generic parser deliberately returns UNKNOWN.
"""
from apps.ingestion.models import InboundMessage
from apps.parsers.providers.base import BackupReportParser
from apps.parsers.providers.generic import GenericUnknownParser


class ParserRegistry:
    def __init__(self, parsers: list[BackupReportParser] | None = None):
        self.parsers = parsers or [GenericUnknownParser()]

    def parser_for(self, message: InboundMessage) -> BackupReportParser:
        return self.parsers[0]


def default_parser_registry() -> ParserRegistry:
    return ParserRegistry()
