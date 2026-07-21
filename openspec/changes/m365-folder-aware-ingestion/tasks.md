# Tasks: Mailbox and Excel driven expected backups

## Phase 1: product decision

- [x] Capture mailbox taxonomy from the user.
- [ ] Confirm whether Excel includes schedule and deadline columns.
- [ ] Confirm fallback defaults if schedule fields are missing.
- [ ] Confirm whether source folder metadata should be stored per message.

## Phase 2: documentation and import design

- [ ] Update the M365 runbook with customer/site/type folder examples.
- [ ] Document Graph folder-ID discovery for nested folders.
- [ ] Update import documentation with schedule/deadline columns.
- [ ] Document how Excel rows reconcile with mailbox folder paths.

## Phase 3: implementation hardening

- [ ] Add import fields for schedule/deadline mapping if approved.
- [ ] Create or match `BackupSchedule` records during import confirmation.
- [ ] Add tests for imported schedules and expected execution generation.
- [ ] Add provider tests for custom folder IDs and read-only sync.
- [ ] Improve Graph errors for folder-not-found or permission failures.

## Phase 4: optional next slice

- [ ] Add read-only Graph folder discovery.
- [ ] Traverse child folders for customer/site/type paths.
- [ ] Add UI to map discovered folders to imported entities.
- [ ] Store source folder ID/path on inbound messages.
- [ ] Use folder metadata in matching explanations.
