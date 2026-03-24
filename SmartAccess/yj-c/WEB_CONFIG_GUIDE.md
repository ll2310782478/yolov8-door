# 🔧 ESP32 Web配置引导流程设计

## 📋 当前自注册流程

### **现状分析**
1. **硬编码配置**: ESP32 固件中硬编码 WiFi SSID/密码和服务器地址
2. **自动注册**: 上电后自动连接 WiFi 并向服务器注册
3. **依赖前提**: 必须提前知道目标 WiFi 信息

### **问题**
- ❌ **部署复杂**: 每个设备都需要重新编译固件
- ❌ **网络依赖**: 必须提前配置 WiFi 信息
- ❌ **不可扩展**: 大批量部署困难

---

## 🎯 新增 Web 配置引导流程

### **整体架构**

```
ESP32首次启动 → AP模式热点 → 用户连接 → Web配置页面 → 保存配置 → 重启连接 → 注册到服务器
```

### **详细流程**

#### **阶段1: AP模式启动**
ESP32 上电检测是否已配置 WiFi：
- **未配置**: 进入 AP 模式，创建热点 "SmartDoor-Setup"
- **已配置**: 正常启动，连接目标 WiFi

#### **阶段2: Web配置界面**
用户连接热点后访问 `http://192.168.4.1` 进入配置页面：
- WiFi 网络扫描和选择
- 密码输入
- 服务器地址配置
- 设备信息设置

#### **阶段3: 配置保存**
- 保存到 ESP32 NVS 存储
- 重启设备
- 连接目标网络
- 注册到服务器

---

## 🛠️ 实现方案

### **1. ESP32 端修改**

#### **添加依赖**
```cpp
#include <WiFi.h>
#include <WebServer.h>        // 新增：Web服务器
#include <Preferences.h>      // NVS存储
#include <DNSServer.h>        // 新增：DNS服务器（可选）
```

#### **配置存储结构**
```cpp
struct DeviceConfig {
  char wifi_ssid[32];
  char wifi_password[64];
  char server_host[64];
  int server_port;
  bool configured;
};
```

#### **AP模式启动逻辑**
```cpp
void setupAPMode() {
  Serial.println("🔧 进入配置模式...");
  
  // 创建AP热点
  WiFi.softAP("SmartDoor-Setup", "12345678");
  Serial.println("📡 AP热点已创建: SmartDoor-Setup");
  
  // 启动Web服务器
  setupWebServer();
  
  // 显示配置提示
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_BLUE);
  tft.setCursor(10, 50);
  tft.println("Configuration Mode");
  tft.setCursor(10, 80);
  tft.println("Connect to:");
  tft.setCursor(10, 110);
  tft.println("WiFi: SmartDoor-Setup");
  tft.setCursor(10, 140);
  tft.println("Password: 12345678");
  tft.setCursor(10, 170);
  tft.println("Then visit:");
  tft.setCursor(10, 200);
  tft.println("http://192.168.4.1");
}
```

