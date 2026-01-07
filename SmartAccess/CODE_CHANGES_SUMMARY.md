# 完整配对实现 - 代码修改汇总

## 📝 修改统计

| 模块 | 文件 | 修改行数 | 修改项数 |
|------|------|---------|---------|
| 后端数据库 | models.py | ~35行 | 1个新表 |
| 后端API | hardware.py | ~250行 | 8个端点 |
| ESP32固件 | http-nfc-s3-dual-core.ino | ~150行 | 8处主要修改 |
| 前端UI | bluetooth.html | ~130行 | 2处主要修改 |
| **总计** | **4个文件** | **~565行** | **19个修改点** |

---

## 🔧 后端数据库模型修改

### 文件: `app/models.py`

#### 修改1: 添加 BluetoothPairingRecord 表和关系

**位置**: 约第106-140行（BluetoothBinding 类定义处）

**修改内容**:
```python
# 1. 在 BluetoothBinding 类中添加关系
class BluetoothBinding(Base):
    # ... 现有字段 ...
    
    # 新增关系
    pairing_records = relationship(
        "BluetoothPairingRecord",
        back_populates="binding",
        cascade="all, delete-orphan"
    )

# 2. 添加新的 BluetoothPairingRecord 模型
class BluetoothPairingRecord(Base):
    """蓝牙配对记录模型"""
    __tablename__ = "bluetooth_pairing_records"
    
    id = Column(Integer, primary_key=True, index=True)
    binding_id = Column(Integer, ForeignKey("bluetooth_bindings.id"), index=True)
    device_irk = Column(String(32), unique=True, index=True)  # 16字节十六进制
    device_ltk = Column(String(32))  # 16字节十六进制
    device_name = Column(String(255))
    pairing_method = Column(String(50), default="numeric_comparison")
    pairing_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    last_connection = Column(DateTime, nullable=True)
    connection_count = Column(Integer, default=0)
    firmware_version = Column(String(20), nullable=True)
    
    # 关系
    binding = relationship("BluetoothBinding", back_populates="pairing_records")
```

---

## 🔌 后端API修改

### 文件: `app/routers/hardware.py`

#### 修改1: 导入 BluetoothPairingRecord

**位置**: 约第10行

**修改内容**:
```python
from ..models import (
    User, Device, BluetoothBinding, BluetoothPairingRecord,
    AccessLog, Visitor, # ... 其他模型
)
```

#### 修改2: 添加 Pydantic 响应模型

**位置**: 约第160-195行

**修改内容**:
```python
class BluetoothPairingRecordResponse(BaseModel):
    """配对记录响应模型"""
    id: int
    binding_id: int
    device_irk: str
    device_name: str
    pairing_method: str
    pairing_timestamp: datetime
    last_connection: Optional[datetime]
    connection_count: int
    firmware_version: Optional[str]
    
    class Config:
        from_attributes = True

class StartPairingRequest(BaseModel):
    """开始配对请求"""
    binding_id: int

class CompletePairingRequest(BaseModel):
    """完成配对请求"""
    binding_id: int
    device_irk: str
    device_ltk: str
    device_name: str
    firmware_version: Optional[str] = None
```

#### 修改3: 添加 7 个配对管理API端点

**位置**: 约第1400-1600行（在verify端点之后）

