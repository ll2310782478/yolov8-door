# 🚀 设备注册快速开始指南（5分钟上手）

## 📋 三步快速部署

### 步骤 1：配置硬件固件（2分钟）

**打开文件**：`yj-c/esp8266_pn532_with_registration.ino`

**修改以下 4 个地方**：

```cpp
// 第 42-43 行：WiFi 配置
const char* SSID = "your-wifi-ssid";              // ← 改为你的 WiFi 名
const char* PASSWORD = "your-wifi-password";       // ← 改为你的 WiFi 密码

// 第 46-47 行：后端服务器
const char* SERVER_HOST = "192.168.1.100";        // ← 改为后端 IP（重要！）
const int SERVER_PORT = 8000;

// 第 50-53 行：设备信息
const char* DEVICE_ID = "nfc_reader_01";          // ← 唯一 ID（必须不重复）
const char* DEVICE_NAME = "一楼门禁";              // ← 显示名称
const char* DEVICE_LOCATION = "主入口";            // ← 设备位置
```

**保存 → 烧录到 ESP8266**

### 步骤 2：启动后端服务（1分钟）

```bash
# 进入项目目录
cd u:\BYSJ\yolov-door\yolov8-door\SmartAccess

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**检查服务是否运行**：
```bash
curl http://localhost:8000/health
# 应该返回：{"status":"ok"}
```

### 步骤 3：验证设备注册（2分钟）

**方法 A：通过 Serial Monitor 观察日志**

1. 打开 Arduino IDE 的串口监视器（波特率 115200）
2. ESP8266 启动后应该看到：
   ```
   [WiFi] 连接成功
   [WiFi] IP 地址: 192.168.1.102
   [Register] ✓ 设备注册成功（201/200）
   [Heartbeat] ✓ 心跳发送成功
   ```

**方法 B：使用 curl 测试**

```bash
# 查询已注册的设备
curl http://localhost:8000/api/hardware/devices

# 应该返回包含你的设备的列表：
# [
#   {
#     "device_id": "nfc_reader_01",
#     "device_name": "一楼门禁",
#     "connection_status": "online"
#   }
# ]
```

---

## ✨ 核心概念（必读）

### 设备注册流程

```
硬件启动
   ↓
连接 WiFi
   ↓
调用 registerDevice()
   ↓
发送 POST /api/hardware/devices
   ↓
后端创建数据库记录
   ↓
设备初始化完成
   ↓
每 30 秒发送心跳信号
   ↓
后端更新 last_heartbeat 和状态为 "online"
```

### 为什么需要注册？

| 功能 | 说明 |
|------|------|
| **设备识别** | 后端知道这是哪一个硬件设备 |
| **在线状态** | 管理员可以看到设备是否在线 |
| **权限管理** | 不同设备可以有不同的权限配置 |
| **日志跟踪** | 记录每个设备的动作 |
| **远程管理** | 可以从 Web UI 编辑设备信息 |

---

## 🔍 验证清单

- [ ] WiFi 配置正确（SSID、密码）
- [ ] SERVER_HOST 改成了后端 IP
- [ ] DEVICE_ID 设置为唯一值
- [ ] 固件成功烧录到 ESP8266
- [ ] FastAPI 服务正在运行
- [ ] Serial Monitor 显示连接成功和注册成功
- [ ] `curl http://localhost:8000/api/hardware/devices` 能看到设备

---

## 📌 重要提示

### 🔴 常见错误 1：服务器连接失败
```
[Register] ❌ 连接服务器失败
```
**解决**：检查 SERVER_HOST 是否是正确的后端 IP

找到后端 IP：
```bash
# Windows
ipconfig
# 找到 IPv4 地址，比如：192.168.1.100
```

### 🔴 常见错误 2：设备 ID 重复
```
[Register] ✓ 设备 ID 已存在（设备已注册）
```
**解决**：这实际上不是错误，说明设备已经注册过了。可以继续使用。

如果想重新注册，先删除旧设备：
```bash
curl -X DELETE http://localhost:8000/api/hardware/devices/nfc_reader_01
```

### 🔴 常见错误 3：WiFi 连接失败
```
[WiFi] 连接失败
```
**解决**：
- 检查 SSID 和 PASSWORD 是否正确
- 确保路由器开启了 2.4GHz 频段（ESP8266 不支持 5GHz）
- 检查 WiFi 信号强度

---

## 🎯 接下来要做什么？

### 1️⃣ 在 Web UI 中查看设备

访问：http://localhost:8000/web/nfc

你应该能看到：
- 设备下拉菜单中列出了你的设备
- 设备显示为"在线"状态

### 2️⃣ 测试扫描功能

