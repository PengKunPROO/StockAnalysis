@echo off
cd /d "%~dp0"
echo === Stopping Stock Agent ===

:: 1. Stop via run.py --stop (graceful: scheduler shutdown + DB dispose)
backend\.venv\Scripts\python.exe run.py --stop 2>NUL

:: 2. Kill any process on port 8002 (fallback)
timeout /t 1 /nobreak >NUL
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /T /PID %%a >NUL 2>&1
)

:: 3. Kill any process on port 5173 (Vite dev, if running)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /T /PID %%a >NUL 2>&1
)

:: 4. Kill orphaned hermes subprocesses spawned by the backend
for /f "tokens=2" %%p in ('tasklist /v /fo csv ^| findstr "StockAgent-BE" ^| findstr hermes') do (
    taskkill /F /PID %%p >NUL 2>&1
)

:: 5. Clean PID file
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

echo All stopped.
timeout /t 1 /nobreak >NUL
