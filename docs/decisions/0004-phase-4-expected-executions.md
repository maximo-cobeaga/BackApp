# ADR 0004: Phase 4 expected executions and initial dashboard

## Status

Accepted

## Context

Phase 4 must show what should run on a selected day and detect missing reports
without implementing mailbox ingestion, parsers, matching, rules, tickets, or
background workers.

`BackupSchedule` already stores frequency, weekdays, scheduled time, timezone,
report deadline time, and deadline offset.

## Decision

Add `ExpectedExecution` as a tenant-owned operation model generated from active
`BackupSchedule` records. Generation is idempotent by organization, schedule, and
service date.

Store both `scheduled_start_at` and `report_deadline_at` as timezone-aware UTC
instants derived from the schedule timezone. A service marks overdue
`WAITING_REPORT` executions as `NO_REPORT` after the configured deadline.

Keep `DailyControlEntry` separate from `ExpectedExecution`. Manual entries may
link to an expected execution, but expected executions do not depend on manual
control to exist.

Add an initial dashboard that counts expected executions, waiting reports,
missing reports, and manual result totals for the selected date.

## Consequences

The pilot can start the day from a generated workload and identify missing
reports before email ingestion exists. Future phases can attach parsed reports to
these expected executions without changing the scheduling boundary.