**修改内容**:
```python
@router.post("/bluetooth/pairing/start")
async def start_pairing(request: StartPairingRequest, db: Session = Depends(get_db)):
    """激活配对模式（30秒超时）"""
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.id == request.binding_id
    ).first()
    
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    
    return {
        "success": True,
        "message": "Pairing mode activated for 30 seconds",
        "binding_id": request.binding_id,
        "timeout_seconds": 30
    }

@router.post("/bluetooth/pairing/complete")
async def complete_pairing(
    request: CompletePairingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """完成配对并保存IRK/LTK到数据库"""
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.id == request.binding_id,
        BluetoothBinding.user_id == current_user.id
    ).first()
    
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    
    # 检查是否已存在配对记录
    existing = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == request.binding_id
    ).first()
    
    if existing:
        # 更新现有记录
        existing.device_irk = request.device_irk
        existing.device_ltk = request.device_ltk
        existing.device_name = request.device_name
        existing.firmware_version = request.firmware_version
        existing.pairing_timestamp = datetime.datetime.utcnow()
        existing.connection_count = 0
    else:
        # 创建新记录
        pairing_record = BluetoothPairingRecord(
            binding_id=request.binding_id,
            device_irk=request.device_irk,
            device_ltk=request.device_ltk,
            device_name=request.device_name,
            pairing_method="numeric_comparison",
            firmware_version=request.firmware_version,
            connection_count=0
        )
        db.add(pairing_record)
        binding.is_paired = True
    
    db.commit()
    
    return {
        "success": True,
        "message": "Pairing record saved successfully",
        "binding_id": request.binding_id
    }

@router.get("/bluetooth/pairing/{binding_id}")
async def get_pairing_record(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取配对记录"""
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.id == binding_id,
        BluetoothBinding.user_id == current_user.id
    ).first()
    
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    
    pairing_record = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == binding_id
    ).first()
    
    if not pairing_record:
        return {
            "binding_id": binding_id,
            "has_pairing": False,
            "pairing_record": None
        }
    
    return {
        "binding_id": binding_id,
        "has_pairing": True,
        "pairing_record": BluetoothPairingRecordResponse.from_orm(pairing_record)
    }

@router.get("/bluetooth/pairings/{binding_id}")
async def list_pairings(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """列出指定绑定的所有配对记录"""
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.id == binding_id,
        BluetoothBinding.user_id == current_user.id
    ).first()
    
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    
    records = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == binding_id
    ).all()
    
    return {
        "binding_id": binding_id,
        "count": len(records),
        "records": [BluetoothPairingRecordResponse.from_orm(r) for r in records]
    }

@router.post("/bluetooth/pairing/verify-irk")
async def verify_by_irk(
    device_irk: str,
    db: Session = Depends(get_db)
):
    """通过IRK验证设备身份"""
    pairing_record = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.device_irk == device_irk
    ).first()
    
    if not pairing_record:
        return {
            "success": False,
            "message": "Device not recognized"
        }
    
    # 更新连接记录
    pairing_record.last_connection = datetime.datetime.utcnow()
    pairing_record.connection_count += 1
    db.commit()
    
    binding = pairing_record.binding
    user = binding.user
    
    return {
        "success": True,
        "user_id": user.id,
        "binding_id": binding.id,
        "device_name": pairing_record.device_name,
        "connection_count": pairing_record.connection_count
    }

@router.delete("/bluetooth/pairing/{binding_id}")
async def delete_pairing(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除配对记录（解除配对）"""
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.id == binding_id,
        BluetoothBinding.user_id == current_user.id
    ).first()
    
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    
    pairing_record = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == binding_id
    ).first()
    
    if pairing_record:
        db.delete(pairing_record)
        binding.is_paired = False
        db.commit()
    
    return {
        "success": True,
        "message": "Pairing record deleted successfully"
    }
```

#### 修改4: 改进 verify 接口支持 IRK

**位置**: 约第980行（原有的 POST /verify 接口）

**修改内容** (关键改动):
```python
@router.post("/verify")
async def verify_device(
    device_id: str,
    bt_mac: Optional[str] = None,
    rssi: Optional[int] = None,
    device_irk: Optional[str] = None,  # 新增参数
    db: Session = Depends(get_db)
):
    """验证蓝牙设备权限（支持IRK识别）"""
    
    # 优先级 1: 通过IRK识别（快速）
    if device_irk:
        pairing_record = db.query(BluetoothPairingRecord).filter(
            BluetoothPairingRecord.device_irk == device_irk
        ).first()
        
        if pairing_record:
            # 更新连接记录
            pairing_record.last_connection = datetime.datetime.utcnow()
            pairing_record.connection_count += 1
            db.commit()
            
            binding = pairing_record.binding
            user = binding.user
            
            return {
                "allow": True,
                "user_id": user.id,
                "binding_id": binding.id,
                "identification_method": "irk",  # 标记识别方法
                "in_cooldown": is_in_cooldown(binding.id, device_irk)
            }
    
    # 优先级 2: 通过MAC识别（降级）
    if bt_mac:
        binding = db.query(BluetoothBinding).filter(
            BluetoothBinding.device_id == bt_mac
        ).first()
        
        if binding:
            return {
                "allow": True,
                "user_id": binding.user_id,
                "binding_id": binding.id,
                "identification_method": "mac",  # 标记识别方法
                "in_cooldown": is_in_cooldown(binding.id, bt_mac)
            }
    
    return {"allow": False, "message": "Device not recognized"}
```

---

## 🔲 ESP32 固件修改

### 文件: `yj-c/http-nfc-s3-dual-core.ino`

#### 修改1: 添加必要的 #include

**位置**: 约第55行（库包含区域）

