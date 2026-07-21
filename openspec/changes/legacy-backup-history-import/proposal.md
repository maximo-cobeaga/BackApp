# Proposal: legacy backup history import

## Problem

The historical backup control file is a semicolon-delimited CSV exported from a
wide Excel matrix. The existing importer expects a simpler row-based workbook and
cannot preserve the historical daily control evidence.

The system needs a dedicated import path that can stage, summarize, validate, and
commit the historical file without data loss or unsafe inference.

## Proposed change

Add a dedicated legacy history importer for
`Gestion de Backups 2026(Control Backups).csv`.

The importer will:

1. Read the CSV using configurable encoding and delimiter.
2. Validate fixed columns, date rows, daily four-column groups, and row widths.
3. Forward-fill customer names without propagating separator values.
4. Detect configuration rows and decorative rows.
5. Preserve raw configuration values and daily values.
6. Normalize statuses through an explicit mapping table.
7. Create staging/audit records for daily non-empty cells.
8. Create imported historical executions only for success, warning, and error.
9. Preserve tickets as external references without creating new tickets remotely.
10. Produce a reproducible dry-run summary before any commit.

## Source of truth boundary

The historical CSV can establish backup configurations and past control evidence.
It cannot, by itself, confirm exact future schedules, because it lacks structured
execution time, weekdays, report deadline, and timezone fields.

Schedule hints may be extracted, but they must be marked as legacy inference and
require confirmation before generating future expected executions.

## First implementation slice

Build the importer in staging mode first:

- parser and structural validator;
- dry-run summary;
- status normalization;
- configuration fingerprinting;
- issue detection;
- tests against a small representative fixture.

Commit-time domain writes should come after the dry-run contract is stable.

## Non-goals

- No automatic ticket creation.
- No emails or notifications during import.
- No inference from lost Excel colors.
- No conversion of blanks into `NO_REPORT`.
- No automatic schedule creation from ambiguous text.
- No merge by fuzzy similarity without operator confirmation.
