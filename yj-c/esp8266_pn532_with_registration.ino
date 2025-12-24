/**
 * ESP8266 + PN532 NFC 读卡器固件（含设备注册和心跳）
 * 
 * 功能：
 * 1. 设备启动时自动向后端注册
 * 2. 定期发送心跳信号保持在线状态
 * 3. 轮询后端获取 SCAN 命令
 * 4. 读取 NFC 卡片并上报
 * 5. 根据后端返回控制继电器
 * 
 * 硬件连接：
 * - ESP8266 (ESP-12F)
 * - PN532 NFC 模块 (I2C 接口)
 * - 继电器模块 (GPIO 控制)
 */

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>

// ==================== 配置 ====================

// WiFi 配置
const char* SSID = "your-wifi-ssid";                    // 修改为你的 WiFi SSID
const char* PASSWORD = "your-wifi-password";             // 修改为你的 WiFi 密码

// 后端服务器配置
const char* SERVER_HOST = "192.168.1.100";              // 修改为后端 IP
const int SERVER_PORT = 8000;

// 设备配置（需与后端注册一致）
const char* DEVICE_ID = "nfc_reader_01";                // 设备唯一 ID
const char* DEVICE_NAME = "一楼门禁";                    // 设备显示名称
const char* DEVICE_TYPE = "nfc_reader";                 // 设备类型
const char* DEVICE_LOCATION = "主入口";                  // 设备位置
const char* FIRMWARE_VERSION = "1.1";                   // 固件版本

// API 端点
const char* API_REGISTER = "/api/hardware/devices";
const char* API_HEARTBEAT_FMT = "/api/hardware/devices/%s/heartbeat";
const char* API_POLL = "/api/hardware/nfc/command/poll";
const char* API_SCAN = "/api/hardware/nfc-scan";

// 轮询和心跳间隔（毫秒）
const unsigned long POLL_INTERVAL = 5000;               // 轮询间隔：5 秒
const unsigned long HEARTBEAT_INTERVAL = 30000;         // 心跳间隔：30 秒

// ==================== 硬件 GPIO 引脚 ====================

#define PN532_SCL 5                                     // GPIO5 (D1)
#define PN532_SDA 4                                     // GPIO4 (D2)
#define RELAY_PIN 12                                    // GPIO12 (D6)
#define LED_PIN 2                                       // GPIO2 (D4)

// ==================== 全局对象 ====================

Adafruit_PN532 nfc(PN532_SCL, PN532_SDA);
WiFiClient wifiClient;
bool device_registered = false;                         // 设备是否已注册标志

// ==================== LED 控制 ====================

void initLED() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
}

void setLED(bool on) {
  digitalWrite(LED_PIN, on ? LOW : HIGH);
}

// ==================== 继电器控制 ====================

void initRelay() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
}

void openDoor(unsigned int duration_ms = 1000) {
  Serial.println("[Door] 打开门锁");
  digitalWrite(RELAY_PIN, HIGH);
  setLED(true);
  delay(duration_ms);
  digitalWrite(RELAY_PIN, LOW);
  setLED(false);
  Serial.println("[Door] 关闭门锁");
}

// ==================== WiFi 初始化 ====================

void initWiFi() {
  Serial.println("[WiFi] 正在连接到 WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("[WiFi] 连接成功");
    Serial.print("[WiFi] IP 地址: ");
    Serial.println(WiFi.localIP());
    setLED(true);
  } else {
    Serial.println();
    Serial.println("[WiFi] 连接失败");
    setLED(false);
  }
}

// ==================== PN532 初始化 ====================

void initPN532() {
  Serial.println("[PN532] 初始化 NFC 模块...");
  
  nfc.begin();
  uint32_t versiondata = nfc.getFirmwareVersion();
  
  if (!versiondata) {
    Serial.println("[PN532] ❌ 未检测到 PN532 模块！");
    return;
  }
  
  Serial.print("[PN532] 固件版本: 0x");
  Serial.println(versiondata >> 24, HEX);
  
  nfc.SAMConfig();
  Serial.println("[PN532] ✓ PN532 初始化完成");
}

