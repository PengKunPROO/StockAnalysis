@echo off
cd /d "%~dp0"
echo === Stock Agent ===

:: Kill any leftover processes
echo [CLEAN] Killing leftover processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do taskkill /F /T /PID %%a >NUL 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /F /T /PID %%a >NUL 2>&1
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

:: Git SSH
"C:\Program Files\Git\usr\bin\ssh-agent.exe" -s > "%TEMP%\ssh-agent.env" 2>NUL
for /f "tokens=*" %%i in ('type "%TEMP%\ssh-agent.env" ^| findstr SSH_AUTH_SOCK') do set %%i
for /f "tokens=*" %%i in ('type "%TEMP%\ssh-agent.env" ^| findstr SSH_AGENT_PID') do set %%i
"C:\Program Files\Git\usr\bin\ssh-add.exe" "%USERPROFILE%\.ssh\id_ed25519" 2>NUL

:: Build frontend if needed
if not exist "backend\static\index.html" (
    echo [BUILD] Building frontend...
    if not exist "frontend\node_modules\.package-lock.json" (
        cd frontend && call npm install && cd ..
    )
    cd frontend && call npm run build && cd ..
)

:: Start backend (detached, auto-opens browser)
echo [START] Starting Stock Agent...
backend\.venv\Scripts\python.exe run.py --bg

echo.
echo   URL: http://localhost:8002
echo   Stop: run stop.bat
echo.
