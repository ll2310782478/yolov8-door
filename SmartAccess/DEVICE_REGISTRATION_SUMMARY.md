# 🎯 设备注册完整实现总结

## 📌 核心概念

设备注册是 NFC 门禁系统的**第一步**。在硬件可以工作之前，需要：

1. **在后端系统中登记设备信息** → 创建 `HardwareDevice` 数据库记录
2. **硬件自动注册或手动配置** → 将设备 ID 与后端关联
3. **定期发送心跳信号** → 保持在线状态标记

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│ 🌐 Web UI 管理员界面 (/web/nfc 或 /web/hardware)            │
│  • 注册新设备                                               │
│  • 查看设备列表                                            │
│  • 编辑设备信息                                            │
│  • 监控在线状态                                            │
└────────────────┬────────────────────────────────────────────┘
                 │
        HTTP REST API 调用
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 🖥️  FastAPI 后端 (http://localhost:8000)                    │
│  • POST   /api/hardware/devices           (注册)            │
│  • GET    /api/hardware/devices           (列表)            │
│  • PUT    /api/hardware/devices/{id}      (更新)            │
│  • DELETE /api/hardware/devices/{id}      (删除)            │
│  • POST   /api/hardware/devices/{id}/heartbeat (心跳)       │
└────────────────┬────────────────────────────────────────────┘
                 │
        存储/查询设备信息
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 🗄️  MySQL 数据库                                            │
│  hardware_devices 表：                                      │
│  • device_id (唯一 ID)                                      │
│  • device_name (显示名称)                                   │
│  • device_type (类型: nfc_reader/door_lock/camera)          │
│  • location (物理位置)                                      │
│  • connection_status (在线/离线)                            │
│  • last_heartbeat (最后心跳时间)                            │
│  • firmware_version (固件版本)                              │
│  • ip_address (设备 IP)                                     │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ HTTP 心跳 + 命令轮询
         │
         │
┌────────┴──────────────────────────────────────────────────────┐
│ 🔌 硬件设备 (ESP8266 + PN532)                                 │
│  • 启动时调用 registerDevice() 注册自己                       │
│  • 每 30 秒调用 sendHeartbeat() 保活                          │
│  • 每 5 秒调用 pollCommand() 获取扫描命令                     │
│  • 读到卡片后上报到后端进行权限检查                          │
└───────────────────────────────────────────────────────────────┘
```

---

## 📂 文件清单

### 后端文件

| 文件 | 说明 |
|------|------|
| `app/models.py` | HardwareDevice 数据模型 |
| `app/routers/hardware.py` | 硬件设备 API 路由 |
| `app/main.py` | FastAPI 应用主文件 |

### 硬件固件文件

| 文件 | 说明 |
|------|------|
| `yj-c/esp8266_pn532_with_registration.ino` | ✨ **新增**：包含注册和心跳功能的完整固件 |
| `yj-c/esp8266_pn532_nfc_reader.ino` | 原始版本（不包含注册功能） |
| `yj-c/README.md` | 硬件设置和库配置指南 |
| `yj-c/HARDWARE_SETUP_QUICK_GUIDE.md` | ✨ **新增**：硬件配置快速参考 |

### 文档文件

| 文件 | 说明 |
|------|------|
| `DEVICE_REGISTRATION_GUIDE.md` | ✨ **新增**：完整的设备注册实现指南 |
| `API_TESTING_GUIDE.md` | ✨ **新增**：API 端点测试指南 |
| `DEVICE_SELECTION_GUIDE.md` | 完整工作流程文档 |

### 测试脚本

| 文件 | 说明 |
|------|------|
| `scripts/test_device_integration.py` | ✨ **新增**：设备注册端到端集成测试脚本 |

---

## 🔄 完整工作流程

### 场景 1：自动注册（推荐）

```
步骤 1: 配置硬件固件
  │
  ├─ 打开 esp8266_pn532_with_registration.ino
  ├─ 修改以下配置：
  │  • SSID = "你的WiFi名"
  │  • PASSWORD = "WiFi密码"
  │  • SERVER_HOST = "192.168.1.100"  # 后端IP
  │  • DEVICE_ID = "nfc_reader_01"
  │  • DEVICE_NAME = "一楼门禁"
  │  • DEVICE_LOCATION = "主入口"
  └─ 保存并烧录到 ESP8266

步骤 2: 硬件启动（自动注册）
  │
  ├─ ESP8266 连接 WiFi
  ├─ 调用 registerDevice() 向后端发送设备信息
  │  POST /api/hardware/devices 
  │  {
  │    "device_id": "nfc_reader_01",
  │    "device_name": "一楼门禁",
  │    "device_type": "nfc_reader",
  │    "location": "主入口",
  │    "ip_address": "192.168.1.102"
  │  }
  └─ 后端创建 HardwareDevice 记录，返回 201

步骤 3: 定期保活（自动进行）
  │
  ├─ 每 30 秒调用 sendHeartbeat()
  │  POST /api/hardware/devices/nfc_reader_01/heartbeat
  │  {
  │    "connection_status": "online",
  │    "firmware_version": "1.1",
  │    "ip_address": "192.168.1.102"
  │  }
  └─ 后端更新 last_heartbeat，设置 connection_status = "online"

步骤 4: 使用设备
  │
  ├─ Web UI 访问 /web/nfc
  ├─ 看到设备在线状态（绿色指示）
  ├─ 点击"触发扫描"按钮
  ├─ 硬件开始等待卡片
  ├─ 用户刷卡
  ├─ 硬件读卡并上报结果
  └─ Web UI 显示扫描结果
```

### 场景 2：手动注册

```
步骤 1: 管理员手动注册设备
  │
  ├─ 访问 Web UI: http://localhost:8000/web/hardware
  ├─ 填写表单：
  │  • 设备 ID: nfc_reader_01
  │  • 设备名称: 一楼门禁
  │  • 设备类型: nfc_reader
  │  • 位置: 主入口
  └─ 点击"注册设备"
      → 前端发送 POST /api/hardware/devices
      → 后端返回 201，设备初始状态为 offline

步骤 2: 配置硬件固件
  │
  ├─ 修改 DEVICE_ID 与注册时使用的 ID 一致
  ├─ 修改 SERVER_HOST 为后端 IP
  └─ 烧录到 ESP8266

步骤 3: 硬件启动
  │
  ├─ 尝试注册，如果 ID 已存在则跳过
  ├─ 定期发送心跳，状态变为 online
  └─ 可以正常使用

步骤 4: 查看设备
  │
  └─ Web UI 显示该设备，状态为在线
```

---

## 🔧 后端实现详解

### 数据模型

```python
# app/models.py

class HardwareDevice(Base):
    """硬件设备"""
    __tablename__ = "hardware_devices"
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String(50), unique=True, nullable=False)  # 唯一标识
    device_name = Column(String(100))
    device_type = Column(String(50), index=True)
    location = Column(String(100))
    is_active = Column(Boolean, default=True)
    connection_status = Column(String(20))  # online, offline
    last_heartbeat = Column(DateTime)  # 最后心跳时间
    firmware_version = Column(String(50))
    ip_address = Column(String(45))
    port = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 关键 API 端点

