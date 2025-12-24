# NFC 卡片管理 - "选择设备"使用逻辑详解

## 📋 概述

"选择设备"是 NFC 卡片管理页面中的核心功能，用于选择哪一个 NFC 读卡器（ESP8266 设备）来执行扫描操作。每当用户点击"识别"按钮时，系统会向选中的设备下发扫描命令。

---

## 🏗️ 架构和数据模型

### 数据库表结构

```
┌─────────────────────────────────┐
│     hardware_devices            │  硬件设备表
├─────────────────────────────────┤
│ id (PK)                         │  主键
│ device_id (UNIQUE)              │  设备唯一标识符（如：nfc_reader_01）
│ device_name                     │  设备显示名称（如：一楼门禁）
│ device_type                     │  设备类型（nfc_reader, door_lock, etc）
│ location                        │  设备位置（如：主入口）
│ is_active                       │  是否启用
│ connection_status               │  连接状态（online, offline, error）
│ ip_address, port                │  网络连接信息
│ last_heartbeat                  │  最后心跳时间
│ firmware_version                │  固件版本
└─────────────────────────────────┘

┌─────────────────────────────────┐
│     nfc_tasks                   │  NFC 命令队列表
├─────────────────────────────────┤
│ id (PK)                         │  任务 ID
│ device_id (FK)                  │  目标设备 ID（指向 hardware_devices）
│ command                         │  命令类型（如：SCAN）
│ payload                         │  命令参数（JSON）
│ status                          │  任务状态（pending, sent, done）
│ result                          │  任务结果（JSON）
│ created_at                      │  创建时间
│ sent_at                         │  发送时间
│ consumed_at                     │  完成时间
└─────────────────────────────────┘
```

---

## 🔄 完整工作流程

### 第一步：设备注册（一次性）

```
管理员在后端注册 NFC 读卡器设备：

POST /api/hardware/devices
{
  "device_id": "nfc_reader_01",          // 唯一标识
  "device_name": "一楼门禁",             // 显示名称
  "device_type": "nfc_reader",           // 设备类型
  "location": "主入口",                  // 位置
  "ip_address": "192.168.1.102"         // 设备 IP（可选）
}

响应：
{
  "id": 1,
  "device_id": "nfc_reader_01",
  "device_name": "一楼门禁",
  "device_type": "nfc_reader",
  "location": "主入口",
  "is_active": true,
  "connection_status": "offline"
}
```

### 第二步：前端加载设备列表

```
用户打开 /web/nfc 页面

触发 fetchDevices() 函数：

GET /api/hardware/devices?device_type=nfc_reader（可选过滤）

返回所有已注册的 NFC 读卡器设备

响应示例：
[
  {
    "id": 1,
    "device_id": "nfc_reader_01",
    "device_name": "一楼门禁",
    "device_type": "nfc_reader",
    "location": "主入口",
    "is_active": true,
    "connection_status": "online",    // ✓ 在线
    "last_heartbeat": "2025-12-24T10:30:00"
  },
  {
    "id": 2,
    "device_id": "nfc_reader_02",
    "device_name": "二楼门禁",
    "device_type": "nfc_reader",
    "location": "楼梯间",
    "is_active": true,
    "connection_status": "offline",   // ✗ 离线
    "last_heartbeat": "2025-12-24T09:15:00"
  }
]

前端将设备列表渲染为下拉菜单：

<select id="deviceSelect">
  <option value="nfc_reader_01">一楼门禁 (nfc_reader) [在线]</option>
  <option value="nfc_reader_02">二楼门禁 (nfc_reader) [离线]</option>
</select>
```

### 第三步：用户选择设备并点击"识别"

```
用户界面操作：

1. 在下拉菜单中选择 "nfc_reader_01"
2. 点击 "识别" 按钮

触发 triggerScan() 函数，执行以下步骤：

A. 验证设备是否选中
   if (!deviceId) { 
     showAlert('请先选择设备', 'danger'); 
     return; 
   }

B. 向后端发送 SCAN 命令
   POST /api/hardware/nfc/command
   {
     "device_id": "nfc_reader_01",
     "command": "SCAN"
   }

   后端创建 NFCTask 记录：
   {
     "id": 123,
     "device_id": "nfc_reader_01",
     "command": "SCAN",
     "status": "pending",             // 等待设备拉取
     "created_at": "2025-12-24T10:30:00"
   }

C. 前端显示等待状态
   status.textContent = "⏳ 等待设备响应... (ID: 123)";
```

