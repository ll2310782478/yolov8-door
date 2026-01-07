# ESP32 编译和配对测试清单

## 🔴 关键检查项 - 编译前必做

### Step 1: 库文件检查
- [ ] Arduino IDE 已安装 ESP32 开发板定义
  ```
  工具 → 开发板 → 开发板管理器 → 搜索 "esp32"
  安装版本 >= 2.0.0
  ```

- [ ] 必需库已安装（Arduino IDE → 项目 → 加载库）：
  - [ ] `ArduinoBLE` (BLE支持)
  - [ ] `Preferences` (NVS存储，通常内置)
  - [ ] `ArduinoJson` (JSON解析)
  
### Step 2: 板子配置
- [ ] 目标开发板: **ESP32-S3**
- [ ] USB驱动: CP210x (Windows可能需要额外安装)
- [ ] COM端口: 检查设备管理器中的 "COM X"

---

## 🟡 编译检查清单

### 打开Arduino IDE 并加载固件
```
文件 → 打开 → http-nfc-s3-dual-core.ino
```

### 预检查（编译前看第一眼）

#### 1. 检查 include 部分
```cpp
// 应该有这些行（大约 line 55）
#include <Preferences.h>
#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
```

#### 2. 检查数据结构（大约 line 152-180）
```cpp
struct BLEDeviceStatus {
  // ... 原有字段 ...
  char device_irk[33];  // 新增：IRK字段
};

struct BLEPairingInfo {  // 新增结构体
  char device_irk[33];
  char device_ltk[33];
  char device_name[100];
  unsigned long pairing_time;
};

struct PairingModeStatus {  // 新增配对模式状态
  bool active;
  unsigned long start_time;
  const unsigned long TIMEOUT = 30000;
};
```

#### 3. 检查setup()函数（大约 line 1639）
```cpp
void setup() {
  // ... 其他初始化 ...
  initNVS();  // 新增：初始化NVS
  // ...
}
```

#### 4. 检查配对函数（大约 line 298-370）
```cpp
void initNVS() { ... }
void savePairingInfo(...) { ... }
bool loadPairingInfo(...) { ... }
void removePairingInfo(...) { ... }
```

### 执行编译
```
按 Ctrl+R 或点击 "✓" 按钮（验证）
```

### 编译结果判断

✅ **编译成功标志**:
```
Sketch uses 1,234,567 bytes (39%) of program storage space.
Global variables use 45,678 bytes (13%) of dynamic memory.
```

❌ **常见编译错误**:

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `'Preferences' was not declared` | 没有include | 检查 #include <Preferences.h> |
| `undefined reference to 'initNVS'` | 函数未定义 | 检查函数是否有声明 |
| `too many initializers` | 结构体初始化错误 | 检查结构体定义和初始化 |
| `'BLEDevice' not found` | BLE库未安装 | 安装 ArduinoBLE 库 |

---

## 🟢 烧录测试清单

### Step 1: 连接开发板
- [ ] USB线连接 ESP32-S3 到电脑
- [ ] Arduino IDE 识别到 COM 端口
  ```
  工具 → 端口 → COM X (ESP32-S3)
  ```

### Step 2: 上传固件
```
按 Ctrl+U 或点击 "→" 按钮（上传）
```

### Step 3: 烧录成功验证
- [ ] 看到 "上传完成" 消息
- [ ] 开发板重启（可能闪烁LED）
- [ ] 打开 "串口监视器"（Ctrl+Shift+M）检查日志

### Step 4: 串口监视器检查
设置波特率: **115200**

**应该看到的日志**:
```
[NVS] Initializing NVS storage...
[NVS] NVS initialized successfully
[BLE] Starting BLE...
[BLE] BLE server started
[BLE] Waiting for connections...
```

---

## 🧪 功能测试清单

### Test 1: 基础BLE功能（无配对）
- [ ] 打开手机蓝牙扫描工具（如 nRF Connect）
- [ ] 扫描到 "SmartAccess-S3" 设备
- [ ] 设备名称显示正确

### Test 2: 配对模式激活
**前提**: 后端服务已启动

```bash
# 在命令行执行（或用API客户端）
curl -X POST http://localhost:8000/api/hardware/bluetooth/pairing/start \
  -H "Content-Type: application/json" \
  -d '{"binding_id": 1}'
```

**预期结果**:
```json
{
  "success": true,
  "message": "Pairing mode activated for 30 seconds",
  "binding_id": 1
}
```

**检查开发板日志**:
```
[PAIRING] Entering pairing mode...
[PAIRING] Pairing mode activated for 30 seconds
[BLE] Advertising pairing service...
```

### Test 3: 完整配对流程（模拟）

1. 激活配对模式（如上）
2. 手机连接到 "SmartAccess-S3"
3. 设备配对（输入密码或确认6位数字）
4. 配对成功后获取密钥信息
5. 调用完成配对API：
```bash
curl -X POST http://localhost:8000/api/hardware/bluetooth/pairing/complete \
  -H "Content-Type: application/json" \
  -d '{
    "binding_id": 1,
    "device_irk": "1234567890ABCDEF1234567890ABCDEF",
    "device_ltk": "FEDCBA0987654321FEDCBA0987654321",
    "device_name": "My Phone",
    "firmware_version": "2.0.1"
  }'
```

