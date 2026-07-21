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
  --tenant organizacion-piloto \
  --encoding cp1252 \
  --delimiter ";" \
  --dry-run \
  --output runtime/reports/legacy-dry-run.json
```

Commit after review:

```bash
python manage.py import_backup_history \
  "Gestion de Backups 2026(Control Backups).csv" \
  --tenant organizacion-piloto \
  --encoding cp1252 \
  --delimiter ";" \
  --dry-run-report runtime/reports/legacy-dry-run.json \
  --commit \
  --output runtime/reports/legacy-commit.json
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

## Review imported data

After commit, open the local app and go to:

```text
Importaciones -> Ver histórico importado
```

Review pages:

- summary and status counts;
- legacy configurations;
- legacy daily records;
- import issues.

The UI can also reconcile one legacy configuration at a time into current
operational records: site, protected object, technology, backup job, and target.
This action requires operator-confirmed form values.

It still does not create schedules, expected executions, tickets, or mailbox
matches.

## Fast operational bootstrap

Manual reconciliation of every legacy row can take too long. To start testing the
app quickly, create provisional operational records from every imported legacy
configuration:

```bash
python manage.py bootstrap_legacy_backups \
  --tenant organizacion-piloto \
  --source runtime/reports/legacy-commit.json \
  --output runtime/reports/legacy-bootstrap.json
```

This creates or reuses:

- sites;
- protected objects;
- backup technologies;
- backup jobs;
- backup job targets.

Every bootstrapped record remains provisional and review-required through the
legacy reconciliation links. The command is idempotent and does not create
schedules, expected executions, tickets, or mailbox matches.

## Fast provisional schedule bootstrap

After backup jobs exist, create provisional assisted schedules so the operations
team can generate expected executions and start testing daily control:

```bash
python manage.py bootstrap_legacy_schedules \
  --tenant organizacion-piloto \
  --frequency DAILY \
  --weekdays "1,2,3,4,5,6,7" \
  --scheduled-time "23:00" \
  --deadline-time "08:00" \
  --deadline-offset-days 1 \
  --mode ASSISTED \
  --output runtime/reports/legacy-schedules-bootstrap.json
```

The command is idempotent. It skips jobs that already have any schedule unless
`--update-existing` is supplied. Use `--update-existing` when the provisional
policy changes, for example when weekend expectations must be included.

To generate expected executions for the full historical recorded range from the
commit report:

```bash
python manage.py generate_legacy_expected_executions \
  --tenant organizacion-piloto \
  --source runtime/reports/legacy-commit.json \
  --output runtime/reports/legacy-expected-executions.json
```

This follows the configured schedules. With the provisional all-day schedule, it
creates expected executions for every day in the recorded range, including
Saturdays and Sundays. It does not create real backup executions or tickets.

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
