# 设备注册完整实现指南

## 📋 概述

设备注册是 NFC 系统的第一步。在管理员将 ESP8266 设备部署到现场之前，需要在后端系统中登记该设备的信息。本指南详细说明如何实现完整的设备注册流程。

---

## 🏗️ 系统组成

### 三个层面的实现

```
┌──────────────────────────────────────────────────────────────┐
│  前端 Web UI (/web/nfc 或 /web/hardware)                     │
│  - 设备注册表单                                              │
│  - 设备列表管理                                              │
│  - 编辑/删除设备                                            │
└──────────────────────────────────────────────────────────────┘
                           ↕
┌──────────────────────────────────────────────────────────────┐
│  后端 FastAPI                                                │
│  - POST /api/hardware/devices (注册设备)                      │
│  - GET /api/hardware/devices (查询设备)                       │
│  - PUT /api/hardware/devices/{device_id} (更新设备)           │
│  - DELETE /api/hardware/devices/{device_id} (删除设备)        │
│  - POST /api/hardware/devices/{device_id}/heartbeat (心跳)    │
└──────────────────────────────────────────────────────────────┘
                           ↕
┌──────────────────────────────────────────────────────────────┐
│  硬件 ESP8266                                                │
│  - 存储设备 ID、Server IP 等配置                              │
│  - 初始化时上传设备信息（自动注册）                           │
│  - 定期发送心跳信号（保活）                                  │
│  - 自动同步时间和配置                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔧 后端实现（FastAPI）

### 1. 数据模型（已有）

```python
# app/models.py

class HardwareDevice(Base):
    """硬件设备模型"""
    __tablename__ = "hardware_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True, nullable=False)
    device_name = Column(String(100))
    device_type = Column(String(50), index=True)  # nfc_reader, door_lock, etc
    location = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    device_config = Column(Text)  # JSON 格式的配置
    firmware_version = Column(String(50))
    connection_status = Column(String(20))  # online, offline, error
    ip_address = Column(String(45))
    port = Column(Integer)
```

### 2. API 端点（已有）

#### 注册设备

```
POST /api/hardware/devices
Content-Type: application/json

请求体：
{
  "device_id": "nfc_reader_01",           // 必填：唯一标识符
  "device_name": "一楼门禁",              // 必填：显示名称
  "device_type": "nfc_reader",            // 必填：设备类型
  "location": "主入口",                   // 可选：物理位置
  "ip_address": "192.168.1.102",          // 可选：设备 IP
  "port": 0                               // 可选：设备端口
}

响应体（201 Created）：
{
  "id": 1,
  "device_id": "nfc_reader_01",
  "device_name": "一楼门禁",
  "device_type": "nfc_reader",
  "location": "主入口",
  "is_active": true,
  "last_heartbeat": null,
  "created_at": "2025-12-24T10:30:00",
  "updated_at": "2025-12-24T10:30:00",
  "connection_status": "offline",
  "firmware_version": null
}
```

#### 查询设备

```
GET /api/hardware/devices
GET /api/hardware/devices?device_type=nfc_reader
GET /api/hardware/devices?is_active=true

响应体：
[
  {
    "id": 1,
    "device_id": "nfc_reader_01",
    "device_name": "一楼门禁",
    "device_type": "nfc_reader",
    "location": "主入口",
    "is_active": true,
    "connection_status": "online",
    "last_heartbeat": "2025-12-24T10:35:00"
  },
  ...
]
```

#### 更新设备

```
PUT /api/hardware/devices/nfc_reader_01
Content-Type: application/json

请求体：
{
  "device_name": "一楼主门禁",
  "location": "主楼入口",
  "is_active": true
}

响应体：
{
  "id": 1,
  "device_id": "nfc_reader_01",
  "device_name": "一楼主门禁",
  ...
}
```

#### 删除设备

```
DELETE /api/hardware/devices/nfc_reader_01

响应体：
{
  "message": "设备已删除"
}
```

#### 设备心跳

```
POST /api/hardware/devices/nfc_reader_01/heartbeat
Content-Type: application/json

