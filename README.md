# Backup Control Center

Backup Control Center is a local Django pilot for controlling backup operations.
It tracks tenants, customers, protected objects, backup configuration, expected
executions, mailbox ingestion, parsed report review, and manual daily control.

The current implementation is intentionally local and operator-driven. It does
not run backup jobs, auto-approve backup results, create tickets, or process
provider-specific backup reports without anonymized samples.

## Current capabilities

- Tenant boundary with `Organization` and `Membership`.
- Managed customers, sites, protected objects, and object relations.
- Backup technologies, jobs, targets, schedules, destinations, and retention.
- Spreadsheet import preview and confirmation.
- Manual daily-control entries and Excel export.
- Expected execution generation from active schedules.
- Read-only mailbox connector foundation.
- Microsoft 365 Outlook connector through Microsoft Graph.
- Full message body storage for safer report classification.
- Parser registry with conservative static mail classification rules.
- Provider/status/rule/evidence extraction for common backup report emails.
- Manual review queue for unknown or low-confidence parsed report items.
- Manual matching from parsed report items to real backup executions.
- Assisted matching suggestions in manual review.

## Not implemented yet

- Provider-specific backup parsers validated with anonymized real samples.
- Fully automatic matching parsed reports to backup jobs.
- Rule engine for consecutive errors.
- ManageEngine ticket creation.
- Automatic attachment text extraction for binary reports.
- Background workers or scheduled polling.
- PostgreSQL, Redis, SaaS infrastructure, or billing.

## Local setup

From the repository root:

```bash
py -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py create_pilot_organization
.venv/Scripts/python manage.py createsuperuser
```

Attach the superuser to the pilot organization:

```bash
.venv/Scripts/python manage.py create_pilot_organization --admin-username <username>
```

Run the local server:

```bash
.venv/Scripts/python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Verification commands

Run these before considering a change complete:

```bash
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py makemigrations --check --dry-run
.venv/Scripts/python -m pytest -q
npx --yes markdownlint-cli2 README.md docs/**/*.md BACKUP_CONTROL_CENTER_MASTER_PROMPT.md
```

## Microsoft 365 Outlook connector

The Microsoft 365 connector uses Microsoft Graph with OAuth client credentials.
The database stores only environment-variable names, not secret values.

Set these variables in the local environment before syncing:

```text
M365_TENANT_ID=<tenant-id>
M365_CLIENT_ID=<application-client-id>
M365_CLIENT_SECRET=<client-secret>
```

The connector form should reference those names:

```text
tenant_id_env=M365_TENANT_ID
client_id_env=M365_CLIENT_ID
client_secret_env=M365_CLIENT_SECRET
```

The Azure app registration needs application permissions appropriate for reading
mail through Microsoft Graph, for example `Mail.Read`, with admin consent. Keep
the mailbox access as narrow as your tenant policy allows.

## Manual test path

1. Sign in as an admin user.
2. Create a managed customer.
3. Create a site.
4. Register protected objects.
5. Create a backup technology.
6. Create a backup job and attach one or more protected objects.
7. Add a schedule with weekdays, time, timezone, and report deadline.
8. Generate expected executions for a date.
9. Confirm the dashboard shows expected/waiting counts.
10. Create a Microsoft 365 mail connector.
11. Trigger mailbox sync.
12. Open inbound messages.
13. Run parser processing.
14. Confirm parsed items include provider, rule IDs, evidence, and review reasons.
15. Associate an item with an expected execution and select the real result.
16. Confirm the item appears as a real backup execution.

Until real anonymized backup report samples are available, static classifications
are proposals for operator confirmation, not automatic approval.

## Spreadsheet import test path

Use an `.xlsx` file with headers similar to:

```text
Cliente | Sede | Referencia | Objeto | Tecnología | Tarea
```

The importer maps columns by header name, not by fixed position. Blank customer
cells are forward-filled to support spreadsheets exported from merged cells.

## Runtime data

Local runtime files live under `runtime/` and are ignored by Git. Do not store
secrets, real mailbox exports, or sensitive evidence in the repository.
