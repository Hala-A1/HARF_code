# Reversible Oracle import: operational guide

## Current status

The local Oracle migration and runtime switch completed on **19 October 2026**. Actual Oracle SQL validation and import verification passed; an independent read-only check confirmed Oracle runtime health, migrated record counts and original backup integrity. Reverse migration is covered by isolated contract tests but has not been exercised against the user's live Oracle data. Do not rerun the initial import or cutover wizard on this now-populated database.

The tools preserve local data, import into an empty schema, verify every imported field, enable Oracle runtime storage, undo an unchanged import, or export newer Oracle data back to local storage. The following installation and cutover steps remain as operational reference; use the recovery section if a future rollback is needed.

No Oracle password is embedded in source code or command lines. The official `oracledb` driver is included in backend dependencies. Administration uses short-lived connections; runtime uses a bounded connection pool. The local wizard saves the entered password in ignored `backend/oracle.local.env`. Deployment should inject credentials using IT-managed secrets.

## First actions in SQL Developer and Windows

1. In SQL Developer, connect as **REWRITE_APP / Harf Local**.
2. Open `03_migration_safety.sql` and press **F5**. Expect `Migration safety installed`. This adds a source-snapshot/audit table and version 002; it does not change existing application data. There will be **18 tables and 2 views** after this step.
3. In Windows File Explorer, double-click `check-oracle.cmd` in this directory. Enter the REWRITE_APP password in the hidden local prompt. Expect `Oracle connection/schema 001: PASS`.
4. If the check fails, share only the displayed error code. Keep passwords and user-content backups private.

## Recommended next step: local switch-over wizard

1. In SQL Developer as **REWRITE_APP**, open `04_runtime_storage.sql` and press **F5**. This installs version 003: one runtime state/revision table and four repository views. Totals become **19 tables and 6 views**. No existing data is moved by this SQL script.
2. Finish generation and editing work, and close other application workers. In File Explorer, double-click `migrate-to-oracle.cmd`. Enter the REWRITE_APP password locally. The password is checked before the application pauses.
3. Before pausing the app, the wizard checks actual Oracle SQL using fictional bilingual CLOB content, feedback/JSON/pagination, quotas and instruction versions, then rolls all check rows back. If it passes, the wizard stops only the recognized local Rewrite backend, creates and verifies a fresh backup, imports and reads back the data, selects Oracle, restarts the backend and checks `/api/health/storage`.
4. Expect **Oracle migration and runtime health check: PASS**. Keep the printed private backup path. Verify sign-in, a saved bilingual copy, an instruction edit/version, an approval and request-limit usage in the application.
5. Once selected, new application changes save to Oracle automatically. There is no ongoing dual writing to the old local stores.

If an import fails before activation, its uncommitted data is rolled back and the original backend is restarted. If the health check fails after activation, the wizard only switches back automatically when it can prove the Oracle dataset is unchanged. If newer data exists, it keeps Oracle selected and the backend stopped, directing the operator to the export/restore procedure below. It never silently falls back to stale local data.

The default connection is `REWRITE_APP` at `localhost:1521/FREEPDB1`. Settings live in `backend/oracle.local.env`; see `backend/oracle.env.example` for a different DSN. This file and `/backups/` are ignored by Git. Administration commands can prompt for a password; the running server needs it in this local file or in an IT-managed environment/secret provider. `REWRITE_STORAGE_BACKEND=local` is the default. Changing it requires a backend restart and an imported runtime state.

## Import during a maintenance window

These are the manual alternative to the wizard. Run them from a PowerShell window in the repository root, only after schema 003 and the connection check succeed.

1. Finish or cancel ongoing generation requests. Stop the backend and all other workers that can edit application data or Markdown instructions. Keep them stopped throughout backup/import/verification. The tool refuses backup/import while port 8000 is listening; the operator must also ensure no other process is writing the stores.
2. Create a backup:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py backup
   ```

   Record the printed directory under `backups/oracle/`. The backup contains account/access data (including existing password hashes), instruction files, all three SQLite databases, an exact structured source snapshot, file hashes and counts. SQLite's backup API includes committed WAL data. Two source comparisons reject changes during backup. The directory is private local data, not a report to publish or commit. Back it up securely according to your retention/access policy.

3. Replace the example directory below with the actual printed directory, then inspect it:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py inspect --backup ".\backups\oracle\YOUR_BACKUP_DIRECTORY"
   ```

