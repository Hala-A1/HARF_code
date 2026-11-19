-- Run with F5 in SQL Developer using your local SYSTEM / FREEPDB1 connection.
-- Creates one new account only. Never changes SYSTEM or an existing password.
-- AIDEV: the DBA must confirm the tablespaces and quota before using this script.
SET SERVEROUTPUT ON
SET ECHO OFF
SET VERIFY OFF
SET DEFINE ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

PROMPT Creating the dedicated REWRITE_APP schema. No tables belong in SYSTEM.
PROMPT Choose a NEW database password locally. Do not use an application test password.
PROMPT Use 16-128 ASCII characters: letters, digits and ! # _ $ % @ * + = . ? -
PROMPT Do not use spaces, quotation marks, apostrophes or ampersands in this setup prompt.
ACCEPT rewrite_new_password CHAR PROMPT 'New REWRITE_APP password (hidden): ' HIDE

DECLARE
    v_existing NUMBER;
    v_password VARCHAR2(128) := '&&rewrite_new_password';
BEGIN
    IF SYS_CONTEXT('USERENV', 'CON_NAME') = 'CDB$ROOT' THEN
        RAISE_APPLICATION_ERROR(-20001, 'Connect to FREEPDB1, not CDB$ROOT.');
    END IF;
    SELECT COUNT(*) INTO v_existing FROM ALL_USERS WHERE USERNAME = 'REWRITE_APP';
    IF v_existing > 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'REWRITE_APP already exists. Nothing was changed. Use its existing connection or ask your DBA.');
    END IF;
    IF NOT REGEXP_LIKE(v_password, '^[A-Za-z0-9!#_$%@*+=.?-]{16,128}$') THEN
        RAISE_APPLICATION_ERROR(-20003, 'Password does not match the displayed setup requirements. No account was created.');
    END IF;
    EXECUTE IMMEDIATE 'CREATE USER REWRITE_APP IDENTIFIED BY "' || v_password ||
        '" DEFAULT TABLESPACE USERS TEMPORARY TABLESPACE TEMP QUOTA 250M ON USERS';
    EXECUTE IMMEDIATE 'GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW TO REWRITE_APP';
    DBMS_OUTPUT.PUT_LINE('REWRITE_APP created. Create a NEW SQL Developer connection using this username.');
END;
/
UNDEFINE rewrite_new_password
SET DEFINE OFF

SELECT username, account_status, default_tablespace
FROM dba_users WHERE username = 'REWRITE_APP';

PROMPT Next: connect as REWRITE_APP, then run 01_create_tables.sql with F5.