// ==================== 设备注册 ====================

/**
 * 向后端注册设备
 * 返回 true: 注册成功, false: 注册失败
 */
bool registerDevice() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Register] ❌ WiFi 未连接");
    return false;
  }

  Serial.println("[Register] 向后端注册设备...");

  // 构建 JSON 请求体
  StaticJsonDocument<512> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_name"] = DEVICE_NAME;
  doc["device_type"] = DEVICE_TYPE;
  doc["location"] = DEVICE_LOCATION;
  doc["ip_address"] = WiFi.localIP().toString();

  String json_str;
  serializeJson(doc, json_str);

  Serial.print("[Register] 请求体: ");
  Serial.println(json_str);

  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Register] ❌ 连接服务器失败");
    return false;
  }

  // 发送 POST 请求
  wifiClient.print("POST ");
  wifiClient.print(API_REGISTER);
  wifiClient.println(" HTTP/1.1");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  wifiClient.print(":");
  wifiClient.println(SERVER_PORT);
  wifiClient.println("Content-Type: application/json");
  wifiClient.print("Content-Length: ");
  wifiClient.println(json_str.length());
  wifiClient.println("Connection: close");
  wifiClient.println();
  wifiClient.print(json_str);

  // 读取响应
  String response = "";
  unsigned long start_time = millis();
  while ((millis() - start_time < 3000) && (wifiClient.connected() || wifiClient.available())) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  wifiClient.stop();

  Serial.print("[Register] 响应长度: ");
  Serial.println(response.length());

  // 简单检查响应状态码
  if (response.indexOf("201") != -1 || response.indexOf("200") != -1) {
    Serial.println("[Register] ✓ 设备注册成功（201/200）");
    device_registered = true;
    return true;
  } else if (response.indexOf("400") != -1) {
    Serial.println("[Register] ✓ 设备 ID 已存在（设备已注册）");
    device_registered = true;
    return true;
  } else {
    Serial.print("[Register] ❌ 注册失败，状态码: ");
    Serial.println(response.substring(0, 100));
    return false;
  }
}

// ==================== 心跳信号 ====================

/**
 * 发送心跳信号
 * 返回 true: 心跳成功, false: 心跳失败
 */
bool sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Heartbeat] WiFi 未连接");
    return false;
  }

  // 构建请求 URL
  char heartbeat_url[100];
  snprintf(heartbeat_url, sizeof(heartbeat_url), API_HEARTBEAT_FMT, DEVICE_ID);

  // 构建 JSON 请求体
  StaticJsonDocument<256> doc;
  doc["connection_status"] = "online";
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["ip_address"] = WiFi.localIP().toString();

  String json_str;
  serializeJson(doc, json_str);

  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Heartbeat] ❌ 连接服务器失败");
    return false;
  }

  // 发送 POST 请求
  wifiClient.print("POST ");
  wifiClient.print(heartbeat_url);
  wifiClient.println(" HTTP/1.1");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  wifiClient.print(":");
  wifiClient.println(SERVER_PORT);
  wifiClient.println("Content-Type: application/json");
  wifiClient.print("Content-Length: ");
  wifiClient.println(json_str.length());
  wifiClient.println("Connection: close");
  wifiClient.println();
  wifiClient.print(json_str);

  // 读取响应
  String response = "";
  unsigned long start_time = millis();
  while ((millis() - start_time < 2000) && (wifiClient.connected() || wifiClient.available())) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  wifiClient.stop();

  if (response.indexOf("200") != -1 || response.indexOf("ok") != -1) {
    Serial.println("[Heartbeat] ✓ 心跳发送成功");
    return true;
  } else {
    Serial.println("[Heartbeat] ❌ 心跳发送失败或无响应");
    return false;
  }
}

// ==================== NFC 读卡 ====================

/**
 * 从 PN532 读取 NFC 卡号
 * 返回卡号字符串（格式: "AA-BB-CC-DD"），失败返回空字符串
 */
