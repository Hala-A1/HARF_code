-- Run once with F5 as REWRITE_APP, after schema 002.
SET DEFINE OFF
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
DECLARE
    v_count NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'REWRITE_APP'
       OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'REWRITE_APP' THEN
        RAISE_APPLICATION_ERROR(-20040, 'Connect as REWRITE_APP.');
    END IF;
    SELECT COUNT(*) INTO v_count FROM genai_harf_schema_versions WHERE version_id='002';
    IF v_count<>1 THEN RAISE_APPLICATION_ERROR(-20041,'Install migration safety first.'); END IF;
    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name='GENAI_HARF_RUNTIME_STATE';
    IF v_count<>0 THEN RAISE_APPLICATION_ERROR(-20042,'Runtime storage already exists. No changes made.'); END IF;
END;
/
CREATE TABLE genai_harf_runtime_state (
    state_id VARCHAR2(30 CHAR) PRIMARY KEY,
    revision NUMBER(18) NOT NULL CHECK (revision>=1),
    migration_id VARCHAR2(80 CHAR) NOT NULL REFERENCES genai_harf_migration_snapshots(migration_id),
    baseline_at VARCHAR2(40 CHAR) NOT NULL,
    access_json CLOB NOT NULL CHECK (access_json IS JSON),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE VIEW rw_feedback_legacy AS
SELECT feedback_id AS id,channel_id,workspace_name AS workspace,user_email,user_name,fingerprint,rating,
       reason_text AS reason,snapshot_json AS snapshot,instruction_manifest,
       TO_CHAR(created_at,'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM') AS created_at,
       TO_CHAR(updated_at,'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM') AS updated_at,
       review_status AS status,admin_note,reviewed_by,
       TO_CHAR(reviewed_at,'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM') AS reviewed_at
FROM genai_harf_feedback;
CREATE VIEW rw_channel_limits_legacy AS SELECT channel_id AS channel,monthly_limit FROM genai_harf_channel_limits;
CREATE VIEW rw_user_limits_legacy AS SELECT channel_id AS channel,principal_id AS principal,monthly_limit FROM genai_harf_user_limits;
CREATE VIEW rw_request_usage_legacy AS
WITH usage_times AS (
    SELECT request_id,channel_id,principal_id,month_key,request_state,created_at,
           (SYS_EXTRACT_UTC(expires_at)-TIMESTAMP '1970-01-01 00:00:00') DAY(9) TO SECOND(6) AS elapsed
    FROM genai_harf_request_usage
)
SELECT request_id AS id,channel_id AS channel,principal_id AS principal,month_key AS month,request_state AS state,
       EXTRACT(DAY FROM elapsed)*86400+EXTRACT(HOUR FROM elapsed)*3600
       +EXTRACT(MINUTE FROM elapsed)*60+EXTRACT(SECOND FROM elapsed) AS expires,
       TO_CHAR(created_at,'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM') AS created_at
FROM usage_times;
INSERT INTO genai_harf_schema_versions(version_id,description) VALUES ('003','Runtime storage revision guard and legacy repository views');
COMMIT;
PROMPT Runtime storage schema installed. Total: 19 tables, 6 views. Application storage has not switched.
