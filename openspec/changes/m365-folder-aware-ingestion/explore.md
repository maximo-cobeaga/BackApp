# Explore: Mailbox and Excel driven expected backups

## Context

Backup Control Center supports read-only Microsoft 365 mailbox ingestion through
Microsoft Graph and OAuth client credentials.

The real operating model clarified by the user is:

- Backup reports arrive at `backups@dominio...`.
- Top-level mailbox folders represent customers.
- Some customer folders contain branch or site subfolders.
- Other customer folders contain backup-type subfolders.
- The expected backup workload should come from mailbox configuration combined
  with the imported Excel configuration.

## Current implementation

Relevant paths:

- `apps/imports/services.py`
  - Creates or matches customers, sites, objects, technologies, jobs, and targets.
  - Does not create `BackupSchedule` records yet.
- `apps/backups/models.py`
  - `BackupSchedule` has the fields required for expected executions.
- `apps/operations/services.py`
  - Generates expected executions from active `BackupSchedule` records.
- `apps/ingestion/models.py`
  - `MailConnector.folder` stores one folder reference.
  - Connectors are enforced as read-only.
- `apps/ingestion/providers/graph.py`
  - Fetches messages from a configured mailbox folder.
  - Requests preview, full body, metadata, sender, and recipients.

## Verification baseline

Commands passed before this change proposal:

```bash
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe -m pytest -q
npx --yes markdownlint-cli2 README.md "docs/**/*.md" BACKUP_CONTROL_CENTER_MASTER_PROMPT.md
```

Result: 62 tests passed; markdownlint found 0 issues.

## Core discovery

The spreadsheet import currently creates backup jobs and targets, but not
schedules. Because expected executions are generated from schedules, the Excel
import must either import schedule columns or apply explicit operator-approved
defaults before it can establish expected backups.

The mailbox folder tree is valuable evidence, but it should not be the source of
truth for backup expectations. It should help route messages and explain matching
suggestions.

## Initial recommendation

First safe slice:

1. Extend the import design to include schedule/deadline mapping.
2. Document the real mailbox folder taxonomy.
3. Keep Microsoft 365 read-only.
4. Use explicit configured folders before recursive discovery.
5. Use folder path as matching evidence, not automatic approval.
