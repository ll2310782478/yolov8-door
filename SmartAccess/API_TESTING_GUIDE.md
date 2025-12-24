# 后端注册接口验证指南

## 📡 API 端点信息

### 设备注册端点

**请求**：
```
POST http://localhost:8000/api/hardware/devices
```

**请求头**：
```
Content-Type: application/json
```

**请求体**（JSON）：
```json
{
  "device_id": "nfc_reader_01",
  "device_name": "一楼门禁",
  "device_type": "nfc_reader",
  "location": "主入口",
  "ip_address": "192.168.1.102"
}
```

**响应（成功 - 201 Created）**：
```json
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

**响应（错误 - 400 Bad Request）**：
```json
{
  "detail": "设备ID已存在"
}
```

---

## 🧪 使用 curl 测试

### 1. 注册新设备

```bash
curl -X POST http://localhost:8000/api/hardware/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "nfc_reader_01",
    "device_name": "一楼门禁",
    "device_type": "nfc_reader",
    "location": "主入口",
    "ip_address": "192.168.1.102"
  }'
```

**预期输出**：
```json
{
  "id": 1,
  "device_id": "nfc_reader_01",
  "device_name": "一楼门禁",
  "device_type": "nfc_reader",
  "location": "主入口",
  "is_active": true,
  "connection_status": "offline",
  ...
}
```

### 2. 查询所有设备

```bash
curl http://localhost:8000/api/hardware/devices
```

**预期输出**：
```json
[
  {
    "id": 1,
    "device_id": "nfc_reader_01",
    "device_name": "一楼门禁",
    "device_type": "nfc_reader",
    "connection_status": "offline",
    "last_heartbeat": null
  }
]
```

### 3. 查询特定类型的设备

```bash
curl "http://localhost:8000/api/hardware/devices?device_type=nfc_reader"
```

### 4. 查询活跃设备

```bash
curl "http://localhost:8000/api/hardware/devices?is_active=true"
```

### 5. 发送心跳（模拟硬件）

```bash
curl -X POST http://localhost:8000/api/hardware/devices/nfc_reader_01/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "connection_status": "online",
    "firmware_version": "1.1",
    "ip_address": "192.168.1.102"
  }'
