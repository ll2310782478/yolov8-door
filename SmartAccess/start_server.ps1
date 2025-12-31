# SmartAccess 快速启动脚本 (PowerShell)
# 使用项目虚拟环境启动后端服务

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  SmartAccess v2.1 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

Write-Host "[1/3] 检查虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "错误: 虚拟环境不存在！" -ForegroundColor Red
    Write-Host "请先运行: python -m venv .venv" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}
Write-Host "    虚拟环境已找到" -ForegroundColor Green

Write-Host ""
Write-Host "[2/3] 检查依赖..." -ForegroundColor Yellow
Write-Host "    Python版本:" -ForegroundColor Gray
& .\.venv\Scripts\python.exe --version

Write-Host ""
Write-Host "[3/3] 启动服务器..." -ForegroundColor Yellow
Write-Host "    API服务: http://localhost:8000" -ForegroundColor Green
Write-Host "    API文档: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "    管理界面: http://localhost:8000/web/hardware" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
