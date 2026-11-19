@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "APP_ROOT=%~dp0"
set "BACKEND_PYTHON=%APP_ROOT%backend\.venv\Scripts\python.exe"

if /I "%~1"=="--backend" goto run_backend
if /I "%~1"=="--frontend" goto run_frontend

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found. Install Node.js and try again.
    exit /b 1
)

if not exist "%BACKEND_PYTHON%" (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_COMMAND=python"
    ) else (
        where py >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Python was not found. Install Python 3 and try again.
            exit /b 1
        )
        set "PYTHON_COMMAND=py -3"
    )

    echo [SETUP] Creating the backend virtual environment...
    !PYTHON_COMMAND! -m venv "%APP_ROOT%backend\.venv"
    if errorlevel 1 exit /b 1
)

"%BACKEND_PYTHON%" -c "import fastapi, uvicorn, openai, dotenv, pydantic" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing backend dependencies...
    "%BACKEND_PYTHON%" -m pip install -r "%APP_ROOT%backend\requirements.txt"
    if errorlevel 1 exit /b 1
)

if not exist "%APP_ROOT%node_modules\vite\bin\vite.js" (
    echo [SETUP] Installing frontend dependencies...
    pushd "%APP_ROOT%"
    call npm install
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

if not exist "%APP_ROOT%.env" (
    echo [WARNING] .env was not found. Configure the project root .env before starting the application.
)

if /I "%~1"=="--check" (
    echo [OK] Frontend and backend dependencies are ready.
    exit /b 0
)

echo Starting the backend at http://127.0.0.1:8000...
start "Rewrite - Backend" /D "%APP_ROOT%" cmd /k call run_all.bat --backend

echo Starting the frontend at http://localhost:5173...
start "Rewrite - Frontend" /D "%APP_ROOT%" cmd /k call run_all.bat --frontend

echo Both services were launched in separate windows.
exit /b 0

:run_backend
cd /d "%APP_ROOT%backend"
"%BACKEND_PYTHON%" main.py
exit /b %errorlevel%

:run_frontend
cd /d "%APP_ROOT%"
call npm run dev
exit /b %errorlevel%
