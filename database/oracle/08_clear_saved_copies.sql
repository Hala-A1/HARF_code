-- LOCAL APPLICATION RESET: empties saved copies across ALL channels.
-- Also removes their approval history and clears ALL notifications.
-- Preserves users, channels, instructions/history, settings, quotas,
-- feedback, activity logs and migration backups (which may retain old content).
-- Stop the backend and create a fresh recovery backup BEFORE running.
-- Run as REWRITE_APP with F5. No DDL, TRUNCATE or automatic COMMIT.
-- Afterwards run COMMIT to keep the reset, or ROLLBACK to cancel it.

SET SERVEROUTPUT ON
SET DEFINE OFF

DECLARE
    v_json CLOB;
    v_updated_json CLOB;
    v_state JSON_OBJECT_T;
    v_count NUMBER;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'REWRITE_APP'
       OR SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') <> 'REWRITE_APP' THEN
        RAISE_APPLICATION_ERROR(-20080, 'Connect as REWRITE_APP, not SYSTEM.');
    END IF;

    SELECT access_json INTO v_json
      FROM genai_harf_runtime_state
     WHERE state_id = 'access'
       FOR UPDATE WAIT 10;

    v_state := JSON_OBJECT_T.parse(v_json);
    IF NOT v_state.has('approval_batches') THEN
        RAISE_APPLICATION_ERROR(-20081, 'Unexpected application state; no reset performed.');
    END IF;

    SELECT COUNT(*) INTO v_count FROM genai_harf_batches;
    v_state.put('approval_batches', JSON_ARRAY_T());
    v_state.put('notifications', JSON_ARRAY_T());
    -- Serialize in PL/SQL first. SQL must receive a CLOB, not JSON_OBJECT_T.
    v_updated_json := v_state.to_clob();

    -- Child tables first, to respect foreign keys.
    DELETE FROM genai_harf_notifications;
    DELETE FROM genai_harf_language_approvals;
    DELETE FROM genai_harf_approval_events;
    DELETE FROM genai_harf_copy_versions;
    DELETE FROM genai_harf_outputs;
    DELETE FROM genai_harf_copy_items;
    DELETE FROM genai_harf_batches;

    UPDATE genai_harf_runtime_state
       SET access_json = v_updated_json,
           revision = revision + 1,
           updated_at = SYSTIMESTAMP
     WHERE state_id = 'access';

    DBMS_OUTPUT.PUT_LINE('Cleared ' || v_count || ' batches, saved outputs, approval history and all notifications.');
    DBMS_OUTPUT.PUT_LINE('NOT COMMITTED. Run COMMIT to keep changes, or ROLLBACK to cancel.');
    DBMS_OUTPUT.PUT_LINE('Restart the backend only after COMMIT or ROLLBACK.');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/
