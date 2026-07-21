# Spec: Mailbox and Excel driven expected backups

## Status

Draft pending remaining product answers.

## Requirements

### REQ-M365-FOLDER-001: Read-only folder-scoped sync

The system SHALL synchronize Microsoft 365 messages from configured mailbox
folders without moving messages, deleting messages, executing attachments, or
changing mailbox state.

### REQ-M365-FOLDER-002: Secret handling

The system SHALL continue storing only environment-variable names in connector
configuration. Tenant ID, client ID, and client secret values SHALL remain outside
the database and repository.

### REQ-M365-FOLDER-003: Folder taxonomy

The system SHALL support a mailbox taxonomy where top-level folders represent
customers and child folders may represent sites, branches, backup types, or other
operator-defined categories.

### REQ-IMPORT-SCHEDULE-001: Schedule import

The system SHALL support importing or confirming schedule data required to create
`BackupSchedule` records for expected backup generation.

### REQ-IMPORT-SCHEDULE-002: Expected execution source

The system SHALL generate `ExpectedExecution` records only from active confirmed
`BackupSchedule` records, not directly from mailbox folders.

### REQ-RECONCILE-001: Folder and Excel reconciliation

The system SHALL reconcile mailbox folder paths with imported Excel rows to help
identify the customer, site, technology, and job related to inbound reports.

### REQ-RECONCILE-002: Human-controlled matching

Folder metadata MAY be used as evidence for suggestions, but SHALL NOT
automatically approve backup results or create real backup executions without
operator confirmation.

### REQ-AUDIT-001: Evidence traceability

When folder metadata is available, the system SHOULD retain enough folder ID/path
information to explain parser and matching suggestions to an operator.