#### 1. 注册设备
```
POST /api/hardware/devices
Content-Type: application/json

请求：
{
  "device_id": "nfc_reader_01",
  "device_name": "一楼门禁",
  "device_type": "nfc_reader",
  "location": "主入口",
  "ip_address": "192.168.1.102"
}

响应 (201):
{
  "id": 1,
  "device_id": "nfc_reader_01",
  "device_name": "一楼门禁",
  "connection_status": "offline",
  "is_active": true,
  "last_heartbeat": null,
  ...
}
```

#### 2. 心跳保活
```
POST /api/hardware/devices/{device_id}/heartbeat
Content-Type: application/json

请求：
{
  "connection_status": "online",
  "firmware_version": "1.1",
  "ip_address": "192.168.1.102"
}

响应 (200):
{
  "status": "ok",
  "device_id": "nfc_reader_01",
  "timestamp": "2025-12-24T10:35:00"
}

效果：
• 更新 last_heartbeat = 当前时间
• 设置 connection_status = "online"
• 设置 is_active = true
```

#### 3. 查询设备列表
```
GET /api/hardware/devices
GET /api/hardware/devices?device_type=nfc_reader
GET /api/hardware/devices?is_active=true

响应 (200):
[
  {
    "id": 1,
    "device_id": "nfc_reader_01",
    "device_name": "一楼门禁",
    "connection_status": "online",
    "last_heartbeat": "2025-12-24T10:35:00"
  }
]
```