### 第四步：设备轮询命令

```
ESP8266 设备固件定期轮询后端（每 5 秒一次）：

GET /api/hardware/nfc/command/poll?device_id=nfc_reader_01

后端查找该设备最早的 pending 任务：

SELECT * FROM nfc_tasks 
WHERE device_id='nfc_reader_01' AND status='pending' 
ORDER BY created_at ASC LIMIT 1;

如果找到任务，返回给设备：
{
  "has_command": true,
  "task_id": 123,
  "command": "SCAN",
  "payload": null
}

设备收到命令，执行扫描操作：
1. 通过 I2C 初始化 PN532 模块
2. 等待 NFC 卡片靠近（10 秒超时）
3. 读取卡的 UID（如：AA-BB-CC-DD）
```

### 第五步：设备上报扫描结果

```
设备读到卡片后，立即上报给后端：

POST /api/hardware/nfc-scan
{
  "card_uid": "AA-BB-CC-DD",
  "device_id": "nfc_reader_01"
}

后端处理流程：
1. 查找卡号对应的用户和卡片记录
2. 验证卡片状态（启用/禁用、权限有效期）
3. 找到对应的 NFCTask（task_id: 123），更新任务结果
4. 返回开门指令给设备

返回响应：
{
  "action": "OPEN",                  // 或 "DENY"
  "msg": "欢迎 张三"
}

后端同时更新 NFCTask：
UPDATE nfc_tasks SET 
  status = 'done',
  result = '{"card_uid":"AA-BB-CC-DD","status":"success","user_id":5}',
  consumed_at = NOW()
WHERE id = 123;

设备收到 OPEN，立即控制继电器打开门（1.5 秒）
```

### 第六步：前端轮询任务结果

```
前端持续轮询任务状态（每 1 秒）：

GET /api/hardware/nfc/command/status/123

直到任务状态从 "pending/sent" 变为 "done"：

{
  "id": 123,
  "status": "done",                   // ✓ 任务完成
  "result": "{\"card_uid\":\"AA-BB-CC-DD\",\"status\":\"success\",\"user_id\":5}",
  "created_at": "2025-12-24T10:30:00",
  "consumed_at": "2025-12-24T10:30:05"
}

前端解析 result JSON 并显示结果：
- ✓ 识别成功：用户 ID 5
- 或 ✗ 拒绝信息
- 或 ✗ 卡片已禁用
- 或 ✗ 权限已过期

同时设备已控制继电器打开门
```

---

## 📊 时间序列图

```
Web 前端                    后端 API                    ESP8266 设备
    │                          │                            │
    │  点击"识别"              │                            │
    ├─────────────────────────>│                            │
    │  POST /nfc/command       │ 创建 NFCTask (pending)    │
    │                          │                            │
    │ ⏳ 等待响应              │                            │
    │                          │<──── 每 5s 轮询 ────────┤
    │                          │  /nfc/command/poll       │
    │                          ├──────────────────────────>│
    │                          │ 返回 SCAN 命令           │
    │                          │                  执行扫描  │
    │                          │                  等待卡片  │
    │                          │                  读卡成功  │
    │                          │<─ POST /nfc-scan ────────┤
    │                          │ (card_uid: AA-BB-CC-DD)  │
    │                          │ 更新 NFCTask (done)       │
    │ GET /nfc/command/status/│ 返回 OPEN/DENY          │
    │─────────────────────────>│                            │
    │ result: success          │ 设备控制继电器打开门      │
    │ ✓ 显示识别结果          │ ✓ 门打开 1.5 秒          │
    │                          │                            │
```

---

## 🔑 核心设计要点

### 1. **设备隔离**
- 每个设备独立轮询，不会相互干扰
- 设备 ID 是全局唯一的（UNIQUE 约束）
- 支持多个 NFC 读卡器同时工作

