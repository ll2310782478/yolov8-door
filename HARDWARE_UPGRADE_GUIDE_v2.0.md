# SmartAccess 硬件升级指南 - 多门禁系统 v2.0

## 概述

本系统已升级为支持多个独立的硬件门禁设备：

- **门禁1 (ESP8266)**: 纯远程控制模式，只支持来自服务器的远程开门指令
- **门禁2 (ESP32-S3)**: 远程+NFC混合模式，同时支持远程开门和NFC卡片刷卡

## 硬件设备信息

### 门禁1 - ESP8266（远程控制模式）

**设备配置**
```
设备ID: door_controller_1
设备名称: 门禁1
设备类型: door_controller
设备模式: remote_only
位置: 实验室大门
```

**支持的功能**
- ✅ 远程开门（通过服务器轮询命令）
- ✅ 多源触发支持（人脸识别、蓝牙、二维码等由服务器指令下发）
- ✅ 两个独立的门锁控制（门1/门2）
- ✅ 设备心跳检测
- ✅ 统一开门接口 `openDoor(doorId, source)`

**不支持的功能**
- ❌ NFC卡片读取和刷卡（已完全移除）

**硬件引脚**
```
门1继电器: GPIO12 (D8)
门2继电器: GPIO13 (D7)
状态LED: GPIO2 (D4)
```

**固件版本**: v5.0（纯远程控制版）

**工作流程**
1. 设备启动后注册到服务器 (`POST /api/hardware/devices`)
2. 定期发送心跳信号 (`POST /api/hardware/devices/{device_id}/heartbeat`)
3. 轮询服务器命令 (`GET /api/hardware/nfc/command/poll?device_id=door_controller_1`)
4. 当收到 `OPEN` 命令时执行开门操作
5. 开门3秒后自动关闭

---

### 门禁2 - ESP32-S3（远程+NFC混合模式）

**设备配置**
```
设备ID: door_controller_2
设备名称: 门禁2
设备类型: door_controller_nfc
设备模式: remote_nfc
位置: 办公室
```

**支持的功能**
- ✅ 远程开门（通过服务器轮询命令）
- ✅ NFC卡片读取和刷卡
- ✅ 卡片权限在线比对（设备上报卡号 → 服务器验证 → 返回开门指令）
- ✅ 多源触发支持（人脸识别、蓝牙、二维码等）
- ✅ 两个独立的门锁控制（门1/门2）
- ✅ 设备心跳检测
- ✅ 统一开门接口 `openDoor(doorId, source)`

**硬件引脚**
```
门1继电器: GPIO18 (D18)
门2继电器: GPIO17 (D17)
状态LED: GPIO7 (D4)

NFC读卡器 (PN532):
SDA: GPIO8 (D5)
SCL: GPIO9 (D6)
IRQ: GPIO6 (D9)
```

**固件版本**: v1.0（远程+NFC版）

**工作流程**

*远程开门流程*
1. 后台调用 `POST /api/hardware/remote-door/open` 创建开门任务
2. 设备轮询 `GET /api/hardware/nfc/command/poll?device_id=door_controller_2`
3. 获取命令并执行开门
4. 3秒后自动关闭

*NFC刷卡流程*
1. 用户刷NFC卡
2. 设备读取卡号并上报到服务器
3. `GET /api/hardware/nfc-scan?card_uid=XX-XX-XX-XX&device_id=door_controller_2`
4. 服务器验证卡片权限、时效、设备绑定等
5. 返回 `OPEN` 或 `DENY` 结果
6. 设备收到 `OPEN` 后执行开门操作

---

## 数据库迁移

### 需要执行的SQL语句

```sql
-- 1. 在 hardware_devices 表添加 device_mode 列
ALTER TABLE hardware_devices ADD COLUMN device_mode VARCHAR(50) DEFAULT 'remote_only';

-- 2. 在 nfc_cards 表添加 device_id 列（用于卡片绑定特定设备）
ALTER TABLE nfc_cards ADD COLUMN device_id VARCHAR(50) NULL;

-- 3. 为新列添加索引（可选，提高查询性能）
ALTER TABLE nfc_cards ADD INDEX idx_device_id (device_id);
```

### 迁移后的现有数据处理

如果系统中已有NFC卡片记录，建议：
1. 对于门禁2要使用的卡片，更新其 `device_id` 为 `door_controller_2`
2. 保持 `device_id` 为 NULL 的卡片对所有设备有效（向后兼容）

---

## API 接口变化

### 新增/变更的接口

#### 1. 创建硬件设备时支持 device_mode

```bash
POST /api/hardware/devices
Content-Type: application/json

{
  "device_id": "door_controller_2",
  "device_name": "门禁2",
  "device_type": "door_controller_nfc",
  "device_mode": "remote_nfc",
  "location": "办公室",
  "ip_address": "192.168.x.x"
}
```

