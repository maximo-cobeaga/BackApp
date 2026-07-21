"""Parser registry.

Provider-specific backup parsers must be added only after anonymized samples are
available. The static mail rules parser implements conservative identification
rules and sends uncertain formats to manual review.
"""
from apps.ingestion.models import InboundMessage
from apps.parsers.providers.base import BackupReportParser
from apps.parsers.providers.static_mail import StaticMailRulesParser


class ParserRegistry:
    def __init__(self, parsers: list[BackupReportParser] | None = None):
        self.parsers = parsers or [StaticMailRulesParser()]

    def parser_for(self, message: InboundMessage) -> BackupReportParser:
        return self.parsers[0]


def default_parser_registry() -> ParserRegistry:
    return ParserRegistry()
