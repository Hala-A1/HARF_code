-- Run once with F5 as REWRITE_APP. Does not modify any existing application data.
SET DEFINE OFF
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
DECLARE
    v_count NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'REWRITE_APP'
       OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'REWRITE_APP' THEN
        RAISE_APPLICATION_ERROR(-20030, 'Connect as REWRITE_APP.');
    END IF;
    SELECT COUNT(*) INTO v_count FROM genai_harf_schema_versions WHERE version_id = '001';
    IF v_count <> 1 THEN
        RAISE_APPLICATION_ERROR(-20031, 'Install and verify schema 001 first.');
    END IF;
    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = 'GENAI_HARF_MIGRATION_SNAPSHOTS';
    IF v_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20032, 'Migration safety table already exists. No changes made.');
    END IF;
END;
/
CREATE TABLE genai_harf_migration_snapshots (
    migration_id VARCHAR2(80 CHAR) PRIMARY KEY,
    snapshot_sha256 VARCHAR2(64 CHAR) NOT NULL,
    snapshot_json CLOB NOT NULL CHECK (snapshot_json IS JSON),
    imported_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    rolled_back_at TIMESTAMP(6) WITH TIME ZONE,
    migration_status VARCHAR2(20 CHAR) NOT NULL CHECK (migration_status IN ('imported','rolled_back'))
);
INSERT INTO genai_harf_schema_versions(version_id, description)
VALUES ('002', 'Preserved source snapshots and guarded migration rollback');
COMMIT;
PROMPT Migration safety installed. There are now 18 application/support tables and 2 views.
