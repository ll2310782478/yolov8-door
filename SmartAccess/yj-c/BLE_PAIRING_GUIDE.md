# ESP32 BLE配对完整指南

## 📋 配对流程概述

```
Web后台 → 下发配对任务 → ESP32接收 → 开启BLE广播 → 手机扫描 → 配对弹窗 → 密钥交换 → 保存绑定
```

---

## 🔧 技术实现细节

### 1. BLE配对模式

ESP32支持两种BLE角色：
- **Central（中心设备）**：主动扫描周围BLE设备（已实现）
- **Peripheral（外设设备）**：广播自己，等待其他设备连接（新增实现）

### 2. 配对安全级别

本实现使用的安全配置：
```cpp
ESP_LE_AUTH_REQ_SC_MITM_BOND  // 安全连接 + MITM保护 + 绑定
ESP_IO_CAP_OUT                // 只能显示（屏幕显示密码）
```

**安全配对方式：**
- ✅ **Numeric Comparison**（数字比对）：ESP32和手机显示相同6位数字，用户确认
- ⚠️ **Passkey Entry**（密码输入）：固定密码123456（可改为随机）
- ❌ **Just Works**：无保护，不推荐

### 3. 密钥类型

配对成功后交换的密钥：
- **IRK（Identity Resolving Key）**：设备身份识别密钥，用于隐私保护
- **LTK（Long Term Key）**：长期密钥，用于加密通信

---

## 🚀 使用步骤

### 步骤1：在Web后台启动配对

1. 访问蓝牙设备管理页面：`http://localhost:8000/web/bluetooth`
2. 找到需要配对的设备绑定
3. 点击"开始配对"按钮
4. 系统会：
   - 选择一个在线的门禁控制器
   - 下发 `BLE_PAIRING_START` 任务
   - 设置30秒配对窗口

### 步骤2：ESP32进入配对模式

ESP32收到任务后会：
1. 停止当前的BLE扫描
2. 初始化BLE Server（如未初始化）
3. 开始BLE广播
4. 在屏幕显示配对提示
5. 播放提示音

**串口日志：**
```
[BLE] 进入配对模式窗口，持续 30000 ms
📡 [BLE] 开始广播，配对窗口: 30 秒
```

### 步骤3：手机端操作

**Android：**
1. 打开"设置" → "蓝牙"
2. 确保蓝牙已开启
3. 在"可用设备"列表中找到 `SmartDoor-BT`
4. 点击连接
5. 系统弹出配对请求：
   - **数字比对**：确认6位数字一致后点"配对"
   - **密码输入**：输入 `123456` 后点"确认"

**iOS：**
1. 打开"设置" → "蓝牙"
2. 在"其他设备"列表中找到 `SmartDoor-BT`
3. 点击设备名称
4. 确认配对请求弹窗

### 步骤4：配对完成

配对成功后：
- ESP32播放成功提示音
- 配对密钥保存到NVS（非易失存储）
- 串口输出密钥信息
- 通知后端服务器（需binding_id）

**串口日志：**
```
✅ [BLE] 配对成功！
[BLE] IRK: A1B2C3D4E5F6...
[BLE] LTK: 9F8E7D6C5B4A...
```

### 步骤5：超时处理

如果30秒内未完成配对：
- ESP32自动停止广播
- 恢复扫描模式
- 播放错误提示音
- 清空屏幕提示

---

## 🔍 故障排查

### 问题1：手机搜索不到 SmartDoor-BT

**可能原因：**
- ESP32未进入配对模式
- 广播未启动
- 蓝牙信号被遮挡

**排查步骤：**
1. 检查串口是否输出 `📡 [BLE] 开始广播`
2. 确认ESP32屏幕显示"BLE Pairing"
3. 靠近ESP32（<2米）重试
4. 关闭手机蓝牙后重新打开

### 问题2：配对请求弹窗不出现

**可能原因：**
- 手机蓝牙权限未授予
- ESP32安全配置不兼容

**解决方法：**
- Android：进入"应用信息" → "权限" → 确认蓝牙权限
- iOS：删除已配对的同名设备后重试

### 问题3：配对失败（fail_reason）

**常见错误码：**
- `0x01`：Passkey不匹配
- `0x02`：配对超时
- `0x05`：PIN码无效

**解决方法：**
- 确保手机和ESP32显示的数字一致
- 在30秒内完成配对
- 检查密码是否为 `123456`

---

## ⚙️ 高级配置

### 修改配对密码

编辑 `http-nfc-s3-dual-core.ino`：
```cpp
uint32_t onPassKeyRequest() {
  return 654321;  // 改为你的密码
}
```

### 修改配对超时时长

**方法1：修改前端默认值**
```javascript
// bluetooth.html
const payload = { 
  binding_id: bindingId, 
  timeout_seconds: 60  // 改为60秒
};
```

**方法2：修改固件默认值**
```cpp
// http-nfc-s3-dual-core.ino
PairingModeStatus pairing_mode = {false, 0, 60000};  // 60秒
```

### 修改BLE广播名称

```cpp
void initBLEServer() {
  BLEDevice::init("MyDoorLock");  // 改为自定义名称
  // ...
}
```

---

## 📊 配对状态检查

### 查看已配对设备（NVS）

ESP32会将配对信息保存在NVS中，重启后仍保留。

**清除所有配对：**
```cpp
Preferences preferences;
preferences.begin("ble_pairing", false);
preferences.clear();
preferences.end();
```

### 串口调试命令

可添加串口调试功能：
```cpp
if (Serial.available()) {
  String cmd = Serial.readStringUntil('\n');
  if (cmd == "pair") {
    startBLEPairing(30000);  // 手动启动配对
  } else if (cmd == "stop") {
    stopBLEPairing();  // 手动停止
  }
}
```

---

## 🔐 安全建议

1. **使用随机密码**：每次配对生成随机6位数字
2. **限制配对次数**：防止暴力破解
3. **配对确认超时**：缩短为10秒
4. **验证设备身份**：保存设备MAC白名单
5. **定期更新密钥**：每30天重新配对

---

## 📚 参考资料

- [ESP32 BLE API文档](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_gap_ble.html)
- [蓝牙安全配对规范](https://www.bluetooth.com/specifications/specs/core-specification-5-3/)
- [ESP32 Arduino BLE库](https://github.com/nkolban/ESP32_BLE_Arduino)

---

## 🎯 总结

本实现提供了完整的ESP32 BLE配对功能：
- ✅ Web后台触发配对
- ✅ ESP32自动开启广播
- ✅ 手机系统配对弹窗
- ✅ 密钥自动保存
- ✅ 超时自动关闭
- ✅ 多种安全配对方式

配对成功后，手机和ESP32建立加密连接，可用于门禁开门、权限验证等场景。
