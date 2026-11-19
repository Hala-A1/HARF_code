@echo off
setlocal
title Rewrite - Safe Oracle migration
echo Finish any ongoing generation or editing before continuing.
echo This wizard backs up local data, imports and verifies it, then enables Oracle.
echo Your database password is entered locally and saved in the ignored backend/oracle.local.env file.
echo.
"%~dp0..\..\backend\.venv\Scripts\python.exe" -B -X utf8 "%~dp0..\..\backend\oracle_migration.py" cutover
echo.
pause
endlocal
