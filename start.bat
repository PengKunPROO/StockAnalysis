@echo off
cd /d "%~dp0"
echo === Stock Agent ===

:: Kill any leftover processes on ports 8002 and 5173
echo [CLEAN] Killing leftover processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >NUL 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >NUL 2>&1

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

:: Backend
echo [1/2] Starting backend on :8002...
start "StockAgent-BE" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002"

:: Wait
echo Waiting for backend...
set /a count=0
:wait_be
timeout /t 2 /nobreak >NUL
set /a count+=2
curl -s http://127.0.0.1:8002/api/v1/health >NUL 2>&1
if %errorlevel% neq 0 if %count% lss 40 goto wait_be
if %count% geq 40 echo WARNING: backend may not be ready

:: Frontend
echo [2/2] Starting frontend on :5173...
start "StockAgent-FE" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 3 /nobreak >NUL
echo.
echo ========================
echo   Backend : http://localhost:8002/docs
echo   Frontend: http://localhost:5173
echo ========================
echo.
echo To stop: close both StockAgent-BE and StockAgent-FE windows,
echo   or run: taskkill /FI "WINDOWTITLE eq StockAgent-*" /F
echo.
pause