#### 2. NFC扫描接口支持GET和POST，验证设备模式

```bash
# GET 方式（设备端调用）
GET /api/hardware/nfc-scan?card_uid=AA-BB-CC-DD&device_id=door_controller_2

# POST 方式
POST /api/hardware/nfc-scan
Content-Type: application/json

{
  "card_uid": "AA-BB-CC-DD",
  "device_id": "door_controller_2"
}

# 响应示例
{
  "action": "OPEN",        // 或 "DENY"
  "door": "door1",         // 要开启的门
  "msg": "欢迎 张三"
}
```

**验证逻辑**
- ✅ 设备必须存在
- ✅ 设备必须支持NFC (device_mode = "remote_nfc")
- ✅ 卡片必须存在且未被禁用
- ✅ 卡片权限必须有效
- ✅ 如果卡片指定了device_id，必须与请求设备匹配

#### 3. 创建NFC卡片时支持device_id绑定

```bash
POST /api/hardware/nfc/cards
Content-Type: application/json

{
  "user_id": 1,
  "card_number": "AA-BB-CC-DD",
  "card_name": "张三的NFC卡",
  "door_id": "door1",           // 默认开启哪个门
  "device_id": "door_controller_2",  // 可选：绑定到特定设备
  "permission_end_date": "2025-12-31T23:59:59",
  "max_daily_uses": 0           // 0=无限制
}
```

**device_id说明**
- 若为 NULL（不指定）：卡片对所有支持NFC的设备有效
- 若为具体值（如"door_controller_2"）：卡片仅对该设备有效

#### 4. 远程开门接口保持不变

```bash
POST /api/hardware/remote-door/open
Content-Type: application/json

{
  "device_id": "door_controller_1",
  "door_id": 1,
  "source": "remote"
}
```

**支持的source值**
- `remote` - 远程控制（默认）
- `face` - 人脸识别触发
- `nfc` - NFC卡片触发
- `bluetooth` - 蓝牙触发
- `qrcode` - 二维码扫描

---

## 固件升级步骤

### 门禁1 (ESP8266) 升级

**文件**: `yj-c/esp8266_pn532_v2.ino` (已修改为v5.0)

**变更内容**
- 完全移除 NFC 库依赖 (`Adafruit_PN532.h`)
- 完全移除 NFC 初始化和扫描代码
- 更新设备标识为 `door_controller_1` 和 `门禁1`
- 添加设备模式标识 `DEVICE_MODE = "remote_only"`
- 简化启动日志，移除 NFC 相关信息

**编译和上传**
```bash
# 使用 Arduino IDE 或 PlatformIO
# 选择 Board: NodeMCU 1.0 (ESP8266-12E)
# 速率: 115200 baud
```

### 门禁2 (ESP32-S3) 新部署

**文件**: `yj-c/esp32_s3_nfc_controller.ino` (新建，v1.0)

**功能**
- 远程开门：轮询 `/api/hardware/nfc/command/poll`
- NFC刷卡：监听卡片，上报到 `/api/hardware/nfc-scan`
- 设备模式：`remote_nfc`
- 两个门锁控制

**编译和上传**
```bash
# 使用 Arduino IDE 或 PlatformIO
# 选择 Board: ESP32-S3-DevKitC-1-N8
# 速率: 115200 baud
```

**依赖库**
```
Adafruit_PN532
ArduinoJson
```

---

## 调试和故障排查

### 门禁1 (ESP8266)

**启动日志**
```
╔════════════════════════════════════════════╗
║   ESP8266 智能门禁控制器 v5.0             ║
║   模式: 门禁1 - 纯远程控制                ║
╚════════════════════════════════════════════╝

✅ WiFi已连接
📍 IP地址: 192.168.x.x
🌐 服务器: 192.168.188.116:8000
[REG] 设备注册成功
✨ 系统启动完成，等待远程指令...
```

**常见问题**

| 问题 | 解决方案 |
|------|---------|
| WiFi连接失败 | 检查SSID和密码配置 |
| 设备注册失败 | 检查服务器连接和设备ID唯一性 |
| 无法接收远程指令 | 检查轮询间隔、服务器状态、设备是否在线 |
| 门锁无响应 | 检查硬件引脚连接、继电器供电 |

### 门禁2 (ESP32-S3)

**启动日志**
```
╔════════════════════════════════════════════╗
║   ESP32-S3 智能门禁控制器 v1.0            ║
║   模式: 门禁2 - 远程+NFC控制              ║
╠════════════════════════════════════════════╣
║  功能: 远程开门 + NFC刷卡                 ║
║  NFC: 已启用，支持卡片读取和比对         ║
╚════════════════════════════════════════════╝

✅ PN532 初始化成功，固件版本: 0x32000407
✅ PN532 SAM 配置成功 (IRQ 模式)
✅ WiFi已连接
📍 IP地址: 192.168.x.x
🌐 服务器: 192.168.188.116:8000
✨ 系统启动完成，等待远程指令和NFC卡片...
```

