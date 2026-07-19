@echo off
cd /d "%~dp0"
echo === Stopping Stock Agent ===

:: 1. Stop via run.py --stop (graceful: scheduler shutdown + DB dispose)
backend\.venv\Scripts\python.exe run.py --stop 2>NUL

:: 2. Kill only the process listening on port 8002 (NO /T flag - don't kill children)
timeout /t 1 /nobreak >NUL
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a (port 8002)
    taskkill /F /PID %%a >NUL 2>&1
)

:: 3. Clean PID file
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

echo All stopped.
timeout /t 1 /nobreak >NUL