```

**预期输出**：
```json
{
  "status": "ok",
  "device_id": "nfc_reader_01",
  "timestamp": "2025-12-24T10:35:00"
}
```

### 6. 删除设备

```bash
curl -X DELETE http://localhost:8000/api/hardware/devices/nfc_reader_01
```

**预期输出**：
```json
{
  "message": "设备已删除"
}
```

---

## 🖥️ 使用 PowerShell 测试（Windows）

### 1. 注册设备

```powershell
$body = @{
  device_id = "nfc_reader_01"
  device_name = "一楼门禁"
  device_type = "nfc_reader"
  location = "主入口"
  ip_address = "192.168.1.102"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/api/hardware/devices" `
  -Method POST `
  -Headers @{"Content-Type" = "application/json"} `
  -Body $body | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

### 2. 查询设备

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/hardware/devices" `
  -Method GET | Select-Object -ExpandProperty Content | ConvertFrom-Json | Format-Table
```

### 3. 发送心跳

```powershell
$body = @{
  connection_status = "online"
  firmware_version = "1.1"
  ip_address = "192.168.1.102"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/api/hardware/devices/nfc_reader_01/heartbeat" `
  -Method POST `
  -Headers @{"Content-Type" = "application/json"} `
  -Body $body | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

---

## 📱 使用 Python 测试

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/hardware"

# 1. 注册设备
def register_device():
    payload = {
        "device_id": "nfc_reader_01",
        "device_name": "一楼门禁",
        "device_type": "nfc_reader",
        "location": "主入口",
        "ip_address": "192.168.1.102"
    }
    response = requests.post(f"{BASE_URL}/devices", json=payload)
    print("注册设备响应:", response.json())
    return response.status_code

# 2. 查询设备
def list_devices():
    response = requests.get(f"{BASE_URL}/devices")
    devices = response.json()
    for device in devices:
        print(f"设备 ID: {device['device_id']}, 状态: {device['connection_status']}")

# 3. 发送心跳
def send_heartbeat(device_id):
    payload = {
        "connection_status": "online",
        "firmware_version": "1.1",
        "ip_address": "192.168.1.102"
    }
    response = requests.post(f"{BASE_URL}/devices/{device_id}/heartbeat", json=payload)
    print("心跳响应:", response.json())

# 4. 删除设备
def delete_device(device_id):
    response = requests.delete(f"{BASE_URL}/devices/{device_id}")
    print("删除响应:", response.json())

# 执行
if __name__ == "__main__":
    print("1. 注册设备")
    register_device()
    
    print("\n2. 查询设备列表")
    list_devices()
    
    print("\n3. 发送心跳")
    send_heartbeat("nfc_reader_01")
    
    print("\n4. 删除设备")
    # delete_device("nfc_reader_01")
```

---

## 🔍 验证步骤

### 步骤 1：启动后端服务

```bash
cd u:\BYSJ\yolov-door\yolov8-door\SmartAccess
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或如果已有启动脚本：
```bash
.\start_server.ps1
```

### 步骤 2：验证服务是否运行

```bash
curl http://localhost:8000/health
```

**预期输出**：
```json
{
  "status": "ok"
}
```

### 步骤 3：测试设备注册

```bash
curl -X POST http://localhost:8000/api/hardware/devices \
  -H "Content-Type: application/json" \
  -d '{"device_id":"nfc_reader_01","device_name":"一楼门禁","device_type":"nfc_reader"}'
```

**预期结果**：
- 首次：返回 201，设备注册成功
- 再次用相同 ID：返回 400，设备 ID 已存在

### 步骤 4：检查数据库

```bash
# 进入 MySQL
mysql -u root -p smartaccess

# 查看 hardware_devices 表
SELECT id, device_id, device_name, connection_status, last_heartbeat FROM hardware_devices;
```

**预期输出**：
```
| id | device_id        | device_name | connection_status | last_heartbeat |
|----|------------------|-------------|-------------------|----------------|
| 1  | nfc_reader_01    | 一楼门禁     | offline           | NULL           |
```

### 步骤 5：模拟心跳更新

```bash
# 发送心跳
curl -X POST http://localhost:8000/api/hardware/devices/nfc_reader_01/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"connection_status":"online","firmware_version":"1.1"}'

# 再次查询数据库，应该看到 connection_status = "online" 和更新的 last_heartbeat
```

---

## ✅ 完整测试脚本（PowerShell）

将以下代码保存为 `test_device_registration.ps1`：

```powershell
# test_device_registration.ps1
$BaseUrl = "http://localhost:8000/api/hardware"

function Register-Device {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "1. 注册新设备" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    
    $body = @{
        device_id = "nfc_reader_01"
        device_name = "一楼门禁"
        device_type = "nfc_reader"
        location = "主入口"
        ip_address = "192.168.1.102"
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$BaseUrl/devices" `
        -Method POST `
        -Headers @{"Content-Type" = "application/json"} `
        -Body $body
    
    $result = $response.Content | ConvertFrom-Json
    Write-Host "✓ 注册成功: $($result.device_id)" -ForegroundColor Green
    Write-Host ""
}

function List-Devices {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "2. 查询设备列表" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    
    $response = Invoke-WebRequest -Uri "$BaseUrl/devices" -Method GET
    $devices = $response.Content | ConvertFrom-Json
    
    if ($devices.Count -eq 0) {
        Write-Host "暂无设备" -ForegroundColor Yellow
    } else {
        $devices | ForEach-Object {
            Write-Host "设备 ID: $($_.device_id)" -ForegroundColor Green
            Write-Host "  名称: $($_.device_name)"
            Write-Host "  类型: $($_.device_type)"
            Write-Host "  状态: $($_.connection_status)"
            Write-Host "  心跳: $($_.last_heartbeat)"
            Write-Host ""
        }
    }
}

function Send-Heartbeat {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "3. 发送心跳信号" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    
    $body = @{
        connection_status = "online"
        firmware_version = "1.1"
        ip_address = "192.168.1.102"
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$BaseUrl/devices/nfc_reader_01/heartbeat" `
        -Method POST `
        -Headers @{"Content-Type" = "application/json"} `
        -Body $body
    
    $result = $response.Content | ConvertFrom-Json
    Write-Host "✓ 心跳发送成功" -ForegroundColor Green
    Write-Host "  状态: $($result.status)"
    Write-Host "  时间: $($result.timestamp)"
    Write-Host ""
}

function Delete-Device {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "4. 删除设备" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    
    $response = Invoke-WebRequest -Uri "$BaseUrl/devices/nfc_reader_01" `
        -Method DELETE
    
    $result = $response.Content | ConvertFrom-Json
    Write-Host "✓ 设备已删除" -ForegroundColor Green
    Write-Host "  消息: $($result.message)"
    Write-Host ""
}

# 执行测试
Register-Device
List-Devices
Send-Heartbeat
List-Devices
# Delete-Device  # 注释掉以保留测试设备
```

运行测试：
```powershell
.\test_device_registration.ps1
```

---

## 🚨 常见错误及解决方案

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| `Connection refused` | 后端服务未运行 | 启动 FastAPI 服务 |
| `400 Bad Request: 设备ID已存在` | 设备已注册过 | 使用不同的 device_id |
| `400 Bad Request: 缺少必填字段` | 请求体不完整 | 检查 JSON 字段 |
| `404 Not Found` | 设备不存在 | 先注册设备再查询 |
| `500 Internal Server Error` | 数据库错误 | 检查数据库连接和表结构 |

---

## 📊 数据库验证

### 查看 hardware_devices 表结构

```sql
DESCRIBE hardware_devices;
```

**预期输出**：
```
Field                Type          Null  Key  Default           Extra
device_id           varchar(50)   NO    PRI  NULL              
device_name         varchar(100)  YES       NULL              
device_type         varchar(50)   YES   MUL  NULL              
location            varchar(100)  YES       NULL              
is_active           tinyint(1)    NO        1                 
last_heartbeat      datetime      YES       NULL              
created_at          datetime      NO        CURRENT_TIMESTAMP 
updated_at          datetime      NO        CURRENT_TIMESTAMP on update
connection_status   varchar(20)   YES       NULL              
firmware_version    varchar(50)   YES       NULL              
ip_address          varchar(45)   YES       NULL              
port                int           YES       NULL              
device_config       text          YES       NULL              
```

### 查看已注册的设备

```sql
SELECT device_id, device_name, connection_status, last_heartbeat FROM hardware_devices;
```

---

## 📚 相关文档

- [设备注册完整实现指南](DEVICE_REGISTRATION_GUIDE.md)
- [硬件端设备注册快速参考](HARDWARE_SETUP_QUICK_GUIDE.md)
- [完整工作流程文档](DEVICE_SELECTION_GUIDE.md)