4. Import:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py import --backup ".\backups\oracle\YOUR_BACKUP_DIRECTORY"
   ```

   Enter the database password locally. The tool checks backup hashes, confirms the source still matches, verifies schema 001/002/003, and refuses occupied application tables or runtime state. Exclusive locks prevent concurrent changes during import. All inserted application rows, the source snapshot and initial runtime state share one transaction. Every mapped field is read back before commit. A pre-commit failure rolls back the whole import; no source files are edited.

5. Independently verify:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py verify --backup ".\backups\oracle\YOUR_BACKUP_DIRECTORY"
   ```

   This verifies the source snapshot and every mapped row in a consistent read-only transaction.

6. To select Oracle manually while the backend is still stopped, run:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py enable-oracle --backup ".\backups\oracle\YOUR_BACKUP_DIRECTORY"
   ```

   Restart the backend and check `/api/health/storage` returns `{"status":"ok","storage":"oracle"}`. If local data changed since import, activation refuses the outdated snapshot. There is no ongoing replication between local and Oracle stores; never switch by editing the mode alone after either dataset has changed.

## Undo the import before cutover

```powershell
.\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py undo-import --backup ".\backups\oracle\YOUR_BACKUP_DIRECTORY"
```

The tool locks the application tables and verifies the entire imported dataset against the preserved backup. If any row was added, changed or removed, it refuses to delete anything. If the dataset is unchanged, it removes the imported application rows in foreign-key order in one transaction and retains the migration snapshot marked `rolled_back`. It does not drop tables, users or schema-version records. Your original local files remain untouched, so no local restore is required for this import-only operation.

**Undo-import is not a rollback after runtime writes start.** Use the following export/restore procedure to preserve newer data.

## Revert after Oracle has received new data

1. Stop the backend and all other writers. Keep the backend stopped through export, restore and verification.
2. Export the current Oracle data:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py export-local
   ```

   Keep the printed `backups/oracle/oracle-export-...` directory. It contains current access/approval data, instruction text/history, feedback, quotas and complete local database files, with an integrity manifest.
3. Restore that export:

   ```powershell
   .\backend\.venv\Scripts\python.exe -B -X utf8 .\backend\oracle_migration.py restore-local --backup ".\backups\oracle\oracle-export-YOUR_EXPORT_ID"
   ```

   The tool locks Oracle application tables, refuses stale exports, preserves a separate backup of the previous local stores, restores files/databases, verifies the restored content, and only then selects local storage. Oracle data remains intact. If restore fails, keep the backend stopped and Oracle selected until recovery finishes.
4. Restart the backend and confirm `/api/health/storage` reports `local`. Review a recently edited copy, a new instruction version and quota totals to confirm the newest content is present.

## Preservation and validation details

- All original top-level fields, nested input/output metadata, notes, unknown future fields and historical snapshots are preserved in the complete source snapshot. Core records also map into the schema's relational tables and JSON CLOB payloads.
- No original account passwords are reconstructed. Existing application hashes remain hashes; LDAP IDs remain stable identities.
- Arabic and English use CLOB/AL32UTF8; text exceeding a short column fails preflight instead of being truncated. Unknown current output languages fail explicitly.
- Oracle treats empty VARCHAR2 values as NULL. Field verification accounts for that storage behaviour; exact empty-string distinctions remain in the preserved source JSON.
- Original instruction histories are retained. If the current Markdown differs from the last history version, an explicit migration-baseline version captures it. Historical modules with no current file are retained as inactive reference records.
- Old activity records without IDs receive deterministic IDs derived from record content and the occurrence count of exact duplicates. Adding a new unrelated event does not shift existing IDs. Original records remain in snapshots. Missing user/channel creation timestamps use capture time in relational columns; this is an import-time fallback, not historical evidence.
- Timestamps preserve explicit offsets; timezone-less source dates fail rather than being guessed. Existing numeric reservation expiries convert to timezone-aware timestamps.
- Pending request reservations and expiry times are copied. When Oracle is selected, the quota adapter uses Oracle tables and transaction locks to protect reservations and allocations.
- The check/import tools do not use SYSTEM and do not modify the root `.env` or application sign-in credentials.

## Validation performed during development

`backend/test_oracle_migration.py` uses disposable source files and a transaction-capable database double to check bilingual round trips, failed-import rollback, guarded undo, unchanged source files, stale-backup rejection, occupied-schema rejection, hash tampering, field-length/orphan rejection, instruction baseline history and SYSTEM-account rejection. These tests do not substitute for a live Oracle import/undo test.

