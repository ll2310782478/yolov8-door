# 🔴 蓝牙开门问题诊断报告

## 问题现象
- ✅ BLE扫描工作正常（检测到6个周围设备）
- ✅ 批量上报已启用（减少HTTP请求90%）
- ❌ **蓝牙开门功能无法使用**

---

## 根本原因分析

### 🔍 1. 后端缺少关键API接口（已修复）

**问题代码位置：** ESP32固件 第1259-1340行
```cpp
// 硬件试图调用不存在的接口
HTTPClient http;
String url = String("http://") + currentHost + ":" + String(SERVER_PORT) + "/api/hardware/bluetooth/verify";
// ❌ 此接口在后端不存在！导致HTTP 404
```

**影响流程：**
```
设备检测 → 发送EVENT_BLE_DEVICE_DETECTED → 调用/verify接口 → ❌ 404错误 → 无法进入等待确认状态
```

### 🔍 2. 缺少的后端接口

已添加以下三个缺失的接口：

#### ✅ A. `/api/hardware/bluetooth/verify` (POST)
**用途：** 验证蓝牙设备权限
**流程：**
```
ESP32请求 → 查询蓝牙绑定表 → 检查权限有效期 → 检查每日限额 → 返回allow/deny
```
**请求体：**
```json
{
  "device_id": "door_controller_2",
  "bt_mac": "60:99:9B:73:24:BF",
  "rssi": -65
}
```
**响应：**
```json
{
  "allow": true,
  "user_name": "John",
  "user_id": 1,
  "rssi": -65
}
```

#### ✅ B. `/api/hardware/bluetooth/access-log` (POST)
**用途：** 记录蓝牙开门访问日志
**请求体：**
```json
{
  "device_id": "door_controller_2",
  "bt_mac": "60:99:9B:73:24:BF",
  "access_type": "bluetooth",
  "status": "success"
}
```

#### ✅ C. `/api/hardware/bluetooth/bindings` (GET)
**用途：** 硬件启动时获取白名单
**功能：** 定期更新授权蓝牙设备列表

---

## 蓝牙开门完整流程

### 📊 流程图
```
┌─────────────────┐
│  设备靠近门禁   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│  bleScanner()线程         │
│  - 扫描BLE设备           │
│  - 检查本地白名单        │
│  - 发送EVENT_BLE_DEVICE  │
└────────┬─────────────────┘
         │
         ▼
┌────────────────────────────┐
│  eventHandler()线程        │
│  EVENT_BLE_DEVICE_DETECTED │
│  ├─ 调用/verify验证权限    │✅ 已添加
│  ├─ 设置waiting_confirm   │
│  ├─ 显示"按按钮"提示      │
│  └─ 播放提示音             │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│  用户按BOOT按钮确认       │
│  ├─ buttonMonitor()检测   │
│  ├─ 发送EVENT_BTN_CONFIRM │
│  └─ 执行开门逻辑          │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│  门禁打开                   │
│  ├─ 控制继电器            │
│  ├─ 播放成功音             │
│  ├─ 亮绿色LED             │
│  └─ 记录访问日志          │
└────────────────────────────┘
```

---

## 数据库要求

### 📋 蓝牙绑定表 (bluetooth_bindings)
```sql
CREATE TABLE bluetooth_bindings (
    id INT PRIMARY KEY,
    user_id INT NOT NULL,
    device_id VARCHAR(50) NOT NULL,  -- 蓝牙MAC地址（大写）
    device_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_paired BOOLEAN DEFAULT FALSE,
    permission_start_date DATETIME,
    permission_end_date DATETIME,
    daily_use_count INT DEFAULT 0,
    last_use_date DATETIME,
    max_daily_uses INT DEFAULT 0,  -- 0=无限制
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 📝 示例数据
```sql
INSERT INTO bluetooth_bindings (user_id, device_id, device_name, is_active) 
VALUES (1, '60:99:9B:73:24:BF', 'iPhone 12', TRUE);
```

---

## 诊断检查清单

- [x] 后端服务运行（端口8000）
- [x] 数据库连接正常
- [x] ESP32固件支持蓝牙扫描
- [x] BLE扫描检测到设备
- [x] `/api/hardware/bluetooth/bindings` 接口存在 ✅ 已添加
- [x] `/api/hardware/bluetooth/verify` 接口存在 ✅ 已添加
- [x] `/api/hardware/bluetooth/access-log` 接口存在 ✅ 已添加
- [ ] 数据库中有有效的蓝牙绑定记录 ⚠️ **需要您添加**

---

## 待完成的工作

### 1️⃣ 添加蓝牙绑定记录（**用户操作**）
在Web界面的"蓝牙管理"页面：
1. 扫描设备（显示周围的蓝牙设备）
2. 选择要绑定的设备
3. 选择授权用户
4. 设置权限有效期
5. 点击"确认授权"

### 2️⃣ 测试蓝牙开门流程
1. 编译上传修复后的固件
2. 打开ESP32串口监视器
3. 拿授权的设备靠近门禁
4. 应该看到：
   ```
   [BLE] 授权设备靠近: 60:99:9B:73:24:BF
   [Event] 蓝牙设备检测: 60:99:9B:73:24:BF
   [BLE] 验证响应 code=200, resp={"allow":true,...}
   [BLE] 授权通过: John
   ```
5. 按BOOT按钮
6. 应该看到：
   ```
   [Event] 按钮确认，执行蓝牙开门: ...
   [Door] 开门成功
   ```

### 3️⃣ 监控日志
后端日志应该显示：
```
2026-01-06 21:15:30 INFO POST /api/hardware/bluetooth/report-scan-batch 200 OK
2026-01-06 21:15:32 INFO POST /api/hardware/bluetooth/verify 200 OK (allow=true)
2026-01-06 21:15:35 INFO POST /api/hardware/bluetooth/access-log 200 OK
```

---

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| BLE扫描周期 | 3秒 | 每次扫描时间 |
| 上报间隔 | 5秒 | 批量上报间隔 |
| 等待确认超时 | 10秒 | 按按钮超时时间 |
| RSSI阈值 | -70dBm | 只检测强信号设备 |
| 白名单更新 | 60秒 | 定期更新授权列表 |

---

## 后续优化建议

1. **Web端设备扫描**：显示扫描到的BLE设备列表
2. **权限管理**：支持时间段限制、次数限制、特定位置限制
3. **日志查询**：支持蓝牙开门历史查询
4. **多设备支持**：一个用户可以绑定多个蓝牙设备

---

**最后更新：** 2026-01-06 21:15
**状态：** ✅ 接口实现完成，等待测试