**检查后端日志**:
```
INFO: Pairing record saved for binding_id=1
INFO: Device IRK stored in database
```

**检查数据库**:
```sql
SELECT * FROM bluetooth_pairing_records WHERE binding_id = 1;
```

应该看到新记录插入。

### Test 4: IRK识别验证
```bash
curl -X POST http://localhost:8000/api/hardware/bluetooth/verify \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "door_controller_2",
    "bt_mac": "AA:BB:CC:DD:EE:FF",
    "rssi": -50,
    "device_irk": "1234567890ABCDEF1234567890ABCDEF"
  }'
```

**预期结果** (should identify via IRK):
```json
{
  "allow": true,
  "user_id": 1,
  "binding_id": 1,
  "identification_method": "irk",
  "in_cooldown": false
}
```

### Test 5: MAC降级识别
同样的请求但没有 `device_irk`:
```bash
curl -X POST http://localhost:8000/api/hardware/bluetooth/verify \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "door_controller_2",
    "bt_mac": "AA:BB:CC:DD:EE:FF",
    "rssi": -50
  }'
```

**预期结果** (should identify via MAC):
```json
{
  "allow": true,
  "user_id": 1,
  "binding_id": 1,
  "identification_method": "mac",
  "in_cooldown": false
}
```

### Test 6: 解除配对
```bash
curl -X DELETE http://localhost:8000/api/hardware/bluetooth/pairing/1
```

**预期结果**:
```json
{
  "success": true,
  "message": "Pairing record deleted"
}
```

**验证**: 再次尝试 Test 4，应该回到 MAC 识别模式。

---

## 📱 前端UI测试

### Step 1: 打开蓝牙绑定页面
```
http://localhost:8000/bluetooth
```

### Step 2: 检查UI元素
- [ ] 设备列表显示所有绑定
- [ ] 每个设备显示配对状态徽章
  - 已配对: 🔐 **已配对** (绿色)
  - 未配对: 🔓 **未配对** (灰色)

### Step 3: 测试配对按钮
- [ ] 点击 "开始配对" 按钮
- [ ] 页面显示 "配对模式已激活，请在30秒内从手机连接"
- [ ] 倒计时开始显示，按钮显示 "⏱️ 配对中... Ns"

### Step 4: 页面反应验证
- [ ] 30秒后，按钮恢复可用
- [ ] 显示 "配对超时，请重试"

### Step 5: 测试删除配对
- [ ] 点击已配对设备的 "删除配对" 按钮
- [ ] 确认对话框弹出
- [ ] 点击确认后配对记录被删除
- [ ] 设备状态变回 "未配对"

---

## ⚠️ 常见问题排查

### 问题1: 编译失败 - "未找到库"
**解决**:
1. Arduino IDE → 项目 → 加载库 → 库管理器
2. 搜索缺失的库名称
3. 点击安装

### 问题2: 烧录后设备无反应
**排查**:
1. 检查串口监视器（波特率115200）是否有输出
2. 检查 USB 连接是否稳定
3. 尝试长按 BOOT 按钮 + RST 重启设备

### 问题3: 配对无法完成
**排查**:
1. 检查后端服务是否运行 (`python main.py`)
2. 检查后端日志中有无错误
3. 检查数据库连接是否正常
4. 检查防火墙是否阻止蓝牙连接

### 问题4: IRK识别失败
**排查**:
1. 检查 `device_irk` 是否正确上报（16字节十六进制）
2. 检查数据库中配对记录是否存在
3. 检查验证API日志中的IRK匹配过程

---

## 📊 测试结果记录

### 编译结果
- 状态: [ ] 通过 / [ ] 失败 / [ ] 进行中
- 日期: _________
- 问题: _________________________________________

### 烧录结果
- 状态: [ ] 通过 / [ ] 失败 / [ ] 进行中
- 日期: _________
- 问题: _________________________________________

### 功能测试
- [ ] Test 1 (基础BLE) - 通过 / 失败
- [ ] Test 2 (配对激活) - 通过 / 失败
- [ ] Test 3 (完整配对) - 通过 / 失败
- [ ] Test 4 (IRK识别) - 通过 / 失败
- [ ] Test 5 (MAC识别) - 通过 / 失败
- [ ] Test 6 (解除配对) - 通过 / 失败

### UI测试
- [ ] 所有UI元素正确显示
- [ ] 配对按钮功能正常
- [ ] 倒计时显示准确
- [ ] 删除配对功能正常

---

## ✅ 完成标志

当所有以下项都打钩时，配对功能实现完成：

- [ ] ESP32 固件编译通过
- [ ] ESP32 固件烧录成功
- [ ] 串口监视器显示正常启动日志
- [ ] 手机可扫描到设备
- [ ] 后端API都能响应
- [ ] 前端UI显示配对状态
- [ ] 完整配对流程通过
- [ ] IRK识别正常工作
- [ ] 解除配对功能正常

---

**下一步**: 根据测试结果，调整配置并进行完整的系统验收测试！
