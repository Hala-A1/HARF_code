# Harf: local Oracle schema installation

These scripts prepare application storage in your existing local Oracle database. SQL Developer is the client used to run the scripts; `FREEPDB1` is your database service. An Oracle schema is the collection of objects owned by a database user. The new application schema is `REWRITE_APP`.

**Status — 19 October 2026:** local installation, actual Oracle SQL validation, verified import and runtime cutover completed successfully. An independent read-only check confirmed `/api/health/storage` reports `oracle`, the imported runtime state exists, migrated record counts are present and the original backup passes file-integrity checks. The running application now uses Oracle; original local stores remain preserved.

After installation, follow [the reversible migration guide](MIGRATION.md). The remaining schema script is `04_runtime_storage.sql` (version 003). Then `migrate-to-oracle.cmd` can back up, import, verify and enable Oracle through a local password prompt.

## 1. Create the dedicated schema

1. Open your working **SYSTEM** connection in SQL Developer (`localhost`, port `1521`, service name `FREEPDB1`, Default role).
2. Open `00_create_application_schema.sql` using File > Open. Confirm the worksheet connection selector is your SYSTEM connection.
3. Press **F5 / Run Script** to execute the whole script. Do not use Run Statement for these installation scripts.
4. Enter a new database password in the hidden prompt on your computer. Do not send it in chat. Use 16–128 ASCII characters from the set shown in the script; exclude spaces, quotes, apostrophes and ampersands.
5. Expect `REWRITE_APP created` and an account row with status `OPEN`.

The script creates only REWRITE_APP, grants CREATE SESSION, CREATE TABLE and CREATE VIEW, and allocates a 250 MB quota in the local USERS tablespace. It refuses to replace an existing account or run in CDB$ROOT. If USERS or TEMP is unavailable, ask the database administrator to select suitable tablespaces before running it.

## 2. Create a new SQL Developer connection

Click the green **+** beside Connections and enter:

| Field | Value |
| --- | --- |
| Connection name | Harf Local |
| Authentication type | Default |
| Username | REWRITE_APP |
| Password | The new password entered locally in step 1 |
| Connection type | Basic |
| Hostname | localhost |
| Port | 1521 |
| Service name | FREEPDB1 |
| Role | Default |

Click **Test**, then **Connect** when it succeeds. The database password is separate from application sign-in passwords. SYSTEM is for database administration; do not configure the application to run as SYSTEM.

## 3. Create the tables

1. Open `01_create_tables.sql`.
2. Select **Harf Local / REWRITE_APP** in the worksheet connection selector.
3. Press **F5 / Run Script**.
4. Expect `Rewrite tables created` without ORA- errors.

The script requires Oracle 19c or newer and AL32UTF8 character storage for Arabic and English. It refuses to run as SYSTEM or replace existing application tables. Oracle schema changes commit automatically: if a statement fails partway through, save the error and have the remaining installation reviewed instead of blindly rerunning it. No DROP or cleanup script is supplied.

## 4. Verify

Run `02_verify_installation.sql` with **F5**, using the REWRITE_APP connection. It should report PASS for **17 tables**, **2 views**, constraints and installation version 001. Refresh **Tables** under Harf Local to see them. The tables start empty except for the installation-version record; no application accounts, demo passwords or old content are imported.

## What each table stores

| Table | Purpose |
| --- | --- |
| GENAI_HARF_SCHEMA_VERSIONS | Records installed schema changes. |
| GENAI_HARF_CHANNELS | Channel configuration, active status and soft deletion history. |
| GENAI_HARF_USERS | User identities, roles, channel membership, reviewer assignment and optional LDAP identity. Password hashes only, never plaintext application passwords. |
| GENAI_HARF_INSTRUCTIONS | Current Markdown instructions per channel and instruction module. |
| GENAI_HARF_INSTRUCTION_VERSIONS | Full previous instruction text, edit author, time, change note and restore reference. |
| GENAI_HARF_BATCHES | Saved generation batches, task/context, creator, submission and approval status. |
| GENAI_HARF_COPY_ITEMS | Individual source files or requested components, input text and generation instructions. |
| GENAI_HARF_OUTPUTS | Current English/Arabic generated text, quality report and character/word counts. |
| GENAI_HARF_COPY_VERSIONS | Previous output versions and requested changes. |
| GENAI_HARF_APPROVAL_EVENTS | Approval decisions, notes, actions, reviewer and timestamps. |
| GENAI_HARF_LANGUAGE_APPROVALS | Per-layer, per-language approvals. Full historical events remain in GENAI_HARF_APPROVAL_EVENTS. |
| GENAI_HARF_NOTIFICATIONS | Recipient notifications and read state. |
| GENAI_HARF_ACTIVITY | User actions with context and timestamps. |
| GENAI_HARF_FEEDBACK | Ratings, reasons, input/output snapshots, referenced instructions and administrator response. |
| GENAI_HARF_CHANNEL_LIMITS | Monthly request budgets assigned to channels. |
| GENAI_HARF_USER_LIMITS | Per-user allocations, keyed by a stable local or LDAP principal. |
| GENAI_HARF_REQUEST_USAGE | Pending, completed and released request reservations by month. |