`backend/test_oracle_runtime.py` exercises the actual application routes/repositories against an Oracle-dialect SQL double: user edits, stale-save conflicts, shared rollback, quota/LDAP identity operations, language approvals, feedback visibility, instruction save/history/restore, cache recovery, channel starter files and reverse migration with newer Arabic content. `backend/test_oracle_cutover.py` tests successful orchestration and failure paths without stopping real processes. Full backend regressions must pass before deployment.

Run the safety/storage regression set:

```powershell
cd backend
.\.venv\Scripts\python.exe -B -m unittest discover -p "test_*.py"
```

References: [Oracle Python connection handling](https://python-oracledb.readthedocs.io/en/v3.4.0/user_guide/connection_handling.html), [Oracle CLOB bindings](https://python-oracledb.readthedocs.io/en/v3.4.0/user_guide/bind.html), [SQLite backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).

## Runtime architecture and deployment notes

- `storage_backend.py` selects local or Oracle explicitly. Oracle failures produce a storage error and never read stale local files as a fallback.
- `oracle_runtime.py` supplies pooled connections, a revision-checked access ledger, changed-row relational projections, feedback/quota SQL adapters and the Markdown retrieval cache. The existing dictionary-based access/approval code retains its complete fields in `HARF_RUNTIME_STATE`; relational tables remain synchronized in the same transaction. Only changed projections are written. A revision cache avoids transferring the complete access CLOB on every read; every standalone read still checks the database revision.
- `storage_lock.py` extends existing critical sections into shared Oracle transactions. Nested account, quota, feedback, notification and activity writes reuse that transaction. Access revisions reject stale saves outside a critical section. AI generation runs outside these database locks; only saving its finished batch enters a short critical section.
- `oracle_instructions.py` stores current Markdown and version history in Oracle. The existing channel Markdown files become a retrieval cache. Admin edits/restores made through the application update Oracle and cache together. On reads/startup, outdated cache files refresh from Oracle. In Oracle mode, maintain instructions through the admin editor; editing a cached file externally is not a substitute for saving an Oracle version.
- `oracle_recovery.py` exports current Oracle state back to the legacy format and verifies restore before switching local. No Oracle tables are dropped during recovery.
- Recovery verifies that the relational access/approval projections still match the access ledger and that current instruction checksums match their content. Unsynchronized direct SQL edits cause recovery to stop for review rather than silently discarding them. Make normal data changes through the application.
- `oracle_probe.py` performs rollback-only checks against the actual target Oracle database before cutover. It requires empty application tables and does not change storage mode permanently. It can also be run independently with `oracle_migration.py test-runtime` after schema 003 is installed.
- Administration connections and every acquired runtime session install Oracle's documented JSON fetch handler. `IS JSON` CLOB fields remain exact JSON text/LOBs rather than being automatically converted into Python dictionaries/lists by python-oracledb. This preserves both field verification and the existing repositories' explicit JSON parsing. See [Oracle's driver compatibility guidance](https://python-oracledb.readthedocs.io/en/v3.4.0/user_guide/appendix_c.html).
- This is a conservative compatibility design: access changes and quota reservations are deliberately serialized for correctness. Load-test with realistic data/concurrency before AIDEV rollout; higher throughput may justify finer per-entity locks and fully relational access queries.
- For AIDEV, have IT review privileges, DSN/TLS/wallet requirements, backup retention and secrets management. The local Windows maintenance wizard only manages the recognized local `python.exe main.py` process; deployment services require their normal maintenance procedure.
- Local backend maintenance uses `backend/backend_process.py` and native `psutil` APIs. It validates the virtual-environment executable, entry point and working directory for every port-8000 listener before stopping any process. It starts the backend without an extra console window. PowerShell script execution and execution-policy changes are not required.


## Live table-prefix migration — 19 October 2026

The local database was backed up, all 19 `RW_*` tables were renamed to `HARF_*`, and all six existing views were recreated using the new names. Exact per-table contents were checked before recording schema version `004`; the exported application snapshot also matched the pre-rename backup. The backend now uses the new table identifiers. Its Oracle health check passed after restart. Existing private source backups remain readable. The owner/schema remains `REWRITE_APP`; table constraints and indexes retain their existing names.