### 2. **命令队列**
- NFCTask 表作为命令队列
- 设备按 FIFO（先进先出）执行命令
- 每个任务有明确的生命周期（pending → sent → done）

### 3. **状态同步**
- 前端通过轮询查询任务状态（无需 WebSocket）
- 设备通过轮询获取待执行命令
- 两端都是主动查询，避免连接管理复杂性

### 4. **容错机制**
- 设备离线时，任务保留为 pending，等待设备重新连接
- 轮询超时（20 秒）时，前端提示用户超时
- 设备读卡超时（10 秒）时，自动放弃读卡

### 5. **扩展性**
- 支持多个设备类型（nfc_reader, door_lock, camera 等）
- 命令类型可扩展（SCAN, UNLOCK, STATUS 等）
- payload 字段支持任意命令参数

---

## 💡 使用场景

### 场景 1：单门禁系统
```
1. 注册 1 个 NFC 读卡器（nfc_reader_01）
2. 用户打开 /web/nfc，自动显示此设备
3. 点击"识别" → 触发扫描
4. 卡片识别成功 → 继电器打开门
```

### 场景 2：多楼层门禁系统
```
1. 注册多个 NFC 读卡器：
   - nfc_reader_01（一楼）
   - nfc_reader_02（二楼）
   - nfc_reader_03（三楼）
2. 用户在 /web/nfc 下拉菜单选择目标楼层
3. 例如选择"二楼门禁"，点击"识别"
4. 只有二楼的读卡器会执行扫描（其他设备无反应）
5. 结果显示在同一界面上
```

### 场景 3：分布式管理
```
1. 后端服务器在云端或局域网内
2. 多个 ESP8266 设备分布在不同位置
3. 每个设备独立连接到后端 WiFi
4. 管理员可从任何地方管理所有设备
5. 各设备独立轮询，按队列执行命令
```

---

## 🚀 快速上手

### 步骤 1：注册设备

```bash
curl -X POST http://localhost:8000/api/hardware/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "nfc_reader_01",
    "device_name": "办公室门禁",
    "device_type": "nfc_reader",
    "location": "A101"
  }'
```

### 步骤 2：配置 ESP8266 固件

修改 `esp8266_pn532_nfc_reader.ino` 中的配置：

```cpp
const char* SERVER_HOST = "192.168.1.100";     // 后端服务器 IP
const int SERVER_PORT = 8000;                  // 后端端口
const char* DEVICE_ID = "nfc_reader_01";       // 与注册设备 ID 一致
```

### 步骤 3：烧录固件到 ESP8266

用 Arduino IDE 编译并上传固件到硬件

### 步骤 4：创建卡片记录

```bash
curl -X POST http://localhost:8000/api/hardware/nfc/cards \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "card_number": "AA-BB-CC-DD",
    "card_name": "管理员卡"
  }'
```

### 步骤 5：打开管理界面

浏览器访问：http://localhost:8000/web/nfc

### 步骤 6：选择设备并测试

1. 在下拉菜单选择 "办公室门禁"
2. 点击"识别"按钮
3. 将 NFC 卡片靠近读卡器
4. 确认识别结果显示

---

## 🔧 故障排查

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 下拉菜单为空 | 未注册设备 | 通过 API 或 /docs 注册设备 |
| 设备显示离线 | 设备未心跳 | 检查 ESP8266 WiFi 连接 |
| 点击"识别"无反应 | 未选择设备或设备离线 | 选择在线设备 |
| 读卡超时 | PN532 故障或卡片问题 | 检查硬件连接和卡片 |
| 轮询超时 | 网络延迟过大 | 检查设备与服务器连接 |

---

## 📝 总结

**"选择设备"的核心逻辑：**

```
选择设备 → 点击识别 → 创建命令 → 设备轮询 → 执行扫描 → 上报结果 → 前端显示
   ↓          ↓         ↓        ↓        ↓        ↓        ↓
用户界面   UI 交互    后端队列  设备拉取  硬件执行  结果同步  用户反馈
```

关键是 **NFCTask 表作为中介**，使得 Web 前端和 ESP8266 设备能异步、独立地工作。
