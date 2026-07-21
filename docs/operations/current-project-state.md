# Current project state

This handoff records the local pilot state after the legacy import, provisional
bootstrap, schedule generation, M365 matching improvements, and M365 connection
tutorial work.

## Safe resume summary

The app is ready for a Microsoft 365 end-to-end pilot test.

Current local runtime data for tenant `organizacion-piloto`:

| Area | Count |
| --- | ---: |
| Legacy configurations | 498 |
| Legacy daily records | 63,311 |
| Legacy import issues | 496 |
| Legacy ticket references | 65 |
| Backup jobs | 498 |
| Backup targets | 498 |
| Provisional assisted schedules | 498 |
| Expected executions | 98,604 |

The expected executions cover the recorded historical range from 2026-01-05 to
2026-07-21 and include Saturdays and Sundays.

## What changed

### Legacy import and review

Added a dedicated legacy history import path for
`Gestion de Backups 2026(Control Backups).csv`:

- dry-run report generation;
- source hash validation before commit;
- staging/audit tables;
- tenant-scoped review UI;
- configuration detail page;
- per-configuration reconciliation;
- fast operational bootstrap.

### Operational bootstrap

Added commands to avoid manual one-by-one setup before testing:

```bash
python manage.py bootstrap_legacy_backups \
  --tenant organizacion-piloto \
  --source runtime/reports/legacy-commit.json \
  --output runtime/reports/legacy-bootstrap.json

python manage.py bootstrap_legacy_schedules \
  --tenant organizacion-piloto \
  --frequency DAILY \
  --weekdays "1,2,3,4,5,6,7" \
  --scheduled-time "23:00" \
  --deadline-time "08:00" \
  --deadline-offset-days 1 \
  --mode ASSISTED \
  --update-existing \
  --output runtime/reports/legacy-schedules-bootstrap-all-days.json

python manage.py generate_legacy_expected_executions \
  --tenant organizacion-piloto \
  --source runtime/reports/legacy-commit.json \
  --output runtime/reports/legacy-expected-executions-all-days.json
```

These commands are idempotent. They do not create real backup executions,
tickets, mailbox matches, or final confirmed schedules.

### M365 ingestion and matching

M365 connector behavior remains read-only:

- message fetch uses Graph `GET`;
- the app does not mark mail as read;
- the app does not move messages;
- the app does not edit folders;
- the app does not edit mailbox rules.

Assisted matching now uses legacy evidence:

- parsed job hints;
- parsed object hints;
- parsed customer hints;
- provider;
- expected execution window;
- reconciled legacy backup name;
- reconciled legacy source asset;
- job targets;
- connector folder as weak customer/site evidence.

## How to test next

1. Follow the tutorial in
   `docs/operations/microsoft-365-mailbox-testing.md`.
2. Connect one selected folder from `backups@dominio.com`.
3. Sync messages.
4. Confirm a repeated sync does not duplicate messages.
5. Confirm Outlook message read state, folders, and rules remain unchanged.
6. Open **Revisión manual**.
7. Select **Procesar mensajes sin parser**.
8. Open a parsed item and review matching suggestions.
9. Confirm the suggested expected execution only when it is correct.

## Useful local reports

Generated reports live under `runtime/reports/` and are ignored by Git:

- `legacy-dry-run.json`
- `legacy-commit.json`
- `legacy-bootstrap.json`
- `legacy-schedules-bootstrap-all-days.json`
- `legacy-expected-executions-all-days.json`

Treat them as local evidence. Do not commit them because they may contain
customer or operational details.

## Verification evidence

Latest verification commands:

```bash
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe -m pytest -q
npx --yes markdownlint-cli2 README.md "docs/**/*.md" \
  BACKUP_CONTROL_CENTER_MASTER_PROMPT.md "openspec/**/*.md"
```

Latest known results:

```text
System check identified no issues
No changes detected
pytest: 76 passed
markdownlint: 0 issues
```

## Pending review/commit note

There are source changes pending in the Git working tree. They are intentional
implementation and documentation changes from this session. Runtime reports are
ignored by Git through `runtime/reports/`.

Do not publish or deploy until the pending source changes are reviewed and
committed intentionally.

## Recommended next slice

Run the Microsoft 365 end-to-end test with one real folder:

```text
M365 sync -> parser processing -> manual review -> suggested match -> BackupExecution
```

If matching is weak, the next code slice should persist/display the exact source
folder path or folder ID on each inbound message and include it in review
explanations.
