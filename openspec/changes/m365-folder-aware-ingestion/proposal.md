# Proposal: Mailbox and Excel driven expected backups

## Status

Draft. Updated after user clarified the mailbox folder taxonomy.

## Problem

Backup reports arrive in `backups@dominio...`. The mailbox is organized by
customer folders. Inside some customer folders there are branch/site subfolders;
inside others there are backup-type subfolders.

The system must not treat the mailbox tree alone as the source of truth. The
operator also imports the spreadsheet configuration. The expected backup workload
should come from reconciling both sources:

- mailbox folders show where reports arrive;
- the spreadsheet defines customers, sites, objects, technologies, jobs, and
  ideally schedules/deadlines;
- expected executions are generated from validated backup schedules.

## Proposed change

Use an incremental, safe slice:

1. Keep Microsoft 365 read-only.
2. Model the mailbox folder tree as operational configuration evidence.
3. Extend the spreadsheet import concept so it can establish expected backups,
   including schedules and reporting deadlines.
4. Reconcile folder paths with imported customer/site/technology/job data.
5. Generate expected executions only from confirmed backup schedules.
6. Use folder metadata as matching evidence, never as automatic approval.

## First implementation slice

The first slice should not recursively poll the whole mailbox automatically.
Instead:

1. Document the folder taxonomy and folder-ID discovery flow.
2. Add explicit spreadsheet fields for schedule/deadline mapping.
3. Add a folder-path mapping concept to the import preview.
4. Keep one connector per selected folder for the first pilot validation.
5. Collect anonymized samples from the real mailbox before adding automatic
   folder discovery or parser-specific behavior.

## Outcome

After import confirmation, the system can create or match backup inventory and
schedules. Operators then generate expected executions for a date. M365 messages
arriving in mapped customer/site/type folders become evidence for matching those
expected executions.

## Non-goals

- No automatic approval from folder names.
- No message moving or read-state changes in Microsoft 365.
- No recursive sync of every folder before validating the taxonomy.
- No provider-specific parser expansion without anonymized samples.

## Open questions

See `proposal-questions.md`.
