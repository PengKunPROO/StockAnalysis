@echo off
cd /d "%~dp0"
echo === Stopping Stock Agent ===

:: 1. Stop via run.py --stop
:: This uses taskkill /F /T on the backend PID from .stock-agent.pid
:: /T kills the process tree: backend + its child hermes chat subprocesses
:: but does NOT affect hermes agents the user started manually (different parent)
backend\.venv\Scripts\python.exe run.py --stop 2>NUL

:: 2. Fallback: kill only the process listening on port 8002 (NO /T)
:: Don't use /T here because we don't know if it has user-spawned children
timeout /t 1 /nobreak >NUL
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a (port 8002)
    taskkill /F /PID %%a >NUL 2>&1
)

:: 3. Clean PID file
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

echo All stopped.
timeout /t 1 /nobreak >NUL