1. 在 Web UI 中选择你的设备
2. 点击"触发扫描"按钮
3. 将 NFC 卡片靠近读卡器
4. 卡号应该显示在 Web UI 中

### 3️⃣ 添加 NFC 卡片和权限

1. 访问 /web/nfc
2. 点击"添加卡片"
3. 填写卡号、用户名等信息
4. 设置权限和时效期限

---

## 📊 参考信息

### 默认配置示例

如果你没有特殊要求，可以使用这个最小配置：

**WiFi**：
```cpp
const char* SSID = "TP-LINK-5G";          // 改成你的 WiFi
const char* PASSWORD = "12345678";         // 改成你的密码
```

**后端**：
```cpp
const char* SERVER_HOST = "192.168.1.50";  // 改成你的后端 IP
```

**设备**：
```cpp
const char* DEVICE_ID = "nfc_reader_01";
const char* DEVICE_NAME = "主门禁";
const char* DEVICE_LOCATION = "入口";
```

### API 端点速查

```bash
# 注册设备
curl -X POST http://localhost:8000/api/hardware/devices \
  -H "Content-Type: application/json" \
  -d '{"device_id":"nfc_reader_01","device_name":"一楼门禁","device_type":"nfc_reader"}'

# 查询设备
curl http://localhost:8000/api/hardware/devices

# 发送心跳（模拟硬件）
curl -X POST http://localhost:8000/api/hardware/devices/nfc_reader_01/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"connection_status":"online","firmware_version":"1.1"}'

# 删除设备
curl -X DELETE http://localhost:8000/api/hardware/devices/nfc_reader_01
```

---

## 🧪 完整测试脚本

运行端到端测试：

```bash
cd SmartAccess
python scripts/test_device_integration.py
```

这个脚本会：
- ✓ 检查服务器是否运行
- ✓ 注册测试设备
- ✓ 获取设备列表
- ✓ 发送心跳信号
- ✓ 多次心跳测试
- ✓ 按类型查询
- ✓ 更新设备信息
- ✓ 删除设备
- ✓ 测试错误处理

---

## 📚 详细文档

| 文档 | 用途 |
|------|------|
| **DEVICE_REGISTRATION_GUIDE.md** | 完整的实现细节（后端+硬件）|
| **HARDWARE_SETUP_QUICK_GUIDE.md** | 硬件配置详细步骤 |
| **API_TESTING_GUIDE.md** | API 测试方法和示例 |
| **DEVICE_SELECTION_GUIDE.md** | 完整工作流程说明 |
| **DEVICE_REGISTRATION_SUMMARY.md** | 全面的实现总结 |

---

## 💡 故障排除

### 日志中看不到注册信息

**可能原因**：
1. Serial Monitor 未连接
2. 波特率设置错误（应为 115200）
3. USB 驱动未安装

**解决**：
- 重启 Arduino IDE
- 检查 COM 端口选择
- 安装 CH340 驱动（ESP8266 通常使用）

### 注册成功但设备显示离线

**可能原因**：
1. 心跳信号未能送达后端
2. 后端网络配置有问题
3. 防火墙阻止

**解决**：
- 检查 WiFi 连接是否稳定
- ping 一下后端服务器
- 检查防火墙规则

### Web UI 中看不到设备

**可能原因**：
1. 数据库未更新
2. 设备未成功注册

**解决**：
- 检查 Serial Monitor 的注册日志
- 使用 curl 查询 `/api/hardware/devices`
- 检查数据库是否有记录

---

## ✅ 成功指标

当你看到以下迹象时，说明设备注册成功了：

1. ✓ Serial Monitor 显示：`[Register] ✓ 设备注册成功`
2. ✓ Serial Monitor 显示：`[Heartbeat] ✓ 心跳发送成功`
3. ✓ `curl http://localhost:8000/api/hardware/devices` 能看到你的设备
4. ✓ Web UI (`/web/nfc`) 的设备选择器中列出了你的设备
5. ✓ 设备显示为"在线"状态

---

## 🎉 恭喜！

你现在已经完全理解了设备注册的完整流程！

**下一步**：
- 部署多个设备（更改 DEVICE_ID）
- 添加 NFC 卡片和权限设置
- 在实际门禁场景中测试
- 集成其他功能（日志、报警等）

---

## 📞 需要帮助？

1. 查看 **DEVICE_REGISTRATION_GUIDE.md** 了解详细实现
2. 查看 **API_TESTING_GUIDE.md** 学习 API 调用
3. 查看 **HARDWARE_SETUP_QUICK_GUIDE.md** 了解硬件配置

或检查 Serial Monitor 输出，大多数问题都能从日志中找到答案！

---

**祝你使用愉快！** 🚀
