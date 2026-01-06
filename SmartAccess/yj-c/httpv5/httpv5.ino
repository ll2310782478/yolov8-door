/*
 * ESP8266 远程门禁控制器 (v5.0 纯远程控制版)
 * 功能特性：
 * 1. 纯远程控制 - 仅通过服务器轮询指令控制
 * 2. 双门控制 - 支持门1和门2独立控制
 * 3. LED状态指示 - 使用板载LED显示设备状态
 * 4. 自动心跳 - 定期向服务器报告在线状态
 * 
 * 更新日志 v5.0:
 * - 移除所有NFC相关功能和库
 * - 改为纯远程指令控制模式
 * - 增强LED状态指示（WiFi连接/在线闪烁/开门常亮/错误快闪）
 * - 简化代码结构，提升稳定性
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

// ==================== 1. 用户配置 ====================

const char* SSID        = "安居门业";           // WiFi名称
const char* PASSWORD    = "15929256728";      // WiFi密码
const char* SERVER_HOST = "192.168.1.45";     // 服务器IP
const int   SERVER_PORT = 8000;               // 服务器端口

// 设备身份信息
const char* DEVICE_ID   = "remote_door_01";        // 设备唯一ID
const char* DEVICE_NAME = "远程门禁-01";            // 设备名称
const char* DEVICE_TYPE = "remote_door_controller"; // 设备类型
const char* DEVICE_LOC  = "实验室大门";             // 安装位置

// 硬件引脚
#define DOOR1_PIN D8      // 门1继电器
#define DOOR2_PIN D7      // 门2继电器
#define STATUS_LED D4     // 板载LED (GPIO2)
const bool LED_INVERTED = true; // 板载LED低电平点亮

// ==================== 2. 全局变量 ====================

WiFiClient client;

// 门锁计时器
unsigned long door1_close_time = 0; 
unsigned long door2_close_time = 0;

// LED状态枚举
enum LedMode {
  LED_OFF,           // 关闭
  LED_ON,            // 常亮
  LED_SLOW_BLINK,    // 慢闪 (1Hz, WiFi连接中)
  LED_FAST_BLINK,    // 快闪 (5Hz, 网络错误)
  LED_HEARTBEAT      // 心跳闪烁 (在线状态)
};
LedMode ledMode = LED_SLOW_BLINK;
unsigned long led_timer = 0;
bool led_state = false;

// 网络轮询计时器
unsigned long last_poll_time = 0;

// ==================== 3. LED控制系统 ====================

void setLed(bool on) {
  if (LED_INVERTED) {
    digitalWrite(STATUS_LED, on ? LOW : HIGH);
  } else {
    digitalWrite(STATUS_LED, on ? HIGH : LOW);
  }
  led_state = on;
}

void ledTask() {
  unsigned long now = millis();
  
  switch (ledMode) {
    case LED_OFF:
      if (led_state) setLed(false);
      break;
      
    case LED_ON:
      if (!led_state) setLed(true);
      break;
      
    case LED_SLOW_BLINK:  // 500ms周期
      if (now - led_timer > 500) {
        led_timer = now;
        setLed(!led_state);
      }
      break;
      
    case LED_FAST_BLINK:  // 100ms周期
      if (now - led_timer > 100) {
        led_timer = now;
        setLed(!led_state);
      }
      break;
      
    case LED_HEARTBEAT:  // 心跳模式：短闪一下
      if (now - led_timer > 2000) {
        led_timer = now;
        setLed(true);
      } else if (now - led_timer > 100 && led_state) {
        setLed(false);
      }
      break;
  }
}


// ==================== 4. 统一开门接口 ====================

/**
 * 统一开门接口 - 远程指令调用此接口开门
 * @param doorId 门编号 (1=门1, 2=门2)
 * @param source 触发来源 (remote/face/bluetooth/qrcode等)
 * @return bool 是否成功触发
 */
bool openDoor(int doorId, String source) {
  // 参数验证
  if (doorId != 1 && doorId != 2) {
    Serial.println("[Door] ❌ 无效门编号: " + String(doorId));
    return false;
  }

  // LED常亮表示开门中
  ledMode = LED_ON;

  // 记录日志
  Serial.println("╔════════════════════════════════════╗");
  Serial.println("║     🔓 门禁开启                    ║");
  Serial.println("╠════════════════════════════════════╣");
  Serial.print("║  门编号: "); 
  Serial.println(doorId == 1 ? "门1              ║" : "门2              ║");
  Serial.print("║  触发源: "); 
  if (source == "remote") Serial.println("远程指令        ║");
  else if (source == "face") Serial.println("人脸识别        ║");
  else if (source == "bluetooth") Serial.println("蓝牙开门        ║");
  else if (source == "qrcode") Serial.println("二维码扫描      ║");
  else Serial.println(source + "          ║");
  Serial.println("║  开锁时长: 3秒                     ║");
  Serial.println("╚════════════════════════════════════╝");

  // 执行开门操作
  if (doorId == 1) {
    digitalWrite(DOOR1_PIN, HIGH);
    door1_close_time = millis() + 3000; // 3秒后自动关闭
  } else {
    digitalWrite(DOOR2_PIN, HIGH);
    door2_close_time = millis() + 3000;
  }

  return true;
}

