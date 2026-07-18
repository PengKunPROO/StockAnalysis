@echo off
cd /d "%~dp0"
echo === Stock Agent ===

:: Kill any leftover processes on ports 8002 and 5173
echo [CLEAN] Killing leftover processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >NUL 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >NUL 2>&1
if exist ".stock-agent.pid" del /q ".stock-agent.pid"

:: Git SSH
echo [SSH]
"C:\Program Files\Git\usr\bin\ssh-agent.exe" -s > "%TEMP%\ssh-agent.env" 2>NUL
for /f "tokens=*" %%i in ('type "%TEMP%\ssh-agent.env" ^| findstr SSH_AUTH_SOCK') do set %%i
for /f "tokens=*" %%i in ('type "%TEMP%\ssh-agent.env" ^| findstr SSH_AGENT_PID') do set %%i
"C:\Program Files\Git\usr\bin\ssh-add.exe" "%USERPROFILE%\.ssh\id_ed25519" 2>NUL

:: Frontend deps (first run only)
if not exist "frontend\node_modules\.package-lock.json" (
    echo [DEPS] Installing frontend packages...
    cd frontend
    call npm install
    cd ..
)

:: Backend - pythonw + run.py --bg (windowless, PID-tracked)
echo [1/2] Starting backend on :8002...
backend\.venv\Scripts\pythonw.exe run.py --bg

:: Wait for backend to be ready
echo Waiting for backend...
set /a count=0
:wait_be
timeout /t 1 /nobreak >NUL
set /a count+=1
curl -s http://127.0.0.1:8002/api/v1/health >NUL 2>&1
if %errorlevel% neq 0 if %count% lss 15 goto wait_be
if %count% geq 15 echo WARNING: backend may not be ready

:: Frontend - hidden via VBS
echo [2/2] Starting frontend on :5173...
wscript "%~dp0fe_bg.vbs"

timeout /t 3 /nobreak >NUL
echo.
echo ========================
echo   Frontend: http://localhost:5173
echo   Backend : http://localhost:8002/docs
echo ========================
echo.
echo To stop: run stop.bat
echo.
pause
