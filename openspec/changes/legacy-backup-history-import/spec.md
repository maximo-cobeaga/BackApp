# Spec: legacy backup history import

## Requirements

### REQ-LEGACY-CSV-001: Configurable CSV reader

The importer SHALL read the historical file with explicit encoding and delimiter
parameters. The default pilot values are `cp1252` and semicolon.

### REQ-LEGACY-CSV-002: Structural validation

The importer SHALL validate row width, fixed headers, date groups, increasing
unique dates, and four-column daily blocks before commit.

### REQ-LEGACY-CSV-003: Decorative row handling

The importer SHALL ignore decorative rows that do not contain backup definition
fields, even when their daily cells contain placeholders.

### REQ-LEGACY-CSV-004: Customer propagation

The importer SHALL forward-fill the last valid customer name. It SHALL NOT use
`.` as a customer name.

### REQ-LEGACY-CSV-005: Raw value preservation

The importer SHALL preserve every imported raw value needed to audit the source
row, source date, status, ticket, responsible person, and observation.

### REQ-LEGACY-STATUS-001: Explicit status normalization

The importer SHALL normalize historical status values only through the approved
mapping table.

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

### REQ-LEGACY-STATUS-002: No false missing reports

The importer SHALL NOT convert empty historical cells into `NO_REPORT`.

### REQ-LEGACY-STATUS-003: KPI exclusion

`NOT_APPLICABLE`, `PLACEHOLDER`, and `UNRECORDED` records SHALL be excluded from
success/error backup KPIs.

### REQ-LEGACY-EXEC-001: Imported execution creation

The importer SHALL create imported historical backup executions only when the
normalized status is `SUCCESS`, `WARNING`, or `ERROR`.

### REQ-LEGACY-TICKET-001: Ticket reference preservation

The importer SHALL store ticket IDs as text and allow the same external ticket
ID to relate to many historical executions.

### REQ-LEGACY-ISSUE-001: Import issues

The importer SHALL record quality issues for unknown statuses, missing customer,
status/observation conflict, possible duplicates, and review-required inference.

### REQ-LEGACY-IDEMPOTENCY-001: Idempotency

The importer SHALL avoid duplicates across repeated imports using source hash,
source row, source date, and legacy configuration fingerprint keys.

### REQ-LEGACY-DRYRUN-001: Dry-run safety

Dry-run SHALL produce the summary and issue report without modifying the database.

### REQ-LEGACY-SCHEDULE-001: Schedule boundary

The importer SHALL NOT create confirmed future schedules unless explicit schedule
fields or approved defaults are provided by the operator.
