"""Parser contract for normalized backup report items."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from apps.ingestion.models import InboundMessage


@dataclass(frozen=True)
class ParsedBackupResult:
    parser_status: str
    summary: str
    occurred_at: datetime | None = None
    customer_hints: list[str] = field(default_factory=list)
    object_hints: list[str] = field(default_factory=list)
    job_hints: list[str] = field(default_factory=list)
    error_code: str = ""
    error_details: str = ""
    warning_details: str = ""
    metrics: dict = field(default_factory=dict)
    confidence: float = 0.0


class BackupReportParser(Protocol):
    name: str
    version: str

    def parse(self, message: InboundMessage) -> list[ParsedBackupResult]:
        """Parse one inbound message into normalized backup report results."""
