# ESP8266 + PN532 NFC 读卡器固件使用指南

## 快速开始

### 1. 硬件准备

#### 所需物料
- **ESP8266 开发板**（推荐 NodeMCU 1.0 或 ESP-12E）
- **PN532 NFC 模块**（Adafruit 或兼容版本，I2C 接口）
- **5V 继电器模块**（1 路或多路）
- **杜邦线** 若干
- **USB 数据线** 用于烧录

#### 硬件接线
```
ESP8266        PN532 NFC 模块
GPIO5 (D1) --> SCL
GPIO4 (D2) --> SDA
GND        --> GND
3V3        --> 3V3

ESP8266        继电器模块
GPIO12(D6) --> IN（控制端）
GND        --> GND
5V         --> 5V（电源，可选外接）

ESP8266        状态 LED（可选）
GPIO2 (D4) --> LED 长脚
GND        --> LED 短脚（通过 220Ω 电阻）
```

### 2. 软件环境配置

#### 2.1 安装 Arduino IDE
- 下载：https://www.arduino.cc/en/software
- 推荐版本：1.8.19 或更新

#### 2.2 安装 ESP8266 支持
在 Arduino IDE 中：
1. 文件 > 首选项 > 附加开发板管理器网址，添加：
   ```
   http://arduino.esp8266.com/stable/package_esp8266com_index.json
   ```
2. 工具 > 开发板 > 开发板管理器，搜索 `esp8266`，安装最新版本

#### 2.3 安装库依赖
在 Arduino IDE 中：
工具 > 管理库，分别搜索并安装：
- **Adafruit-PN532** (by Adafruit)
- **ArduinoJson** (by Benoit Blanchon)

#### 2.4 选择开发板配置
工具菜单中设置：
- 开发板：NodeMCU 1.0 (ESP-12E Module)
- 闪存大小：4M (3M SPIFFS)
- 波特率：115200
- 端口：选择你的 USB 端口

### 3. 固件配置

打开 `esp8266_pn532_nfc_reader.ino` 文件，找到配置段并修改：

```cpp
// WiFi 配置
const char* SSID = "your-wifi-ssid";              // 改为你的 WiFi 名称
const char* PASSWORD = "your-wifi-password";       // 改为你的 WiFi 密码

// 后端服务器配置
const char* SERVER_HOST = "192.168.1.100";        // 改为你的服务器 IP
const int SERVER_PORT = 8000;                      // 后端 FastAPI 端口
const char* DEVICE_ID = "nfc_reader_01";          // 设备 ID（与后端注册一致）

// GPIO 引脚配置（根据你的接线修改）
#define PN532_SCL 5   // GPIO5 (D1)
#define PN532_SDA 4   // GPIO4 (D2)
#define RELAY_PIN 12  // GPIO12 (D6)
#define LED_PIN 2     // GPIO2 (D4)
```

### 4. 编译和烧录

1. **编译**：工具 > 验证/编译（快捷键 Ctrl+R）
2. **烧录**：工具 > 上传（快捷键 Ctrl+U）
3. **查看日志**：工具 > 串口监视器（波特率改为 115200）

### 5. 后端 API 配置

#### 5.1 注册设备
使用 POST 请求创建设备：
```bash
curl -X POST http://your-server:8000/api/hardware/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "nfc_reader_01",
    "device_name": "ESP PN532",
    "device_type": "nfc_reader",
    "location": "门禁"
  }'
```

#### 5.2 创建测试用户和卡片
```bash
# 创建用户
curl -X POST http://your-server:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass","full_name":"测试用户"}'

# 创建 NFC 卡片（用户 ID 改为实际 ID）
curl -X POST http://your-server:8000/api/hardware/nfc/cards \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "card_number": "AA-BB-CC-DD",
    "card_name": "我的卡"
  }'
```

### 6. 工作流程

1. **固件启动** → 连接 WiFi → 初始化 PN532
2. **轮询循环**（每 5 秒）→ 查询后端是否有 SCAN 命令
3. **收到命令** → 等待读卡（10 秒超时）
4. **读卡成功** → 将卡号上报给后端
5. **后端返回** → OPEN（开门）或 DENY（拒绝）
6. **执行动作** → 控制继电器打开门或输出提示信息

### 7. 故障排查

#### 串口日志示例

**正常启动流程：**
```
========== ESP8266 + PN532 NFC 读卡器 ==========
固件版本: 1.0

[WiFi] 连接到 WiFi...
.................
[WiFi] 连接成功
[WiFi] IP 地址: 192.168.1.102
[PN532] 初始化 NFC 模块...
[PN532] 固件版本: 32
[PN532] PN532 初始化完成
[Setup] 初始化完成，开始运行
[Poll] 轮询命令: /api/hardware/nfc/command/poll?device_id=nfc_reader_01
[Poll] 没有命令
[Poll] 轮询命令: /api/hardware/nfc/command/poll?device_id=nfc_reader_01
[Poll] 收到任务 ID: 1, 命令: SCAN
[Loop] 执行 SCAN 命令 (task_id: 1)
[NFC] 等待卡片...
[NFC] 读到卡号: AA-BB-CC-DD
[Report] 上报卡号: AA-BB-CC-DD
[Report] 动作: OPEN, 消息: 欢迎 测试用户
[Loop] 后端允许开门，执行开门动作
```

#### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| WiFi 连接失败 | SSID/密码错误 | 检查配置，确保信号强度 |
| PN532 初始化失败 | I2C 接线错误 | 检查 SDA/SCL 接线，尝试 I2C 扫描 |
| 无法连接后端 | IP/端口错误或防火墙 | ping 服务器，检查防火墙规则 |
| 继电器不工作 | GPIO 配置错误 | 检查 RELAY_PIN 定义和接线 |
| 读卡超时 | PN532 故障或卡片问题 | 更换卡片，检查模块电源 |

### 8. 高级功能

#### 自定义继电器时长
修改 `loop()` 函数中的开门函数调用：
```cpp
openDoor(2000);  // 改为 2000ms (2秒)
```

#### 添加蜂鸣器提示
```cpp
#define BUZZER_PIN 13  // GPIO13 (D7)
digitalWrite(BUZZER_PIN, HIGH);
delay(100);
digitalWrite(BUZZER_PIN, LOW);
```

#### 连接性诊断
固件已包含详细的串口日志，可用于实时诊断网络和硬件状态。

### 9. 安全建议

- **生产环境**：将 WiFi 密码和服务器 IP 存储在 EEPROM 或 SPIFFS
- **API 认证**：添加 API Key 或 Token 验证防止设备被冒充
- **HTTPS**：使用 TLS/SSL 保护网络通信（ESP8266 支持）
- **继电器隔离**：使用光耦隔离保护 ESP8266

### 10. 参考资源

- Adafruit PN532 库文档：https://github.com/adafruit/Adafruit-PN532
- ESP8266 文档：https://arduino-esp8266.readthedocs.io/
- Arduino JSON 库：https://github.com/bblanchon/ArduinoJson
