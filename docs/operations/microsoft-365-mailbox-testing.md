# Test Microsoft 365 mailbox ingestion

Use this runbook to test the Outlook/Microsoft 365 connector in the local pilot.

## Preconditions

- Local Django app is migrated and running.
- Admin user has an active membership in the pilot organization.
- Microsoft Entra app registration exists.
- The app registration has Microsoft Graph mail-read permission with admin
  consent.
- The mailbox used for backup reports is known.

## Environment variables

Set secret values outside the repository:

```text
M365_TENANT_ID=<tenant-id>
M365_CLIENT_ID=<application-client-id>
M365_CLIENT_SECRET=<client-secret>
```

The database must store only these variable names, not their values.

## Connector setup

1. Sign in to the local app.
2. Open **Correos**.
3. Create a connector.
4. Select **Microsoft 365 Outlook**.
5. Use **OAuth client credentials**.
6. Set the mailbox address, for example `backups@example.com`.
7. Set folder to `Inbox` unless the reports arrive elsewhere.
8. Keep the environment references as:

   ```text
   M365_TENANT_ID
   M365_CLIENT_ID
   M365_CLIENT_SECRET
   ```

9. Save the connector.

## Manual sync test

1. Open **Correos**.
2. Click **Sincronizar** on the connector.
3. Open **Ver mensajes**.
4. Confirm new messages appear once.
5. Sync again.
6. Confirm existing messages are skipped, not duplicated.

## Parser review test

1. Open **Revisión**.
2. Click **Procesar mensajes sin parser**.
3. Confirm parsed items show provider, status, rule IDs, and evidence when a
   static rule matches.
4. Confirm unknown or low-confidence formats remain in manual review.
5. Open one item.
6. Associate it with an expected execution or mark it reviewed.
7. Confirm the technical parser status is not changed by the manual decision.

## Expected behavior

- The connector is read-only.
- Secrets are not saved in the database.
- Messages are idempotent by connector and provider message ID.
- Full text or HTML body content is available for classification.
- Attachments are not executed.
- Static classifications include evidence and rule IDs.
- Unknown or low-confidence formats go to manual review.
- A manual decision does not rewrite the technical parser status.

## Troubleshooting

- **Sync says environment variable is missing**: confirm the process running
  Django can read the `M365_*` variables.
- **Graph authentication fails**: confirm tenant ID, client ID, client secret,
  permissions, and admin consent.
- **No messages appear**: confirm mailbox address, folder name, and Graph app
  access policy.
- **Duplicate messages appear**: verify Microsoft Graph message IDs are stable for
  the selected mailbox/folder.
- **Parser shows unknown**: the format did not match a conservative static rule.
  It may need provider-specific validation from anonymized samples.

## Collecting parser samples later

When mailbox access is available, collect anonymized samples for each provider and
result type:

- Success.
- Warning.
- Failure.
- HTML body.
- Plain text body.
- Attachment-based report.
- Unexpected format.

Remove or replace customer names, hostnames, public IPs, ticket IDs, usernames,
email addresses, file paths, and any secret-looking values before sharing them.
