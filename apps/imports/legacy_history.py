"""Dry-run parser for the legacy backup history CSV matrix."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


FIXED_COLUMN_COUNT = 8
DAILY_BLOCK_SIZE = 4
DATE_ROW_INDEX = 5
HEADER_ROW_INDEX = 6
DATA_START_ROW_INDEX = 8

FIXED_HEADERS = [
    "Cliente",
    "Fecha de Alta del Cliente",
    "Fecha de Baja del Cliente",
    "Sucursal",
    "Servidor",
    "Tipo de Backup",
    "Método de Backup",
    "Responsable de Disco Externo",
]

EXECUTION_STATUSES = {"SUCCESS", "WARNING", "ERROR"}


class LegacyImportError(ValueError):
    """Raised when the legacy CSV structure is invalid."""


class LegacyStatus:
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PLACEHOLDER = "PLACEHOLDER"
    UNKNOWN = "UNKNOWN"
    UNRECORDED = "UNRECORDED"


STATUS_MAPPING = {
    "correcto": LegacyStatus.SUCCESS,
    "correctos": LegacyStatus.SUCCESS,
    "warning": LegacyStatus.WARNING,
    "warnings": LegacyStatus.WARNING,
    "error": LegacyStatus.ERROR,
    "n/a": LegacyStatus.NOT_APPLICABLE,
    "na": LegacyStatus.NOT_APPLICABLE,
    ".": LegacyStatus.PLACEHOLDER,
    ",": LegacyStatus.UNKNOWN,
    "n": LegacyStatus.UNKNOWN,
    "": LegacyStatus.UNRECORDED,
}

PROVIDER_BY_METHOD = {
    "iperius backup": "IPERIUS",
    "iperius": "IPERIUS",
    "veeam backup": "VEEAM",
    "veeam": "VEEAM",
    "microsoft azure backup": "AZURE_BACKUP",
    "microsoft azure": "AZURE_BACKUP",
    "dlm aws": "AWS_DLM",
    "aws dlm": "AWS_DLM",
    "qnap": "QNAP",
    "script": "SCRIPT",
    "robocopy": "CUSTOM_ROBOCOPY",
    "shadow copy": "CUSTOM_SHADOW_COPY",
    "drp aws": "AWS_DRP",
}

PROVIDER_HINTS = {
    "nakivo": "NAKIVO",
    "cubebackup": "CUBEBACKUP",
    "cube backup": "CUBEBACKUP",
    "aws dlm": "AWS_DLM",
    "dlm aws": "AWS_DLM",
    "aws drp": "AWS_DRP",
    "drp aws": "AWS_DRP",
    "qnap": "QNAP",
}


@dataclass(frozen=True)
class ProviderSuggestion:
    provider: str
    requires_confirmation: bool


@dataclass
class LegacyImportSummary:
    source_file: str
    source_sha256: str
    encoding: str
    delimiter: str
    rows: int
    columns: int
    effective_columns: int
    ignored_trailing_empty_columns: int
    date_groups: int
    first_matrix_date: str | None
    last_matrix_date: str | None
    first_recorded_date: str | None = None
    last_recorded_date: str | None = None
    managed_customers: int = 0
    configuration_rows: int = 0
    separator_rows: int = 0
    legacy_status_cells: int = 0
    legacy_daily_records: int = 0
    observations: int = 0
    ticket_references: int = 0
    unique_ticket_ids: int = 0
    imported_execution_candidates: int = 0
    provider_confirmation_required: int = 0
    status_counts: defaultdict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    provider_counts: defaultdict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    derived_reason_counts: defaultdict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, *, tenant: str | None = None, dry_run: bool = True) -> dict[str, Any]:
        payload = {
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "dry_run": dry_run,
            "rows": self.rows,
            "columns": self.columns,
            "effective_columns": self.effective_columns,
            "ignored_trailing_empty_columns": self.ignored_trailing_empty_columns,
            "managed_customers": self.managed_customers,
            "configuration_rows": self.configuration_rows,
            "separator_rows": self.separator_rows,
            "date_groups": self.date_groups,
            "first_matrix_date": self.first_matrix_date,
            "last_matrix_date": self.last_matrix_date,
            "first_recorded_date": self.first_recorded_date,
            "last_recorded_date": self.last_recorded_date,
            "legacy_status_cells": self.legacy_status_cells,
            "legacy_daily_records": self.legacy_daily_records,
            "observations": self.observations,
            "ticket_references": self.ticket_references,
            "unique_ticket_ids": self.unique_ticket_ids,
            "imported_execution_candidates": self.imported_execution_candidates,
            "provider_confirmation_required": self.provider_confirmation_required,
            "status_counts": dict(sorted(self.status_counts.items())),
            "provider_counts": dict(sorted(self.provider_counts.items())),
            "derived_reason_counts": dict(sorted(self.derived_reason_counts.items())),
            "issues": self.issues,
        }
        if tenant is not None:
            payload["tenant"] = tenant
        return payload

    def to_json(self, *, tenant: str | None = None, dry_run: bool = True) -> str:
        return json.dumps(
            self.to_dict(tenant=tenant, dry_run=dry_run),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )


def normalize_legacy_status(raw_status: str | None) -> str:
    normalized = _clean(raw_status).casefold()
    return STATUS_MAPPING.get(normalized, LegacyStatus.UNKNOWN)


def parse_legacy_backup_history(
    path: str | Path,
    *,
    encoding: str = "cp1252",
    delimiter: str = ";",
) -> LegacyImportSummary:
    source_path = Path(path)
    raw_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    with source_path.open("r", encoding=encoding, newline="") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))

    if len(rows) <= DATA_START_ROW_INDEX:
        raise LegacyImportError("Legacy CSV does not contain data rows.")

    columns = _validate_consistent_width(rows)
    effective_columns = _effective_columns(rows)
    ignored_trailing = columns - effective_columns
    _validate_matrix_width(effective_columns)
    _validate_headers(rows[HEADER_ROW_INDEX], effective_columns)
    dates = _parse_date_groups(rows[DATE_ROW_INDEX], effective_columns)

    summary = LegacyImportSummary(
        source_file=source_path.name,
        source_sha256=source_sha256,
        encoding=encoding,
        delimiter=delimiter,
        rows=len(rows),
        columns=columns,
        effective_columns=effective_columns,
        ignored_trailing_empty_columns=ignored_trailing,
        date_groups=len(dates),
        first_matrix_date=dates[0].isoformat() if dates else None,
        last_matrix_date=dates[-1].isoformat() if dates else None,
    )

    current_customer = ""
    managed_customers: set[str] = set()
    unique_ticket_ids: set[str] = set()

    for row_index, row in enumerate(rows[DATA_START_ROW_INDEX:], start=DATA_START_ROW_INDEX):
        source_row = row_index + 1
        working_row = row[:effective_columns]
        raw_customer = _clean(_cell(working_row, 0))
        if _is_valid_customer(raw_customer):
            current_customer = raw_customer
        if not _has_backup_definition(working_row):
            summary.separator_rows += 1
            continue
        if not current_customer:
            summary.issues.append(
                _issue(
                    source_row=source_row,
                    issue_code="MISSING_CUSTOMER",
                    severity="ERROR",
                    details="Configuration row has no propagated customer.",
                )
            )
            continue

        summary.configuration_rows += 1
        managed_customers.add(current_customer)
        suggestion = suggest_provider(
            legacy_method=_cell(working_row, 6),
            legacy_backup_name=_cell(working_row, 5),
        )
        if suggestion.provider:
            summary.provider_counts[suggestion.provider] += 1
        if suggestion.requires_confirmation:
            summary.provider_confirmation_required += 1

        for day_index, source_date in enumerate(dates):
            base_column = FIXED_COLUMN_COUNT + day_index * DAILY_BLOCK_SIZE
            responsible = _clean(_cell(working_row, base_column))
            raw_status = _clean(_cell(working_row, base_column + 1))
            ticket = _clean(_cell(working_row, base_column + 2))
            observation = _clean(_cell(working_row, base_column + 3))
            if not any((responsible, raw_status, ticket, observation)):
                continue

            summary.legacy_daily_records += 1
            if raw_status:
                summary.legacy_status_cells += 1
                _record_date(summary, source_date)
            if observation:
                summary.observations += 1
                for reason in derive_observation_reasons(observation):
                    summary.derived_reason_counts[reason] += 1
            if ticket:
                summary.ticket_references += 1
                unique_ticket_ids.add(ticket)

            status = normalize_legacy_status(raw_status)
            summary.status_counts[status] += 1
            if status in EXECUTION_STATUSES:
                summary.imported_execution_candidates += 1
            if status == LegacyStatus.UNKNOWN:
                summary.issues.append(
                    _issue(
                        source_row=source_row,
                        source_date=source_date.isoformat(),
                        issue_code="UNKNOWN_STATUS",
                        severity="WARNING",
                        details=f"Unknown legacy status: {raw_status!r}",
                    )
                )
            if _has_status_observation_conflict(status=status, observation=observation):
                summary.issues.append(
                    _issue(
                        source_row=source_row,
                        source_date=source_date.isoformat(),
                        issue_code="STATUS_OBSERVATION_CONFLICT",
                        severity="WARNING",
                        details="Status is error but observation suggests a successful backup or missing report.",
                    )
                )

    summary.managed_customers = len(managed_customers)
    summary.unique_ticket_ids = len(unique_ticket_ids)
    return summary


def suggest_provider(*, legacy_method: str, legacy_backup_name: str) -> ProviderSuggestion:
    method = _normalize_text(legacy_method)
    if method in PROVIDER_BY_METHOD:
        return ProviderSuggestion(PROVIDER_BY_METHOD[method], False)
    if method:
        return ProviderSuggestion("", False)

    backup_name = _normalize_text(legacy_backup_name)
    for hint, provider in PROVIDER_HINTS.items():
        if hint in backup_name:
            return ProviderSuggestion(provider, True)
    return ProviderSuggestion("", False)


def derive_observation_reasons(observation: str) -> list[str]:
    text = _normalize_text(observation)
    reasons: list[str] = []
    if re.search(r"sin\s+modificaciones?.*?(\d+)\s+d[ií]as", text):
        reasons.append("STALE_NO_CHANGES")
    if any(phrase in text for phrase in ("no llego el reporte", "no llegaron logs", "no se recibio correo")):
        reasons.append("REPORT_OR_LOG_MISSING")
    if "ayer" in text and any(word in text for word in ("correcto", "correctamente")):
        reasons.append("PREVIOUS_EXECUTION_SUCCESS")
    if any(phrase in text for phrase in ("error repetido", "continua el error", "repeticion")):
        reasons.append("REPEATED_ERROR")
    if any(phrase in text for phrase in ("lo gestionan ellos", "infra no administrada", "tercero")):
        reasons.append("CUSTOMER_OR_THIRD_PARTY_MANAGED")
    return reasons


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return row[index]


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", _clean(value))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text).strip().casefold()


def _validate_consistent_width(rows: list[list[str]]) -> int:
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise LegacyImportError(f"Legacy CSV row widths differ: {sorted(widths)}")
    return widths.pop()


def _effective_columns(rows: list[list[str]]) -> int:
    last_non_empty = -1
    for row in rows:
        for index, value in enumerate(row):
            if _clean(value):
                last_non_empty = max(last_non_empty, index)
    return last_non_empty + 1


def _validate_matrix_width(effective_columns: int) -> None:
    if effective_columns <= FIXED_COLUMN_COUNT:
        raise LegacyImportError("Legacy CSV has no daily date blocks.")
    variable_columns = effective_columns - FIXED_COLUMN_COUNT
    if variable_columns % DAILY_BLOCK_SIZE != 0:
        raise LegacyImportError("Daily matrix columns must be groups of four.")


def _validate_headers(header_row: list[str], effective_columns: int) -> None:
    observed = [_clean(value) for value in header_row[:FIXED_COLUMN_COUNT]]
    if observed != FIXED_HEADERS:
        raise LegacyImportError(
            "Unexpected fixed headers. Expected: "
            + ", ".join(FIXED_HEADERS)
            + "."
        )
    for index in range(FIXED_COLUMN_COUNT, effective_columns, DAILY_BLOCK_SIZE):
        block_headers = [_normalize_text(value) for value in header_row[index : index + 4]]
        if block_headers != ["responsable", "estado", "ticket", "observaciones"]:
            raise LegacyImportError("Unexpected daily block headers.")


def _parse_date_groups(date_row: list[str], effective_columns: int) -> list[datetime.date]:
    dates = []
    for index in range(FIXED_COLUMN_COUNT, effective_columns, DAILY_BLOCK_SIZE):
        raw_date = _clean(date_row[index])
        if not raw_date:
            raise LegacyImportError(f"Missing date at column {index + 1}.")
        parsed = _parse_legacy_date(raw_date)
        if dates and parsed <= dates[-1]:
            raise LegacyImportError("Date groups must be increasing and unique.")
        dates.append(parsed)
    return dates


def _parse_legacy_date(raw_date: str):
    for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_date, date_format).date()
        except ValueError:
            continue
    raise LegacyImportError(f"Invalid date value: {raw_date!r}")


def _is_valid_customer(raw_customer: str) -> bool:
    return bool(raw_customer and raw_customer != ".")


def _has_backup_definition(row: list[str]) -> bool:
    definition_values = row[3:FIXED_COLUMN_COUNT]
    return any(_clean(value) and _clean(value) != "." for value in definition_values)


def _record_date(summary: LegacyImportSummary, source_date) -> None:
    date_value = source_date.isoformat()
    if summary.first_recorded_date is None or date_value < summary.first_recorded_date:
        summary.first_recorded_date = date_value
    if summary.last_recorded_date is None or date_value > summary.last_recorded_date:
        summary.last_recorded_date = date_value


def _has_status_observation_conflict(*, status: str, observation: str) -> bool:
    if status != LegacyStatus.ERROR or not observation:
        return False
    text = _normalize_text(observation)
    success_signal = any(word in text for word in ("correcto", "correctamente", "realizo"))
    missing_report_signal = any(phrase in text for phrase in ("no llego reporte", "no llego el reporte"))
    return success_signal or missing_report_signal


def _issue(
    *,
    source_row: int,
    issue_code: str,
    severity: str,
    details: str,
    source_date: str | None = None,
) -> dict[str, Any]:
    issue = {
        "source_row": source_row,
        "issue_code": issue_code,
        "severity": severity,
        "details": details,
    }
    if source_date is not None:
        issue["source_date"] = source_date
    return issue