请求体：
{
  "connection_status": "online",
  "firmware_version": "1.0",
  "ip_address": "192.168.1.102"
}

响应体：
{
  "status": "ok",
  "device_id": "nfc_reader_01",
  "timestamp": "2025-12-24T10:35:00",
  "server_time": "2025-12-24T10:35:00"
}
```

### 3. 后端代码实现（已存在）

在 `app/routers/hardware.py` 中已包含：

```python
@router.get("/devices", response_model=List[HardwareDeviceResponse])
def list_devices(device_type: Optional[str] = None, is_active: Optional[bool] = None, db: Session = Depends(get_db)):
    """获取所有硬件设备"""
    query = db.query(HardwareDevice)
    if device_type:
        query = query.filter(HardwareDevice.device_type == device_type)
    if is_active is not None:
        query = query.filter(HardwareDevice.is_active == is_active)
    return query.all()


@router.post("/devices", response_model=HardwareDeviceResponse)
def create_device(device: HardwareDeviceCreate, db: Session = Depends(get_db)):
    """注册新硬件设备"""
    existing = db.query(HardwareDevice).filter(HardwareDevice.device_id == device.device_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="设备ID已存在")
    
    db_device = HardwareDevice(
        device_id=device.device_id,
        device_name=device.device_name,
        device_type=device.device_type,
        location=device.location,
        ip_address=device.ip_address,
        port=device.port,
        connection_status="offline"
    )
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device


@router.post("/devices/{device_id}/heartbeat")
def device_heartbeat(device_id: str, connection_status: str = "online", db: Session = Depends(get_db)):
    """设备心跳检测"""
    db_device = db.query(HardwareDevice).filter(HardwareDevice.device_id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    db_device.last_heartbeat = datetime.utcnow()
    db_device.is_active = True
    db_device.connection_status = connection_status
    db.commit()
    return {"status": "ok", "device_id": device_id, "timestamp": datetime.utcnow()}
```

---

## 🖥️ 硬件端实现（ESP8266）

### 1. 配置常量

在 `esp8266_pn532_nfc_reader.ino` 中添加或修改以下部分：

```cpp
// ==================== 配置 ====================

// WiFi 配置
const char* SSID = "your-wifi-ssid";
const char* PASSWORD = "your-wifi-password";

// 后端服务器配置
const char* SERVER_HOST = "192.168.1.100";           // 后端 IP
const int SERVER_PORT = 8000;
const char* DEVICE_ID = "nfc_reader_01";             // 设备唯一 ID
const char* DEVICE_NAME = "一楼门禁";                // 设备显示名称
const char* DEVICE_TYPE = "nfc_reader";              // 设备类型
const char* DEVICE_LOCATION = "主入口";              // 设备位置

// 心跳间隔（毫秒）
const unsigned long HEARTBEAT_INTERVAL = 30000;     // 30 秒发送一次心跳

// 固件版本
const char* FIRMWARE_VERSION = "1.0";
```

### 2. 设备初始化时自动注册

在固件启动时，自动向后端注册设备（如果尚未注册）：

```cpp
/**
 * 向后端注册设备
 * 设备启动时调用一次，或者当检测到自己不存在时调用
 */
bool registerDevice() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Register] WiFi 未连接");
    return false;
  }

  Serial.println("[Register] 向后端注册设备...");

  // 构建 JSON 请求体
  StaticJsonDocument<512> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_name"] = DEVICE_NAME;
  doc["device_type"] = DEVICE_TYPE;
  doc["location"] = DEVICE_LOCATION;
  doc["ip_address"] = WiFi.localIP().toString();

  String json_str;
  serializeJson(doc, json_str);

  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Register] 连接服务器失败");
    return false;
  }

  // 发送 POST 请求
  wifiClient.print("POST /api/hardware/devices HTTP/1.1\r\n");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  wifiClient.print(":");
  wifiClient.println(SERVER_PORT);
  wifiClient.println("Content-Type: application/json");
  wifiClient.print("Content-Length: ");
  wifiClient.println(json_str.length());
  wifiClient.println("Connection: close");
  wifiClient.println();
  wifiClient.print(json_str);

  // 读取响应
  String response = "";
  while (wifiClient.connected() || wifiClient.available()) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  wifiClient.stop();

  // 简单检查响应状态码
  if (response.indexOf("200") != -1 || response.indexOf("201") != -1) {
    Serial.println("[Register] 设备注册成功");
    return true;
  } else if (response.indexOf("400") != -1) {
    Serial.println("[Register] 设备 ID 已存在（设备已注册）");
    return true;  // 如果已存在，视为成功
  } else {
    Serial.print("[Register] 注册失败: ");
    Serial.println(response.substring(0, 200));
    return false;
  }
}
```

### 3. 定期发送心跳信号

在主循环中定期发送心跳以保持设备在线状态：

```cpp
/**
 * 发送心跳信号
 * 告诉后端设备仍然在线，更新 last_heartbeat 时间
 */