// ==================== 5. 门锁自动关闭任务 ====================

void doorTask() {
  unsigned long now = millis();
  
  if (door1_close_time > 0 && now >= door1_close_time) {
    digitalWrite(DOOR1_PIN, LOW);
    door1_close_time = 0;
    ledMode = LED_HEARTBEAT; // 恢复心跳模式
    Serial.println("[Door] 🔒 门1 自动关闭");
  }
  
  if (door2_close_time > 0 && now >= door2_close_time) {
    digitalWrite(DOOR2_PIN, LOW);
    door2_close_time = 0;
    ledMode = LED_HEARTBEAT; // 恢复心跳模式
    Serial.println("[Door] 🔒 门2 自动关闭");
  }
}


// ==================== 6. 网络通信 ====================

String sendRequest(String method, String path, String jsonBody) {
  if (WiFi.status() != WL_CONNECTED) {
    ledMode = LED_FAST_BLINK; // 网络断开快闪
    return "";
  }
  
  client.stop();
  if (!client.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[NET] ❌ 连接服务器失败");
    ledMode = LED_FAST_BLINK;
    return "";
  }

  // 发送HTTP请求
  client.print(method + " " + path + " HTTP/1.1\r\n");
  client.print("Host: " + String(SERVER_HOST) + "\r\n");
  client.print("Connection: close\r\n");
  
  if (jsonBody.length() > 0) {
    client.print("Content-Type: application/json\r\n");
    client.print("Content-Length: " + String(jsonBody.length()) + "\r\n");
    client.print("\r\n");
    client.print(jsonBody);
  } else {
    client.print("\r\n");
  }

  // 读取响应
  String response = "";
  unsigned long timeout = millis();
  while (client.connected() || client.available()) {
    if (client.available()) {
      response += (char)client.read();
    }
    if (millis() - timeout > 2000) break; // 2秒超时
  }
  client.stop();
  
  // 恢复在线心跳模式
  if (ledMode == LED_FAST_BLINK) {
    ledMode = LED_HEARTBEAT;
  }
  
  return response;
}

bool postJson(const String& path, const String& jsonBody) {
  if (WiFi.status() != WL_CONNECTED) {
    ledMode = LED_FAST_BLINK;
    return false;
  }
  
  HTTPClient http;
  WiFiClient wifiClient;
  String url = String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + path;
  
  http.begin(wifiClient, url);
  if (jsonBody.length() > 0) {
    http.addHeader("Content-Type", "application/json");
  }
  
  int code = jsonBody.length() > 0 ? http.POST(jsonBody) : http.POST((uint8_t*)nullptr, 0);
  
  if (code > 0) {
    Serial.printf("[HTTP] %s -> %d\n", path.c_str(), code);
  } else {
    Serial.printf("[HTTP] %s 请求失败: %s\n", path.c_str(), http.errorToString(code).c_str());
    ledMode = LED_FAST_BLINK;
  }
  
  http.end();
  
  if (ledMode == LED_FAST_BLINK && code > 0) {
    ledMode = LED_HEARTBEAT;
  }
  
  return code > 0 && code < 300;
}

void registerDevice() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_name"] = DEVICE_NAME;
  doc["device_type"] = DEVICE_TYPE;
  doc["location"] = DEVICE_LOC;
  doc["ip_address"] = WiFi.localIP().toString();
  String body; 
  serializeJson(doc, body);

  bool ok = postJson("/api/hardware/devices", body);
  if (ok) {
    Serial.println("[REG] ✅ 设备注册成功");
  } else {
    Serial.println("[REG] ⚠️  设备可能已注册或失败，继续运行...");
  }
}

void heartbeatTask() {
  static unsigned long lastHeartbeatAt = 0;
  if (millis() - lastHeartbeatAt < 30000) return; // 30秒一次
  lastHeartbeatAt = millis();

  StaticJsonDocument<192> doc;
  doc["connection_status"] = "online";
  doc["ip_address"] = WiFi.localIP().toString();
  doc["firmware_version"] = "v5.0";
  String body; 
  serializeJson(doc, body);

  bool ok = postJson(String("/api/hardware/devices/") + DEVICE_ID + "/heartbeat", body);
  Serial.println(ok ? "💓 心跳: 成功" : "💔 心跳: 失败");
}


// ==================== 7. 远程开门轮询任务 ====================

