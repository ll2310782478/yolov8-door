@echo off
REM SmartAccess 快速启动脚本
REM 使用项目虚拟环境启动后端服务

echo ========================================
echo   SmartAccess v2.1 启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查虚拟环境...
if not exist ".venv\Scripts\python.exe" (
    echo 错误: 虚拟环境不存在！
    echo 请先运行: python -m venv .venv
    pause
    exit /b 1
)
echo     虚拟环境已找到

echo.
echo [2/3] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo.
echo [3/3] 启动服务器...
echo     API服务: http://localhost:8000
echo     API文档: http://localhost:8000/docs
echo     管理界面: http://localhost:8000/web/hardware
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
