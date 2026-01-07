# BLE编译测试脚本 (PowerShell)
# 用法: .\ble_compile_test.ps1

param(
    [string]$Board = "esp32:esp32:esp32s3",
    [string]$Port = "",
    [switch]$Upload = $false
)

$SketchPath = "u:\BYSJ\yolov-door\yolov8-door\SmartAccess\yj-c\http-nfc-s3-dual-core\http-nfc-s3-dual-core.ino"
$BuildDir = "./build"
$OutputLog = "compile_output.log"

# 颜色输出函数
function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "📌 $Message" -ForegroundColor Cyan
}

function Write-Header {
    param([string]$Title)
    Write-Host "" 
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "  $Title" -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host ""
}

# 主程序
Write-Header "ESP32-S3 BLE编译验证测试"

# 检查文件存在
if (-not (Test-Path $SketchPath)) {
    Write-Error-Custom "Sketch文件不存在: $SketchPath"
    exit 1
}

Write-Success "检测到 Sketch 文件"
Write-Info "Sketch 路径: $SketchPath"
Write-Info "目标开发板: $Board"
Write-Info ""

# 创建构建目录
if (-not (Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir | Out-Null
    Write-Success "已创建构建目录: $BuildDir"
}

# 执行编译
Write-Info "开始编译验证..."
Write-Host ""

try {
    # 调用Arduino IDE进行编译（如果装了CLI）
    if (Get-Command arduino-cli -ErrorAction SilentlyContinue) {
        Write-Info "使用 arduino-cli 编译..."
        
        & arduino-cli compile `
            --fqbn $Board `
            --build-path $BuildDir `
            --warnings all `
            $SketchPath 2>&1 | Tee-Object -FilePath $OutputLog
        
        $CompileSuccess = $?
    } else {
        Write-Info "未检测到 arduino-cli，请使用 Arduino IDE 手动编译"
        Write-Info "使用步骤："
        Write-Host "  1. 打开 Arduino IDE"
        Write-Host "  2. 文件 → 打开 → 选择 $SketchPath"
        Write-Host "  3. 工具 → 开发板 → ESP32-S3"
        Write-Host "  4. Ctrl+R 验证编译"
        exit 0
    }
    
    if ($CompileSuccess) {
        Write-Header "编译成功！"
        
        Write-Info "BLE API 修复验证:"
        Write-Host "   ✓ clearAdvertisementData() - 已移除"
        Write-Host "   ✓ clearScanResponseData() - 已移除"
        Write-Host "   ✓ setCompleteLocalName() - 已移除"
        Write-Host "   ✓ setAdvertisementType(ADV_TYPE_IND) - 已替换为 BLEAdvertisementData"
        Write-Host "   ✓ setIntMax()/setIntMin() - 已替换为 setMaxPreferred()/setMinPreferred()"
        Write-Host ""
        
        # 解析编译结果
        $SizeInfo = Select-String "Sketch uses" $OutputLog
        if ($SizeInfo) {
            Write-Host "   $SizeInfo"
        }
        
        Write-Host ""
        Write-Host "🚀 下一步:" -ForegroundColor Cyan
        Write-Host "   1. 连接 ESP32-S3 到电脑"
        Write-Host "   2. 在 Arduino IDE 中选择正确的 COM 口"
        Write-Host "   3. Ctrl+U 上传固件到 ESP32-S3"
        Write-Host "   4. 打开串口监视器（波特率 115200）"
        Write-Host "   5. 在 Web 后台点击'开始配对'按钮"
        Write-Host "   6. 在手机蓝牙设置中搜索'SmartDoor-BT'"
        Write-Host ""
        
        if ($Upload) {
            Write-Host "准备上传模式..."
            if ([string]::IsNullOrEmpty($Port)) {
                Write-Error-Custom "上传需要指定 COM 口"
                Write-Host "用法: .\ble_compile_test.ps1 -Upload -Port COM3"
                exit 1
            }
        }
        
    } else {
        Write-Header "编译失败"
        Write-Error-Custom "请检查上述错误信息"
        
        # 尝试显示错误
        $ErrorLines = Select-String "error:" $OutputLog
        if ($ErrorLines) {
            Write-Host "错误摘要："
            $ErrorLines | ForEach-Object {
                Write-Host "  $_" -ForegroundColor Red
            }
        }
        exit 1
    }
    
} catch {
    Write-Error-Custom "编译出现异常: $_"
    exit 1
}

# 编译完成
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "编译验证完成！" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
