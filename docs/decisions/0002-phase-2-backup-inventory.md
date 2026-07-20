# ADR 0002: Phase 2 backup inventory configuration

## Status

Accepted

## Context

Phase 2 adds backup configuration without implementing report ingestion,
execution tracking, ticketing, background workers, or SaaS infrastructure.

The domain must support multiple backup jobs per protected object and multiple
protected objects per backup job.

## Decision

Add tenant-owned backup inventory models:

- `BackupTechnology`
- `BackupJob`
- `BackupJobTarget`
- `BackupSchedule`
- `BackupDestination`
- `RetentionPolicy`
- `BackupConfigurationChange`

Use `BackupJobTarget` as an explicit through model instead of a plain many-to-many
field so each target can store role, inclusions, exclusions, notes, and status.

Every phase 2 model carries `organization_id`. Child configuration records derive
their organization from their parent backup job during validation and save.

## Consequences

The pilot can represent one job protecting many objects and one object protected
by many jobs without relying on hostname as a unique identifier.

Future phases can generate expected executions from `BackupSchedule`, but this
phase does not create operational execution records yet.