bool sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;  // WiFi 未连接，跳过心跳
  }

  // 构建请求 URL
  String url = String("/api/hardware/devices/") + DEVICE_ID + "/heartbeat";

  // 构建 JSON 请求体
  StaticJsonDocument<256> doc;
  doc["connection_status"] = "online";
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["ip_address"] = WiFi.localIP().toString();

  String json_str;
  serializeJson(doc, json_str);

  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Heartbeat] 连接服务器失败");
    return false;
  }

  // 发送 POST 请求
  wifiClient.print("POST ");
  wifiClient.print(url);
  wifiClient.println(" HTTP/1.1");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  wifiClient.print(":");
  wifiClient.println(SERVER_PORT);
  wifiClient.println("Content-Type: application/json");
  wifiClient.print("Content-Length: ");
  wifiClient.println(json_str.length());
  wifiClient.println("Connection: close");
  wifiClient.println();
  wifiClient.print(json_str);

  // 读取响应（可选，只记录日志）
  String response = "";
  unsigned long start_time = millis();
  while ((millis() - start_time < 2000) && (wifiClient.connected() || wifiClient.available())) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  wifiClient.stop();

  if (response.indexOf("200") != -1 || response.indexOf("ok") != -1) {
    Serial.println("[Heartbeat] 心跳发送成功");
    return true;
  } else {
    Serial.println("[Heartbeat] 心跳发送失败或无响应");
    return false;
  }
}

// 在 loop() 中定期调用
static unsigned long last_heartbeat_time = 0;
unsigned long now = millis();

if (now - last_heartbeat_time >= HEARTBEAT_INTERVAL) {
  last_heartbeat_time = now;
  sendHeartbeat();
}
```

### 4. 完整的注册和初始化流程

```cpp
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n");
  Serial.println("========== ESP8266 + PN532 NFC 读卡器 ==========");
  Serial.println("固件版本: 1.0");
  Serial.println("");

  // 初始化 GPIO
  initLED();
  initRelay();

  // 初始化 PN532
  initPN532();

  // 初始化 WiFi
  initWiFi();

  // ★ 尝试向后端注册设备
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[Setup] 尝试向后端注册设备...");
    bool reg_success = false;
    for (int i = 0; i < 3; i++) {  // 尝试 3 次
      if (registerDevice()) {
        reg_success = true;
        break;
      }
      delay(2000);
    }
    if (!reg_success) {
      Serial.println("[Setup] 注册失败，但继续运行（可能已注册）");
    }
  }

  Serial.println("[Setup] 初始化完成，开始运行");
}
```

---

## 🌐 前端实现（Web UI）

### 1. 设备管理页面

在 `/web/nfc` 或 `/web/hardware` 中添加设备管理功能：

```html
<!-- 设备注册表单 -->
<div class="card-box">
  <div class="section-title">注册新设备</div>
  <form id="registerDeviceForm">
    <div class="form-row">
      <div class="form-group">
        <label>设备 ID *</label>
        <input id="deviceId" type="text" placeholder="例：nfc_reader_01" required>
      </div>
      <div class="form-group">
        <label>设备名称 *</label>
        <input id="deviceName" type="text" placeholder="例：一楼门禁" required>
      </div>
      <div class="form-group">
        <label>设备类型 *</label>
        <select id="deviceType" required>
          <option value="">-- 选择类型 --</option>
          <option value="nfc_reader">NFC 读卡器</option>
          <option value="door_lock">门锁</option>
          <option value="camera">摄像头</option>
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>位置</label>
        <input id="deviceLocation" type="text" placeholder="例：主入口">
      </div>
      <div class="form-group">
        <label>IP 地址</label>
        <input id="deviceIp" type="text" placeholder="例：192.168.1.102">
      </div>
      <div class="form-group" style="justify-content: flex-end;">
        <button type="submit" class="btn-primary">注册设备</button>
      </div>
    </div>
  </form>
