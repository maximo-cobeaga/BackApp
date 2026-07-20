# ADR 0005: Phase 5 read-only mailbox connectors

## Status

Accepted

## Context

Phase 5 starts email ingestion, but must not implement parsers, matching, rule
engines, ticket automation, background workers, or SaaS infrastructure yet.

The pilot uses Microsoft 365 Outlook. The domain should still support future IMAP
and Gmail connectors through the same provider contract.

## Decision

Add tenant-owned `MailConnector`, `InboundMessage`, and `MessageAttachment`
models. Connectors are enforced as read-only and store only non-secret
configuration references.

Implement a provider registry with these provider types:

- `MICROSOFT_GRAPH`
- `IMAP`
- `GMAIL_API`

Only `MICROSOFT_GRAPH` is implemented in this phase. IMAP and Gmail are registered
as explicit future providers that fail closed with `ProviderNotImplemented`.

Microsoft 365 uses Microsoft Graph with OAuth client credentials. The connector
stores environment-variable names:

- `tenant_id_env`
- `client_id_env`
- `client_secret_env`

The actual tenant ID, client ID, and client secret remain outside the database and
repository.

Fetched messages are stored idempotently by organization, connector, and provider
message ID. Attachment metadata stores filename, content type, size, SHA-256, and
storage path metadata only; attachments are never executed.

## Consequences

The pilot can synchronize an Outlook/Microsoft 365 mailbox through a read-only
contract and persist traceable message metadata without committing to parser or
matching behavior yet.

Future phases can add IMAP and Gmail providers behind the same interface and can
attach parser output to `InboundMessage` records.
