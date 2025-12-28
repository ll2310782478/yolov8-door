/*
 * ESP8266 + PN532 NFC 硬件固件 (v2)
 * 功能：设备注册/心跳、命令轮询、读卡上报、开门（继电器）、指示灯
 */

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>

// ==================== 配置 ====================

// WiFi 配置
const char* SSID = "lll";            // 修改为你的 WiFi SSID
const char* PASSWORD = "12345678";   // 修改为你的 WiFi 密码

// 后端服务器配置
const char* SERVER_HOST = "192.168.188.56"; // 修改为后端服务器 IP
const int   SERVER_PORT = 8000;            // FastAPI 端口

// 设备信息（需与后端注册一致）
const char* DEVICE_ID   = "nfc_reader_01";
const char* DEVICE_NAME = "一楼门禁";
const char* DEVICE_TYPE = "nfc_reader";
const char* DEVICE_LOCATION = "主入口";
const char* FIRMWARE_VERSION = "2.0";

// API 端点
const char* API_REGISTER      = "/api/hardware/devices";
const char* API_HEARTBEAT_FMT = "/api/hardware/devices/%s/heartbeat";
const char* API_POLL          = "/api/hardware/nfc/command/poll";
const char* API_SCAN          = "/api/hardware/nfc-scan";

// 间隔（毫秒）
const unsigned long POLL_INTERVAL      = 5000;   // 5 秒轮询一次
const unsigned long HEARTBEAT_INTERVAL = 30000;  // 30 秒心跳一次

// ==================== GPIO 引脚 ====================

// I2C 引脚
#define PN532_SCL 5    // GPIO5 (D1)
#define PN532_SDA 4    // GPIO4 (D2)
#define PN532_IRQ 0    // 占位
#define PN532_RESET 16 // 占位

// 两路门锁/指示输出（门1=D8，门2=D7），另用板载LED做状态灯
#define DOOR1_PIN 15      // GPIO15 (D8) -> 门1
#define DOOR2_PIN 13      // GPIO13 (D7) -> 门2
#define STATUS_LED_PIN 2  // GPIO2 (D4)  板载LED，低电平点亮
const bool LED_ACTIVE_LOW = true; // 若使用外接高电平点亮LED，改为 false

// ==================== 全局对象与状态 ====================

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET);
WiFiClient httpClient;
bool device_registered = false;
String last_command = "";
String last_payload = "";
String last_uid = "";
unsigned long last_uid_time = 0;
const unsigned long UID_DEBOUNCE_MS = 2000;
const bool CONTINUOUS_SCAN_MODE = true;
String last_door = "door1";  // 保存最后一次扫卡的门号信息

// ==================== 日志/指示 ====================

void initLED() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LED_ACTIVE_LOW ? HIGH : LOW); // 默认关闭
}

void setLED(bool on) {
  if (LED_ACTIVE_LOW) {
    digitalWrite(STATUS_LED_PIN, on ? LOW : HIGH); // 低电平点亮
  } else {
    digitalWrite(STATUS_LED_PIN, on ? HIGH : LOW); // 高电平点亮
  }
}

void initRelay() {
  pinMode(DOOR1_PIN, OUTPUT);
  pinMode(DOOR2_PIN, OUTPUT);
  digitalWrite(DOOR1_PIN, LOW); // 初始关闭
  digitalWrite(DOOR2_PIN, LOW);
}

void openDoor(uint8_t door = 1, unsigned int duration_ms = 1500) {
  uint8_t pin = (door == 2) ? DOOR2_PIN : DOOR1_PIN;
  Serial.print("[Door] 打开门锁: 门"); Serial.println(door);
  digitalWrite(pin, HIGH);
  setLED(true);
  delay(duration_ms);
  digitalWrite(pin, LOW);
  setLED(false);
  Serial.println("[Door] 关闭门锁");
}

// ==================== WiFi ====================

void initWiFi() {
  Serial.println("[WiFi] 连接 WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[WiFi] ✓ 已连接");
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
    setLED(true);
  } else {
    Serial.println("[WiFi] ✗ 连接失败");
    setLED(false);
  }
}

// ==================== PN532 ====================

void initPN532() {
  Serial.println("[PN532] 初始化 NFC 模块...");
  Wire.begin(PN532_SDA, PN532_SCL);

  Wire.beginTransmission(0x24);
  if (Wire.endTransmission() == 0) {
    Serial.println("[PN532] I2C 探测到 PN532 (0x24)");
  } else {
    Serial.println("[PN532] ⚠ I2C 未探测到 0x24，检查 SDA/SCL 及供电");
  }

  nfc.begin();
  uint32_t ver = nfc.getFirmwareVersion();
  if (!ver) {
    Serial.println("[PN532] ✗ 未检测到 PN532 模块");
    return;
  }
  Serial.print("[PN532] 固件版本: 0x");
  Serial.println(ver >> 24, HEX);
  nfc.SAMConfig();
  Serial.println("[PN532] ✓ 初始化完成");
}

// ==================== HTTP 工具 ====================

