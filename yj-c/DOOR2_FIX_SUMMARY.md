# 门2控制异常 - 修复摘要

## 问题
使用门2卡片开门时：
- ✓ 门2正确打开
- ✗ 延时结束后，门1也会打开（不应该发生）
- 门1正常工作（无此问题）

## 根本原因
`reportCard()` 函数内部执行 `openDoor()` 并直接返回，但调用者 `loop()` 中又用默认参数 `openDoor(1500)` 再执行一次，导致门1被额外打开。

## 修复方案
**解耦门控逻辑**：
1. `reportCard()` 仅负责上报卡号并返回 true/false，不执行开门
2. `loop()` 根据返回的门号信息（`last_door`）正确调用 `openDoor(door_id, 1500)`
3. 确保每次刷卡只执行一次 `openDoor()` 调用，且使用正确的门号

## 改动文件
- `esp8266_pn532_v2.ino`（4处修改）：
  - ✅ 添加全局变量 `last_door`
  - ✅ 修改 `reportCard()` 函数（移除内部 openDoor 调用）
  - ✅ 修改 SCAN 命令处理（使用 last_door）
  - ✅ 修改持续扫描模式（使用 last_door）

## 下一步操作
1. 编译修改后的固件
2. 烧录到 ESP8266
3. 重新测试门2卡片，验证问题已解决
4. 确保门1和门2都能独立正确打开

## 关键代码变化
```cpp
// ❌ 旧逻辑（问题）
bool ok = reportCard(uid);
if (ok) openDoor(1500);  // 默认打开 door=1

// ✅ 新逻辑（修复）
bool ok = reportCard(uid);
if (ok) {
  uint8_t door_id = (last_door == "door2") ? 2 : 1;
  openDoor(door_id, 1500);  // 使用正确的门号
}
```