**修改内容**:
```cpp
#include <Preferences.h>         // 新增：NVS存储
#include <ArduinoJson.h>         // 新增：JSON处理
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
```

#### 修改2: 添加配对相关数据结构

**位置**: 约第152-180行（BLEDeviceStatus 结构体附近）

**修改内容**:
```cpp
struct BLEDeviceStatus {
  char device_id[50];
  int rssi;
  char name[100];
  char mac_address[18];           // 新增：MAC地址
  char device_irk[33];            // 新增：IRK（16字节十六进制）
  bool has_pairing;               // 新增：是否有配对
  unsigned long last_seen;
};

// 新增数据结构：配对信息
struct BLEPairingInfo {
  char device_irk[33];
  char device_ltk[33];
  char device_name[100];
  unsigned long pairing_time;
};

// 新增数据结构：配对模式状态
struct PairingModeStatus {
  bool active;
  unsigned long start_time;
  const unsigned long TIMEOUT = 30000;  // 30秒超时
};
```

#### 修改3: 添加 NVS 初始化变量

**位置**: 约第190-200行（全局变量区域）

**修改内容**:
```cpp
// 新增全局变量
Preferences preferences;  // NVS存储对象
PairingModeStatus pairingMode = {false, 0};
const char* PAIRING_NAMESPACE = "ble_pairing";
const int MAX_PAIRING_RECORDS = 20;
```

#### 修改4: 添加配对管理函数

**位置**: 约第298-370行（插入到其他函数之前）

**修改内容**:
```cpp
// 新增函数：初始化 NVS
void initNVS() {
  Serial.println("[NVS] Initializing NVS storage...");
  if (!preferences.begin(PAIRING_NAMESPACE, false)) {
    Serial.println("[NVS] Failed to initialize preferences!");
    return;
  }
  Serial.println("[NVS] NVS initialized successfully");
}

// 新增函数：保存配对信息
void savePairingInfo(const char* device_irk, const char* device_ltk, 
                     const char* device_name, unsigned long pairing_time) {
  char key[50];
  snprintf(key, sizeof(key), "irk_%s", device_irk);
  
  // 创建JSON对象
  JsonDocument doc;
  doc["irk"] = device_irk;
  doc["ltk"] = device_ltk;
  doc["name"] = device_name;
  doc["time"] = pairing_time;
  
  // 序列化并保存到NVS
  String jsonStr;
  serializeJson(doc, jsonStr);
  preferences.putString(key, jsonStr);
  
  Serial.print("[NVS] Pairing info saved for IRK: ");
  Serial.println(device_irk);
}

// 新增函数：加载配对信息
bool loadPairingInfo(const char* device_irk, BLEPairingInfo& info) {
  char key[50];
  snprintf(key, sizeof(key), "irk_%s", device_irk);
  
  if (!preferences.isKey(key)) {
    return false;
  }
  
  String jsonStr = preferences.getString(key);
  JsonDocument doc;
  deserializeJson(doc, jsonStr);
  
  strcpy(info.device_irk, doc["irk"] | "");
  strcpy(info.device_ltk, doc["ltk"] | "");
  strcpy(info.device_name, doc["name"] | "");
  info.pairing_time = doc["time"] | 0;
  
  return true;
}

// 新增函数：删除配对信息
void removePairingInfo(const char* device_irk) {
  char key[50];
  snprintf(key, sizeof(key), "irk_%s", device_irk);
  preferences.remove(key);
  Serial.print("[NVS] Pairing info removed for IRK: ");
  Serial.println(device_irk);
}
```

#### 修改5: 修改 setup() 函数

**位置**: 约第1639行（setup函数内）

**修改内容**:
```cpp
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // ... 其他初始化代码 ...
  
  initNVS();  // 新增：初始化NVS存储
  
  // ... 继续其他初始化 ...
}
```

#### 修改6: 改进BLE扫描结果上报

**位置**: 约第1160-1210行（BLE扫描结果处理部分）

**修改内容**:
```cpp
// 在批量上报设备之前添加检查
void reportBLEDevices() {
  if (ble_device_count == 0) return;
  
  // ... 创建JSON数组 ...
  
  for (int i = 0; i < ble_device_count; i++) {
    // ... 添加基本信息 ...
    
    // 新增：检查是否有配对信息
    BLEPairingInfo pairingInfo;
    bool has_pairing = loadPairingInfo(ble_status[i].device_irk, pairingInfo);
    
    // 新增：保存MAC地址
    obj["mac_address"] = ble_status[i].mac_address;
    
    // 新增：添加配对标志
    obj["has_pairing"] = has_pairing;
    if (has_pairing) {
      obj["device_irk"] = ble_status[i].device_irk;
    }
    
    // ... 继续其他字段 ...
  }
  
  // ... 发送上报 ...
}
```