#### 4. 更新设备
```
PUT /api/hardware/devices/{device_id}
Content-Type: application/json

请求：
{
  "device_name": "一楼主门禁",
  "location": "主楼入口"
}

响应 (200):
{
  "id": 1,
  "device_id": "nfc_reader_01",
  "device_name": "一楼主门禁",
  "location": "主楼入口",
  ...
}
```

#### 5. 删除设备
```
DELETE /api/hardware/devices/{device_id}

响应 (200):
{
  "message": "设备已删除"
}
```

---

## 🔌 硬件端实现详解

### 主要函数

#### 1. registerDevice()
```cpp
/**
 * 向后端注册设备（启动时调用）
 * 发送：POST /api/hardware/devices
 * 返回：true 成功, false 失败
 */
bool registerDevice() {
  // 1. 检查 WiFi 是否连接
  if (WiFi.status() != WL_CONNECTED) return false;
  
  // 2. 构建 JSON 请求体
  StaticJsonDocument<512> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_name"] = DEVICE_NAME;
  doc["device_type"] = DEVICE_TYPE;
  doc["location"] = DEVICE_LOCATION;
  doc["ip_address"] = WiFi.localIP().toString();
  
  // 3. 发送 HTTP POST 请求
  String json_str;
  serializeJson(doc, json_str);
  wifiClient.print("POST /api/hardware/devices HTTP/1.1\r\n");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  // ... 完整的 HTTP 头 ...
  wifiClient.print(json_str);
  
  // 4. 读取响应
  String response = "";
  while (wifiClient.connected() || wifiClient.available()) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  
  // 5. 检查状态码（201 或 200 表示成功）
  if (response.indexOf("201") != -1 || response.indexOf("200") != -1) {
    device_registered = true;
    return true;
  }
  return false;
}
```

#### 2. sendHeartbeat()
```cpp
/**
 * 发送心跳信号（每 30 秒调用一次）
 * 发送：POST /api/hardware/devices/{device_id}/heartbeat
 * 效果：更新设备在线状态
 */
bool sendHeartbeat() {
  // 构建请求体
  StaticJsonDocument<256> doc;
  doc["connection_status"] = "online";
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["ip_address"] = WiFi.localIP().toString();
  
  // 发送 HTTP POST 请求
  // POST /api/hardware/devices/nfc_reader_01/heartbeat
  
  // 返回成功/失败
}
```

#### 3. setup() - 初始化流程
```cpp
void setup() {
  // 1. 初始化 GPIO（LED、继电器）
  initLED();
  initRelay();
  
  // 2. 初始化 PN532
  initPN532();
  
  // 3. 连接 WiFi
  initWiFi();
  
  // 4. ★ 尝试注册设备（最多 3 次重试）
  if (WiFi.status() == WL_CONNECTED) {
    for (int i = 0; i < 3; i++) {
      if (registerDevice()) {
        break;
      }
      delay(3000);  // 失败后等待 3 秒重试
    }
  }
}
```