String readNFCCard() {
  Serial.println("[NFC] 等待卡片...");
  setLED(true);
  
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;
  
  unsigned long start_time = millis();
  while (millis() - start_time < 10000) {
    bool success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength);
    
    if (success) {
      String card_uid = "";
      for (uint8_t i = 0; i < uidLength; i++) {
        if (i > 0) card_uid += "-";
        if (uid[i] < 0x10) card_uid += "0";
        card_uid += String(uid[i], HEX);
      }
      card_uid.toUpperCase();
      
      Serial.print("[NFC] ✓ 读到卡号: ");
      Serial.println(card_uid);
      setLED(false);
      
      return card_uid;
    }
    
    delay(100);
  }
  
  Serial.println("[NFC] ⏱ 读卡超时");
  setLED(false);
  return "";
}

// ==================== 轮询命令 ====================

/**
 * 轮询后端获取待执行命令
 * 返回任务 ID，如果没有任务返回 -1
 */
int pollCommand() {
  if (WiFi.status() != WL_CONNECTED) {
    return -1;
  }
  
  String url = String(API_POLL) + "?device_id=" + DEVICE_ID;
  
  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Poll] ❌ 连接服务器失败");
    return -1;
  }
  
  // 发送 GET 请求
  wifiClient.print("GET ");
  wifiClient.print(url);
  wifiClient.println(" HTTP/1.1");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  wifiClient.print(":");
  wifiClient.println(SERVER_PORT);
  wifiClient.println("Connection: close");
  wifiClient.println();
  
  // 读取响应
  String response = "";
  while (wifiClient.connected() || wifiClient.available()) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  wifiClient.stop();
  
  // 解析响应
  int body_start = response.indexOf("\r\n\r\n");
  if (body_start == -1) {
    body_start = response.indexOf("\n\n");
    if (body_start != -1) body_start += 2;
  } else {
    body_start += 4;
  }
  
  if (body_start == -1) {
    return -1;
  }
  
  String json_body = response.substring(body_start);
  
  // 解析 JSON
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, json_body);
  
  if (error) {
    return -1;
  }
  
  if (!doc["has_command"].is<bool>() || !doc["has_command"].as<bool>()) {
    return -1;
  }
  
  int task_id = doc["task_id"].as<int>();
  Serial.print("[Poll] ✓ 收到任务 ID: ");
  Serial.println(task_id);
  
  return task_id;
}

// ==================== 上报扫描结果 ====================

/**
 * 将读取到的卡号上报给后端
 * 返回 true: 开门, false: 拒绝
 */
bool reportCard(const String& card_uid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Report] WiFi 未连接");
    return false;
  }
  
  Serial.print("[Report] 上报卡号: ");
  Serial.println(card_uid);
  
  // 构建 JSON 请求体
  StaticJsonDocument<256> doc;
  doc["card_uid"] = card_uid;
  doc["device_id"] = DEVICE_ID;
  
  String json_str;
  serializeJson(doc, json_str);
  
  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Report] ❌ 连接服务器失败");
    return false;
  }
  
  // 发送 POST 请求
  wifiClient.print("POST ");
  wifiClient.print(API_SCAN);
  wifiClient.println(" HTTP/1.1");
  wifiClient.print("Host: ");
  wifiClient.print(SERVER_HOST);
  wifiClient.print(":");
  wifiClient.println(SERVER_PORT);
  wifiClient.println("Content-Type: application/json");
  wifiClient.print("Content-Length: ");
  wifiClient.println(json_str.length());
  wifiClient.println("Connection: close");
  wifiClient.println();
  wifiClient.print(json_str);
  
  // 读取响应
  String response = "";
  while (wifiClient.connected() || wifiClient.available()) {
    if (wifiClient.available()) {
      response += (char)wifiClient.read();
    }
  }
  wifiClient.stop();
  
  // 解析响应
  int body_start = response.indexOf("\r\n\r\n");
  if (body_start == -1) {
    body_start = response.indexOf("\n\n");
    if (body_start != -1) body_start += 2;
  } else {
    body_start += 4;
  }
  
  if (body_start == -1) {
    return false;
  }
  
  String json_body = response.substring(body_start);
  
  // 解析 JSON
  StaticJsonDocument<256> resp_doc;
  DeserializationError error = deserializeJson(resp_doc, json_body);
  
  if (error) {
    return false;
  }
  
  String action = resp_doc["action"].as<String>();
  Serial.print("[Report] 动作: ");
  Serial.println(action);
  
  return action == "OPEN";
}

