@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM SmartAccess 快速启动脚本
REM 使用项目虚拟环境启动后端服务
REM 版本: v2.3 (修复编码问题)

echo ========================================
echo   SmartAccess v2.3 启动脚本
echo ========================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM ============ 步骤 1: 检查虚拟环境 ============
echo [1/5] 检查虚拟环境...
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ❌ 错误: 虚拟环境不存在！
    echo.
    echo 解决方案:
    echo   1. 打开 PowerShell 或命令行
    echo   2. 切换到项目目录: cd u:\BYSJ\yolov-door\yolov8-door\SmartAccess
    echo   3. 创建虚拟环境: python -m venv .venv
    echo   4. 重新运行本脚本
    echo.
    pause
    exit /b 1
)
echo ✅ 虚拟环境已找到

REM ============ 步骤 2: 激活虚拟环境 ============
echo.
echo [2/5] 激活虚拟环境...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo ❌ 错误: 虚拟环境激活失败！
    echo.
    pause
    exit /b 1
)
echo ✅ 虚拟环境已激活

REM ============ 步骤 3: 检查依赖库 ============
echo.
echo [3/5] 检查依赖库（FastAPI, uvicorn, pymysql...）...
python -m pip list | findstr /i "fastapi uvicorn pymysql" >nul
if errorlevel 1 (
    echo ⚠️  警告: 部分依赖库可能缺失
    echo     正在安装依赖库...
    python -m pip install -r requirements.txt >nul 2>&1
    if errorlevel 1 (
        echo ❌ 错误: 依赖库安装失败！
        echo     请检查 requirements.txt 是否存在
        echo     或手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo ✅ 依赖库已安装
) else (
    echo ✅ 依赖库齐全
)

REM ============ 步骤 4: 检查数据库配置 ============
echo.
echo [4/5] 检查数据库配置...
if not exist "app\database.py" (
    echo ⚠️  警告: 数据库配置文件不找到 (app\database.py)
) else (
    echo ✅ 数据库配置文件已找到
)

REM ============ 步骤 5: 启动服务器 ============
echo.
echo [5/5] 启动服务器...
echo.
echo ========================================
echo   🌐 服务已启动
echo ========================================
echo.
echo 📍 访问地址:
echo    • API 服务:  http://localhost:8000
echo    • API 文档:  http://localhost:8000/docs (Swagger UI)
echo    • ReDoc:    http://localhost:8000/redoc
echo    • 管理界面:  http://localhost:8000/web/hardware
echo.
echo 📊 数据库配置:
echo    • 数据库: mysql+pymysql://root:123456@localhost:3306/smartaccess
echo.
echo ⚠️  按 Ctrl+C 停止服务器
echo.
echo ========================================
echo.

REM 启动 uvicorn 服务器
REM --reload: Auto-reload on file changes (dev mode)
REM --host 0.0.0.0: Allow remote access
REM --port 8000: Listen port
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

REM 服务器停止后的处理
echo.
echo ========================================
echo   ⚠️  服务已停止
echo ========================================
echo.
pause