#### 4. loop() - 主循环
```cpp
void loop() {
  // 1. 检查 WiFi 是否断开，如断开则重新连接
  if (WiFi.status() != WL_CONNECTED) {
    initWiFi();
  }
  
  // 2. 尝试注册（如果还未成功注册）
  if (!device_registered && WiFi.status() == WL_CONNECTED) {
    registerDevice();
  }
  
  // 3. 定时发送心跳（每 30 秒）
  static unsigned long last_heartbeat_time = 0;
  unsigned long now = millis();
  if (now - last_heartbeat_time >= 30000) {
    last_heartbeat_time = now;
    sendHeartbeat();
  }
  
  // 4. 定时轮询命令（每 5 秒）
  static unsigned long last_poll_time = 0;
  if (now - last_poll_time >= 5000) {
    last_poll_time = now;
    int task_id = pollCommand();
    if (task_id >= 0) {
      // 收到扫描命令，执行扫描
      String card_uid = readNFCCard();
      if (card_uid.length() > 0) {
        reportCard(card_uid);
      }
    }
  }
  
  delay(100);
}
```

---

## ✅ 快速检查清单

### 后端准备

- [ ] FastAPI 应用已启动（`python -m uvicorn app.main:app --reload`）
- [ ] MySQL 数据库已连接
- [ ] `hardware_devices` 表已创建
- [ ] `/api/hardware/devices` 端点可访问（http://localhost:8000/docs）

### 硬件准备

- [ ] 获取 `esp8266_pn532_with_registration.ino` 最新版本
- [ ] 修改 WiFi 配置（SSID、PASSWORD）
- [ ] 修改服务器配置（SERVER_HOST）
- [ ] 设置唯一的 DEVICE_ID
- [ ] Arduino IDE 已安装依赖库：
  - [ ] Adafruit_PN532
  - [ ] ArduinoJson
  - [ ] ESP8266 核心库
- [ ] 成功烧录固件到 ESP8266

### 测试验证

- [ ] 打开 Serial Monitor（115200 波特率）
- [ ] 观察 `[WiFi] 连接成功` 日志
- [ ] 观察 `[Register] ✓ 设备注册成功` 日志
- [ ] 运行后端测试脚本：
  ```bash
  python scripts/test_device_integration.py
  ```
- [ ] 所有测试通过（✓）

---

## 🚨 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|--------|
| 硬件连接失败 | 后端服务未运行 | 启动 FastAPI：`uvicorn app.main:app --reload` |
| 注册失败 | WiFi 未连接 | 检查 WiFi 配置和路由器信号 |
| 注册失败 | 后端 IP 错误 | 检查 SERVER_HOST 配置 |
| 设备不在线 | 心跳未发送 | 检查网络连接和防火墙设置 |
| 重复注册错误 | 设备 ID 已存在 | 删除旧设备或更改 DEVICE_ID |
| PN532 检测失败 | I2C 接线问题 | 检查 SDA/SCL 连接和上拉电阻 |

---

## 📞 获取帮助

如果遇到问题，请检查以下文档：

1. **后端注册指南**：`DEVICE_REGISTRATION_GUIDE.md`
2. **硬件快速参考**：`HARDWARE_SETUP_QUICK_GUIDE.md`
3. **API 测试指南**：`API_TESTING_GUIDE.md`
4. **完整工作流程**：`DEVICE_SELECTION_GUIDE.md`

---

## 📊 数据库验证

```sql
-- 查看已注册的设备
SELECT device_id, device_name, connection_status, last_heartbeat 
FROM hardware_devices;

-- 查看在线设备
SELECT device_id, device_name FROM hardware_devices 
WHERE connection_status = 'online';

-- 查看离线或很久未心跳的设备
SELECT device_id, device_name, last_heartbeat 
FROM hardware_devices 
WHERE last_heartbeat IS NULL OR last_heartbeat < DATE_SUB(NOW(), INTERVAL 1 MINUTE);
```

---

**✨ 祝贺！你已经拥有完整的设备注册系统！** 🎉
