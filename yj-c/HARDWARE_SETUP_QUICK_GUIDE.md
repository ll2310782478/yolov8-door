# 硬件端设备注册快速参考

## 🔧 修改清单

在烧录固件前，需要修改以下配置常量（文件：`esp8266_pn532_with_registration.ino`）：

### 1. WiFi 配置
```cpp
// 第 42-43 行
const char* SSID = "your-wifi-ssid";           // ← 改为你的 WiFi 名称
const char* PASSWORD = "your-wifi-password";    // ← 改为你的 WiFi 密码
```

### 2. 后端服务器
```cpp
// 第 46-47 行
const char* SERVER_HOST = "192.168.1.100";     // ← 改为后端服务器 IP
const int SERVER_PORT = 8000;                  // 保持不变（FastAPI 端口）
```

### 3. 设备信息
```cpp
// 第 50-53 行
const char* DEVICE_ID = "nfc_reader_01";       // ← 唯一标识符（必须与后端一致）
const char* DEVICE_NAME = "一楼门禁";           // ← 显示名称
const char* DEVICE_TYPE = "nfc_reader";        // 保持不变
const char* DEVICE_LOCATION = "主入口";         // ← 设备位置描述
```

**重要**: 记住这个 `DEVICE_ID`，后续需要在后端注册时用到！

---

## 📝 配置示例

假设你的硬件信息如下：
- WiFi: `TP-LINK-5G` / `password123`
- 服务器 IP: `192.168.1.50`
- 设备位置: `会议室门口`

则配置应为：
```cpp
const char* SSID = "TP-LINK-5G";
const char* PASSWORD = "password123";
const char* SERVER_HOST = "192.168.1.50";
const char* DEVICE_ID = "nfc_reader_conference";
const char* DEVICE_NAME = "会议室门禁";
const char* DEVICE_LOCATION = "会议室门口";
```

---

## 🚀 工作流程

### 首次部署流程

```
┌─ 配置固件 (修改上述 4 个配置项)
│
├─ 烧录到 ESP8266
│
├─ 设备上电启动
│  ├─ [WiFi] 连接到 WiFi → ✓ 成功
│  ├─ [Register] 向后端注册设备 → ✓ 成功（或已注册）
│  ├─ [Heartbeat] 定期发送心跳 → ✓ 每 30 秒一次
│  └─ [Poll] 轮询后端命令 → ✓ 每 5 秒一次
│
├─ 打开 Serial Monitor (115200 波特率)
│  观察以上信息确认一切正常
│
└─ 开始使用
   ├─ Web UI 访问 http://localhost:8000/web/nfc
   ├─ 选择该设备
   ├─ 点击"触发扫描"按钮
   ├─ 将 NFC 卡片放在读卡器上
   ├─ 硬件读到卡号后上报给后端
   └─ 后端检查权限后返回 OPEN/DENY
```

---

## 📊 Serial Monitor 日志解读

### ✅ 一切正常的日志

```
╔════════════════════════════════════════╗
║ ESP8266 + PN532 NFC 读卡器 (含注册)    ║
║ 固件版本: 1.1                          ║
╚════════════════════════════════════════╝

[Setup] 设备 ID: nfc_reader_01
[Setup] 服务器: 192.168.1.100:8000

[WiFi] 正在连接到 WiFi...
.....................
[WiFi] 连接成功
[WiFi] IP 地址: 192.168.1.102

[PN532] 初始化 NFC 模块...
[PN532] 固件版本: 0x32
[PN532] ✓ PN532 初始化完成

[Setup] 尝试注册设备...
[Register] 向后端注册设备...
[Register] 请求体: {"device_id":"nfc_reader_01",...}
[Register] ✓ 设备注册成功（201/200）

[Setup] ✓ 初始化完成，开始运行

[Heartbeat] ✓ 心跳发送成功
[Poll] ✓ 收到任务 ID: 123
[NFC] 等待卡片...
[NFC] ✓ 读到卡号: AB-CD-EF-12
[Report] 上报卡号: AB-CD-EF-12
[Report] 动作: OPEN
[Door] 打开门锁
[Door] 关闭门锁
```

### ⚠️ 常见问题日志

| 日志信息 | 问题 | 解决方案 |
|---------|------|--------|
| `[WiFi] 连接失败` | WiFi 配置错误 | 检查 SSID 和 PASSWORD |
| `[Register] ❌ 连接服务器失败` | 服务器不可达 | 检查 SERVER_HOST 和 SERVER_PORT |
| `[PN532] ❌ 未检测到 PN532 模块` | I2C 接线问题 | 检查 SDA/SCL 连接 |
| `[Register] ✓ 设备 ID 已存在（设备已注册）` | 设备已注册过 | 此为正常，可继续使用 |
| `[NFC] ⏱ 读卡超时` | 卡片未放上 | 将卡片放在读卡器上 |

---

## 🔄 后续使用

### 修改设备配置

如果需要修改设备信息（比如位置、名称等）：

**方法 1：重新修改固件 + 烧录**（硬件重启后自动更新）
```cpp
const char* DEVICE_LOCATION = "新位置";
```

**方法 2：通过 Web UI 编辑**（无需重新烧录）
1. 访问 http://localhost:8000/web/hardware (需创建此页面)
2. 选择要编辑的设备
3. 修改位置、名称等信息
4. 点击保存（后端会执行 PUT /api/hardware/devices/{device_id}）

### 批量部署多台设备

1. 修改固件中的 `DEVICE_ID` 为 `nfc_reader_02`、`nfc_reader_03` 等
2. 分别烧录到不同 ESP8266
3. 每台设备启动时会自动注册自己的 ID
4. 前端就能看到多个设备了

---

## 📌 重要提示

1. **设备 ID 必须唯一**
   - 不能两台硬件使用相同的 DEVICE_ID
   - 修改后需要重新烧录

2. **服务器 IP 要正确**
   - 如果不确定，在电脑上运行：
   ```bash
   ipconfig  # Windows
   # 或
   ifconfig  # Linux/Mac
   ```
   - 找到 IPv4 地址（通常是 192.168.x.x）

3. **首次注册可能失败**
   - 固件会重试 3 次
   - 如果仍失败，检查网络连接后重启硬件

4. **心跳间隔可调整**
   ```cpp
   const unsigned long HEARTBEAT_INTERVAL = 30000;  // 改为其他值（毫秒）
   ```
   - 30000 = 30 秒（推荐）
   - 10000 = 10 秒（更频繁更新）
   - 60000 = 1 分钟（降低网络负荷）

---

## 🧪 测试清单

- [ ] 修改了 WiFi 配置
- [ ] 修改了服务器 IP
- [ ] 记住了设备 ID（比如 `nfc_reader_01`）
- [ ] 烧录固件到 ESP8266
- [ ] 打开 Serial Monitor 观察启动日志
- [ ] 看到 `[WiFi] 连接成功`
- [ ] 看到 `[Register] ✓ 设备注册成功` 或 `[Register] ✓ 设备 ID 已存在`
- [ ] 每 30 秒看到一条 `[Heartbeat] ✓ 心跳发送成功`

---

## 📞 调试支持

如果遇到问题，请提供以下信息：
1. Serial Monitor 完整日志输出
2. 固件中的配置值（IP、WiFi 名称等）
3. 后端服务器是否运行（http://localhost:8000/docs 可访问）
4. 硬件接线图和照片
