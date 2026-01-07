# ESP32 BLE蓝牙搜索不到 - 故障排查指南

## 🔍 问题现象
- 手机蓝牙设置中搜索不到 `SmartDoor-BT` 设备
- 或者能看到设备但无法连接

---

## 🛠️ 排查步骤

### 步骤1：检查串口日志

连接ESP32到电脑，打开串口监视器（波特率 115200），点击"开始配对"后观察：

#### ✅ 正常日志
```
========== BLE配对流程开始 ==========
目标超时时间: 30000 ms (30 秒)
[BLE] ✓ 已停止BLE扫描
[BLE] 初始化BLE Server...
[BLE] Server创建成功
[BLE] 服务和特征值创建成功
[BLE] 广播参数配置完成
✅ [BLE] Server初始化完成
[BLE] 启动BLE广播...
✅ [BLE] 广播已启动
📡 [BLE] 设备名称: SmartDoor-BT
⏱️  [BLE] 配对窗口: 30 秒
========== BLE配对流程完成 ==========
```

#### ❌ 异常日志
| 日志 | 原因 | 解决方案 |
|------|------|--------|
| `❌ [BLE] 错误：广播对象为空！` | 广播对象创建失败 | 重启ESP32 |
| `[BLE] ⚠️ 警告：广播已在运行` | 广播未正确关闭 | 检查stopBLEPairing |
| `Server创建失败` | 内存不足 | 重启设备 |

### 步骤2：运行BLE诊断

当ESP32在配对模式运行时，查看诊断信息（每30秒自动打印一次）：

```
========== BLE诊断信息 ==========
BLE广播状态: 运行中
配对模式: 激活
BLE Server对象: 已创建
BLE广播对象: 已创建
BLE扫描对象: 已创建
==================================
```

**问题排查表：**

| 广播状态 | Server | 广播对象 | 扫描对象 | 问题 | 解决 |
|---------|--------|---------|---------|------|------|
| 停止 | - | - | - | 广播未启动 | 检查后端是否下发任务 |
| 运行中 | 未创建 | - | - | Server初始化失败 | 重启ESP32 |
| 运行中 | 已创建 | 未创建 | - | 广播对象未创建 | 重启ESP32 |
| 运行中 | 已创建 | 已创建 | 已创建 | ✅ 正常 | 检查手机端 |

### 步骤3：检查手机端

**Android：**
1. 设置 → 蓝牙 → 打开蓝牙
2. 等待设备列表刷新（2-3秒）
3. 找 `SmartDoor-BT`

**iOS：**
1. 设置 → 蓝牙 → 打开蓝牙
2. 向下滚动查看"其他设备"列表
3. 找 `SmartDoor-BT`

如果在列表中看到：
- ✅ `SmartDoor-BT` → 广播正常，点击连接
- ❌ 列表为空或看不到 → 进入步骤4

### 步骤4：检查硬件和固件

#### 问题A：蓝牙模块损坏

**检查方法：**
1. 使用其他支持BLE的设备（如手机）靠近ESP32
2. 确认手机蓝牙能开启

**修复：**
- 重启ESP32
- 检查蓝牙天线是否接触不良
- 检查电源是否稳定（3.3V）

#### 问题B：固件BLE配置错误

**检查编译输出：**
```
Compiling sketch...
[BLE初始化完成]  ← 应该出现此行
```

如果编译时有错误：
```
error: 'BLEAdvertising' has no member named...
```

**修复：**
1. 确保Arduino Core版本 ≥ 2.0.0
2. 安装最新的ESP32库：
   ```
   工具 → 开发板管理器 → 搜索"ESP32" → 安装最新版本
   ```

#### 问题C：冲突的BLE模式

**问题描述：** NFC扫描时BLE广播冲突

**修复：** 已在代码中处理（startBLEPairing会停止扫描）

**检查日志：**
```
[BLE] ✓ 已停止BLE扫描  ← 应该出现此行
```

### 步骤5：增强故障排查

#### 方法A：添加串口命令诊断

在 `setup()` 中添加以下串口命令支持：

```cpp
// 在loop()中添加
if (Serial.available()) {
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  
  if (cmd == "ble-start") {
    startBLEPairing(30000);
  } 
  else if (cmd == "ble-stop") {
    stopBLEPairing();
  }
  else if (cmd == "ble-diag") {
    diagnoseBLE();
  }
}
```

