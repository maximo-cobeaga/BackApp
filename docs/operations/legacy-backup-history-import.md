# Import legacy backup history CSV

Use this runbook to import the historical backup control CSV safely.

## Quick path

1. Run a dry-run with explicit encoding and delimiter.
2. Review the summary, provider suggestions, tickets, and import issues.
3. Commit only after the operator accepts the dry-run evidence.

## Source file

```text
Gestion de Backups 2026(Control Backups).csv
```

Expected pilot options:

| Option | Value |
| --- | --- |
| Encoding | `cp1252` |
| Delimiter | `;` |
| Fixed columns | 8 |
| Daily block size | 4 columns |
| Date groups | 365 |

## Commands

Dry-run:

```bash
python manage.py import_backup_history \
  "Gestion de Backups 2026(Control Backups).csv" \
  --tenant pilot \
  --encoding cp1252 \
  --delimiter ";" \
  --dry-run
```

Commit after review:

```bash
python manage.py import_backup_history \
  "Gestion de Backups 2026(Control Backups).csv" \
  --tenant pilot \
  --encoding cp1252 \
  --delimiter ";" \
  --commit
```

## Status mapping

| Raw value | Normalized status |
| --- | --- |
| `Correcto` | `SUCCESS` |
| `Correctos` | `SUCCESS` |
| `Warning` | `WARNING` |
| `Warnings` | `WARNING` |
| `Error` | `ERROR` |
| `N/A` | `NOT_APPLICABLE` |
| `NA` | `NOT_APPLICABLE` |
| `.` | `PLACEHOLDER` |
| `,` | `UNKNOWN` |
| `N` | `UNKNOWN` |
| empty | `UNRECORDED` |

## Safety rules

- Preserve raw values before normalization.
- Do not import decorative rows as backups.
- Do not create users from `.` or `..` responsible values.
- Do not convert blanks into `NO_REPORT`.
- Do not count `N/A` as success or failure.
- Do not infer lost Excel colors from the CSV.
- Do not create remote tickets.
- Do not send emails or notifications.
- Do not create confirmed schedules from ambiguous text.

## Review checklist

Before commit, review:

- detected customers;
- configuration rows;
- decorative rows;
- provider suggestions requiring confirmation;
- external backup hints;
- ticket references;
- status/observation conflicts;
- unknown statuses;
- possible duplicates with existing executions;
- schedule hints that require confirmation.

## Expected dry-run summary

The dry-run should report at least:

```json
{
  "source_file": "Gestion de Backups 2026(Control Backups).csv",
  "encoding": "cp1252",
  "delimiter": ";",
  "rows": 547,
  "columns": 1520,
  "managed_customers": 41,
  "configuration_rows": 498,
  "separator_rows": 41,
  "date_groups": 365,
  "first_recorded_date": "2026-01-05",
  "last_recorded_date": "2026-07-21",
  "legacy_status_cells": 64755,
  "observations": 3271,
  "ticket_references": 239,
  "unique_ticket_ids": 65,
  "issues": []
}
```

The values above are the baseline for the received file, not constants for every
future file.
