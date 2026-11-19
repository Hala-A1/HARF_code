-- Local development only: run with F5 using SYSTEM / localhost / FREEPDB1.
-- In AIDEV, ask the database administrator to approve the appropriate quota.
-- Increases the existing application schema's allowance to 2 GB.
-- Does not rename objects, change passwords, delete data or reserve 2 GB at once.
-- Leaves an existing larger or unlimited quota unchanged when quota metadata is accessible.
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK
DECLARE
    current_quota NUMBER;
    target_quota CONSTANT NUMBER := 2147483648;
BEGIN
    IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'SYSTEM' THEN
        RAISE_APPLICATION_ERROR(-20032, 'Select your SYSTEM connection in the worksheet dropdown, not REWRITE_APP. No quota was changed.');
    END IF;
    IF SYS_CONTEXT('USERENV', 'CON_NAME') <> 'FREEPDB1' THEN
        RAISE_APPLICATION_ERROR(-20031, 'Use your local FREEPDB1 connection. No quota was changed.');
    END IF;
    BEGIN
        EXECUTE IMMEDIATE 'SELECT max_bytes FROM sys.dba_ts_quotas WHERE username = :owner AND tablespace_name = :space'
            INTO current_quota USING 'REWRITE_APP', 'USERS';
    EXCEPTION
        WHEN NO_DATA_FOUND THEN current_quota := 0;
        WHEN OTHERS THEN
            IF SQLCODE IN (-942, -1031) THEN
                current_quota := NULL;
                DBMS_OUTPUT.PUT_LINE('Quota metadata is unavailable. Applying the requested 2 GB local allowance.');
            ELSE RAISE;
            END IF;
    END;
    IF current_quota IS NULL OR (current_quota <> -1 AND current_quota < target_quota) THEN
        EXECUTE IMMEDIATE 'ALTER USER REWRITE_APP QUOTA 2G ON USERS';
        DBMS_OUTPUT.PUT_LINE('Application storage allowance increased to 2 GB. Existing data is unchanged.');
    ELSE
        DBMS_OUTPUT.PUT_LINE('Existing quota is already sufficient; no change needed.');
    END IF;
END;
/
PROMPT Verify using your REWRITE_APP connection:
PROMPT SELECT tablespace_name, bytes/1024/1024 allocated_mb, max_bytes/1024/1024 quota_mb FROM user_ts_quotas;
