@echo off
chcp 65001 >nul
echo ========================================
echo   SmartAccess 快速启动
echo ========================================
echo.
cd /d "%~dp0"
echo 正在启动服务器...
echo.
echo访问地址:
echo   - 登录页面：http://localhost:8000/web/auth
echo   - API文档：http://localhost:8000/docs
echo.
echo 按Ctrl+C 停止服务
echo ========================================
echo.
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