// ==================== Arduino 主函数 ====================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("╔════════════════════════════════════════╗");
  Serial.println("║ ESP8266 + PN532 NFC 读卡器 (含注册)    ║");
  Serial.println("║ 固件版本: 1.1                          ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.println("");
  Serial.print("[Setup] 设备 ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("[Setup] 服务器: ");
  Serial.print(SERVER_HOST);
  Serial.print(":");
  Serial.println(SERVER_PORT);
  Serial.println("");
  
  // 初始化硬件
  initLED();
  initRelay();
  initPN532();
  initWiFi();
  
  // ★ 尝试注册设备
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[Setup] 尝试注册设备...");
    for (int i = 0; i < 3; i++) {
      if (registerDevice()) {
        break;
      }
      Serial.print("[Setup] 注册失败，");
      Serial.print(3 - i - 1);
      Serial.println(" 秒后重试...");
      delay(3000);
    }
  } else {
    Serial.println("[Setup] ⚠ WiFi 未连接，跳过初始化注册");
    Serial.println("[Setup] 设备将在后续轮询时尝试注册");
  }
  
  Serial.println("[Setup] ✓ 初始化完成，开始运行");
  Serial.println("");
}

void loop() {
  // 检查 WiFi 连接
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Loop] ⚠ WiFi 已断开，重新连接...");
    initWiFi();
  }
  
  // 尝试注册（如果还未注册）
  if (!device_registered && WiFi.status() == WL_CONNECTED) {
    registerDevice();
  }
  
  // 发送心跳
  static unsigned long last_heartbeat_time = 0;
  unsigned long now = millis();
  
  if (now - last_heartbeat_time >= HEARTBEAT_INTERVAL) {
    last_heartbeat_time = now;
    sendHeartbeat();
  }
  
  // 轮询命令
  static unsigned long last_poll_time = 0;
  
  if (now - last_poll_time >= POLL_INTERVAL) {
    last_poll_time = now;
    
    int task_id = pollCommand();
    
    if (task_id >= 0) {
      // 收到 SCAN 命令
      Serial.print("[Loop] 执行 SCAN 命令 (task_id: ");
      Serial.print(task_id);
      Serial.println(")");
      
      String card_uid = readNFCCard();
      
      if (card_uid.length() > 0) {
        // 成功读到卡，上报给后端
        bool should_open = reportCard(card_uid);
        
        if (should_open) {
          Serial.println("[Loop] ✓ 后端允许开门");
          openDoor(1500);
        } else {
          Serial.println("[Loop] ✗ 后端拒绝开门");
        }
      } else {
        Serial.println("[Loop] ✗ 读卡失败");
      }
    }
  }
  
  delay(100);
}

/**
 * 调试提示：
 * 
 * 1. 打开 Arduino IDE 串口监视器（波特率 115200）
 * 2. 观察以下输出：
 *    [WiFi] 连接成功 - WiFi 已连接
 *    [Register] ✓ 设备注册成功 - 设备已注册到后端
 *    [Heartbeat] ✓ 心跳发送成功 - 设备在线
 *    [Poll] ✓ 收到任务 ID - 收到扫描命令
 * 
 * 3. 如果出现问题：
 *    - [WiFi] 连接失败 → 检查 SSID/密码
 *    - [Register] ❌ 连接服务器失败 → 检查 SERVER_HOST/PORT
 *    - [PN532] ❌ 未检测到 PN532 模块 → 检查 I2C 接线
 */
