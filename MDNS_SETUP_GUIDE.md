# 🌐 mDNS 自动发现服务器配置指南

**版本**: v1.0  
**更新日期**: 2026-01-03  
**状态**: ✅ 已实现

---

## 🎯 mDNS 是什么？

mDNS (Multicast DNS) 允许硬件设备通过**域名**（如 `smartaccess.local`）自动发现服务器IP地址，无需手动配置IP。

### 优势

✅ **零配置** - 无需硬编码服务器IP地址  
✅ **自动更新** - 服务器IP变化后自动适应  
✅ **简化部署** - 烧录固件时无需修改IP配置  
✅ **局域网友好** - 同一WiFi下即可工作  

---

## 📋 实现概览

```
┌─────────────────┐
│  后端服务器      │
│  (FastAPI)      │
│  启动时注册      │
│  smartaccess.local
│  → 192.168.x.x  │
└────────┬────────┘
         │ mDNS 广播
         │
    ┌────┴─────────────────┐
    │                      │
┌───▼────┐           ┌────▼────┐
│ 门禁1   │           │ 门禁2    │
│ESP8266 │           │ESP32-S3 │
│        │           │         │
│查询:    │           │查询:     │
│smartaccess.local   │smartaccess.local
│        │           │         │
│自动解析 │           │自动解析  │
│为实际IP │           │为实际IP  │
└────────┘           └─────────┘
```

---

## 🚀 部署步骤

### 第1步: 后端安装依赖 (1分钟)

```bash
# 进入后端目录
cd SmartAccess

# 安装 zeroconf 库
pip install zeroconf

# 或添加到 requirements.txt
echo "zeroconf>=0.131.0" >> requirements.txt
pip install -r requirements.txt
```

### 第2步: 后端代码已自动配置 ✅

`SmartAccess/app/main.py` 已添加mDNS服务注册：

```python
@app.on_event("startup")
def startup_event():
    # mDNS服务注册
    if MDNS_AVAILABLE:
        zeroconf = Zeroconf()
        service_info = ServiceInfo(
            "_http._tcp.local.",
            "SmartAccess._http._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=8000,
            server="smartaccess.local.",
        )
        zeroconf.register_service(service_info)
        print(f"🌐 mDNS服务已注册: smartaccess.local -> {local_ip}:8000")
```

### 第3步: 硬件固件已自动配置 ✅

#### 门禁1 (ESP8266)
- **文件**: `yj-c/esp8266_pn532_v2.ino`
- **域名**: `smartaccess.local`
- **mDNS客户端**: 已启用

#### 门禁2 (ESP32-S3)
- **文件**: `yj-c/esp32_s3_nfc_controller.ino`
- **域名**: `smartaccess.local`
- **mDNS客户端**: 已启用

### 第4步: 重启服务并测试 (5分钟)

#### 重启后端
```bash
cd SmartAccess
python -m uvicorn app.main:app --reload
```

**预期输出**:
```
✅ SmartAccess v2.0 应用已启动
🌐 mDNS服务已注册: smartaccess.local -> 192.168.1.100:8000
💡 硬件设备可使用域名 'smartaccess.local' 自动连接
```

#### 上传固件
1. 打开Arduino IDE
2. 编译并上传 `esp8266_pn532_v2.ino` 到门禁1
3. 编译并上传 `esp32_s3_nfc_controller.ino` 到门禁2

**预期串口输出**:
```
✅ WiFi已连接
📍 IP地址: 192.168.1.101
🌐 服务器: smartaccess.local:8000
✅ mDNS客户端已启动
💡 可使用域名 'smartaccess.local' 自动发现服务器
```

---

## 🧪 验证测试

### 测试1: 检查mDNS服务注册

**Windows**:
```powershell
# 使用 dns-sd 工具
dns-sd -B _http._tcp local
```

**macOS/Linux**:
```bash
# 使用 avahi-browse
avahi-browse -a

# 或 ping 测试
ping smartaccess.local
```

### 测试2: 检查设备连接

查看门禁1和门禁2的串口输出，应该看到：
```
✅ mDNS客户端已启动
📡 正在连接服务器 smartaccess.local...
✅ 设备注册成功
```

### 测试3: 远程开门测试

通过Web界面或API触发远程开门，观察硬件是否响应。

---

## ⚙️ 配置说明

### 后端配置

| 配置项 | 值 | 说明 |
|--------|---|------|
| 服务名称 | SmartAccess | mDNS服务显示名称 |
| 域名 | smartaccess.local | 硬件访问的域名 |
| 端口 | 8000 | FastAPI服务端口 |
| 服务类型 | _http._tcp.local. | HTTP服务 |

### 硬件配置

