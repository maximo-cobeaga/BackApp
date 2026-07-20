# ADR 0006: Phase 6 parser registry and manual review queue

## Status

Accepted

## Context

Inbound messages can now be synchronized from a read-only Microsoft 365 mailbox.
The project still lacks anonymized real backup report samples, so provider-
specific parsers must not be invented.

The system needs a safe bridge between stored messages and future parser-specific
work.

## Decision

Add `ParsedReportItem` as normalized parser output linked to `InboundMessage`.
Parser status and review status are separate dimensions.

Add a parser registry with a `GenericUnknownParser`. The generic parser creates
one `UNKNOWN` item with confidence `0.0` and requires manual review. It never
marks a backup as successful.

Parsing is operator-triggered and idempotent by organization, message, parser
name, parser version, and item index.

Add a tenant-scoped manual review queue. Operators can mark unknown parsed items
as reviewed, but this does not change the technical parser status.

## Consequences

The pilot can safely surface synchronized messages for human review before real
provider parsers exist.

Future parsers for Veeam, Iperius, Azure Backup, or other technologies require
anonymized samples and can be added behind the same registry contract.
