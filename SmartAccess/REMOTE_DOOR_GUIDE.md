# 远程开门模块使用指南

## 功能概述
远程开门模块允许通过Web界面远程控制已注册的门禁设备，支持同时控制多个门。

## 系统架构

### 1. 前端界面
- 文件：`app/templates/remote_door.html`
- 功能：
  - 显示所有已注册的硬件设备
  - 实时显示设备在线/离线状态
  - 为每个设备提供"开门1"和"开门2"按钮
  - 30秒自动刷新设备状态
  - Toast通知提示操作结果

### 2. 导航菜单
- 文件：`app/templates/layout.html`
- 修改：在顶部导航栏添加"远程开门"链接
- 访问路径：`/web/remote-door`

### 3. 后端API
- 文件：`app/routers/hardware.py`
- 新增接口：`POST /api/hardware/remote-door/open`
- 请求参数：
  ```json
  {
    "device_id": "设备ID",
    "door_id": 1或2,
    "source": "remote"
  }
  ```
- 响应示例：
  ```json
  {
    "success": true,
    "message": "开门指令已下发",
    "task_id": 123
  }
  ```

### 4. 页面路由
- 文件：`app/routers/web.py`
- 路由：`GET /web/remote-door`
- 返回：`remote_door.html`

### 5. 硬件集成
- 文件：`yj-c/esp8266_pn532_v2.ino`
- 功能：ESP8266通过轮询接口获取OPEN指令
- 轮询间隔：2秒
- 接口：`POST /api/hardware/nfc/command/poll`

## 工作流程

```
用户点击"开门1"按钮
    ↓
前端发送 POST 请求到 /api/hardware/remote-door/open
    ↓
后端验证设备存在且状态为active
    ↓
创建NFCTask记录（command="OPEN", status="pending"）
    ↓
返回成功响应给前端
    ↓
ESP8266轮询 /api/hardware/nfc/command/poll
    ↓
获取到OPEN指令
    ↓
调用 openDoor(doorId, "remote")
    ↓
控制继电器开门
    ↓
更新任务状态为"completed"
```

## 使用步骤

### 1. 启动服务器
```bash
cd SmartAccess
uvicorn app.main:app --reload
```

### 2. 访问远程开门页面
打开浏览器访问：
```
http://localhost:8000/web/remote-door
```

### 3. 注册硬件设备（如果还没有）
- 访问 `/web/hardware` 注册设备
- 或通过API POST到 `/api/hardware/devices/register`
- 确保ESP8266固件已烧录并连接WiFi

### 4. 远程开门操作
1. 在远程开门页面查看设备列表
2. 确认设备状态为"在线"（绿色标签）
3. 点击"开门1"或"开门2"按钮
4. 等待Toast通知确认操作成功
5. ESP8266将在2秒内执行开门动作

## 数据库表

### hardware_devices
存储已注册的硬件设备信息：
- `device_id`: 设备唯一标识（主键）
- `device_name`: 设备名称
- `device_type`: 设备类型（door_controller）
- `status`: 设备状态（active/inactive）
- `ip_address`: 设备IP地址
- `last_heartbeat`: 最后心跳时间

### nfc_task_queue
存储待执行的任务：
- `id`: 任务ID（自增主键）
- `device_id`: 目标设备ID
- `command`: 指令类型（OPEN）
- `payload`: JSON格式的参数
  ```json
  {"door": "door1", "source": "remote"}
  ```
- `status`: 任务状态（pending/completed/failed）
- `created_at`: 创建时间

## 前端页面特性

### 设备卡片显示
```html
<div class="device-card">
  <div class="device-name">门禁设备 A</div>
  <div class="device-info">
    <span class="badge online">在线</span>
    <span>IP: 192.168.1.100</span>
  </div>
  <div class="door-buttons">
    <button onclick="openDoor('device_1', 1)">开门1</button>
    <button onclick="openDoor('device_1', 2)">开门2</button>
  </div>
</div>
```

### JavaScript交互
- `loadDevices()`: 加载设备列表
- `openDoor(deviceId, doorId)`: 下发开门指令
- `showToast(message, type)`: 显示通知
- 自动刷新：`setInterval(loadDevices, 30000)`

## API接口详细说明

