# 硬件升级快速启动指南

## 📋 升级概览

本次升级将系统从**单一门禁设备**升级为**多设备架构**：

| 设备 | 模式 | 功能 | 固件文件 |
|------|------|------|---------|
| **门禁1** (ESP8266) | remote_only | 远程开门 | `esp8266_pn532_v2.ino` (v5.0) |
| **门禁2** (ESP32-S3) | remote_nfc | 远程+NFC | `esp32_s3_nfc_controller.ino` (v1.0) |

## 🔧 升级步骤

### 1️⃣ 备份数据库
```bash
# MySQL
mysqldump -u root -p smartaccess > backup_before_upgrade.sql
```

### 2️⃣ 执行数据库迁移
```bash
# 在MySQL中执行迁移脚本
mysql -u root -p smartaccess < MIGRATION_SCRIPT_v2.0.sql

# 验证迁移成功
mysql -u root -p smartaccess -e "SELECT * FROM hardware_devices;"
```

### 3️⃣ 更新后端代码

后端代码已自动支持新的数据模型，主要变更包括：

✅ `app/models.py`
- HardwareDevice 添加 `device_mode` 字段
- NFCCard 添加 `device_id` 字段

✅ `app/routers/hardware.py`
- 创建/更新设备时支持 `device_mode`
- NFC扫描接口验证设备模式和NFC支持
- NFC卡片支持设备绑定

### 4️⃣ 升级门禁1硬件（ESP8266）

**变更内容**
- ✅ 移除所有NFC相关代码
- ✅ 更新设备标识为 `door_controller_1`
- ✅ 设置模式为 `remote_only`

**操作步骤**
1. 在Arduino IDE中打开 `yj-c/esp8266_pn532_v2.ino`（已更新为v5.0）
2. 配置WiFi参数：
   ```cpp
   const char* SSID        = "你的WiFi名称";
   const char* PASSWORD    = "你的WiFi密码";
   const char* SERVER_HOST = "服务器IP";
   const int   SERVER_PORT = 8000;
   ```
3. 选择开发板：**NodeMCU 1.0 (ESP8266-12E)**
4. 编译并上传

### 5️⃣ 部署门禁2硬件（ESP32-S3）

**新增功能**
- ✅ 远程开门（轮询服务器命令）
- ✅ NFC卡片读取和验证
- ✅ 卡号上报 → 权限比对 → 下发开门

**操作步骤**
1. 在Arduino IDE中打开 `yj-c/esp32_s3_nfc_controller.ino`（新建文件）
2. 安装依赖库：
   - Adafruit PN532
   - ArduinoJson (>= 6.0)
3. 配置WiFi和服务器参数（同门禁1）
4. 确认硬件接线：
   ```
   PN532 NFC模块:
     SDA: GPIO8
     SCL: GPIO9
     IRQ: GPIO6
   门锁继电器:
     门1: GPIO18
     门2: GPIO17
   LED: GPIO7
   ```
5. 选择开发板：**ESP32-S3-DevKitC-1-N8**
6. 编译并上传

### 6️⃣ 验证部署

**后端验证**
```bash
# 启动FastAPI（在SmartAccess目录）
cd SmartAccess
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 检查日志是否出现错误
```

**硬件验证**
```bash
# 打开串口监视器 (115200 baud)

# 门禁1应显示:
# ✅ WiFi已连接
# [REG] 设备注册成功
# 💓 心跳: 成功

# 门禁2应显示:
# ✅ PN532 初始化成功
# ✅ WiFi已连接
# [REG] 设备注册成功
```

**API验证**
```bash
# 检查设备是否注册
curl http://localhost:8000/api/hardware/devices

# 应返回两个设备:
# [{
#   "device_id": "door_controller_1",
#   "device_name": "门禁1",
#   "device_mode": "remote_only"
# }, {
#   "device_id": "door_controller_2",
#   "device_name": "门禁2",
#   "device_mode": "remote_nfc"
# }]
```

## 🧪 功能测试

### 门禁1 测试
```bash
# 远程开门1
curl -X POST http://localhost:8000/api/hardware/remote-door/open \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "door_controller_1",
    "door_id": 1,
    "source": "remote"
  }'

# 预期：门1会开启3秒并自动关闭
```

### 门禁2 测试 - 远程开门
```bash
# 远程开门2
curl -X POST http://localhost:8000/api/hardware/remote-door/open \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "door_controller_2",
    "door_id": 2,
    "source": "remote"
  }'
```

### 门禁2 测试 - NFC卡片

**前置：创建NFC卡片**
```bash
# 先从硬件获取卡号，假设为 AA-BB-CC-DD

# 创建卡片
curl -X POST http://localhost:8000/api/hardware/nfc/cards \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "card_number": "AA-BB-CC-DD",
    "card_name": "我的NFC卡",
    "door_id": "door1",
    "device_id": "door_controller_2"
  }'
```

**刷卡测试**
```bash
# 在门禁2上刷卡，设备会自动上报:
# GET /api/hardware/nfc-scan?card_uid=AA-BB-CC-DD&device_id=door_controller_2

# 如果验证成功，门会自动开启
# 检查访问日志:
curl http://localhost:8000/api/access-logs
```

## 📊 关键配置对照表

### WiFi配置
```cpp
// 两个设备都需要配置
const char* SSID        = "lll";
const char* PASSWORD    = "12345678";
const char* SERVER_HOST = "192.168.188.116";
const int   SERVER_PORT = 8000;
```

### 设备标识
```cpp
// 门禁1 (ESP8266)
const char* DEVICE_ID   = "door_controller_1";
const char* DEVICE_NAME = "门禁1";
const char* DEVICE_MODE = "remote_only";

// 门禁2 (ESP32-S3)
const char* DEVICE_ID   = "door_controller_2";
const char* DEVICE_NAME = "门禁2";
const char* DEVICE_MODE = "remote_nfc";
```

## 🚨 常见问题

**Q: 升级后现有的NFC卡片还能用吗？**
A: 可以，但需要检查：
- 如果之前的设备ID是 `nfc_reader_01`，改为 `door_controller_1`
- 卡片的 `device_id` 字段会默认为 NULL（对所有设备有效）
- 如需限制卡片仅在门禁2使用，手动更新 `device_id` 为 `door_controller_2`

**Q: 门禁1能用NFC吗？**
A: 不能，NFC代码已完全移除以减少固件体积和复杂度

**Q: 能否添加门禁3？**
A: 可以，选择合适的硬件平台（如另一个ESP32-S3），定义新的 `device_id` 和 `device_mode`，系统会自动支持

**Q: 数据库回滚怎么做？**
A: 执行 `MIGRATION_SCRIPT_v2.0.sql` 中的回滚脚本

## 📞 支持

如遇到问题，请查看：
- 详细文档：`HARDWARE_UPGRADE_GUIDE_v2.0.md`
- 数据库脚本：`MIGRATION_SCRIPT_v2.0.sql`
- 固件代码：
  - `yj-c/esp8266_pn532_v2.ino` (门禁1)
  - `yj-c/esp32_s3_nfc_controller.ino` (门禁2)

---

**升级时间**: ~20分钟  
**难度**: ⭐⭐ (中等)  
**最后更新**: 2026-01-03
