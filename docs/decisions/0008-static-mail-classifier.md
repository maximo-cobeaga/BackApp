# ADR 0008: Static mail classifier for backup identification

## Status

Accepted

## Context

The project now stores inbound messages and can create real backup executions from
manual review. Operators still need the system to identify likely backup provider,
status, evidence, and job hints before provider-specific parsers are validated with
real anonymized samples.

`PROMPT_AGENTE_CLASIFICACION_BACKUPS.md` defines a conservative classifier contract
covering Veeam, Iperius, Azure Backup, NAKIVO, QNAP HBS 3, AWS DLM, scripts, and
CubeBackup.

## Decision

Implement a deterministic `StaticMailRulesParser` from the prompt rules.
Make it the default parser registry entry.

The parser inspects the message subject, sender, body preview, and available Graph
body content. It detects provider signals, explicit status fields or phrases,
non-zero warning/error counters, script-contract contradictions, Azure resolved
alerts, untrusted instructions inside emails, and configured backup-job hints.

The parser stores provider, confidence, rule IDs, evidence, dashboard status,
review reasons, security flags, counters, and configuration-match state in the
parsed item's `metrics` field.

It remains conservative: unknown templates and low-confidence matches still require
manual review. The classifier does not create tickets, does not execute content,
and does not invent backup configurations.

## Consequences

The pilot can now identify many common backup reports before real provider parsers
exist.

Provider-specific parsers can later replace or extend these static rules once
anonymized sample coverage proves they meet the zero-false-success requirement.
