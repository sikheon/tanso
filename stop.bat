@echo off
setlocal
chcp 65001 > nul
title E.L.O Stop

echo ===============================================
echo   E.L.O - Stopping
echo ===============================================

echo [.] Killing uvicorn / next dev processes...
taskkill /F /FI "WINDOWTITLE eq E.L.O Backend*" > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq E.L.O Frontend*" > nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000 :8010 :3000"') do (
    taskkill /F /PID %%a > nul 2>&1
)

echo [.] Stopping Postgres container...
docker compose stop postgres > nul 2>&1

echo [OK] Stopped.
endlocal
pause
exit /b 0
