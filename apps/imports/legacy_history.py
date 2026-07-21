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

RESPONSIBLE_HEADER_VARIANTS = {
    "responsable",
    "responsable de verificacion de backup",
    "responsable de verificación de backup",
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
            _count_raw_status_cells(summary=summary, row=working_row, dates=dates)
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
        if (
            block_headers[0] not in RESPONSIBLE_HEADER_VARIANTS
            or block_headers[1:] != ["estado", "ticket", "observaciones"]
        ):
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


def _count_raw_status_cells(
    *,
    summary: LegacyImportSummary,
    row: list[str],
    dates: list,
) -> None:
    for day_index, source_date in enumerate(dates):
        base_column = FIXED_COLUMN_COUNT + day_index * DAILY_BLOCK_SIZE
        raw_status = _clean(_cell(row, base_column + 1))
        if not raw_status:
            continue
        status = normalize_legacy_status(raw_status)
        summary.legacy_status_cells += 1
        summary.status_counts[status] += 1
        _record_date(summary, source_date)


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


@dataclass(frozen=True)
class LegacyConfigurationCandidate:
    source_row: int
    legacy_fingerprint: str
    legacy_customer_name: str
    legacy_site_label: str
    source_asset_label: str
    legacy_backup_name: str
    legacy_method: str
    provider: str
    provider_requires_confirmation: bool
    external_responsible: str
    is_external: bool
    schedule_hint: str
    schedule_requires_confirmation: bool
    quality_flags: list[str]


@dataclass(frozen=True)
class LegacyDailyRecordCandidate:
    legacy_fingerprint: str
    source_row: int
    source_date: Any
    raw_responsible: str
    raw_status: str
    raw_ticket: str
    raw_observation: str
    normalized_status: str
    normalization_rule: str
    quality_flags: list[str]


@dataclass(frozen=True)
class LegacyParsedHistory:
    summary: LegacyImportSummary
    configurations: list[LegacyConfigurationCandidate]
    daily_records: list[LegacyDailyRecordCandidate]


def parse_legacy_backup_history_details(
    path: str | Path,
    *,
    encoding: str = "cp1252",
    delimiter: str = ";",
) -> LegacyParsedHistory:
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
    configurations: list[LegacyConfigurationCandidate] = []
    daily_records: list[LegacyDailyRecordCandidate] = []
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
            _count_raw_status_cells(summary=summary, row=working_row, dates=dates)
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

        legacy_site_label = _clean(_cell(working_row, 3))
        source_asset_label = _clean(_cell(working_row, 4))
        legacy_backup_name = _clean(_cell(working_row, 5))
        legacy_method = _clean(_cell(working_row, 6))
        external_responsible = _clean(_cell(working_row, 7))
        legacy_fingerprint = legacy_configuration_fingerprint(
            customer=current_customer,
            site=legacy_site_label,
            source_asset=source_asset_label,
            backup_name=legacy_backup_name,
            method=legacy_method,
        )
        summary.configuration_rows += 1
        managed_customers.add(current_customer)
        suggestion = suggest_provider(
            legacy_method=legacy_method,
            legacy_backup_name=legacy_backup_name,
        )
        if suggestion.provider:
            summary.provider_counts[suggestion.provider] += 1
        if suggestion.requires_confirmation:
            summary.provider_confirmation_required += 1
        configurations.append(
            LegacyConfigurationCandidate(
                source_row=source_row,
                legacy_fingerprint=legacy_fingerprint,
                legacy_customer_name=current_customer,
                legacy_site_label=legacy_site_label,
                source_asset_label=source_asset_label,
                legacy_backup_name=legacy_backup_name,
                legacy_method=legacy_method,
                provider=suggestion.provider,
                provider_requires_confirmation=suggestion.requires_confirmation,
                external_responsible=external_responsible,
                is_external=_is_external_backup(legacy_backup_name, external_responsible),
                schedule_hint=_schedule_hint(legacy_backup_name),
                schedule_requires_confirmation=bool(_schedule_hint(legacy_backup_name)),
                quality_flags=_configuration_quality_flags(
                    legacy_method=legacy_method,
                    provider_requires_confirmation=suggestion.requires_confirmation,
                    source_asset_label=source_asset_label,
                ),
            )
        )

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
            quality_flags = derive_observation_reasons(observation)
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
                quality_flags.append("UNKNOWN_STATUS")
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
                quality_flags.append("STATUS_OBSERVATION_CONFLICT")

            daily_records.append(
                LegacyDailyRecordCandidate(
                    legacy_fingerprint=legacy_fingerprint,
                    source_row=source_row,
                    source_date=source_date,
                    raw_responsible=responsible,
                    raw_status=raw_status,
                    raw_ticket=ticket,
                    raw_observation=observation,
                    normalized_status=status,
                    normalization_rule=_normalization_rule(raw_status),
                    quality_flags=quality_flags,
                )
            )

    summary.managed_customers = len(managed_customers)
    summary.unique_ticket_ids = len(unique_ticket_ids)
    return LegacyParsedHistory(summary, configurations, daily_records)


def legacy_configuration_fingerprint(
    *,
    customer: str,
    site: str,
    source_asset: str,
    backup_name: str,
    method: str,
) -> str:
    payload = "|".join(
        _normalize_text(value)
        for value in (customer, site, source_asset, backup_name, method)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalization_rule(raw_status: str) -> str:
    status_key = _clean(raw_status).casefold()
    if status_key in STATUS_MAPPING:
        return f"STATUS_MAPPING:{status_key or 'empty'}"
    return "STATUS_MAPPING:unknown"


def _is_external_backup(backup_name: str, external_responsible: str) -> bool:
    return "externo" in _normalize_text(backup_name) or bool(_clean(external_responsible))


def _schedule_hint(backup_name: str) -> str:
    text = _clean(backup_name)
    normalized = _normalize_text(text)
    hints = [
        "lunes",
        "martes",
        "miercoles",
        "miércoles",
        "jueves",
        "viernes",
        "sabado",
        "sábado",
        "domingo",
        " hs",
        " am",
        " pm",
    ]
    if any(hint in normalized for hint in hints):
        return text
    return ""


def _configuration_quality_flags(
    *,
    legacy_method: str,
    provider_requires_confirmation: bool,
    source_asset_label: str,
) -> list[str]:
    flags: list[str] = []
    if not _clean(legacy_method):
        flags.append("MISSING_LEGACY_METHOD")
    if provider_requires_confirmation:
        flags.append("PROVIDER_REQUIRES_CONFIRMATION")
    if not _clean(source_asset_label):
        flags.append("MISSING_SOURCE_ASSET_LABEL")
    return flags


@dataclass(frozen=True)
class LegacyCommitResult:
    summary: LegacyImportSummary
    batch_created: bool
    managed_customers_created: int
    configurations_created: int
    daily_records_created: int
    issues_created: int
    ticket_references_created: int

    def to_dict(self, *, tenant: str) -> dict[str, Any]:
        return {
            "tenant": tenant,
            "dry_run": False,
            "source_file": self.summary.source_file,
            "source_sha256": self.summary.source_sha256,
            "batch_created": self.batch_created,
            "managed_customers_created": self.managed_customers_created,
            "configurations_created": self.configurations_created,
            "daily_records_created": self.daily_records_created,
            "issues_created": self.issues_created,
            "ticket_references_created": self.ticket_references_created,
            "summary": self.summary.to_dict(tenant=tenant, dry_run=False),
        }

    def to_json(self, *, tenant: str) -> str:
        return json.dumps(
            self.to_dict(tenant=tenant),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )


def commit_legacy_backup_history(
    path: str | Path,
    *,
    organization,
    dry_run_report_path: str | Path,
    encoding: str = "cp1252",
    delimiter: str = ";",
) -> LegacyCommitResult:
    from django.db import transaction

    from apps.customers.models import ManagedCustomer
    from apps.imports.models import (
        ImportBatch,
        LegacyBackupConfiguration,
        LegacyDailyRecord,
        LegacyImportIssue,
        LegacyTicketReference,
    )

    parsed = parse_legacy_backup_history_details(
        path,
        encoding=encoding,
        delimiter=delimiter,
    )
    _validate_dry_run_report(parsed.summary, dry_run_report_path)

    with transaction.atomic():
        batch, batch_created = ImportBatch.objects.get_or_create(
            organization=organization,
            source_sha256=parsed.summary.source_sha256,
            defaults={
                "original_filename": parsed.summary.source_file,
                "status": ImportBatch.Status.IMPORTED,
                "column_mapping": {"legacy_history_import": True},
                "row_count": parsed.summary.configuration_rows,
                "encoding": encoding,
                "delimiter": delimiter,
                "dry_run": False,
                "summary_json": parsed.summary.to_dict(
                    tenant=organization.slug,
                    dry_run=False,
                ),
            },
        )
        if not batch_created:
            batch.status = ImportBatch.Status.IMPORTED
            batch.row_count = parsed.summary.configuration_rows
            batch.encoding = encoding
            batch.delimiter = delimiter
            batch.dry_run = False
            batch.summary_json = parsed.summary.to_dict(
                tenant=organization.slug,
                dry_run=False,
            )
            batch.save(
                update_fields=[
                    "status",
                    "row_count",
                    "encoding",
                    "delimiter",
                    "dry_run",
                    "summary_json",
                    "updated_at",
                ]
            )

        customer_names = sorted(
            {candidate.legacy_customer_name for candidate in parsed.configurations}
        )
        existing_customers = {
            customer.name: customer
            for customer in ManagedCustomer.objects.filter(
                organization=organization,
                name__in=customer_names,
            )
        }
        missing_customers = [
            ManagedCustomer(
                organization=organization,
                name=name,
                notes="Imported from legacy backup history CSV.",
            )
            for name in customer_names
            if name not in existing_customers
        ]
        ManagedCustomer.objects.bulk_create(missing_customers, ignore_conflicts=True)
        customers = {
            customer.name: customer
            for customer in ManagedCustomer.objects.filter(
                organization=organization,
                name__in=customer_names,
            )
        }

        config_before = LegacyBackupConfiguration.objects.filter(
            organization=organization,
            source_sha256=parsed.summary.source_sha256,
        ).count()
        config_objects = [
            LegacyBackupConfiguration(
                organization=organization,
                import_batch=batch,
                managed_customer=customers[candidate.legacy_customer_name],
                source_sha256=parsed.summary.source_sha256,
                source_row=candidate.source_row,
                legacy_fingerprint=candidate.legacy_fingerprint,
                legacy_customer_name=candidate.legacy_customer_name,
                legacy_site_label=candidate.legacy_site_label,
                source_asset_label=candidate.source_asset_label,
                legacy_backup_name=candidate.legacy_backup_name,
                legacy_method=candidate.legacy_method,
                provider=candidate.provider,
                provider_requires_confirmation=candidate.provider_requires_confirmation,
                external_responsible=candidate.external_responsible,
                is_external=candidate.is_external,
                schedule_hint=candidate.schedule_hint,
                schedule_requires_confirmation=candidate.schedule_requires_confirmation,
                quality_flags=candidate.quality_flags,
            )
            for candidate in parsed.configurations
        ]
        LegacyBackupConfiguration.objects.bulk_create(
            config_objects,
            ignore_conflicts=True,
        )
        configurations = {
            config.legacy_fingerprint: config
            for config in LegacyBackupConfiguration.objects.filter(
                organization=organization,
                source_sha256=parsed.summary.source_sha256,
            )
        }
        config_after = len(configurations)

        daily_before = LegacyDailyRecord.objects.filter(
            organization=organization,
            source_sha256=parsed.summary.source_sha256,
        ).count()
        daily_objects = [
            LegacyDailyRecord(
                organization=organization,
                import_batch=batch,
                backup_configuration=configurations[record.legacy_fingerprint],
                source_sha256=parsed.summary.source_sha256,
                source_row=record.source_row,
                source_date=record.source_date,
                raw_responsible=record.raw_responsible,
                raw_status=record.raw_status,
                raw_ticket=record.raw_ticket,
                raw_observation=record.raw_observation,
                normalized_status=record.normalized_status,
                normalization_rule=record.normalization_rule,
                quality_flags=record.quality_flags,
            )
            for record in parsed.daily_records
        ]
        LegacyDailyRecord.objects.bulk_create(daily_objects, ignore_conflicts=True)
        daily_after = LegacyDailyRecord.objects.filter(
            organization=organization,
            source_sha256=parsed.summary.source_sha256,
        ).count()

        issue_before = LegacyImportIssue.objects.filter(
            organization=organization,
            source_sha256=parsed.summary.source_sha256,
        ).count()
        issue_objects = [
            LegacyImportIssue(
                organization=organization,
                import_batch=batch,
                source_sha256=parsed.summary.source_sha256,
                source_row=issue["source_row"],
                source_date=_optional_date(issue.get("source_date")),
                issue_code=issue["issue_code"],
                severity=issue["severity"],
                details=issue.get("details", ""),
            )
            for issue in parsed.summary.issues
        ]
        LegacyImportIssue.objects.bulk_create(issue_objects, ignore_conflicts=True)
        issue_after = LegacyImportIssue.objects.filter(
            organization=organization,
            source_sha256=parsed.summary.source_sha256,
        ).count()

        ticket_ids = sorted({record.raw_ticket for record in parsed.daily_records if record.raw_ticket})
        ticket_before = LegacyTicketReference.objects.filter(
            organization=organization,
            external_system=LegacyTicketReference.ExternalSystem.MANAGEENGINE,
        ).count()
        LegacyTicketReference.objects.bulk_create(
            [
                LegacyTicketReference(
                    organization=organization,
                    external_system=LegacyTicketReference.ExternalSystem.MANAGEENGINE,
                    external_id=ticket_id,
                )
                for ticket_id in ticket_ids
            ],
            ignore_conflicts=True,
        )
        ticket_after = LegacyTicketReference.objects.filter(
            organization=organization,
            external_system=LegacyTicketReference.ExternalSystem.MANAGEENGINE,
        ).count()

    return LegacyCommitResult(
        summary=parsed.summary,
        batch_created=batch_created,
        managed_customers_created=len(missing_customers),
        configurations_created=config_after - config_before,
        daily_records_created=daily_after - daily_before,
        issues_created=issue_after - issue_before,
        ticket_references_created=ticket_after - ticket_before,
    )


def _validate_dry_run_report(
    summary: LegacyImportSummary,
    dry_run_report_path: str | Path,
) -> None:
    report_path = Path(dry_run_report_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LegacyImportError(f"Dry-run report not found: {report_path}") from exc
    if report.get("source_sha256") != summary.source_sha256:
        raise LegacyImportError("Dry-run report does not match the source CSV hash.")
    expected_fields = [
        "configuration_rows",
        "date_groups",
        "legacy_status_cells",
        "observations",
        "ticket_references",
        "unique_ticket_ids",
    ]
    for field_name in expected_fields:
        if report.get(field_name) != getattr(summary, field_name):
            raise LegacyImportError(
                f"Dry-run report field mismatch for {field_name}."
            )


def _optional_date(raw_date: str | None):
    if not raw_date:
        return None
    return datetime.strptime(raw_date, "%Y-%m-%d").date()