#### **Web服务器配置**
```cpp
WebServer server(80);

void setupWebServer() {
  // 根页面：配置表单
  server.on("/", HTTP_GET, []() {
    String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <title>SmartDoor Configuration</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .wifi-list { max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 5px; }
        .wifi-item { padding: 5px; cursor: pointer; border-bottom: 1px solid #eee; }
        .wifi-item:hover { background: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚪 SmartDoor 配置</h1>
        <form id="configForm">
            <div class="form-group">
                <label>WiFi 网络:</label>
                <select id="wifiSelect" required>
                    <option value="">选择网络...</option>
                </select>
                <button type="button" onclick="scanWifi()">扫描网络</button>
            </div>
            
            <div class="form-group">
                <label>WiFi 密码:</label>
                <input type="password" id="wifiPassword" required>
            </div>
            
            <div class="form-group">
                <label>服务器地址:</label>
                <input type="text" id="serverHost" placeholder="192.168.1.100" required>
            </div>
            
            <div class="form-group">
                <label>服务器端口:</label>
                <input type="number" id="serverPort" value="8000" required>
            </div>
            
            <div class="form-group">
                <label>设备名称:</label>
                <input type="text" id="deviceName" placeholder="门禁控制器" required>
            </div>
            
            <div class="form-group">
                <label>设备位置:</label>
                <input type="text" id="deviceLocation" placeholder="办公室入口">
            </div>
            
            <button type="submit">保存并重启</button>
        </form>
        
        <div id="status"></div>
    </div>

    <script>
        async function scanWifi() {
            try {
                const response = await fetch('/scan');
                const networks = await response.json();
                
                const select = document.getElementById('wifiSelect');
                select.innerHTML = '<option value="">选择网络...</option>';
                
                networks.forEach(network => {
                    const option = document.createElement('option');
                    option.value = network.ssid;
                    option.textContent = `${network.ssid} (${network.rssi}dBm)`;
                    select.appendChild(option);
                });
            } catch (error) {
                alert('扫描失败: ' + error.message);
            }
        }
        
        document.getElementById('configForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = {
                wifi_ssid: document.getElementById('wifiSelect').value,
                wifi_password: document.getElementById('wifiPassword').value,
                server_host: document.getElementById('serverHost').value,
                server_port: parseInt(document.getElementById('serverPort').value),
                device_name: document.getElementById('deviceName').value,
                device_location: document.getElementById('deviceLocation').value
            };
            
            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                
                const result = await response.json();
                if (result.success) {
                    document.getElementById('status').innerHTML = 
                        '<p style="color: green;">✅ 配置保存成功！设备将重启...</p>';
                    setTimeout(() => {
                        fetch('/restart');
                    }, 2000);
                } else {
                    throw new Error(result.message);
                }
            } catch (error) {
                document.getElementById('status').innerHTML = 
                    `<p style="color: red;">❌ 保存失败: ${error.message}</p>`;
            }
        });
        
        // 页面加载时自动扫描WiFi
        scanWifi();
    </script>
</body>
</html>
    )rawliteral";
    
    server.send(200, "text/html", html);
  });
  
  // WiFi扫描API
  server.on("/scan", HTTP_GET, []() {
    String json = "[";
    int n = WiFi.scanNetworks();
    
    for (int i = 0; i < n; ++i) {
      if (i > 0) json += ",";
      json += "{";
      json += "\"ssid\":\"" + WiFi.SSID(i) + "\",";
      json += "\"rssi\":" + String(WiFi.RSSI(i)) + ",";
      json += "\"encryption\":" + String(WiFi.encryptionType(i));
      json += "}";
    }
    
    json += "]";
    server.send(200, "application/json", json);
  });
  
  // 保存配置API
  server.on("/save", HTTP_POST, []() {
    String json = server.arg("plain");
    
    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, json);
    
    if (error) {
      server.send(400, "application/json", "{\"success\":false,\"message\":\"JSON解析失败\"}");
      return;
    }
    
    // 保存到NVS
    Preferences prefs;
    prefs.begin("device_config", false);
    
    prefs.putString("wifi_ssid", doc["wifi_ssid"]);
    prefs.putString("wifi_password", doc["wifi_password"]);
    prefs.putString("server_host", doc["server_host"]);
    prefs.putInt("server_port", doc["server_port"]);
    prefs.putString("device_name", doc["device_name"]);
    prefs.putString("device_location", doc["device_location"]);
    prefs.putBool("configured", true);
    
    prefs.end();
    
    server.send(200, "application/json", "{\"success\":true,\"message\":\"配置已保存\"}");
  });
  
  // 重启API
  server.on("/restart", HTTP_GET, []() {
    server.send(200, "application/json", "{\"message\":\"正在重启...\"}");
    delay(1000);
    ESP.restart();
  });
  
  server.begin();
  Serial.println("🌐 Web服务器已启动: http://192.168.4.1");
}
```

#### **配置检查和加载**
```cpp
bool loadDeviceConfig(DeviceConfig& config) {
  Preferences prefs;
  prefs.begin("device_config", true);  // 只读模式
  
  config.configured = prefs.getBool("configured", false);
  
  if (config.configured) {
    String ssid = prefs.getString("wifi_ssid", "");
    String pass = prefs.getString("wifi_password", "");
    String host = prefs.getString("server_host", "");
    int port = prefs.getInt("server_port", 8000);
    String name = prefs.getString("device_name", "");
    String loc = prefs.getString("device_location", "");
    
    strncpy(config.wifi_ssid, ssid.c_str(), sizeof(config.wifi_ssid));
    strncpy(config.wifi_password, pass.c_str(), sizeof(config.wifi_password));
    strncpy(config.server_host, host.c_str(), sizeof(config.server_host));
    config.server_port = port;
    
    // 更新全局变量
    DEVICE_NAME = name.c_str();
    DEVICE_LOC = loc.c_str();
    SERVER_HOST = host.c_str();
    SERVER_PORT = port;
    SSID = ssid.c_str();
    PASSWORD = pass.c_str();
  }
  
  prefs.end();
  return config.configured;
}
```

#### **修改 setup() 函数**
```cpp
void setup() {
  // ... 其他初始化 ...
  
  // 检查是否已配置
  DeviceConfig config;
  if (!loadDeviceConfig(config)) {
    // 未配置，进入AP模式
    setupAPMode();
    return;  // 不继续正常启动
  }
  
  // 已配置，继续正常启动流程
  // ... WiFi连接和设备注册 ...
}
```

### **2. 后端增强**

