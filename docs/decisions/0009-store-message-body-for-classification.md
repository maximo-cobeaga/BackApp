# ADR 0009: Store message body text for classification

## Status

Accepted

## Context

The static mail classifier can identify backup provider, status, evidence, and job
hints, but it needs more than the Microsoft Graph `bodyPreview` to work reliably.
Real backup evidence usually appears in the full text body, HTML body, or extracted
attachment text.

The ingestion boundary must remain read-only and must not execute attachments or
remote content.

## Decision

Extend inbound message storage with full body fields:

- `text_body`
- `html_body`
- `html_as_text`

Extend attachment metadata with `extracted_text` for already-extracted safe text.
The system still stores attachment metadata only; it does not execute attachments.

For Microsoft Graph messages, request the `body` field.
Convert HTML content to plain text using a local parser and keep the original
Graph payload for traceability.

The static mail classifier now reads subject, sender, preview, text body, HTML text,
extracted attachment text, and Graph body text when available.

## Consequences

Classification can use complete report evidence instead of relying on short
previews.

Future work can add safe attachment text extraction per MIME type, but binary
attachment execution remains out of scope.
