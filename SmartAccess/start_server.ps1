# SmartAccess 快速启动脚本 (PowerShell)
# 使用项目虚拟环境启动后端服务
# 版本: v2.2 改进版（增强错误检查和日志）

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  SmartAccess v2.2 启动脚本 (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot
$ErrorActionPreference = "Continue"

# ============ 步骤 1: 检查虚拟环境 ============
Write-Host "[1/5] 检查虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host ""
    Write-Host "❌ 错误: 虚拟环境不存在！" -ForegroundColor Red
    Write-Host ""
    Write-Host "解决方案:" -ForegroundColor Yellow
    Write-Host "  1. 打开 PowerShell (管理员)"
    Write-Host "  2. 切换到项目目录: cd u:\BYSJ\yolov-door\yolov8-door\SmartAccess"
    Write-Host "  3. 创建虚拟环境: python -m venv .venv"
    Write-Host "  4. 重新运行本脚本"
    Write-Host ""
    Read-Host "按任意键退出"
    exit 1
}
Write-Host "✅ 虚拟环境已找到" -ForegroundColor Green

# ============ 步骤 2: 激活虚拟环境 ============
Write-Host ""
Write-Host "[2/5] 激活虚拟环境..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ 错误: 虚拟环境激活失败！" -ForegroundColor Red
    Write-Host ""
    Read-Host "按任意键退出"
    exit 1
}
Write-Host "✅ 虚拟环境已激活" -ForegroundColor Green

# ============ 步骤 3: 检查 Python 和依赖 ============
Write-Host ""
Write-Host "[3/5] 检查 Python 版本和依赖库..." -ForegroundColor Yellow
$pythonVersion = & python --version 2>&1
Write-Host "    Python版本: $pythonVersion" -ForegroundColor Cyan

# 检查关键依赖
$missingDeps = $false
$requiredPackages = @("fastapi", "uvicorn", "pymysql")

foreach ($package in $requiredPackages) {
    $checkCmd = python -c "import $package" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    ⚠️  缺失: $package" -ForegroundColor Yellow
        $missingDeps = $true
    } else {
        Write-Host "    ✅ 已安装: $package" -ForegroundColor Cyan
    }
}

if ($missingDeps) {
    Write-Host ""
    Write-Host "    正在安装缺失的依赖库..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "❌ 错误: 依赖库安装失败！" -ForegroundColor Red
        Write-Host "    请检查 requirements.txt 是否存在" -ForegroundColor Red
        Read-Host "按任意键退出"
        exit 1
    }
    Write-Host "✅ 依赖库已安装" -ForegroundColor Green
} else {
    Write-Host "✅ 所有依赖库齐全" -ForegroundColor Green
}

# ============ 步骤 4: 检查项目结构 ============
Write-Host ""
Write-Host "[4/5] 检查项目结构..." -ForegroundColor Yellow
$requiredFiles = @(
    "app\main.py",
    "app\database.py",
    "requirements.txt"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "    ✅ 已找到: $file" -ForegroundColor Cyan
    } else {
        Write-Host "    ⚠️  缺失: $file" -ForegroundColor Yellow
    }
}

# ============ 步骤 5: 启动服务器 ============
Write-Host ""
Write-Host "[5/5] 启动服务器..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  🌐 服务已启动" -ForegroundColor Green
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 访问地址:" -ForegroundColor Cyan
Write-Host "   • API 服务:  http://localhost:8000" -ForegroundColor Green
Write-Host "   • API 文档:  http://localhost:8000/docs (Swagger UI)" -ForegroundColor Green
Write-Host "   • ReDoc:    http://localhost:8000/redoc" -ForegroundColor Green
Write-Host "   • 管理界面:  http://localhost:8000/web/hardware" -ForegroundColor Green
Write-Host ""
Write-Host "📊 数据库配置:" -ForegroundColor Cyan
Write-Host "   • 数据库: mysql+pymysql://root:123456@localhost:3306/smartaccess" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# 启动 uvicorn 服务器
# --reload: 文件变化时自动重启（开发模式）
# --host 0.0.0.0: 允许远程访问
# --port 8000: 监听端口
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 服务器停止后的处理
Write-Host ""
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  ⚠️  服务已停止" -ForegroundColor Yellow
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""
Read-Host "按任意键退出"