</div>

<!-- 设备列表 -->
<div class="card-box">
  <div class="section-title">已注册设备列表</div>
  <table class="table">
    <thead>
      <tr>
        <th>设备 ID</th>
        <th>设备名称</th>
        <th>类型</th>
        <th>位置</th>
        <th>状态</th>
        <th>最后心跳</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody id="deviceListBody"></tbody>
  </table>
</div>
```

### 2. JavaScript 处理逻辑

```javascript
const apiBase = '/api/hardware';

// 注册设备
async function registerDevice(evt) {
  evt.preventDefault();
  
  const payload = {
    device_id: document.getElementById('deviceId').value.trim(),
    device_name: document.getElementById('deviceName').value.trim(),
    device_type: document.getElementById('deviceType').value,
    location: document.getElementById('deviceLocation').value.trim(),
    ip_address: document.getElementById('deviceIp').value.trim()
  };

  const res = await fetch(apiBase + '/devices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    showAlert('设备注册成功', 'success');
    document.getElementById('registerDeviceForm').reset();
    await fetchDeviceList();
  } else {
    const err = await res.json();
    showAlert('注册失败: ' + (err.detail || '未知错误'), 'danger');
  }
}

// 获取设备列表
async function fetchDeviceList() {
  const res = await fetch(apiBase + '/devices');
  const devices = await res.json();
  const tbody = document.getElementById('deviceListBody');
  
  tbody.innerHTML = '';
  devices.forEach(d => {
    const tr = document.createElement('tr');
    const status = d.connection_status === 'online' 
      ? '<span class="status-badge status-active">在线</span>'
      : '<span class="status-badge status-inactive">离线</span>';
    const lastHB = d.last_heartbeat 
      ? new Date(d.last_heartbeat).toLocaleString()
      : '-';
    
    tr.innerHTML = `
      <td><code>${d.device_id}</code></td>
      <td>${d.device_name}</td>
      <td>${d.device_type}</td>
      <td>${d.location || '-'}</td>
      <td>${status}</td>
      <td>${lastHB}</td>
      <td>
        <button class="btn-outline" onclick="deleteDevice('${d.device_id}')">删除</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// 删除设备
async function deleteDevice(deviceId) {
  if (!confirm('确定删除设备？')) return;
  const res = await fetch(apiBase + '/devices/' + deviceId, { method: 'DELETE' });
  if (res.ok) {
    showAlert('设备已删除', 'success');
    await fetchDeviceList();
  } else {
    showAlert('删除失败', 'danger');
  }
}

// 页面加载时获取设备列表
window.addEventListener('load', async () => {
  document.getElementById('registerDeviceForm').addEventListener('submit', registerDevice);
  await fetchDeviceList();
});
```

---

## 📝 完整工作流程

### 自动注册流程（推荐）

```
1. 硬件部署
   ↓
2. ESP8266 通电并连接 WiFi
   ↓
3. 固件读取配置中的 DEVICE_ID、DEVICE_NAME 等
   ↓
4. 固件启动 registerDevice() 向后端发送 POST /api/hardware/devices
   ↓
5. 后端检查 device_id 是否已存在
   - 如果不存在：创建新设备，返回 201
   - 如果已存在：返回 400（视为已注册）
   ↓
6. ESP8266 定期发送心跳（/api/hardware/devices/{device_id}/heartbeat）
   ↓
7. 后端更新 last_heartbeat 和 connection_status 为 "online"
   ↓
8. 前端访问 /api/hardware/devices 查询时，显示设备为"在线"
```

### 手动注册流程（备用）

```
1. 管理员在 Web UI 填写设备信息
   - 设备 ID: nfc_reader_01
   - 设备名称: 一楼门禁
   - 设备类型: nfc_reader
   - 位置: 主入口
   ↓
2. 点击"注册设备"按钮
   ↓
3. 前端发送 POST /api/hardware/devices
   ↓
4. 后端创建设备记录，初始 connection_status = "offline"
   ↓
5. 管理员配置硬件固件（DEVICE_ID = nfc_reader_01）
   ↓
6. 硬件上电启动，定期发送心跳
   ↓
7. 连接状态自动变为 "online"
```

---

## 🔑 关键点总结

| 功能 | 后端 | 硬件 |
|------|------|------|
| **设备信息存储** | HardwareDevice 表 | 配置常量 |
| **注册接口** | POST /api/hardware/devices | registerDevice() |
| **设备发现** | GET /api/hardware/devices | - |
| **状态更新** | POST /api/hardware/devices/{id}/heartbeat | sendHeartbeat() |
| **在线判断** | last_heartbeat > 1 分钟内 | - |
| **设备删除** | DELETE /api/hardware/devices/{id} | - |

---

## 🚀 快速上手清单

### ✅ 后端配置
- [ ] FastAPI 已有 `/api/hardware/devices` 相关接口
- [ ] HardwareDevice 数据库表已创建
- [ ] 可通过 /docs 访问 API 文档

### ✅ 硬件配置
- [ ] 修改 `esp8266_pn532_nfc_reader.ino` 中的配置常量
  - [ ] DEVICE_ID
  - [ ] DEVICE_NAME
  - [ ] DEVICE_TYPE
  - [ ] DEVICE_LOCATION
  - [ ] SERVER_HOST
  - [ ] FIRMWARE_VERSION
- [ ] 添加 `registerDevice()` 函数
- [ ] 添加 `sendHeartbeat()` 函数
- [ ] 在 `setup()` 中调用 `registerDevice()`
- [ ] 在 `loop()` 中定期调用 `sendHeartbeat()`

### ✅ 前端配置
- [ ] 在 Web UI 中添加设备注册表单
- [ ] 添加设备列表显示
- [ ] 实现设备删除功能
- [ ] 显示设备在线状态和最后心跳时间

### ✅ 测试
- [ ] [ ] 使用 curl 或 Postman 测试 POST /api/hardware/devices
- [ ] [ ] 手动注册一个设备
- [ ] [ ] 硬件固件烧录后观察 Serial Monitor
- [ ] [ ] 检查后端数据库 hardware_devices 表是否有记录
- [ ] [ ] 刷新前端 Web UI，查看设备状态是否为"在线"

---

## 🔧 故障排查

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 硬件无法连接 WiFi | WiFi 配置错误 | 检查 SSID 和 PASSWORD |
| 注册失败 | 后端不可达 | 检查 SERVER_HOST 和 SERVER_PORT |
| 设备 ID 重复 | 已注册过相同 ID | 删除旧设备或修改 DEVICE_ID |
| 设备显示离线 | 心跳信号断开 | 检查网络连接、增加心跳频率 |
| 数据库错误 | 表未创建 | 检查 init_db() 是否执行 |

---

## 📚 相关 API 参考

查看完整 API 文档：http://localhost:8000/docs

搜索 "hardware" 或 "device" 查看所有设备相关接口。
