# ADR 0011: Legacy backup history CSV import

## Status

Proposed

## Context

The historical file `Gestion de Backups 2026(Control Backups).csv` is not a
normal table. It is a wide daily-control matrix with eight fixed configuration
columns and 365 four-column daily groups.

The file must seed the historical evidence base for Backup Control Center while
preserving auditability and avoiding unsafe inference.

## Decision

Add a dedicated legacy importer instead of adapting the generic workbook preview.

The importer will run in two stages:

1. dry-run parsing, validation, summary, and issue detection;
2. explicit commit after operator review.

The importer preserves raw values before normalization. It creates imported
historical executions only for `SUCCESS`, `WARNING`, and `ERROR`. It keeps
`NOT_APPLICABLE`, placeholders, unknown values, and unrecorded blanks as legacy
evidence rather than operational backup results.

The importer does not create tickets, send messages, infer lost Excel colors, or
turn blank cells into `NO_REPORT`.

## Consequences

The system can preserve the historical control record and compare it against the
new mailbox-driven flow.

Future expected executions still require confirmed schedules. The CSV can provide
configuration rows and schedule hints, but those hints require operator
confirmation before they drive future workload generation.