#### ESP8266 (门禁1)
```cpp
const char* SERVER_HOST = "smartaccess.local"; // 使用mDNS域名
const int   SERVER_PORT = 8000;

// 如果mDNS不可用，回退到手动IP（取消下方注释）
// const char* SERVER_HOST = "192.168.1.100";
```

#### ESP32-S3 (门禁2)
```cpp
const char* SERVER_HOST = "smartaccess.local"; // 使用mDNS域名
const int   SERVER_PORT = 8000;

// 如果mDNS不可用，回退到手动IP（取消下方注释）
// const char* SERVER_HOST = "192.168.1.100";
```

---

## 🔧 故障排查

### 问题1: 后端提示 "zeroconf未安装"

**解决方法**:
```bash
pip install zeroconf
```

### 问题2: 硬件无法解析 smartaccess.local

**可能原因**:
1. 路由器不支持mDNS广播
2. 防火墙拦截mDNS端口(5353)
3. 硬件和服务器不在同一局域网

**解决方法**:
1. 检查路由器mDNS设置（某些路由器默认禁用）
2. 关闭防火墙或开放UDP 5353端口
3. 使用手动IP配置（见下方回退方案）

### 问题3: mDNS客户端启动失败

**ESP8266硬件输出**:
```
⚠️  mDNS启动失败，将尝试直接连接服务器
```

**解决方法**:
在固件中取消注释手动IP配置：
```cpp
// 取消下方注释，使用手动IP
const char* SERVER_HOST = "192.168.1.100"; // 改为你的服务器IP
```

---

## 🔄 回退方案

如果mDNS不可用，可回退到手动配置IP：

### 方法1: 修改固件常量

在两个固件文件中找到：
```cpp
const char* SERVER_HOST = "smartaccess.local";
```

改为：
```cpp
const char* SERVER_HOST = "192.168.1.100"; // 你的服务器实际IP
```

### 方法2: 使用条件编译

```cpp
#define USE_MDNS 1  // 1=使用mDNS，0=使用手动IP

#if USE_MDNS
const char* SERVER_HOST = "smartaccess.local";
#else
const char* SERVER_HOST = "192.168.1.100";
#endif
```

---

## 📊 mDNS vs 手动IP 对比

| 特性 | mDNS | 手动IP |
|------|------|--------|
| 配置难度 | ⭐ 简单 | ⭐⭐⭐ 需要手动 |
| IP变化适应 | ✅ 自动 | ❌ 需重新烧录 |
| 网络要求 | 同一局域网 | 任意网络 |
| 路由器支持 | 需要支持 | 无要求 |
| 调试难度 | ⭐⭐ 较易 | ⭐ 简单 |

---

## 💡 最佳实践

### 开发环境
- ✅ 使用mDNS，方便快速迭代
- ✅ 服务器IP变化无需重新烧录固件

### 生产环境
- ✅ 使用mDNS（推荐）- 简化部署
- ⚠️ 或使用静态IP + 手动配置 - 更可靠

### 多环境部署
在固件中实现自动回退：
```cpp
// 尝试连接mDNS域名
String serverHost = "smartaccess.local";

// 如果解析失败，回退到备用IP
if (!testConnection(serverHost)) {
    serverHost = "192.168.1.100"; // 备用IP
}
```

---

## 📝 常见问题 (FAQ)

**Q: mDNS域名可以改吗？**  
A: 可以，在后端 `main.py` 中修改 `server="smartaccess.local."` 并同步修改固件的 `SERVER_HOST`

**Q: 支持跨网段吗？**  
A: 不支持。mDNS仅在同一局域网（广播域）内工作

**Q: 可以同时运行多个服务器吗？**  
A: 可以，但需要使用不同的域名（如 `smartaccess1.local`, `smartaccess2.local`）

**Q: Windows支持mDNS吗？**  
A: 支持，但需要安装Bonjour服务（随iTunes自动安装）或Apple Bonjour Print Services

**Q: 如何查看当前网络的mDNS服务？**  
A: 
- Windows: `dns-sd -B _http._tcp local`
- macOS: `dns-sd -B _http._tcp`
- Linux: `avahi-browse -a`

---

## 🎯 下一步

mDNS配置完成后：

1. ✅ 后端自动注册服务
2. ✅ 硬件自动发现服务器
3. ✅ 无需手动配置IP

现在可以：
- 🚀 开始升级部署 (参考 `QUICK_START_UPGRADE.md`)
- 🧪 运行自动化测试 (`test_hardware_upgrade.py`)
- 📖 查阅详细手册 (`HARDWARE_UPGRADE_GUIDE_v2.0.md`)

---

**版本**: v1.0  
**状态**: ✅ 生产就绪  
**支持**: ESP8266 + ESP32-S3 + FastAPI

祝部署顺利！🎉
