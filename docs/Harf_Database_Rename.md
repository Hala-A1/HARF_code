# GENAI_HARF naming and compatibility

The 19 application/support tables use `GENAI_HARF_`. Runtime SQL, mapping code, recovery/export tools, installation scripts and tests use those physical names. Schema version **006** records the migration; version 005 records the earlier HARF rename.

The existing owner/account **REWRITE_APP**, Oracle service **FREEPDB1**, credentials, indexes and constraints stay unchanged. SQL Developer connection display names are left intact: changing account/schema identity or editing live client settings would introduce avoidable risk. A display label is independent of the schema and does not affect the application connection.

The six existing `RW_` views retain their names and point at the renamed tables. Nineteen `GENAI_RW_` and nineteen `HARF_` compatibility views preserve previous table references without duplicating any data. They use a direct single-table `SELECT *`, so legacy single-table DML remains possible. Avoid dropping these aliases until downstream dependencies have been reviewed. New application SQL uses the physical GENAI_HARF tables.

`backend/oracle_genai_harf_names.py` refuses missing/colliding objects, invalid objects, non-view dependencies, external grants or missing view privileges. It requires the backend to be stopped, creates and verifies a current Oracle-to-local backup, stores original view SQL and per-table row hashes in a private journal, renames the tables, rebuilds views and checks exact row contents. No application table is dropped or recreated. On a failure it attempts compensating DDL and records whether reversal succeeded; Oracle DDL itself cannot be transactionally rolled back.

Private backups/journals are under ignored `backups/oracle/oracle-export-…/`; retain them for recovery. The earlier `oracle_table_names.py` and `oracle_harf_names.py` are historical migration tools. Existing databases must not rerun installation SQL. Table renaming does not increase the Oracle account's storage quota; that remains a separate SYSTEM/DBA operation.

The interface uses **Output**. Safe component/CSS identifiers use Harf names. Stored workspace value `rewrite`, browser event/storage identifiers, the `REWRITE_STORAGE_BACKEND` configuration contract and the account `REWRITE_APP` remain compatibility identifiers. Writing-task verbs such as “rewrite” remain valid instructions; they are not product names.

Oracle reference: [RENAME and dependent objects](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/RENAME.html).
