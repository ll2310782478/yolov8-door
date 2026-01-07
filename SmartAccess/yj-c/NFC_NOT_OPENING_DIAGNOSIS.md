# 🔧 NFC 读卡但不开门 - 诊断与修复

**症状:** 
```
[NFC] 读取成功，卡号: D3-99-4F-02
[Event] 上报失败，放弃本次读卡，code=-1
```

**根本原因:** WiFi/网络不通，上报到后端服务失败 → 没有收到"开门"指令

---

## 📋 诊断清单

### 1️⃣ 检查后端服务是否运行

```powershell
# 你的笔记本/服务器上
cd u:\BYSJ\yolov-door\yolov8-door\SmartAccess

# 启动后端
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**预期输出:**
```
Uvicorn running on http://0.0.0.0:8000
```

### 2️⃣ 确认 ESP32 能访问到后端

获取你电脑/服务器的 IP：
```powershell
# Windows
ipconfig

# 找 IPv4 地址，例如 192.168.1.45
```

修改固件中的配置：
```cpp
const char* SERVER_HOST = "192.168.1.45";    // ← 改成你实际的 IP
const int   SERVER_PORT = 8000;
const char* SSID        = "安居门业";         // ← 确认 WiFi 名称
const char* PASSWORD    = "15929256728";     // ← 确认 WiFi 密码
```

### 3️⃣ 编译上传后，查看串口输出

```
✅ WiFi 已连接
📍 IP: 192.168.x.x
🔗 Gateway: 192.168.1.1
🌐 Server: 192.168.1.45:8000
```

**如果看到这些，说明 WiFi 连接正常。**

如果 WiFi 不连接，检查：
- SSID 名称是否完全一致（包括空格）
- 密码是否正确
- WiFi 是否支持 2.4GHz（ESP32 不支持 5GHz）

### 4️⃣ 测试 HTTP 连接

在代码中的 NFC 读卡后加一行诊断：
```cpp
[NFC] 读取成功，卡号: D3-99-4F-02
[Event] 尝试连接 http://192.168.1.45:8000  ← 应该输出这行
[Event] 上报尝试 1/3, code=200, resp=...    ← code=200 表示成功
```

如果 code=-1 持续出现，说明网络无法连接到后端。

---

## 🛠️ 修复方案

### 方案A：确保网络畅通（优先）

1. **确认后端运行中**
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **确认 ESP32 WiFi 配置**
   - SSID、密码正确
   - SERVER_HOST 是你电脑的 IP（用 `ipconfig` 查）

3. **防火墙检查**
   - Windows 防火墙是否阻止了 8000 端口
   - 临时关闭防火墙测试

4. **网络拓扑**
   - ESP32 和电脑是否在同一 WiFi 网络
   - 路由器是否隔离了客户端（通常在"AP 隔离"设置中）

### 方案B：临时离线模式（仅用于调试）

如果网络实在不通，可临时启用离线模式强制开门：

**打开代码第 1710 行左右，取消注释：**
```cpp
// 🔧 备用逻辑：网络完全不可用时，可临时启用"离线模式"
SystemEvent fallback_event;
fallback_event.type = EVENT_NFC_PERMISSION_OK;
strcpy(fallback_event.data, "offline");
xQueueSend(event_queue, &fallback_event, 0);
```

**重新编译上传后，NFC 读卡 → 直接开门（不依赖网络）**

⚠️ **安全提示:** 离线模式会接受所有卡片，仅用于临时调试，生产环境必须禁用！

---

## 📊 错误代码对应表

| HTTP 返回码 | 含义 | 解决 |
|-----------|------|------|
| `-1` | 连接失败/超时 | 检查网络/后端是否运行 |
| `0` | 无响应 | 检查服务器是否可达 |
| `200` | 成功 | ✅ 正常 |
| `401` | 认证失败 | 检查 API token |
| `404` | 端点不存在 | 检查后端路由 |
| `500` | 后端错误 | 查看后端日志 |

---

## 🔍 逐步调试流程

**Step 1:** 确认后端运行，查看启动日志
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Step 2:** 重新编译上传 ESP32，观察启动日志
```
✅ WiFi 已连接
📍 IP: 192.168.x.x
```

**Step 3:** 读卡，观察上报日志
```
[NFC] 读取成功，卡号: D3-99-4F-02
[Event] 上报尝试 1/3, code=???
```

- 如果 `code=200` → 网络通，检查后端业务逻辑
- 如果 `code=-1` → 网络不通，返回 Step 1

**Step 4:** 后端日志验证

打开另一个终端，查看 FastAPI 输出：
```
POST /api/hardware/nfc/access HTTP/1.1" 200 OK
```

如果看不到 POST 请求，说明网络确实不通。

---

## 🎯 成功标志

✅ **完整流程应该是：**

```
[NFC] 读取成功，卡号: D3-99-4F-02
[Event] 上报尝试 1/3, code=200, resp={"status":"success","action":"OPEN"}
[Event] 服务器响应: {"status":"success","action":"OPEN"}
[Door] 💚 开门成功！
```

**如果还是不行，请告诉我：**
1. 后端是否真的在运行（有 Uvicorn 的启动日志吗？）
2. ESP32 WiFi 连接后显示的 IP 是什么
3. 你的电脑/服务器的 IP 是什么（`ipconfig` 结果）
4. 两者是否在同一网络（如 192.168.1.x）

---

**临时离线方案配置**

如果当前必须先能用，可以用离线模式快速验证硬件，等网络问题解决后再改回正常模式：

1. 打开 `http-nfc-s3-dual-core.ino` 第 ~1710 行
2. 找到注释掉的 `fallback_event` 代码
3. 取消注释（删除 `//`）
4. 重新编译上传
5. 测试：NFC 读卡 → 应该立即开门（不等网络）

等网络通了，再注释掉这个离线逻辑。
