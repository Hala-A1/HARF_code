-- Read-only verification. Run with F5 as REWRITE_APP after 01_create_tables.sql.
SET DEFINE OFF
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

SELECT SYS_CONTEXT('USERENV','SESSION_USER') AS connected_user,
       SYS_CONTEXT('USERENV','CON_NAME') AS container_name,
       SYS_CONTEXT('USERENV','SERVICE_NAME') AS service_name
FROM dual;

DECLARE
    v_count NUMBER;
    v_charset VARCHAR2(100);
    v_expected SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST(
        'GENAI_HARF_SCHEMA_VERSIONS', 'GENAI_HARF_CHANNELS', 'GENAI_HARF_USERS', 'GENAI_HARF_INSTRUCTIONS',
        'GENAI_HARF_INSTRUCTION_VERSIONS', 'GENAI_HARF_BATCHES', 'GENAI_HARF_COPY_ITEMS', 'GENAI_HARF_OUTPUTS',
        'GENAI_HARF_COPY_VERSIONS', 'GENAI_HARF_APPROVAL_EVENTS', 'GENAI_HARF_LANGUAGE_APPROVALS',
        'GENAI_HARF_NOTIFICATIONS', 'GENAI_HARF_ACTIVITY', 'GENAI_HARF_FEEDBACK', 'GENAI_HARF_CHANNEL_LIMITS',
        'GENAI_HARF_USER_LIMITS', 'GENAI_HARF_REQUEST_USAGE');
BEGIN
    IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'REWRITE_APP'
       OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'REWRITE_APP' THEN
        RAISE_APPLICATION_ERROR(-20020, 'Run this script from the REWRITE_APP connection.');
    END IF;
    FOR i IN 1..v_expected.COUNT LOOP
        SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = v_expected(i);
        IF v_count <> 1 THEN
            RAISE_APPLICATION_ERROR(-20021, 'Missing table: ' || v_expected(i));
        END IF;
    END LOOP;
    SELECT COUNT(*) INTO v_count FROM user_views
    WHERE view_name IN ('RW_APPROVAL_QUEUE','RW_CHANNEL_REQUEST_USAGE');
    IF v_count <> 2 THEN
        RAISE_APPLICATION_ERROR(-20022, 'One or both application views are missing.');
    END IF;
    SELECT COUNT(*) INTO v_count FROM user_objects
    WHERE (object_name LIKE 'RW\_%' ESCAPE '\' OR object_name LIKE 'HARF\_%' ESCAPE '\') AND status <> 'VALID';
    IF v_count <> 0 THEN
        RAISE_APPLICATION_ERROR(-20023, 'Invalid application objects found. Review USER_ERRORS.');
    END IF;
    SELECT COUNT(*) INTO v_count FROM user_constraints
    WHERE table_name LIKE 'HARF\_%' ESCAPE '\'
      AND (status <> 'ENABLED' OR validated <> 'VALIDATED');
    IF v_count <> 0 THEN
        RAISE_APPLICATION_ERROR(-20024, 'An application constraint is disabled or not validated.');
    END IF;
    SELECT COUNT(*) INTO v_count FROM genai_harf_schema_versions WHERE version_id = '001';
    IF v_count <> 1 THEN
        RAISE_APPLICATION_ERROR(-20025, 'Installation version 001 is missing.');
    END IF;
    SELECT value INTO v_charset FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET';
    IF v_charset <> 'AL32UTF8' THEN
        RAISE_APPLICATION_ERROR(-20026, 'Expected AL32UTF8 for Arabic and English storage.');
    END IF;
    DBMS_OUTPUT.PUT_LINE('PASS: all 17 application tables and both views exist and are valid.');
    DBMS_OUTPUT.PUT_LINE('PASS: constraints are enabled and validated; version 001 is installed.');
    DBMS_OUTPUT.PUT_LINE('This checks the schema only. It does not connect or migrate the Rewrite application.');
END;
/

SELECT table_name FROM user_tables WHERE table_name LIKE 'HARF\_%' ESCAPE '\' ORDER BY table_name;
SELECT view_name FROM user_views WHERE view_name LIKE 'RW\_%' ESCAPE '\' ORDER BY view_name;
SELECT version_id, description, installed_at FROM genai_harf_schema_versions ORDER BY version_id;
