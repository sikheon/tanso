@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 > nul
title E.L.O Setup

echo ===============================================
echo   E.L.O - One-shot setup
echo ===============================================
echo.

REM ----- 1. Prereq check -----
echo [1/7] Checking prerequisites...
where python >nul 2>&1
if errorlevel 1 (echo   [X] Python not found. Install Python 3.12+ from python.org and re-run. & goto :fail)
where node >nul 2>&1
if errorlevel 1 (echo   [X] Node.js not found. Install Node.js 20+ from nodejs.org and re-run. & goto :fail)
where docker >nul 2>&1
if errorlevel 1 (echo   [X] Docker not found. Install Docker Desktop and re-run. & goto :fail)
docker info >nul 2>&1
if errorlevel 1 (echo   [X] Docker is installed but the daemon is not running. Start Docker Desktop and re-run. & goto :fail)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   [OK] Python !PYVER!, Node, Docker

REM ----- 2. .env scaffolding -----
echo.
echo [2/7] Preparing env files...
if not exist .env (
    copy /Y .env.example .env > nul
    echo   [!] .env created from template - fill API keys before running start.bat
) else (
    echo   [OK] .env already present
)
if not exist frontend\.env.local (
    copy /Y frontend\.env.local.example frontend\.env.local > nul
    echo   [!] frontend\.env.local created - fill NEXT_PUBLIC_KAKAO_MAP_KEY
) else (
    echo   [OK] frontend\.env.local already present
)

REM ----- 3. Backend venv -----
echo.
echo [3/7] Creating Python venv (backend\.venv)...
if not exist backend\.venv (
    python -m venv backend\.venv || goto :fail
    echo   [OK] venv created
) else (
    echo   [OK] venv already present
)

REM ----- 4. Backend deps -----
echo.
echo [4/7] Installing backend dependencies (this may take ~2 min)...
call backend\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet || goto :fail
call backend\.venv\Scripts\python.exe -m pip install -e backend --quiet || goto :fail
echo   [OK] Backend deps installed

REM ----- 5. PostgreSQL via Docker -----
echo.
echo [5/7] Starting PostgreSQL+PostGIS container...
docker compose up -d postgres || goto :fail
echo   [.] Waiting for healthcheck...
set /a tries=0
:wait_db
set /a tries+=1
if !tries! GTR 30 (echo   [X] Postgres did not become healthy in 60s & goto :fail)
for /f %%i in ('docker inspect -f "{{.State.Health.Status}}" elo-postgres 2^>nul') do set DBSTATUS=%%i
if "!DBSTATUS!"=="healthy" goto :db_ready
timeout /t 2 /nobreak > nul
goto :wait_db
:db_ready
echo   [OK] Postgres healthy

REM ----- 6. Alembic migrate -----
echo.
echo [6/7] Applying database migrations...
pushd backend
call .venv\Scripts\alembic.exe upgrade head || (popd & goto :fail)
popd
echo   [OK] Migrations applied

REM ----- 6b. Seeds -----
echo.
echo [6b]  Loading seed data (errors on rerun are normal)...
for %%f in (backend\seeds\01_emission_factors.sql backend\seeds\02_speed_bin_factors.sql backend\seeds\03_vehicles_sample.sql backend\seeds\04_extended_trucks.sql backend\seeds\05_heavy_vehicles_sample.sql) do (
    if exist %%f (
        type %%f | docker exec -i elo-postgres psql -U elo -d elo -q -v ON_ERROR_STOP=0 > nul 2>&1
        echo   [OK] %%~nxf
    )
)

REM ----- 7. Frontend deps -----
echo.
echo [7/7] Installing frontend dependencies (this may take ~2 min)...
pushd frontend
call npm install --silent --no-audit --no-fund || (popd & goto :fail)
popd
echo   [OK] Frontend deps installed

echo.
echo ===============================================
echo   Setup complete.
echo.
echo   Next steps:
echo     1. Open .env and frontend\.env.local
echo        - fill KAKAO_REST_API_KEY, ORS_API_KEY,
echo          GEMINI_API_KEY, NEXT_PUBLIC_KAKAO_MAP_KEY
echo     2. Double-click start.bat to launch the app
echo ===============================================
endlocal
pause
exit /b 0

:fail
echo.
echo ===============================================
echo   Setup FAILED. See the error above.
echo ===============================================
endlocal
pause
exit /b 1
