# API 变更总结 - v2.0 多设备架构

## 概述

v2.0 升级引入了**多硬件设备支持**。系统现在可以管理多个独立的门禁设备，每个设备有不同的功能模式。

## 核心变更

### 1. 设备模式（device_mode）

所有硬件设备现在支持以下模式：

| 模式 | 描述 | 支持功能 | 示例设备 |
|------|------|---------|---------|
| `remote_only` | 纯远程控制 | 远程开门、统一接口 | ESP8266 门禁1 |
| `remote_nfc` | 远程+NFC混合 | 远程开门、NFC刷卡、统一接口 | ESP32-S3 门禁2 |

### 2. 设备绑定（device_id）

NFC卡片现在可以绑定到特定设备：

- **device_id = NULL**: 卡片对所有支持NFC的设备有效
- **device_id = "door_controller_2"**: 卡片仅对指定设备有效

## API 端点变更

### 硬件设备管理

#### 创建硬件设备 - `POST /api/hardware/devices`

**请求体变化**
```json
{
  "device_id": "door_controller_2",
  "device_name": "门禁2",
  "device_type": "door_controller_nfc",
  "device_mode": "remote_nfc",           // ✨ 新增字段
  "location": "办公室",
  "ip_address": "192.168.x.x"
}
```

**响应体变化**
```json
{
  "id": 2,
  "device_id": "door_controller_2",
  "device_name": "门禁2",
  "device_type": "door_controller_nfc",
  "device_mode": "remote_nfc",           // ✨ 新增字段
  "location": "办公室",
  "is_active": true,
  "connection_status": "offline",
  "ip_address": "192.168.x.x"
}
```

#### 更新硬件设备 - `PUT /api/hardware/devices/{device_id}`

**新增可更新字段**
- `device_mode` - 现在可以更改设备模式

```json
{
  "device_name": "新名称",
  "device_mode": "remote_nfc",           // ✨ 新增
  "location": "新位置"
}
```

### NFC相关接口

#### NFC卡片创建 - `POST /api/hardware/nfc/cards`

**请求体变化**
```json
{
  "user_id": 1,
  "card_number": "AA-BB-CC-DD",
  "card_name": "我的NFC卡",
  "door_id": "door1",
  "device_id": "door_controller_2",      // ✨ 新增字段（可选）
  "permission_end_date": "2025-12-31T23:59:59",
  "max_daily_uses": 0
}
```

**响应体变化**
```json
{
  "id": 1,
  "user_id": 1,
  "card_number": "AA-BB-CC-DD",
  "card_name": "我的NFC卡",
  "door_id": "door1",
  "device_id": "door_controller_2",      // ✨ 新增字段
  "is_active": true,
  "created_at": "2026-01-03T10:00:00"
}
```

#### NFC卡片更新 - `PUT /api/hardware/nfc/card/{card_id}`

**新增可更新字段**
- `device_id` - 现在可以改变卡片绑定的设备

```json
{
  "card_name": "新名称",
  "device_id": "door_controller_2"       // ✨ 新增
}
```

#### NFC扫描接口 - `GET/POST /api/hardware/nfc-scan`

**变更**
- ✨ 现在同时支持 GET 和 POST 方式
- ✨ 验证设备模式（设备必须支持NFC才能处理）
- ✨ 验证卡片设备绑定（如果卡片指定了device_id）

**GET 请求**
```
GET /api/hardware/nfc-scan?card_uid=AA-BB-CC-DD&device_id=door_controller_2
```

**POST 请求**
```json
POST /api/hardware/nfc-scan
{
  "card_uid": "AA-BB-CC-DD",
  "device_id": "door_controller_2"
}
```

**响应示例**
```json
{
  "action": "OPEN",
  "door": "door1",
  "msg": "欢迎 张三"
}
```

**拒绝原因**（action = "DENY"）
- `未知卡片` - 卡号未在系统中注册
- `此设备不支持NFC功能` - 设备模式非 remote_nfc
- `卡片未授权给此设备` - 卡片的device_id与请求设备不匹配
- `卡片已被禁用` - 卡片被管理员禁用
- `卡片权限已过期` - 卡片的permission_end_date已过期

### 远程开门接口

#### 远程开门 - `POST /api/hardware/remote-door/open`

**无变更** - 接口保持向后兼容

```json
POST /api/hardware/remote-door/open
{
  "device_id": "door_controller_1",
  "door_id": 1,
  "source": "remote"
}
```

**新增验证**
- 设备必须存在
- 设备必须是active状态
- 不再验证device_mode（所有模式都支持远程开门）

### 命令轮询接口

#### 轮询命令 - `GET/POST /api/hardware/nfc/command/poll`

**无变更** - 接口保持向后兼容

```
GET /api/hardware/nfc/command/poll?device_id=door_controller_2
```