使用方法：
1. 打开串口监视器
2. 输入 `ble-start` 开始配对
3. 输入 `ble-diag` 查看诊断
4. 输入 `ble-stop` 停止配对

#### 方法B：查看WiFi连接状态

```cpp
Serial.printf("WiFi状态: %d\n", WiFi.status());
// 0 = 断开, 1 = 扫描, 2 = 连接中, 3 = 已连接, 4 = 连接失败
```

---

## 📋 完整排查清单

- [ ] 1. 检查串口是否输出 `✅ [BLE] 广播已启动`
- [ ] 2. 确认诊断信息显示 `广播状态: 运行中`
- [ ] 3. 手机蓝牙已打开
- [ ] 4. 手机和ESP32距离 < 2米
- [ ] 5. 手机搜索看到 `SmartDoor-BT`
- [ ] 6. 点击连接时看到配对请求
- [ ] 7. 输入密码 `123456` 或确认配对

---

## 🚨 常见错误和解决

### 错误1：Server创建失败

**原因：** 内存溢出或BLE资源被占用

**解决：**
```cpp
// 减少其他任务的栈大小
// 或者重启ESP32
ESP.restart();
```

### 错误2：广播启动但手机搜不到

**原因：** 广播数据损坏或不兼容

**解决：**
1. 检查设备名称长度是否过长
2. 减少广播数据量
3. 更新Arduino ESP32核心库

**代码修复：**
```cpp
// 在initBLEServer()中
pBLEAdvertising->setCompleteLocalName("SmartDoor");  // 缩短名称
```

### 错误3：配对后仍无法通信

**原因：** 特征值权限配置错误

**解决：**
```cpp
BLECharacteristic *pChar = pService->createCharacteristic(
  BLEUUID((uint16_t)0xFFF1),
  BLECharacteristic::PROPERTY_READ |   // 可读
  BLECharacteristic::PROPERTY_WRITE |  // 可写
  BLECharacteristic::PROPERTY_NOTIFY   // 可通知
);
```

---

## 📞 进阶诊断

### 使用BLE分析工具

**Android：**
- nRF Connect (Nordic)
- BLE Scanner

**iOS：**
- LightBlue (Punchthrough)

**Windows/Mac：**
- BLEAH
- nRF Connect Desktop

### 查看WiFi+BLE干扰

检查 `BLEAdvertising` 和 `WiFi` 是否冲突：

```cpp
// 减少WiFi扫描频率
WiFi.mode(WIFI_STA);
WiFi.setAutoReconnect(true);

// 为BLE分配更多资源
esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, ESP_PWR_LVL_P9);  // 最大功率
```

---

## ✅ 验证修复

修复后重新测试：

1. **打开串口监视器**
2. **点击Web后台的"开始配对"**
3. **查看串口输出** `✅ [BLE] 广播已启动`
4. **打开手机蓝牙**
5. **应该看到 `SmartDoor-BT` 在可用设备列表中**
6. **点击连接**
7. **应该看到配对请求弹窗**
8. **点击"配对"或输入密码**

---

## 💡 优化建议

### 1. 提高发现速度

```cpp
// 在initBLEServer中
pBLEAdvertising->setIntMax(0x80);   // 减小广播间隔
pBLEAdvertising->setIntMin(0x50);
```

### 2. 增强信号强度

```cpp
// 设置发射功率
esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, ESP_PWR_LVL_P9);  // +9dBm
esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_CONN_HDL, ESP_PWR_LVL_P9);
```

### 3. 自定义设备名称

```cpp
// 在initBLEServer中
pBLEAdvertising->setCompleteLocalName("MySmartDoor-ABC123");
```

---

## 📊 性能监控

实时监控BLE状态：

```cpp
void monitorBLE() {
  static unsigned long last_check = 0;
  if (millis() - last_check > 5000) {
    last_check = millis();
    
    Serial.printf("[BLE] 广播: %s, 配对: %s, Server: %s\n",
      ble_advertising ? "ON" : "OFF",
      pairing_mode.active ? "ACTIVE" : "INACTIVE",
      pBLEServer != nullptr ? "READY" : "NONE"
    );
  }
}
```

在 `loop()` 中调用 `monitorBLE()` 以持续监控
