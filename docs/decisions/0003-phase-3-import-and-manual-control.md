# ADR 0003: Phase 3 spreadsheet import and manual daily control

## Status

Accepted

## Context

Phase 3 must replace part of the spreadsheet workflow without implementing email
ingestion, parser matching, expected executions, rule engines, or tickets.

The current workbook format is not fixed, and merged customer cells are expected.
The domain must not assume that each row is a server or that a reference is
unique.

## Decision

Add an import workflow with `ImportBatch` and `ImportRow` records. The upload form
requires a column mapping by header name. The preview step stores raw and
normalized data before creating domain records.

Confirmation creates or matches customers, sites, protected objects, backup
technologies, backup jobs, and job targets. Incomplete rows are skipped and kept
as evidence in the batch.

Remove the unique constraint on `ProtectedObject.external_reference` because the
same visible reference may appear on several spreadsheet rows.

Add `DailyControlEntry` for manual daily results linked to a backup job and,
optionally, a job target. This is manual control only; expected executions remain
for a later phase.

## Consequences

Operators can preview imports, confirm safe rows, record manual results, and
export the daily-control table to Excel while the spreadsheet remains available
for parallel validation.