String readHttpBody(String &raw) {
  int pos = raw.indexOf("\r\n\r\n");
  if (pos == -1) {
    pos = raw.indexOf("\n\n");
    if (pos != -1) pos += 2;
  } else {
    pos += 4;
  }
  if (pos == -1) return String("");
  return raw.substring(pos);
}

bool httpGet(const String &url_path_and_query, String &response) {
  response = "";
  if (!httpClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[HTTP] ✗ 连接服务器失败(GET)");
    return false;
  }
  httpClient.print("GET ");
  httpClient.print(url_path_and_query);
  httpClient.println(" HTTP/1.1");
  httpClient.print("Host: ");
  httpClient.print(SERVER_HOST);
  httpClient.print(":");
  httpClient.println(SERVER_PORT);
  httpClient.println("Connection: close");
  httpClient.println();

  unsigned long start = millis();
  while ((millis() - start) < 4000 && (httpClient.connected() || httpClient.available())) {
    if (httpClient.available()) response += (char)httpClient.read();
  }
  httpClient.stop();
  return response.length() > 0;
}

bool httpPost(const String &url_path, const String &jsonBody, String &response) {
  response = "";
  if (!httpClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[HTTP] ✗ 连接服务器失败(POST)");
    return false;
  }
  httpClient.print("POST ");
  httpClient.print(url_path);
  httpClient.println(" HTTP/1.1");
  httpClient.print("Host: ");
  httpClient.print(SERVER_HOST);
  httpClient.print(":");
  httpClient.println(SERVER_PORT);
  httpClient.println("Content-Type: application/json");
  httpClient.print("Content-Length: ");
  httpClient.println(jsonBody.length());
  httpClient.println("Connection: close");
  httpClient.println();
  httpClient.print(jsonBody);

  unsigned long start = millis();
  while ((millis() - start) < 5000 && (httpClient.connected() || httpClient.available())) {
    if (httpClient.available()) response += (char)httpClient.read();
  }
  httpClient.stop();
  return response.length() > 0;
}

// ==================== 设备注册/心跳 ====================

bool registerDevice() {
  if (WiFi.status() != WL_CONNECTED) return false;
  Serial.println("[Register] 注册设备...");

  StaticJsonDocument<512> doc;
  doc["device_id"]   = DEVICE_ID;
  doc["device_name"] = DEVICE_NAME;
  doc["device_type"] = DEVICE_TYPE;
  doc["location"]    = DEVICE_LOCATION;
  doc["ip_address"]  = WiFi.localIP().toString();
  String payload;
  serializeJson(doc, payload);

  String resp;
  if (!httpPost(String(API_REGISTER), payload, resp)) return false;

  if (resp.indexOf(" 200 ") != -1 || resp.indexOf(" 201 ") != -1) {
    device_registered = true;
    Serial.println("[Register] ✓ 设备注册成功");
    return true;
  }
  if (resp.indexOf(" 400 ") != -1) {
    device_registered = true; // 已存在视为成功
    Serial.println("[Register] ✓ 设备已存在");
    return true;
  }
  Serial.print("[Register] ✗ 注册失败，响应头: ");
  Serial.println(resp.substring(0, 80));
  return false;
}

bool sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return false;

  char heartbeat_path[120];
  snprintf(heartbeat_path, sizeof(heartbeat_path), API_HEARTBEAT_FMT, DEVICE_ID);

  StaticJsonDocument<256> doc;
  doc["connection_status"] = "online";
  doc["firmware_version"]  = FIRMWARE_VERSION;
  doc["ip_address"]        = WiFi.localIP().toString();
  String payload;
  serializeJson(doc, payload);

  String resp;
  if (!httpPost(String(heartbeat_path), payload, resp)) return false;

  String body = readHttpBody(resp);
  if (body.indexOf("ok") != -1 || resp.indexOf(" 200 ") != -1) {
    Serial.println("[Heartbeat] ✓ 心跳成功");
    return true;
  }
  Serial.println("[Heartbeat] ✗ 心跳失败");
  return false;
}

// ==================== NFC 读卡/轮询/上报 ====================

String readNFCCard(unsigned long timeout_ms = 10000) {
  Serial.println("[NFC] 等待卡片...");
  setLED(true);

  uint8_t uid[7];
  uint8_t uidLen;
  unsigned long start = millis();

  while (millis() - start < timeout_ms) {
    bool ok = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLen);
    if (ok) {
      String card_uid = "";
      for (uint8_t i = 0; i < uidLen; i++) {
        if (i) card_uid += "-";
        if (uid[i] < 0x10) card_uid += "0";
        card_uid += String(uid[i], HEX);
      }
      card_uid.toUpperCase();
      Serial.print("[NFC] ✓ 卡号: ");
      Serial.println(card_uid);
      setLED(false);
      return card_uid;
    }
    delay(100);
  }
  Serial.println("[NFC] ⏱ 超时未读到卡");
  setLED(false);
  return String("");
}

