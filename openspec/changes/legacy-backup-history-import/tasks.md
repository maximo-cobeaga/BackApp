# Tasks: legacy backup history import

## Phase 1: contract and fixtures

- [x] Add this change to the master technical prompt and project docs.
- [x] Create a small anonymized representative CSV fixture.
- [x] Cover fixed rows, customer forward-fill, decorative rows, and daily blocks.
- [x] Define dry-run summary fields and issue codes.

## Phase 2: parser and dry-run

- [x] Add CSV reader with encoding and delimiter options.
- [x] Validate fixed headers and row width.
- [x] Detect and ignore trailing empty columns.
- [x] Parse 365 date groups of four columns.
- [x] Classify configuration rows versus decorative rows.
- [x] Forward-fill customer names safely.
- [x] Normalize statuses through the approved table.
- [x] Produce a deterministic dry-run summary without database writes.

## Phase 3: staging models

- [x] Add or extend import batch metadata for source hash and dry-run summary.
- [x] Add legacy configuration records or staging records.
- [x] Add legacy daily record preservation.
- [x] Add import issue records.
- [x] Add ticket reference preservation.
- [x] Add admin and read-only UI review pages for imported historical data.

## Phase 4: commit path

- [x] Commit staging writes in one transaction after dry-run report validation.
- [x] Create or match managed customers and legacy backup configurations.
- [ ] Create imported historical executions for success/warning/error only.
- [x] Link repeated ticket IDs without creating remote tickets.
- [ ] Avoid overwriting existing manual or mail-derived executions.
- [x] Prove repeated imports do not duplicate staging data.

## Phase 5: later reconciliation

- [x] Link one legacy configuration to current operational records with
  operator confirmation.
- [x] Store schedule hints as legacy inferences requiring confirmation.
- [x] Add fast provisional bootstrap for all legacy configurations.
- [ ] Add bulk/assisted reconciliation review for many configurations.
- [x] Add provisional assisted schedule bootstrap for fast operational testing.
- [x] Generate historical-range expected executions after provisional schedules.
- [ ] Compare historical human control against future mail parser results.
