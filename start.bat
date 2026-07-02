@echo off
echo === Stock Agent 启动中 ===

:: SSH agent (for git push)
ssh-agent -s > NUL 2>&1
ssh-add %USERPROFILE%\.ssh\id_ed25519 > NUL 2>&1

:: 后端
echo [1/2] 启动后端...
start "StockAgent-Backend" cmd /c "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: 等待后端就绪
echo 等待后端启动...
timeout /t 4 /nobreak > NUL

:: 前端
echo [2/2] 启动前端...
start "StockAgent-Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo === 启动完成 ===
echo 后端: http://localhost:8000/docs
echo 前端: http://localhost:5173
echo.
pause