**常见问题**

| 问题 | 解决方案 |
|------|---------|
| PN532 未找到 | 检查I2C接线、SDA/SCL引脚配置、地址是否正确 |
| NFC无法读卡 | 检查IRQ引脚接线、卡片距离、PN532固件版本 |
| 卡片读到但返回DENY | 检查卡片权限、device_id绑定、数据库中是否存在 |
| WiFi或远程指令问题 | 参考门禁1的故障排查 |

---

## 系统测试清单

### 功能测试

#### 门禁1测试
- [ ] 设备能成功注册到服务器
- [ ] 设备定期发送心跳，状态显示为 "online"
- [ ] 通过 `/api/hardware/remote-door/open` 接口远程开门1
- [ ] 通过 `/api/hardware/remote-door/open` 接口远程开门2
- [ ] 开门3秒后自动关闭
- [ ] LED状态灯亮起和熄灭符合预期

#### 门禁2测试
- [ ] 设备能成功注册到服务器，device_mode = "remote_nfc"
- [ ] NFC模块初始化成功（见启动日志）
- [ ] 通过 `/api/hardware/remote-door/open` 接口远程开门1
- [ ] 通过 `/api/hardware/remote-door/open` 接口远程开门2
- [ ] 刷已注册的NFC卡，收到 `OPEN` 响应并执行开门
- [ ] 刷未知NFC卡，收到 `DENY` 响应并拒绝开门
- [ ] 刷已禁用的NFC卡，收到 `DENY` 响应
- [ ] 刷权限已过期的NFC卡，收到 `DENY` 响应
- [ ] 刷指定给其他设备的NFC卡（device_id为其他值），收到 `DENY` 响应
- [ ] 开门3秒后自动关闭

#### 多设备隔离测试
- [ ] 用门禁1的device_id轮询，不会收到门禁2相关的命令
- [ ] 用门禁2的device_id上报NFC卡，能正确比对和响应
- [ ] 为卡片指定 device_id="door_controller_2" 后，门禁1的NFC(如果启用)上报该卡拒绝

### 数据库验证
```sql
-- 检查硬件设备
SELECT device_id, device_name, device_mode FROM hardware_devices;

-- 检查NFC卡片及其设备绑定
SELECT id, card_number, device_id, is_active FROM nfc_cards;

-- 检查访问日志
SELECT user_id, access_type, status, device_id, timestamp FROM access_logs 
ORDER BY timestamp DESC LIMIT 20;
```

---

## 集成建议

### 后端启动

```bash
cd yolov8-door/SmartAccess

# 创建/迁移数据库
python -c "from app.database import init_db; init_db()"

# 启动FastAPI服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端集成（如有）

如果前端需要区分两个设备：

```javascript
// 获取所有设备列表
fetch('/api/hardware/devices')
  .then(r => r.json())
  .then(devices => {
    devices.forEach(dev => {
      if (dev.device_mode === 'remote_only') {
        console.log('门禁1:', dev.device_name);
      } else if (dev.device_mode === 'remote_nfc') {
        console.log('门禁2:', dev.device_name, '(支持NFC)');
      }
    });
  });

// 远程开门调用
async function openDoor(deviceId, doorId) {
  const resp = await fetch('/api/hardware/remote-door/open', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: deviceId,
      door_id: doorId,
      source: 'remote'
    })
  });
  return resp.json();
}

// NFC卡管理（仅在支持NFC的设备上）
async function createNFCCard(userId, cardNumber, deviceId) {
  const resp = await fetch('/api/hardware/nfc/cards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      card_number: cardNumber,
      device_id: deviceId,  // 指定设备
      door_id: 'door1'
    })
  });
  return resp.json();
}
```

---

## 后续扩展

### 支持更多设备

如需添加门禁3、门禁4等：

1. 选择合适的硬件平台（ESP32、STM32等）
2. 定义新的 device_id（如 `door_controller_3`）
3. 选择 device_mode：
   - `remote_only` - 仅远程控制
   - `remote_nfc` - 远程+NFC
   - `remote_nfc_bluetooth` - 远程+NFC+蓝牙（未来）
4. 烧录对应的固件
5. 后台系统会自动支持（无需代码改动）

### 支持新的认证方式

例如添加蓝牙开门：

1. 在ESP32-S3上添加蓝牙模块代码
2. 定义新的 device_mode（如 `remote_nfc_bluetooth`）
3. 设备上报蓝牙认证 → 服务器验证 → 返回开门指令
4. 逻辑与NFC完全相同

---

## 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| v2.0 | 2026-01-03 | 支持多设备架构，门禁1纯远程，门禁2远程+NFC |
| v1.0 | 之前 | 单一设备，集远程+NFC于一身 |

---

**文档维护**: SmartAccess Team  
**最后更新**: 2026-01-03