void pollTask() {
  if (millis() - last_poll_time < 2000) return; // 2秒轮询一次
  last_poll_time = millis();
  
  // 构造轮询请求
  StaticJsonDocument<64> doc;
  doc["device_id"] = DEVICE_ID;
  String json; 
  serializeJson(doc, json);

  // 发送轮询请求
  String resp = sendRequest("POST", "/api/hardware/nfc/command/poll", json);
  
  // 解析响应
  if (resp.length() > 0 && resp.indexOf("OPEN") != -1) {
    Serial.println("╔════════════════════════════════════╗");
    Serial.println("║  📡 收到远程开门指令               ║");
    Serial.println("╚════════════════════════════════════╝");
    
    // 解析门编号
    int doorId = 1;  // 默认门1
    String source = "remote";  // 默认来源
    
    if (resp.indexOf("door2") != -1) {
      doorId = 2;
    }
    
    // 解析触发来源
    if (resp.indexOf("face") != -1) source = "face";
    else if (resp.indexOf("bluetooth") != -1) source = "bluetooth";
    else if (resp.indexOf("qrcode") != -1) source = "qrcode";
    
    // 调用开门接口
    openDoor(doorId, source);
  }
}


// ==================== 8. 主程序 ====================

void setup() {
  Serial.begin(115200);
  delay(500);
  
  // 显示启动信息
  Serial.println("\n╔════════════════════════════════════════════╗");
  Serial.println("║   ESP8266 远程门禁控制器 v5.0             ║");
  Serial.println("╠════════════════════════════════════════════╣");
  Serial.println("║  功能: 纯远程控制 + 双门独立              ║");
  Serial.println("║  模式: 轮询式指令接收                     ║");
  Serial.println("║  LED: 板载状态指示                        ║");
  Serial.println("╚════════════════════════════════════════════╝\n");

  // 初始化硬件引脚
  pinMode(DOOR1_PIN, OUTPUT);
  pinMode(DOOR2_PIN, OUTPUT);
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(DOOR1_PIN, LOW);
  digitalWrite(DOOR2_PIN, LOW);
  setLed(false);
  
  Serial.println("✅ 硬件初始化完成");
  Serial.println("   门1继电器: D8 (GPIO15)");
  Serial.println("   门2继电器: D7 (GPIO13)");
  Serial.println("   状态LED: D4 (GPIO2, 板载)\n");

  // 连接WiFi
  ledMode = LED_SLOW_BLINK; // 慢闪表示正在连接
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  Serial.print("🔌 正在连接WiFi");
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n❌ WiFi连接失败！进入快闪错误模式");
    ledMode = LED_FAST_BLINK;
    while(1) { ledTask(); delay(10); } // 停在错误模式
  }
  
  Serial.println("\n✅ WiFi已连接");
  Serial.println("📍 IP地址: " + WiFi.localIP().toString());
  Serial.println("🌐 服务器: " + String(SERVER_HOST) + ":" + String(SERVER_PORT));
  
  ledMode = LED_HEARTBEAT; // 切换到心跳模式

  // 设备注册
  registerDevice();
  
  Serial.println("\n✨ 系统启动完成，等待远程指令...");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
  Serial.println("LED状态说明:");
  Serial.println("  💙 慢闪 (1Hz)   - WiFi连接中");
  Serial.println("  💚 心跳闪烁     - 在线待命");
  Serial.println("  💛 常亮         - 开门中");
  Serial.println("  ❤️ 快闪 (5Hz)   - 网络错误\n");
}

void loop() {
  static unsigned long last_status = 0;
  
  // 每30秒输出运行状态
  if (millis() - last_status > 30000) {
    last_status = millis();
    Serial.println("💓 系统运行正常 | 在线: " + String(millis()/1000) + "秒 | IP: " + WiFi.localIP().toString());
  }
  
  // === 核心任务调度 ===
  
  ledTask();         // LED状态控制
  pollTask();        // 远程指令轮询
  heartbeatTask();   // 心跳上报
  doorTask();        // 门锁自动关闭
  
  delay(10);
}

/*
 * ==================== 使用说明 ====================
 * 
 * 硬件连接:
 *   - 门1继电器: D8 (GPIO15)
 *   - 门2继电器: D7 (GPIO13)
 *   - 状态LED: D4 (GPIO2, 板载)
 * 
 * LED状态指示:
 *   - 慢闪 (1Hz): WiFi连接中
 *   - 心跳闪烁: 在线待命
 *   - 常亮: 开门中 (3秒)
 *   - 快闪 (5Hz): 网络错误
 * 
 * 服务器API:
 *   POST /api/hardware/nfc/command/poll
 *   请求: {"device_id": "remote_door_01"}
 *   响应: {"command": "OPEN", "door": "door1", "source": "face"}
 * 
 * 开门触发来源:
 *   - remote: 远程手动控制
 *   - face: 人脸识别
 *   - bluetooth: 蓝牙开门
 *   - qrcode: 二维码扫描
 * 
 * ================================================
 */
