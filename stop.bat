@echo off
echo === Stopping Stock Agent ===

:: Kill processes listening on ports 8002 and 5173
echo [1/2] Stopping backend (port 8002)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a >NUL 2>&1
)

echo [2/2] Stopping frontend (port 5173)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a >NUL 2>&1
)

:: Also kill any orphaned hermes chat subprocesses
taskkill /F /IM hermes.exe >NUL 2>&1

:: Close cmd windows with StockAgent title
taskkill /FI "WINDOWTITLE eq StockAgent-BE*" /F >NUL 2>&1
taskkill /FI "WINDOWTITLE eq StockAgent-FE*" /F >NUL 2>&1

echo.
echo All stopped. Ports 8002 and 5173 should be free.
timeout /t 2 /nobreak >NUL
