@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 > nul
title E.L.O Setup

echo ===============================================
echo   E.L.O - One-shot setup
echo ===============================================
echo.

REM ----- 1. Prereq check (with winget auto-install) -----
echo [1/7] Checking prerequisites...

where winget >nul 2>&1
set HAS_WINGET=1
if errorlevel 1 set HAS_WINGET=0

REM Python 3.12+
where python >nul 2>&1
if errorlevel 1 (
    if "!HAS_WINGET!"=="1" (
        echo   [.] Python not found - installing via winget ^(UAC prompt may appear^)...
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
        REM Refresh PATH for current session
        for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USERPATH=%%b"
        set "PATH=!PATH!;!USERPATH!"
        where python >nul 2>&1 || (echo   [X] Python still missing after install. Open a new terminal and re-run setup.bat. & goto :fail)
    ) else (
        echo   [X] Python not found and winget unavailable. Install Python 3.12+ from python.org. & goto :fail
    )
)

REM Node.js 20+
where node >nul 2>&1
if errorlevel 1 (
    if "!HAS_WINGET!"=="1" (
        echo   [.] Node.js not found - installing via winget...
        winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements --silent
        for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USERPATH=%%b"
        set "PATH=!PATH!;!USERPATH!;%ProgramFiles%\nodejs"
        where node >nul 2>&1 || (echo   [X] Node.js still missing. Open a new terminal and re-run setup.bat. & goto :fail)
    ) else (
        echo   [X] Node.js not found and winget unavailable. Install Node 20+ from nodejs.org. & goto :fail
    )
)

REM Docker Desktop
where docker >nul 2>&1
if errorlevel 1 (
    if "!HAS_WINGET!"=="1" (
        echo.
        echo   [!] Docker Desktop not found.
        echo       Docker Desktop uses WSL2 as its engine on Windows.
        echo         - Windows 11: usually no reboot
        echo         - Windows 10: WSL2 activation may require ONE reboot
        echo       Installing via winget now ^(this can take a few minutes^)...
        echo.
        winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
        echo.
        echo   [!] Docker Desktop install finished.
        echo       - If WSL2 activation prompted you to reboot, reboot now and re-run setup.bat.
        echo       - Otherwise, launch "Docker Desktop" once from the Start Menu, accept the
        echo         terms, then re-run setup.bat.
        goto :fail
    ) else (
        echo   [X] Docker not found and winget unavailable.
        echo       Install Docker Desktop manually ^(WSL2 may need to be enabled - 1 reboot^). & goto :fail
    )
)

REM Daemon running?
docker info >nul 2>&1
if errorlevel 1 (
    echo   [.] Docker daemon not running - attempting to launch Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else (
        echo   [X] Docker Desktop.exe not at expected path. Start it manually and re-run. & goto :fail
    )
    echo   [.] Waiting up to 90s for Docker daemon to come online...
    set /a wtries=0
    :wait_docker
    set /a wtries+=1
    if !wtries! GTR 45 (echo   [X] Docker daemon did not come online in 90s. Start Docker Desktop manually and re-run. & goto :fail)
    timeout /t 2 /nobreak > nul
    docker info >nul 2>&1
    if errorlevel 1 goto :wait_docker
)

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