int pollCommand() {
  if (WiFi.status() != WL_CONNECTED) return -1;

  String url = String(API_POLL) + "?device_id=" + DEVICE_ID;
  String resp;
  if (!httpGet(url, resp)) return -1;

  String body = readHttpBody(resp);
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) return -1;

  if (!doc["has_command"].is<bool>() || !doc["has_command"].as<bool>()) return -1;
  int task_id = doc["task_id"].as<int>();
  last_command = doc["command"].as<String>();
  last_payload = doc["payload"].as<String>();
  Serial.print("[Poll] 任务: "); Serial.print(task_id); Serial.print(" 命令: "); Serial.println(last_command);
  return task_id;
}

bool reportCard(const String &card_uid) {
  if (WiFi.status() != WL_CONNECTED) return false;

  StaticJsonDocument<256> doc;
  doc["card_uid"] = card_uid;
  doc["device_id"] = DEVICE_ID;
  String payload; serializeJson(doc, payload);

  String resp;
  if (!httpPost(String(API_SCAN), payload, resp)) return false;
  String body = readHttpBody(resp);

  StaticJsonDocument<256> rdoc;
  DeserializationError err = deserializeJson(rdoc, body);
  if (err) {
    Serial.println("[Report] ✗ 响应 JSON 解析失败");
    return false;
  }
  String action = rdoc["action"].as<String>();
  String msg    = rdoc["msg"].as<String>();
  String door   = rdoc["door"].as<String>();
  Serial.print("[Report] 动作: "); Serial.print(action); Serial.print("，消息: "); Serial.println(msg);
  Serial.print("[Report] 门号: "); Serial.println(door);
  
  // 保存门号信息供 loop 中使用
  if (door.length() > 0) {
    last_door = door;
  }
  
  // 注意：不在此处打开门，由 loop 中的调用者根据返回值决定是否打开门
  if (action == "OPEN") {
    return true;  // 仅返回 true，不在此处执行 openDoor
  }
  return false;
}

// ==================== Arduino 入口 ====================

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println(); Serial.println();
  Serial.println("╔════════════════════════════════════════╗");
  Serial.println("║ ESP8266 + PN532 NFC 固件 (v2)         ║");
  Serial.println("║ Firmware: 2.0                         ║");
  Serial.println("╚════════════════════════════════════════╝");

  initLED();
  initRelay();
  initPN532();
  initWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    for (int i = 0; i < 3 && !device_registered; i++) {
      if (registerDevice()) break;
      Serial.println("[Setup] 注册失败，3 秒后重试...");
      delay(3000);
    }
  }

  Serial.println("[Setup] 初始化完成，进入循环");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Loop] WiFi 断开，重连...");
    initWiFi();
  }

  if (!device_registered && WiFi.status() == WL_CONNECTED) {
    registerDevice();
  }

  static unsigned long last_hb = 0;
  unsigned long now = millis();
  if (now - last_hb >= HEARTBEAT_INTERVAL) {
    last_hb = now;
    sendHeartbeat();
  }

  static unsigned long last_poll = 0;
  if (now - last_poll >= POLL_INTERVAL) {
    last_poll = now;
    int task_id = pollCommand();
    if (task_id >= 0) {
      if (last_command == "SCAN") {
        Serial.print("[Loop] 执行 SCAN 任务: "); Serial.println(task_id);
        String uid = readNFCCard();
        if (uid.length() > 0) {
          bool ok = reportCard(uid);
          if (ok) {
            // 根据后端返回的门号打开对应的门
            uint8_t door_id = (last_door == "door2") ? 2 : 1;
            openDoor(door_id, 1500);
          }
        } else {
          Serial.println("[Loop] ✗ 未读到卡或超时");
        }
      } else if (last_command == "ENROLL") {
        Serial.print("[Loop] 执行 ENROLL 任务: "); Serial.println(task_id);
        String uid = readNFCCard();
        if (uid.length() > 0) {
          reportCard(uid);
          Serial.println("[Loop] ✓ 已将录入卡号上报");
        } else {
          Serial.println("[Loop] ✗ 录入模式未读到卡");
        }
      } else if (last_command == "OPEN" || last_command == "UNLOCK") {
        Serial.print("[Loop] 执行 OPEN 任务: "); Serial.println(task_id);
        uint8_t door_id = 1;
        if (last_payload.length()) {
          StaticJsonDocument<64> pdoc;
          if (deserializeJson(pdoc, last_payload) == DeserializationError::Ok) {
            String d = pdoc["door_id"].as<String>();
            if (d == "door2") door_id = 2;
          }
        }
        openDoor(door_id, 1500);
      } else {
        Serial.print("[Loop] 未知命令，忽略: "); Serial.println(last_command);
      }
    }
  }

  if (CONTINUOUS_SCAN_MODE) {
    String uid = readNFCCard(200);
    if (uid.length() > 0) {
      if (uid != last_uid || millis() - last_uid_time > UID_DEBOUNCE_MS) {
        last_uid = uid;
        last_uid_time = millis();
        bool ok = reportCard(uid);
        if (ok) {
          // 根据后端返回的门号打开对应的门
          uint8_t door_id = (last_door == "door2") ? 2 : 1;
          openDoor(door_id, 1500);
        }
      }
    }
  }

  delay(100);
}