#### **添加配置状态查询API**
```python
@router.get("/devices/unconfigured")
def get_unconfigured_devices(db: Session = Depends(get_db)):
    """获取未配置的设备（用于管理页面显示）"""
    devices = db.query(HardwareDevice).filter(
        HardwareDevice.connection_status == "unconfigured"
    ).all()
    return devices

@router.post("/devices/{device_id}/configure")
def configure_device(
    device_id: str,
    config: dict,
    db: Session = Depends(get_db)
):
    """远程配置设备（预留接口）"""
    # 这里可以实现远程推送配置到设备
    pass
```

### **3. Web前端配置引导页面**

#### **创建设备发现页面**
```html
<!-- devices.html -->
<div class="device-discovery">
    <h2>🔍 设备发现与配置</h2>
    
    <div class="discovery-section">
        <h3>未配置设备</h3>
        <div id="unconfiguredDevices">
            <p>扫描中...</p>
        </div>
        <button onclick="scanDevices()">重新扫描</button>
    </div>
    
    <div class="config-section" id="configPanel" style="display: none;">
        <h3>配置设备</h3>
        <form id="deviceConfigForm">
            <div class="form-group">
                <label>设备ID:</label>
                <input type="text" id="configDeviceId" readonly>
            </div>
            
            <div class="form-group">
                <label>设备名称:</label>
                <input type="text" id="configDeviceName" required>
            </div>
            
            <div class="form-group">
                <label>位置:</label>
                <input type="text" id="configLocation">
            </div>
            
            <div class="form-group">
                <label>模式:</label>
                <select id="configMode">
                    <option value="remote_only">远程控制</option>
                    <option value="remote_nfc">NFC + 远程</option>
                </select>
            </div>
            
            <button type="submit">保存配置</button>
            <button type="button" onclick="cancelConfig()">取消</button>
        </form>
    </div>
</div>

<script>
async function scanDevices() {
    try {
        const response = await fetch('/api/hardware/devices/unconfigured');
        const devices = await response.json();
        
        const container = document.getElementById('unconfiguredDevices');
        container.innerHTML = '';
        
        if (devices.length === 0) {
            container.innerHTML = '<p>暂无未配置设备</p>';
            return;
        }
        
        devices.forEach(device => {
            const deviceCard = document.createElement('div');
            deviceCard.className = 'device-card';
            deviceCard.innerHTML = `
                <h4>${device.device_name || '未知设备'}</h4>
                <p>ID: ${device.device_id}</p>
                <p>IP: ${device.ip_address || '未知'}</p>
                <p>状态: ${device.connection_status}</p>
                <button onclick="configureDevice('${device.device_id}')">配置</button>
            `;
            container.appendChild(deviceCard);
        });
    } catch (error) {
        console.error('扫描设备失败:', error);
    }
}

function configureDevice(deviceId) {
    // 显示配置面板
    document.getElementById('configPanel').style.display = 'block';
    document.getElementById('configDeviceId').value = deviceId;
    
    // 滚动到配置面板
    document.getElementById('configPanel').scrollIntoView();
}

document.getElementById('deviceConfigForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const deviceId = document.getElementById('configDeviceId').value;
    const config = {
        device_name: document.getElementById('configDeviceName').value,
        location: document.getElementById('configLocation').value,
        device_mode: document.getElementById('configMode').value
    };
    
    try {
        const response = await fetch(`/api/hardware/devices/${deviceId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            alert('配置成功！');
            document.getElementById('configPanel').style.display = 'none';
            scanDevices(); // 重新扫描
        } else {
            throw new Error('配置失败');
        }
    } catch (error) {
        alert('配置失败: ' + error.message);
    }
});

// 页面加载时自动扫描
scanDevices();
</script>
```

---

## 📋 完整流程图

```
1. ESP32首次启动
   ↓
2. 检查NVS配置
   ├── 已配置 → 连接WiFi → 注册到服务器
   └── 未配置 → 进入AP模式
                  ↓
3. 创建热点 "SmartDoor-Setup"
   ↓
4. 用户连接热点
   ↓
5. 访问 http://192.168.4.1
   ↓
6. Web配置页面
   ├── 扫描可用WiFi
   ├── 输入服务器信息
   └── 设置设备参数
         ↓
7. 保存配置到NVS
   ↓
8. 重启ESP32
   ↓
9. 连接目标WiFi
   ↓
10. 注册到服务器
    ↓
11. 正常工作模式
```

---

## 🎯 优势

- ✅ **零预配置**: 无需提前知道WiFi信息
- ✅ **用户友好**: 图形化配置界面
- ✅ **批量部署**: 支持多设备同时配置
- ✅ **错误处理**: 配置失败时可重试
- ✅ **状态跟踪**: 后端可监控配置状态

---

## 🚀 实施建议

1. **优先实现**: ESP32 AP模式 + Web服务器
2. **测试验证**: 确保配置保存和重启正常
3. **UI优化**: 添加进度条和错误提示
4. **安全增强**: 添加配置密码验证
5. **批量管理**: 后端支持多设备配置

这个方案将大大简化设备部署流程，让终端用户可以自主完成配置！