**返回示例**
```json
{
  "has_command": true,
  "task_id": 123,
  "command": "OPEN",
  "payload": "{\"door\": \"door1\", \"source\": \"remote\"}"
}
```

## 数据库变更

### hardware_devices 表

**新增列**
```sql
ALTER TABLE hardware_devices ADD COLUMN device_mode VARCHAR(50) DEFAULT 'remote_only';
```

| 列名 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `device_mode` | VARCHAR(50) | `remote_only` | 设备模式 |

### nfc_cards 表

**新增列**
```sql
ALTER TABLE nfc_cards ADD COLUMN device_id VARCHAR(50) NULL;
```

| 列名 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `device_id` | VARCHAR(50) | NULL | 绑定的硬件设备ID |

**说明**
- NULL值表示卡片对所有支持NFC的设备有效（向后兼容）
- 指定device_id表示卡片仅对该设备有效

## 向后兼容性

✅ **向后兼容** - 所有现有API调用仍可正常使用

- 不指定 `device_mode` 时默认为 `remote_only`
- 不指定 `device_id` 时默认为 NULL（对所有设备有效）
- 现有的远程开门请求完全不变

## 逻辑流程图

### 门禁1 (remote_only) 工作流

```
┌─────────────────┐
│  服务器触发     │
│  远程开门       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建OPEN任务   │
│  device_id=1    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  门禁1轮询      │
│  /poll          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  执行openDoor   │
│  开启门1/门2    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3秒后自动关闭  │
└─────────────────┘
```

### 门禁2 (remote_nfc) 工作流

```
┌─────────────────────┐
│   方式1: 远程开门    │
│  (流程同门禁1)      │
└─────────────────────┘

┌─────────────────────┐
│   方式2: NFC刷卡     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  用户刷卡           │
│  设备读取卡号       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  上报卡号到服务器   │
│  /nfc-scan          │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  服务器验证         │
│  • 卡片是否存在      │
│  • 权限是否有效      │
│  • 设备绑定是否匹配  │
└────────┬────────────┘
         │
    ┌────┴────┐
    │          │
    ▼          ▼
┌─────┐    ┌──────┐
│OPEN │    │DENY  │
└──┬──┘    └──────┘
   │
   ▼
┌──────────────────┐
│ 设备执行开门     │
│ 3秒后自动关闭    │
└──────────────────┘
```

## 迁移建议

### 对于现有系统

1. **备份数据库**
   ```bash
   mysqldump -u root -p smartaccess > backup.sql
   ```

2. **执行迁移脚本**
   ```bash
   mysql -u root -p smartaccess < MIGRATION_SCRIPT_v2.0.sql
   ```

3. **更新现有设备**
   ```sql
   -- 将旧设备标识为门禁1
   UPDATE hardware_devices 
   SET device_id = 'door_controller_1',
       device_name = '门禁1',
       device_mode = 'remote_only'
   WHERE device_id = 'nfc_reader_01';
   ```

4. **重启后端**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

## 示例代码

### 创建多设备

```python
import requests

BASE_URL = "http://localhost:8000"

# 创建门禁1
devices = [
    {
        "device_id": "door_controller_1",
        "device_name": "门禁1",
        "device_type": "door_controller",
        "device_mode": "remote_only",
        "location": "实验室大门"
    },
    {
        "device_id": "door_controller_2",
        "device_name": "门禁2",
        "device_type": "door_controller_nfc",
        "device_mode": "remote_nfc",
        "location": "办公室"
    }
]

for dev in devices:
    resp = requests.post(f"{BASE_URL}/api/hardware/devices", json=dev)
    print(f"创建 {dev['device_name']}: {resp.status_code}")
```

### 创建限制在门禁2的NFC卡片

```python
# 创建卡片，仅在门禁2可用
card = {
    "user_id": 1,
    "card_number": "AA-BB-CC-DD",
    "card_name": "门禁2专用卡",
    "door_id": "door1",
    "device_id": "door_controller_2",  # 限制到门禁2
    "max_daily_uses": 0
}

resp = requests.post(f"{BASE_URL}/api/hardware/nfc/cards", json=card)
print(f"创建卡片: {resp.json()}")
```

### 检测设备功能

```python
# 获取所有设备
resp = requests.get(f"{BASE_URL}/api/hardware/devices")
devices = resp.json()

for dev in devices:
    has_nfc = dev.get('device_mode') == 'remote_nfc'
    print(f"{dev['device_name']}: NFC支持={has_nfc}")
    
    if has_nfc:
        # 设备支持NFC，可以创建NFC卡片
        pass
    else:
        # 设备仅支持远程控制
        pass
```

---

**版本**: v2.0  
**日期**: 2026-01-03  
**兼容性**: 向后兼容（v1.0 API 调用仍可正常工作）
