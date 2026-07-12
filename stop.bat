@echo off
cd /d "%~dp0"
echo === Stopping Stock Agent ===

:: Method 1: via run.py --stop
backend\.venv\Scripts\python.exe run.py --stop 2>NUL

:: Method 2: kill any process on port 8002 (fallback)
timeout /t 1 /nobreak >NUL
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a >NUL 2>&1
)

:: Kill any orphaned hermes subprocesses
taskkill /F /IM hermes.exe >NUL 2>&1

:: Clean PID file
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

echo All stopped.
timeout /t 1 /nobreak >NUL
