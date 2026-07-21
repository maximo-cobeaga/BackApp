# Tasks: legacy backup history import

## Phase 1: contract and fixtures

- [ ] Add this change to the master technical prompt and project docs.
- [ ] Create a small anonymized representative CSV fixture.
- [ ] Cover fixed rows, customer forward-fill, decorative rows, and daily blocks.
- [ ] Define dry-run summary fields and issue codes.

## Phase 2: parser and dry-run

- [ ] Add CSV reader with encoding and delimiter options.
- [ ] Validate fixed headers and row width.
- [ ] Detect and ignore trailing empty columns.
- [ ] Parse 365 date groups of four columns.
- [ ] Classify configuration rows versus decorative rows.
- [ ] Forward-fill customer names safely.
- [ ] Normalize statuses through the approved table.
- [ ] Produce a deterministic dry-run summary without database writes.

## Phase 3: staging models

- [ ] Add or extend import batch metadata for source hash and dry-run summary.
- [ ] Add legacy configuration records or staging records.
- [ ] Add legacy daily record preservation.
- [ ] Add import issue records.
- [ ] Add ticket reference preservation.

## Phase 4: commit path

- [ ] Commit domain writes in one transaction.
- [ ] Create or match managed customers and backup configurations.
- [ ] Create imported historical executions for success/warning/error only.
- [ ] Link repeated ticket IDs without creating remote tickets.
- [ ] Avoid overwriting existing manual or mail-derived executions.
- [ ] Prove repeated imports do not duplicate data.

## Phase 5: later reconciliation

- [ ] Link legacy configurations to current backup jobs.
- [ ] Store schedule hints as legacy inferences requiring confirmation.
- [ ] Generate expected executions only after schedule confirmation.
- [ ] Compare historical human control against future mail parser results.
