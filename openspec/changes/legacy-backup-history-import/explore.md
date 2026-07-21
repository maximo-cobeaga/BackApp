# Explore: legacy backup history import

## Context

The historical file is `Gestion de Backups 2026(Control Backups).csv`.

The user supplied a detailed import contract. The file is not a normalized table.
It is a matrix:

```text
one row = one backup configuration
one four-column block = one day of the year
```

The import must be deterministic, auditable, idempotent, and reversible.

## Confirmed file shape

Baseline values from the received file:

| Property | Value |
| --- | ---: |
| Encoding | Windows-1252 compatible |
| Delimiter | Semicolon |
| Records | 547 |
| Columns per record | 1520 |
| Configuration rows | 498 |
| Decorative rows | 41 |
| Managed customers | 41 |
| Date groups | 365 |
| First matrix date | 2026-01-01 |
| Last matrix date | 2026-12-31 |
| First date with states | 2026-01-05 |
| Last date with states | 2026-07-21 |
| Legacy status cells | 64,755 |
| Observations | 3,271 |
| Ticket references | 239 |
| Unique ticket IDs | 65 |

The final 52 empty columns are formatting residue and must be ignored.

## Current implementation gap

The current generic spreadsheet import creates or matches:

- managed customers;
- sites;
- protected objects;
- backup technologies;
- backup jobs;
- job targets.

It does not parse a daily matrix, preserve historical daily records, import
legacy ticket references, or create imported historical backup executions.

It also does not create schedules. Therefore the historical CSV can establish
backup configurations and historical evidence, but not confirmed future expected
executions without explicit schedule data or operator-approved defaults.

## Key domain rule

The historical CSV is evidence, not a perfectly normalized source of truth.

The importer must:

- preserve raw values first;
- normalize after preservation;
- infer only as a proposal;
- require confirmation when ambiguous;
- never invent information lost in the CSV export.

## Related work

This change complements `m365-folder-aware-ingestion`:

- the CSV establishes historical configuration and control evidence;
- the M365 mailbox tree provides report routing evidence;
- future expected executions still require confirmed schedules.
