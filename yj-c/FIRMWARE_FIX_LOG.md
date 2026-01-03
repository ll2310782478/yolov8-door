# ESP8266 PN532 固件修复日志

## 问题描述
- **现象**：使用门2卡片开门时，门2正确打开，但延时结束后门1也会打开
- **影响**：只有门2有此问题，门1正常工作
- **根本原因**：`reportCard()` 函数内部直接执行 `openDoor()`，且未正确传递门号信息给 loop 调用者

## 修复详情

### 1. 问题分析
在旧代码中，`reportCard()` 函数有两个问题：
```cpp
// 旧代码问题
bool reportCard(const String &card_uid) {
  // ... 省略 ...
  if (action == "OPEN") {
    uint8_t door_id = (door == "door2") ? 2 : 1;
    openDoor(door_id, 1500);  // ❌ 在此处打开门
    return true;
  }
  // ...
}

// loop 中调用
if (ok) openDoor(1500);  // ❌ 使用默认参数 door=1 再次打开门
```

这导致：
1. `reportCard()` 内部打开了正确的门（门1或门2）
2. loop 中又调用 `openDoor(1500)`，使用默认参数打开门1
3. 门1卡片正常（两次都打开门1）；门2卡片异常（先打开门2，后打开门1）

### 2. 解决方案

#### 步骤1：添加全局变量保存门号信息
```cpp
String last_door = "door1";  // 保存最后一次扫卡的门号信息
```

#### 步骤2：修改 reportCard() 函数
- 移除函数内部的 `openDoor()` 调用
- 保存响应中的门号信息到 `last_door`
- 仅返回 true/false，由调用者决定是否打开门

```cpp
bool reportCard(const String &card_uid) {
  // ... 获取响应 ...
  
  // 保存门号信息供 loop 中使用
  if (door.length() > 0) {
    last_door = door;
  }
  
  if (action == "OPEN") {
    return true;  // ✅ 仅返回 true，不在此处执行 openDoor
  }
  return false;
}
```

#### 步骤3：修改 loop() 中的调用逻辑
在三个地方正确使用保存的门号信息：

**SCAN 命令处理：**
```cpp
if (last_command == "SCAN") {
  // ...
  if (ok) {
    uint8_t door_id = (last_door == "door2") ? 2 : 1;
    openDoor(door_id, 1500);  // ✅ 使用正确的门号
  }
}
```

**OPEN/UNLOCK 命令处理：** (已正确，无需修改)
```cpp
else if (last_command == "OPEN" || last_command == "UNLOCK") {
  uint8_t door_id = 1;
  if (last_payload.length()) {
    // 从 payload 解析 door_id
    if (d == "door2") door_id = 2;
  }
  openDoor(door_id, 1500);  // ✅ 使用正确的门号
}
```

**持续扫描模式：**
```cpp
if (CONTINUOUS_SCAN_MODE) {
  // ...
  if (ok) {
    uint8_t door_id = (last_door == "door2") ? 2 : 1;
    openDoor(door_id, 1500);  // ✅ 使用正确的门号
  }
}
```

## 文件修改

**文件**：`esp8266_pn532_v2.ino`

**修改内容**：
1. 第 64 行：添加 `String last_door = "door1";` 全局变量
2. 第 325-359 行：修改 `reportCard()` 函数
3. 第 412-421 行：修改 SCAN 命令处理
4. 第 450-461 行：修改持续扫描模式处理

## 验证步骤

1. **编译固件**：使用 Arduino IDE 或 PlatformIO 编译修改后的代码
2. **烧录固件**：将修改后的固件烧录到 ESP8266
3. **测试门1**：使用门1的卡片刷卡，验证只打开门1
4. **测试门2**：使用门2的卡片刷卡，验证只打开门2，延时后不打开门1
5. **测试远程命令**：使用 Web 界面远程下发 OPEN 命令指定门号，验证正确的门打开

## 部署建议

- 在完整的硬件测试后再部署到生产环境
- 保持旧版本固件作为备份
- 建议在固件启动时打印版本号，便于识别正在运行的版本
