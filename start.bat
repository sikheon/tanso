@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 > nul
title E.L.O Launcher

REM Configurable ports - override with: start.bat 8000 8010
set BACKEND_PORT=8000
set FRONTEND_PORT=3000
if not "%~1"=="" set BACKEND_PORT=%~1
if not "%~2"=="" set FRONTEND_PORT=%~2

echo ===============================================
echo   E.L.O - Launching
echo     Backend  : http://localhost:%BACKEND_PORT%
echo     Frontend : http://localhost:%FRONTEND_PORT%
echo ===============================================
echo.

REM ----- Pre-flight -----
if not exist backend\.venv\Scripts\python.exe (
    echo [X] backend venv missing. Run setup.bat first.
    pause & exit /b 1
)
if not exist frontend\node_modules (
    echo [X] frontend node_modules missing. Run setup.bat first.
    pause & exit /b 1
)
if not exist .env (
    echo [X] .env missing. Run setup.bat first.
    pause & exit /b 1
)

REM ----- 1. Postgres -----
echo [1/3] Ensuring Postgres container is up...
docker compose up -d postgres > nul 2>&1
echo   [OK]

REM ----- 2. Backend -----
echo [2/3] Starting backend (new window)...
start "E.L.O Backend :%BACKEND_PORT%" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload --loop asyncio"
timeout /t 3 /nobreak > nul

REM ----- 3. Frontend -----
echo [3/3] Starting frontend (new window)...
start "E.L.O Frontend :%FRONTEND_PORT%" cmd /k "cd /d %~dp0frontend && npx next dev --port %FRONTEND_PORT% --hostname 0.0.0.0"

echo.
echo ===============================================
echo   Launched. Two new windows opened.
echo     - Open http://localhost:%FRONTEND_PORT% in a browser
echo     - Close those windows (or run stop.bat) to stop
echo ===============================================
endlocal
exit /b 0
