# BLE 配对机制完整实现指南

## 📋 实现概览

已完整实现 **Numeric Comparison + IRK** 配对方案，包括后端、前端和ESP32固件支持。

## 🔧 实现组件

### ✅ 后端（Python FastAPI）

#### 1. 数据模型 (`models.py`)
```python
class BluetoothPairingRecord(Base):
    """蓝牙配对记录模型"""
    - device_irk: 设备IRK（16字节）
    - device_ltk: 设备LTK（16字节）
    - device_name: 配对时设备名
    - pairing_method: numeric_comparison
    - pairing_timestamp: 配对时间
    - connection_count: 连接次数
    - firmware_version: 固件版本
```

#### 2. API 端点 (`hardware.py`)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/hardware/bluetooth/pairing/start` | POST | 开始配对模式（30秒） |
| `/api/hardware/bluetooth/pairing/complete` | POST | 完成配对并保存IRK/LTK |
| `/api/hardware/bluetooth/pairing/{binding_id}` | GET | 获取配对记录 |
| `/api/hardware/bluetooth/pairings/{binding_id}` | GET | 列出所有配对 |
| `/api/hardware/bluetooth/pairing/verify-irk` | POST | 通过IRK验证身份 |
| `/api/hardware/bluetooth/pairing/{binding_id}` | DELETE | 删除配对（解除配对） |

#### 3. 增强的验证接口
```python
@router.post("/bluetooth/verify")
- 新增 device_irk 参数（可选）
- 优先级：IRK识别 > MAC识别
- 自动更新连接统计
```

### ✅ 前端（HTML/JavaScript）

#### 1. 配对UI 显示
- 设备卡片显示配对状态 (🔐 已配对/未配对)
- 配对按钮 (开始配对/重新配对)
- 配对倒计时显示

#### 2. 配对函数
```javascript
startPairing(bindingId)           // 开始配对模式
completePairing(...)              // 完成配对
removePairing(bindingId)          // 删除配对
showPairingCountdown(seconds)     // 显示倒计时
```

### ✅ ESP32固件（C++）

#### 1. 数据结构
```cpp
struct BLEPairingInfo {
  char device_irk[33];      // 16字节十六进制
  char device_ltk[33];      // 16字节十六进制
  char device_name[100];    // 设备名称
  unsigned long pairing_time;
};

struct PairingModeStatus {
  bool active;              // 是否在配对模式
  unsigned long start_time; // 开始时间
  const unsigned long TIMEOUT = 30000;  // 30秒超时
};
```

#### 2. NVS 存储管理
```cpp
void initNVS()                          // 初始化NVS
void savePairingInfo(irk, ltk, name)   // 保存配对信息
bool loadPairingInfo(irk, info)        // 加载配对信息
void removePairingInfo(irk)            // 删除配对信息
```

#### 3. BLE 扫描增强
- 上报设备是否有配对信息
- 配对信息存储在ESP32本地NVS

---

## 📡 工作流程

### 首次配对流程

```
1. 用户点击 "开始配对"
   └─→ POST /pairing/start
       └─→ ESP32进入可发现状态（30秒超时）
           └─→ 显示蓝牙名称可发现

2. 手机搜索并发起BLE连接
   └─→ ESP32 BLE接受连接
       └─→ 显示Numeric Comparison（6位数字）

3. 用户在手机和ESP32上都确认6位数字
   └─→ 密钥交换成功
       └─→ ESP32获得：device_irk, device_ltk

4. ESP32 保存配对信息
   └─→ NVS存储：irk_XXXXXXXXXXX = {irk, ltk, name, time}

5. 配对完成回调
   └─→ POST /pairing/complete
       ├─ binding_id: 绑定记录ID
       ├─ device_irk: 从ESP32获取
       ├─ device_ltk: 从ESP32获取
       ├─ device_name: 设备名称
       └─ firmware_version: 固件版本
       
6. 后端保存配对记录
   └─→ BluetoothPairingRecord 表
       └─→ 更新 binding.is_paired = true
```

### 后续使用流程

```
1. 手机靠近ESP32（蓝牙信号范围内）
   └─→ ESP32扫描BLE信号
       └─→ 获取设备的MAC和IRK

2. 上报设备信息
   └─→ POST /report-scan-batch
       ├─ devices[].mac: 当前广播的MAC（随机）
       ├─ devices[].rssi: 信号强度
       ├─ devices[].name: 设备名称
       └─ devices[].has_pairing: true/false

3. 后端验证权限
   └─→ POST /verify
       ├─ device_id: door_controller_2
       ├─ bt_mac: 当前MAC（随机的）
       ├─ rssi: 信号强度
       └─ device_irk: IRK（如果有）
       
4. 后端识别流程
   └─→ 如果有 device_irk：
       ├─ 查询 BluetoothPairingRecord.device_irk
       └─→ 立即确认身份 ✨ (快速)
   └─→ 如果没有 device_irk：
       ├─ 查询 BluetoothBinding.device_id = bt_mac
       └─→ 降级到MAC识别 (兼容)

5. 返回权限结果
   └─→ {
       "allow": true,
       "user_id": 1,
       "binding_id": 5,
       "in_cooldown": false
     }

6. 用户按按钮确认开门
   └─→ ESP32记录冷却期
       └─→ addToCooldown(mac)
           └─→ 3分钟内同设备不再提示

7. 后端记录日志
   └─→ POST /access-log
       └─→ 更新 bluetooth_cooldown_cache
```

