# ADR 0010: Assisted matching suggestions

## Status

Accepted

## Context

Backup Control Center can parse inbound reports and operators can manually create
real backup executions from parsed items.

The manual review form still required the operator to search the full list of
expected executions.

The system has enough conservative signals to suggest candidates without approving
or changing results automatically:

- parsed job hints;
- detected provider;
- backup technology;
- received time and expected report window.

## Decision

Add an assisted matching service that ranks expected executions for a parsed report
item. The service assigns confidence from explicit job matches, technology/provider
matches, and report-window proximity.

The parser review form now marks suggested expected executions in the select label
and preselects a single strong candidate. The operator must still confirm the
association and result before a `BackupExecution` is created.

## Consequences

Manual review becomes faster while preserving human control.

Ambiguous or weak suggestions remain visible but are not automatically confirmed.
Future work can add richer candidate explanations and provider-specific matching
once real anonymized samples are available.
