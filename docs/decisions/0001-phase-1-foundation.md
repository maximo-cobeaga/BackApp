# ADR 0001: Phase 1 foundation and tenant boundary

## Status

Accepted

## Context

The pilot starts as a local internal Django monolith with SQLite, but the domain
must include an organization boundary from day one.

## Decision

Use Django's built-in `User` model, add `Organization` and `Membership`, and make
phase-1 business data organization-owned. Resolve the active organization from
the authenticated user's membership and never accept `organization_id` from
browser forms.

For phase 1, implement the `ADMIN` behavior required to create customers, sites,
protected objects, and object relations. Keep `OPERATOR` and `VIEWER` as role
choices without a complete permission matrix.

## Consequences

The pilot remains simple while tests can prove that data from another
organization is not exposed through forms, services, or list views.
