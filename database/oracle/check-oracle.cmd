@echo off
setlocal
title Rewrite - Oracle connection check
echo This checks your local REWRITE_APP connection only.
echo It does not import data or switch the application to Oracle.
echo Enter your database password at the hidden prompt. Do not share it in chat.
echo.
"%~dp0..\..\backend\.venv\Scripts\python.exe" -B -X utf8 "%~dp0..\..\backend\oracle_migration.py" check
echo.
pause
endlocal
