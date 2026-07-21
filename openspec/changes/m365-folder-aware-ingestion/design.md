# Design: Mailbox and Excel driven expected backups

## Status

Draft pending remaining product answers.

## Current design

The current Excel import creates or matches customers, sites, protected objects,
technologies, backup jobs, and job targets. It does not create schedules.

Expected executions currently come from `BackupSchedule` records. Therefore,
Excel cannot fully establish expected backups until schedule fields are imported
or confirmed.

The current Microsoft 365 connector syncs one configured mailbox folder and is
read-only.

## Target model

Use two complementary inputs:

1. Excel import: source of truth for backup configuration.
2. Mailbox folder tree: operational routing and matching evidence.

The safe domain flow is:

```text
Excel rows -> inventory/jobs/schedules -> expected executions
Mailbox folders -> inbound messages -> parser items -> suggested matches
Operator confirmation -> real backup executions
```

## Folder taxonomy

The folder tree should be interpreted as a path, not as a fixed schema.

Examples:

```text
Cliente A/Veeam
Cliente B/MDP
Cliente C/MDP/Azure
```

The path can contribute signals:

- customer candidate;
- site or branch candidate;
- technology or backup type candidate;
- evidence for manual matching explanations.

## First slice design

Keep one connector per selected folder for the first pilot. Add documentation and
import planning before implementing recursive discovery.

Extend import planning to include schedule fields:

- frequency;
- weekdays;
- scheduled time;
- timezone;
- report deadline time;
- report deadline offset days;
- optional mailbox folder path or folder ID.

## Future folder discovery

After validating the real mailbox taxonomy, add a read-only folder discovery
service:

1. List top-level folders for `backups@dominio...`.
2. Traverse child folders.
3. Store stable Graph folder IDs and display paths.
4. Let operators map folder paths to customers, sites, or technologies.

## Non-goals

- No automatic message moving.
- No read/unread flag mutation.
- No automatic approval.
- No binary attachment execution.
- No inferred schedules without explicit defaults or imported data.
