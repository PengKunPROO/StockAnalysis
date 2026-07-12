@echo off
cd /d "%~dp0"

:: Kill any leftover processes on port 8002
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >NUL 2>&1
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

:: SSH
"C:\Program Files\Git\usr\bin\ssh-agent.exe" -s > "%TEMP%\ssh-agent.env" 2>NUL
for /f "tokens=*" %%i in ('type "%TEMP%\ssh-agent.env" ^| findstr SSH_AUTH_SOCK') do set %%i
for /f "tokens=*" %%i in ('type "%TEMP%\ssh-agent.env" ^| findstr SSH_AGENT_PID') do set %%i
"C:\Program Files\Git\usr\bin\ssh-add.exe" "%USERPROFILE%\.ssh\id_ed25519" 2>NUL

:: Build frontend if static dir doesn't exist
if not exist "backend\static\index.html" (
    echo [BUILD] Building frontend...
    :: Install deps if needed
    if not exist "frontend\node_modules\.package-lock.json" (
        cd frontend && call npm install && cd ..
    )
    cd frontend && call npm run build && cd ..
    if not exist "backend\static\index.html" (
        echo [ERROR] Frontend build failed!
        pause
        exit /b 1
    )
)

:: Start in background (pythonw, no window, auto-opens browser)
echo [START] Stock Agent starting in background...
backend\.venv\Scripts\pythonw.exe run.py --bg

:: Wait a moment then exit (pythonw runs detached)
timeout /t 3 /nobreak >NUL
