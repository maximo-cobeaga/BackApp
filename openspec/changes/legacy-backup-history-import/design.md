# Design: legacy backup history import

## Architecture

Add a dedicated import path instead of overloading the generic spreadsheet
preview importer.

Recommended components:

```text
CSV reader -> structural validator -> row classifier -> daily matrix parser
-> normalizer -> dry-run summary -> commit transaction
```

## Data model additions

Recommended new models:

- `LegacyBackupConfiguration`
- `LegacyDailyRecord`
- `LegacyImportIssue`
- `ExternalTicketReference`
- `BackupExecutionTicket`

`ImportBatch` can be extended or wrapped for source hash, dry-run summary,
encoding, delimiter, and reproducible statistics.

## Backup configuration fingerprint

The initial legacy fingerprint should be derived from normalized values of:

- customer;
- site label;
- server/source asset label;
- backup type/name;
- method.

The fingerprint is a migration key, not the final product identity.

## Daily matrix parsing

The first eight columns describe the configuration. Each day starts at:

```text
base_column = 8 + day_index * 4
```

The daily fields are:

1. verification responsible;
2. status;
3. ticket;
4. observation.

The date comes from row 6 at `base_column`.

## Status handling

Raw status is always preserved. Normalization is explicit and deterministic.

Only `SUCCESS`, `WARNING`, and `ERROR` create imported historical backup
executions. Other statuses remain as legacy daily records and may contribute to
issues or audit reports.

## Observation tags

Observation text is preserved unchanged. Derived tags may be added for review,
including:

- `STALE_NO_CHANGES`;
- `REPORT_OR_LOG_MISSING`;
- `PREVIOUS_EXECUTION_SUCCESS`;
- `REPEATED_ERROR`;
- `CUSTOMER_OR_THIRD_PARTY_MANAGED`;
- `STATUS_OBSERVATION_CONFLICT`.

Derived tags never replace the original observation.

## Schedule boundary

The CSV does not contain enough structured data to create confirmed operational
schedules. Any schedule hints from backup names or observations should be stored
as `LEGACY_INFERENCE` and marked `requires_confirmation`.

Future expected executions should be generated only after schedule confirmation.

## Command shape

```bash
python manage.py import_backup_history \
  "Gestion de Backups 2026(Control Backups).csv" \
  --tenant pilot \
  --encoding cp1252 \
  --delimiter ";" \
  --dry-run
```

Then, after review:

```bash
python manage.py import_backup_history \
  "Gestion de Backups 2026(Control Backups).csv" \
  --tenant pilot \
  --encoding cp1252 \
  --delimiter ";" \
  --commit
```
