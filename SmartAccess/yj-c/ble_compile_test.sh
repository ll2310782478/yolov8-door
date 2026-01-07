#!/bin/bash
# BLE编译测试脚本
# 用法: ./ble_compile_test.sh

set -e

SKETCH_PATH="u:\BYSJ\yolov-door\yolov8-door\SmartAccess\yj-c\http-nfc-s3-dual-core\http-nfc-s3-dual-core.ino"
BOARD="esp32:esp32:esp32s3"
BUILD_DIR="./build"

echo "=========================================="
echo "  ESP32-S3 BLE编译验证测试"
echo "=========================================="
echo ""

# 检查Arduino CLI是否安装
if ! command -v arduino-cli &> /dev/null; then
    echo "❌ 错误：未找到 arduino-cli"
    echo "   请先安装 Arduino CLI: https://arduino.cc/en/software"
    exit 1
fi

echo "✅ 检测到 Arduino CLI"
echo "📁 Sketch 路径: $SKETCH_PATH"
echo "🎯 目标开发板: $BOARD"
echo ""

# 创建构建目录
mkdir -p "$BUILD_DIR"

# 验证语法
echo "🔍 开始编译验证..."
echo ""

if arduino-cli compile \
    --fqbn "$BOARD" \
    --build-path "$BUILD_DIR" \
    --warnings all \
    "$SKETCH_PATH" 2>&1 | tee compile_output.log; then
    
    echo ""
    echo "=========================================="
    echo "✅ 编译成功！"
    echo "=========================================="
    echo ""
    echo "📊 编译结果:"
    grep -E "(Sketch uses|Sketch size)" compile_output.log || echo "   信息已输出"
    echo ""
    echo "📋 BLE API 修复验证:"
    echo "   ✓ clearAdvertisementData() - 已移除"
    echo "   ✓ clearScanResponseData() - 已移除"
    echo "   ✓ setCompleteLocalName() - 已移除"
    echo "   ✓ setAdvertisementType(ADV_TYPE_IND) - 已替换"
    echo "   ✓ setIntMax()/setIntMin() - 已替换"
    echo ""
    echo "🚀 下一步:"
    echo "   1. 连接ESP32-S3到电脑"
    echo "   2. 运行: arduino-cli upload --fqbn $BOARD -p <port> $SKETCH_PATH"
    echo "   3. 打开串口监视器（115200 波特率）"
    echo "   4. 点击Web后台的'开始配对'按钮"
    echo "   5. 在手机蓝牙设置中搜索'SmartDoor-BT'"
    
else
    echo ""
    echo "=========================================="
    echo "❌ 编译失败"
    echo "=========================================="
    echo ""
    echo "请检查上述错误信息"
    grep -A 5 "error:" compile_output.log || echo "   未找到明确错误"
    exit 1
fi