### 1. 获取设备列表
```
GET /api/hardware/devices
```
响应：
```json
[
  {
    "device_id": "device_1",
    "device_name": "门禁设备A",
    "device_type": "door_controller",
    "status": "active",
    "ip_address": "192.168.1.100",
    "last_heartbeat": "2024-01-20T10:30:00"
  }
]
```

### 2. 下发开门指令
```
POST /api/hardware/remote-door/open
Content-Type: application/json

{
  "device_id": "device_1",
  "door_id": 1,
  "source": "remote"
}
```
响应：
```json
{
  "success": true,
  "message": "开门指令已下发",
  "task_id": 123
}
```

### 3. 设备轮询指令（ESP8266调用）
```
POST /api/hardware/nfc/command/poll
Content-Type: application/json

{
  "device_id": "device_1"
}
```
响应：
```json
{
  "command": "OPEN",
  "payload": "{\"door\": \"door1\", \"source\": \"remote\"}"
}
```

## 硬件端代码

### openDoor 函数
```cpp
bool openDoor(int doorId, String source) {
    Serial.print("Opening door ");
    Serial.print(doorId);
    Serial.print(" from source: ");
    Serial.println(source);
    
    int relayPin = (doorId == 1) ? RELAY_PIN_1 : RELAY_PIN_2;
    
    digitalWrite(relayPin, LOW);
    delay(3000);
    digitalWrite(relayPin, HIGH);
    
    return true;
}
```

### 轮询任务处理
```cpp
void pollTask() {
    if (WiFi.status() != WL_CONNECTED) return;
    
    HTTPClient http;
    String url = String(SERVER_URL) + "/api/hardware/nfc/command/poll";
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    String body = "{\"device_id\":\"" + String(DEVICE_ID) + "\"}";
    int httpCode = http.POST(body);
    
    if (httpCode == 200) {
        String response = http.getString();
        DynamicJsonDocument doc(1024);
        deserializeJson(doc, response);
        
        String command = doc["command"];
        if (command == "OPEN") {
            String payload = doc["payload"];
            DynamicJsonDocument payloadDoc(512);
            deserializeJson(payloadDoc, payload);
            
            String door = payloadDoc["door"];
            String source = payloadDoc["source"];
            
            int doorId = (door == "door1") ? 1 : 2;
            openDoor(doorId, source);
        }
    }
    http.end();
}
```

## 安全建议

1. **身份验证**：建议添加JWT令牌验证
2. **权限控制**：限制只有管理员可以远程开门
3. **操作日志**：记录所有开门操作到access_logs表
4. **频率限制**：防止频繁点击，添加防抖
5. **HTTPS**：生产环境使用HTTPS加密通信

## 故障排查

### 问题1：点击按钮无反应
- 检查浏览器控制台错误
- 确认设备状态为"active"
- 检查网络请求是否成功

### 问题2：ESP8266未收到指令
- 确认ESP8266正常轮询（查看串口日志）
- 检查数据库中nfc_task_queue是否有pending任务
- 验证device_id匹配

### 问题3：设备显示离线
- 检查ESP8266网络连接
- 确认心跳机制正常工作
- 查看last_heartbeat时间戳

## 测试步骤

1. **注册设备**
   ```bash
   curl -X POST http://localhost:8000/api/hardware/devices/register \
     -H "Content-Type: application/json" \
     -d '{
       "device_id": "test_device",
       "device_name": "测试设备",
       "device_type": "door_controller",
       "ip_address": "192.168.1.100"
     }'
   ```

2. **访问页面**
   - 打开 http://localhost:8000/web/remote-door
   - 确认设备出现在列表中

3. **测试开门**
   - 点击"开门1"按钮
   - 观察Toast通知
   - 检查ESP8266串口输出

4. **数据库验证**
   ```sql
   SELECT * FROM nfc_task_queue 
   WHERE device_id = 'test_device' 
   ORDER BY created_at DESC 
   LIMIT 1;
   ```

## 未来优化

- [ ] 添加开门历史记录查询
- [ ] 支持定时开门任务
- [ ] 设备分组管理
- [ ] 实时WebSocket推送门状态
- [ ] 移动端响应式适配
- [ ] 二次确认对话框
- [ ] 开门倒计时显示

---

**创建日期**: 2024-01-20  
**最后更新**: 2024-01-20  
**版本**: v1.0
