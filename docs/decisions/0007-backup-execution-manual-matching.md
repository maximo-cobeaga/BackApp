# ADR 0007: Backup execution and manual matching

## Status

Accepted

## Context

The system can generate expected executions and parse inbound messages into
normalized report items. It still needs a domain record for what actually happened
with a backup run.

Provider-specific parsers and automatic matching are not safe to invent without
anonymized samples, so the next step must keep the operator in control.

## Decision

Add `BackupExecution` as the tenant-owned operational result for a backup run.
It links a backup job, an optional expected execution, and optional parsed report
item evidence.

Manual review can now associate a parsed report item with an expected execution,
select the real result, and create a `BackupExecution` with
`MANUAL_MATCHED` status. The parsed item remains technically unchanged, but its
review status becomes reviewed after the operator decision.

A parsed report item can create at most one backup execution. Cross-organization
matching is rejected by form scoping and service validation.

## Consequences

The pilot now has a bridge between expected workload, mailbox evidence, parser
output, and the real operational result.

Future automatic matching can create the same model with `AUTO_MATCHED`, while
uncertain cases can continue through manual review.

Rules, consecutive-error detection, ticket suggestions, and ManageEngine linking
remain deferred until real execution history exists.