---

## 🚀 使用指南

### 对用户
1. 打开蓝牙设备管理页面
2. 找到要配对的设备
3. 点击 "开始配对" 按钮
4. 手机打开蓝牙，搜索 "SmartAccess-S3" 
5. 发起配对，输入配对密码（如需要）
6. 在两设备上确认显示的6位数字
7. 配对完成！✅

### 对开发者
1. 后端数据库自动创建表
2. ESP32固件自动初始化NVS存储
3. 配对信息在数据库和ESP32本地双重存储
4. 可随时删除配对（解除配对）

---

## 🔐 安全特性

### 密钥管理
- **IRK（Identity Resolving Key）**: 用于识别配对设备
  - 即使MAC地址随机变化也能识别
  - 存储在后端数据库
  
- **LTK（Long Term Key）**: 用于加密通信
  - 存储在后端（用于重连验证）
  - 存储在ESP32 NVS中

### 配对方式
- **Numeric Comparison**: 
  - 双向确认6位数字
  - 防止中间人攻击
  - 用户友好

### 冷却期保护
- 3分钟内同设备不重复提示
- 防止意外多次开门
- MAC和IRK都参与冷却期计算

---

## ⚙️ 配置说明

### ESP32 配置
```cpp
const unsigned long BLE_COOLDOWN_PERIOD = 180000;  // 3分钟冷却期
const int MAX_PAIRING_RECORDS = 20;                 // 最多20个配对设备
const unsigned long PAIRING_MODE_TIMEOUT = 30000;  // 30秒配对超时
```

### 后端配置
```python
COOLDOWN_PERIOD_SECONDS = 180  # 3分钟
PAIRING_TABLE_RETENTION = 365  # 保留365天配对记录
```

---

## 📊 数据库架构

### BluetoothBinding（已有）
```
id, user_id, device_id (MAC), device_name, is_paired, ...
```

### BluetoothPairingRecord（新增）
```
id, binding_id (FK), device_irk, device_ltk, device_name,
pairing_method, pairing_timestamp, last_connection,
connection_count, firmware_version
```

### 关系
```
BluetoothBinding ──1──*── BluetoothPairingRecord
(一个绑定可有多条配对记录，支持设备重配对历史)
```

---

## 🧪 测试清单

### 功能测试
- [ ] 开始配对 → ESP32进入配对模式
- [ ] 手机BLE配对 → 6位数字确认
- [ ] 配对完成 → 数据保存到数据库和NVS
- [ ] IRK识别 → MAC变化后仍可识别
- [ ] 冷却期 → 3分钟内不重复提示
- [ ] 解除配对 → 恢复MAC识别模式

### 性能测试
- [ ] 配对时间 < 10秒
- [ ] IRK识别时间 < 100ms
- [ ] 扫描响应延迟 < 1秒

### 安全测试
- [ ] 未配对设备无法伪造IRK
- [ ] 密钥不能在网络传输中泄露
- [ ] 冷却期不能被绕过

---

## 🔄 版本升级说明

### 从旧系统迁移
1. 现有MAC绑定继续有效（降级到MAC识别）
2. 新设备可立即进行配对
3. 无需停机维护

### 回滚方案
1. 删除所有配对记录：`DELETE FROM bluetooth_pairing_records`
2. 系统自动降级到MAC识别模式
3. 设备继续正常工作

---

## 📞 故障排除

### 配对失败
- [ ] 检查蓝牙是否打开
- [ ] 检查ESP32是否进入配对模式
- [ ] 检查两设备距离（< 3米）
- [ ] 查看后端日志

### IRK识别失败
- [ ] 检查 `device_irk` 是否正确上报
- [ ] 确认配对记录已保存到数据库
- [ ] 查看verify接口日志

### 冷却期问题
- [ ] 检查 `bluetooth_cooldown_cache` 状态
- [ ] 验证 `COOLDOWN_PERIOD_SECONDS` 配置
- [ ] 查看访问日志中的时间戳

---

## 🎯 下一步功能建议

1. **多设备支持**: 一个用户多个配对设备
2. **配对历史**: 记录所有配对/解除配对操作
3. **固件升级**: 配对设备固件OTA更新
4. **远程管理**: 网页端管理所有配对设备
5. **设备信任**: 标记经常使用的配对设备

---

**实现完成！🎉**

所有代码已集成到项目中，后端服务器已重启并应用所有更改。