`RW_APPROVAL_QUEUE` lists submitted batches, excluding unsent drafts. `RW_CHANNEL_REQUEST_USAGE` counts completed requests and unexpired reservations. These views do not enforce application permissions; the backend must continue to enforce user/channel access.

Long documents and outputs use CLOB fields. Timestamps include time-zone information. Relational keys support filtering and integrity; JSON CLOB fields retain additional context and snapshots without forcing their content into short text columns. Historical actor details are stored with events so audit records survive changes to user accounts.

## Before connecting the application or deploying to AIDEV

The following work is still required; these scripts alone do not implement it:

1. Obtain the actual AIDEV host, port, service name, allowed schema, Oracle version and TLS/wallet requirements from IT. AIDEV may be a connection label rather than the service name.
2. Have the DBA review the schema, storage quota, tablespaces, backup policy and runtime privileges. For production, separate migration-owner privileges from a runtime account with only the required data access.
3. The official Oracle driver, administration connection and runtime connection pool are implemented. Configure credentials in the ignored local backend file or IT-managed secrets; never frontend code.
4. The Oracle adapters cover access/approvals/activity/notifications, instruction history, feedback and quotas. Live-test all repository contracts with the target Oracle version before deployment. Existing role restrictions and instruction routing remain in the application modules.
5. Run and live-test the prepared migration tools, reconciling channels, users, copies, approvals, instruction versions, feedback, activity and quota data. The tools preserve source snapshots and convert timestamp formats, including reservation expiry values; the local Oracle import was completed and verified; deployment requires its own controlled migration.
6. Runtime units of work, revision checks and bounded row/table locks now protect quota reservations, approval transitions and instruction version updates. Load-test this deliberately conservative locking design with the expected deployment concurrency.
7. Test bilingual round trips, rollback, concurrency, permissions, migration totals and restore before enabling Oracle storage in deployment.

Official references: [Oracle user creation and tablespace quotas](https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/CREATE-USER.html), [SQL Developer connections](https://docs.oracle.com/en/database/oracle/oracle-database/19/tdddg/connecting-oracle-database-sql-developer.html), [Oracle table creation](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/CREATE-TABLE.html).


## Table prefix update — 30 October 2026

All 19 live application/support tables now use `GENAI_HARF_`. The owner remains `REWRITE_APP`. The six `RW_` views retain their public names and point at the renamed tables. Nineteen `GENAI_RW_` and nineteen `HARF_` compatibility views preserve older references without duplicating data. Constraint and index names remain unchanged. Schema version `006` records the GENAI_HARF rename; `005` records the earlier HARF rename. Installation scripts create GENAI_HARF table names directly; do not rerun them on the existing database.

The current one-time migration tool is `backend/oracle_genai_harf_names.py`. It requires a stopped backend, creates and verifies a current Oracle export, journals each rename, verifies every row by hash and attempts compensating renames if a step fails. A broken connection triggers a fresh recovery connection. Oracle DDL commits immediately, so the private backup and journal must be retained. `oracle_table_names.py` and `oracle_harf_names.py` are historical tools; do not run these migrations against an already-renamed schema. The account, service and existing SQL Developer connection labels were intentionally retained to avoid connection failures.

Updated ER diagram: [SVG](../../reports/harf-oracle-erd.svg), [Mermaid](../../reports/harf-oracle-erd.mmd). Older diagram files are historical artifacts.