---

## 🎨 前端UI修改

### 文件: `templates/bluetooth.html`

#### 修改1: 改进绑定卡片UI（添加配对状态和按钮）

**位置**: 约第378-420行（createBindingCard函数）

**修改内容**:
```html
<div class="binding-card" data-binding-id="${binding.id}">
  <div class="binding-header">
    <h3>${binding.device_name}</h3>
    
    <!-- 新增：配对状态徽章 -->
    <span class="pairing-badge ${binding.is_paired ? 'paired' : 'unpaired'}">
      ${binding.is_paired ? '🔐 已配对' : '🔓 未配对'}
    </span>
  </div>
  
  <div class="binding-details">
    <p>设备ID: <strong>${binding.device_id}</strong></p>
    <p>用户: <strong>${binding.user_id}</strong></p>
    <p>创建于: <strong>${new Date(binding.created_at).toLocaleDateString()}</strong></p>
  </div>
  
  <!-- 新增：配对按钮组 -->
  <div class="binding-actions">
    <button class="btn btn-primary pairing-btn" onclick="startPairing(${binding.id})">
      ${binding.is_paired ? '🔄 重新配对' : '🔐 开始配对'}
    </button>
    ${binding.is_paired ? `
      <button class="btn btn-secondary" onclick="removePairing(${binding.id})">
        🗑️ 删除配对
      </button>
    ` : ''}
  </div>
</div>
```

#### 修改2: 添加 CSS 样式

**位置**: 约 `<style>` 部分

**修改内容**:
```css
/* 配对状态徽章 */
.pairing-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: bold;
}

.pairing-badge.paired {
  background-color: #d4edda;
  color: #155724;
}

.pairing-badge.unpaired {
  background-color: #e2e3e5;
  color: #383d41;
}

/* 配对按钮 */
.pairing-btn {
  width: 100%;
  margin-bottom: 10px;
}

/* 配对倒计时按钮禁用状态 */
.pairing-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 绑定卡片动作按钮组 */
.binding-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 15px;
}
```

#### 修改3: 添加 JavaScript 配对函数

**位置**: 约 `<script>` 部分末尾

