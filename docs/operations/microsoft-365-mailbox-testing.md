# Connect Microsoft 365 mailbox ingestion

Use this tutorial to connect the local pilot to the Microsoft 365 mailbox that
receives backup reports.

The happy path is:

```text
Entra app -> Graph Mail.Read -> local env vars
-> mail connector -> sync -> parser review
```

## Safety contract

The connector is intentionally read-only.

It does:

- request an OAuth token;
- read messages with Microsoft Graph `GET`;
- store message metadata and body content locally for review.

It does not:

- mark messages as read;
- move messages between folders;
- create, edit, or delete folders;
- create, edit, or delete mailbox rules;
- execute attachments;
- store Microsoft secrets in the database or repository.

## Prerequisites

You need:

- local Django app migrated and running;
- admin user attached to `organizacion-piloto`;
- Microsoft 365 admin access;
- the mailbox address, for example `backups@dominio.com`;
- permission to grant Microsoft Graph application permissions.

## Step 1: Create the Microsoft Entra app

In Azure Portal:

1. Open **Microsoft Entra ID**.
2. Open **App registrations**.
3. Select **New registration**.
4. Use a clear name, for example:

   ```text
   Backup Control Center Local Pilot
   ```

5. Choose **Single tenant** unless your Microsoft tenant policy requires another
   option.
6. Register the app.
7. Copy these values:

   ```text
   Directory tenant ID
   Application client ID
   ```

## Step 2: Create the client secret

In the app registration:

1. Open **Certificates & secrets**.
2. Select **New client secret**.
3. Choose an expiration appropriate for the pilot.
4. Copy the secret **Value** immediately.

You now have:

```text
M365_TENANT_ID=<Directory tenant ID>
M365_CLIENT_ID=<Application client ID>
M365_CLIENT_SECRET=<Client secret value>
```

## Step 3: Grant Microsoft Graph mail permission

In the app registration:

1. Open **API permissions**.
2. Select **Add a permission**.
3. Select **Microsoft Graph**.
4. Select **Application permissions**.
5. Add:

   ```text
   Mail.Read
   ```

6. Select **Grant admin consent**.

For production hardening, restrict the application to the backup mailbox with
Exchange Online application access policy or application RBAC. The local pilot
still only performs read operations, but Graph application permission can be broad
unless Microsoft 365 policy restricts it.

## Step 4: Set local environment variables

In the same PowerShell terminal that will run Django:

```powershell
$env:M365_TENANT_ID="<Directory tenant ID>"
$env:M365_CLIENT_ID="<Application client ID>"
$env:M365_CLIENT_SECRET="<Client secret value>"
```

Do not put these values in Git, docs, screenshots, or the database.

Run the server from that same terminal:

```powershell
python manage.py runserver
```

## Step 5: Find folder IDs for custom folders

If reports are routed into folders under `backups@dominio.com`, use Graph folder
IDs instead of only display names.

Get a token in PowerShell:

```powershell
$body = @{
  client_id     = $env:M365_CLIENT_ID
  scope         = "https://graph.microsoft.com/.default"
  client_secret = $env:M365_CLIENT_SECRET
  grant_type    = "client_credentials"
}

$tokenUri = "https://login.microsoftonline.com/$env:M365_TENANT_ID" +
  "/oauth2/v2.0/token"

$token = Invoke-RestMethod `
  -Method Post `
  -Uri $tokenUri `
  -Body $body
```

List top-level folders:

```powershell
$graphUser = "https://graph.microsoft.com/v1.0/users/backups@dominio.com"
$foldersUri = $graphUser + "/mailFolders?`$select=id,displayName,parentFolderId"

Invoke-RestMethod `
  -Headers @{ Authorization = "Bearer $($token.access_token)" } `
  -Uri $foldersUri
```

List folders under Inbox:

```powershell
$childFoldersUri = $graphUser +
  "/mailFolders/inbox/childFolders?`$select=id,displayName,parentFolderId"

Invoke-RestMethod `
  -Headers @{ Authorization = "Bearer $($token.access_token)" } `
  -Uri $childFoldersUri
```

Use the returned `id` as the connector folder value for custom folders.

## Step 6: Create the connector in Backup Control Center

In the local app:

1. Sign in as an admin user.
2. Open **Correos**.
3. Select **Crear conector**.
4. Set provider to **Microsoft 365 Outlook**.
5. Set auth mode to **OAuth client credentials**.
6. Set mailbox address:

   ```text
   backups@dominio.com
   ```

7. Set folder:

   ```text
   Inbox
   ```

   Or use a Microsoft Graph folder ID for a routed custom folder.

8. Keep environment variable references as names only:

   ```text
   M365_TENANT_ID
   M365_CLIENT_ID
   M365_CLIENT_SECRET
   ```

9. Save the connector.

For the current pilot, create one connector per selected folder. Recursive folder
discovery can be added later, but explicit folders are safer for initial testing.

## Step 7: Sync messages

1. Open **Correos**.
2. Select **Sincronizar** on the connector.
3. Open **Ver mensajes**.
4. Confirm new messages appear.
5. Sync again.
6. Confirm existing messages are skipped, not duplicated.

Expected result:

```text
Sincronización completa: <n> nuevos, <m> omitidos.
```

## Step 8: Process parser results

1. Open **Revisión manual**.
2. Select **Procesar mensajes sin parser**.
3. Open a parsed item.
4. Review provider, status, rule IDs, evidence, and matching suggestions.
5. Associate it with the expected execution when the suggestion is correct.
6. Otherwise, leave a review note or mark it reviewed manually.

The system can use imported legacy evidence to improve suggestions, but the
operator still confirms the final association and result.

## Step 9: End-to-end test checklist

Use this checklist for a real pilot test:

- [ ] Django process has the `M365_*` variables.
- [ ] Entra app has Graph `Mail.Read` application permission.
- [ ] Admin consent is granted.
- [ ] Connector uses `backups@dominio.com`.
- [ ] Folder is `Inbox` or a valid Graph folder ID.
- [ ] Sync imports messages once.
- [ ] Repeated sync skips duplicates.
- [ ] Messages are not marked as read in Outlook.
- [ ] Messages remain in the same folders.
- [ ] Folder structure and rules remain unchanged.
- [ ] Parser review shows evidence and matching suggestions.
- [ ] Operator manually confirms or rejects the suggested match.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing env var | Run Django where `M365_*` is set. |
| Graph auth fails | Check IDs, secret, `Mail.Read`, and consent. |
| No messages | Check mailbox, folder ID, and access policy. |
| Folder not found | Use Graph folder ID for custom folders. |
| Duplicates | Verify Graph message IDs are stable. |
| Parser unknown | Review format or add anonymized samples. |

## Collect parser samples later

When mailbox access is available, collect anonymized samples for each provider and
result type:

- success;
- warning;
- failure;
- HTML body;
- plain text body;
- attachment-based report;
- unexpected format.

Remove customer names, hostnames, public IPs, ticket IDs, usernames, email
addresses, file paths, and secret-looking values before sharing samples.