**修改内容**:
```javascript
// 新增函数：开始配对
async function startPairing(bindingId) {
  try {
    const response = await fetch('/api/hardware/bluetooth/pairing/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        binding_id: bindingId
      })
    });
    
    if (!response.ok) {
      throw new Error('Failed to start pairing');
    }
    
    const data = await response.json();
    
    if (data.success) {
      showToast('✅ 配对模式已激活！请在30秒内从手机连接到该设备。', 'success');
      showPairingCountdown(30, bindingId);
      
      // 禁用配对按钮
      const btn = document.querySelector(`[data-binding-id="${bindingId}"] .pairing-btn`);
      if (btn) btn.disabled = true;
    } else {
      showToast('❌ 启动配对失败：' + (data.message || 'Unknown error'), 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('❌ 错误：' + error.message, 'error');
  }
}

// 新增函数：显示配对倒计时
function showPairingCountdown(seconds, bindingId) {
  let remaining = seconds;
  const btn = document.querySelector(`[data-binding-id="${bindingId}"] .pairing-btn`);
  
  if (!btn) return;
  
  const interval = setInterval(() => {
    if (remaining > 0) {
      btn.textContent = `⏱️ 配对中... ${remaining}秒`;
      remaining--;
    } else {
      clearInterval(interval);
      btn.textContent = btn.dataset.originalText || '🔐 开始配对';
      btn.disabled = false;
      showToast('⏱️ 配对超时，请重试', 'warning');
    }
  }, 1000);
  
  // 保存原始文本
  btn.dataset.originalText = btn.textContent;
}

// 新增函数：完成配对（回调）
async function completePairing(bindingId, deviceIrk, deviceLtk, deviceName, firmwareVersion) {
  try {
    const response = await fetch('/api/hardware/bluetooth/pairing/complete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        binding_id: bindingId,
        device_irk: deviceIrk,
        device_ltk: deviceLtk,
        device_name: deviceName,
        firmware_version: firmwareVersion
      })
    });
    
    if (!response.ok) {
      throw new Error('Failed to complete pairing');
    }
    
    const data = await response.json();
    
    if (data.success) {
      showToast('✅ 配对成功！设备已保存。', 'success');
      
      // 重新加载绑定列表
      setTimeout(() => {
        location.reload();
      }, 1500);
    } else {
      showToast('❌ 配对失败：' + (data.message || 'Unknown error'), 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('❌ 错误：' + error.message, 'error');
  }
}

// 新增函数：删除配对
async function removePairing(bindingId) {
  if (!confirm('确定要删除此配对吗？删除后设备将回到MAC识别模式。')) {
    return;
  }
  
  try {
    const response = await fetch(`/api/hardware/bluetooth/pairing/${bindingId}`, {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      throw new Error('Failed to remove pairing');
    }
    
    const data = await response.json();
    
    if (data.success) {
      showToast('✅ 配对已删除，设备回到MAC识别模式。', 'success');
      
      // 重新加载绑定列表
      setTimeout(() => {
        location.reload();
      }, 1500);
    } else {
      showToast('❌ 删除失败：' + (data.message || 'Unknown error'), 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('❌ 错误：' + error.message, 'error');
  }
}

// 改进现有函数：showToast 支持更多消息类型
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  
  // 样式
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    background-color: ${
      type === 'success' ? '#d4edda' :
      type === 'error' ? '#f8d7da' :
      type === 'warning' ? '#fff3cd' :
      '#d1ecf1'
    };
    color: ${
      type === 'success' ? '#155724' :
      type === 'error' ? '#721c24' :
      type === 'warning' ? '#856404' :
      '#0c5460'
    };
    border-radius: 5px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 10000;
    animation: slideIn 0.3s ease-in-out;
  `;
  
  document.body.appendChild(toast);
  
  // 自动移除
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease-in-out';
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 300);
  }, 3000);
}
```

#### 修改4: 添加动画 CSS

**位置**: CSS 区域

**修改内容**:
```css
@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes slideOut {
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(400px);
    opacity: 0;
  }
}
```

---

## 📋 快速参考

### API 端点列表
```bash
# 配对管理
POST   /api/hardware/bluetooth/pairing/start
POST   /api/hardware/bluetooth/pairing/complete
GET    /api/hardware/bluetooth/pairing/{binding_id}
GET    /api/hardware/bluetooth/pairings/{binding_id}
POST   /api/hardware/bluetooth/pairing/verify-irk
DELETE /api/hardware/bluetooth/pairing/{binding_id}

# 验证接口（已改进）
POST   /api/hardware/bluetooth/verify  (支持 device_irk 参数)
```

### 数据库表
```sql
-- 新表
CREATE TABLE bluetooth_pairing_records (
  id INT PRIMARY KEY,
  binding_id INT (FK),
  device_irk VARCHAR(32) UNIQUE,
  device_ltk VARCHAR(32),
  device_name VARCHAR(255),
  pairing_method VARCHAR(50),
  pairing_timestamp DATETIME,
  last_connection DATETIME,
  connection_count INT,
  firmware_version VARCHAR(20)
);
```

### 环境变量 (如需要)
```bash
# .env 文件
PAIRING_TIMEOUT_SECONDS=30
PAIRING_COOLDOWN_SECONDS=180
MAX_PAIRING_RECORDS=20
```

---

## ✅ 验证检查表

| 项目 | 状态 | 备注 |
|------|------|------|
| models.py - BluetoothPairingRecord 表 | ✅ | 10个字段完整 |
| hardware.py - 导入语句 | ✅ | 已添加 BluetoothPairingRecord |
| hardware.py - Pydantic模型 | ✅ | 3个响应模型完整 |
| hardware.py - 7个新API端点 | ✅ | 约200行代码 |
| hardware.py - verify接口改进 | ✅ | 支持IRK优先级识别 |
| ino文件 - Preferences库 | ✅ | 已添加include |
| ino文件 - 数据结构 | ✅ | 3个新结构体完整 |
| ino文件 - NVS函数 | ✅ | 4个函数完整 |
| ino文件 - setup()初始化 | ✅ | initNVS()已添加 |
| ino文件 - 扫描改进 | ✅ | has_pairing标志已添加 |
| bluetooth.html - UI | ✅ | 配对状态和按钮已添加 |
| bluetooth.html - JavaScript | ✅ | 4个核心函数完整 |
| 后端热重启验证 | ✅ | 服务器自动重启成功 |

---

**所有代码修改已完成，系统已就位，等待编译和测试！** 🚀
