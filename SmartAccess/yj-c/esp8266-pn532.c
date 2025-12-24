/*
esp8266-pn532.c

ESP8266 + PN532 (Adafruit) 固件 - 硬件I2C版
修复了 "PN532 not found" 但 I2C 扫描能扫到的问题。
*/

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <ArduinoJson.h>

// ================= 配置区域 =================
const char* ssid = "lll";             // 你的 WiFi 名称
const char* password = "12345678";    // 你的 WiFi 密码

// 服务器配置
const char* server_base = "http://192.168.188.116:8000";
// 为诊断方便，单独保留主机/端口
const char* server_host = "192.168.188.116";
const uint16_t server_port = 8000;

// 认证方式配置
const char* api_token = ""; 
const char* basic_user = "";
const char* basic_pass = "";
bool use_bearer = true;  
bool use_basic = false;  

// 设备信息
const char* firmware_version = "1.1-HardwareI2C";

// 定时参数
const unsigned long HEARTBEAT_INTERVAL_MS = 30000; 
const unsigned long REGISTER_RETRY_MS = 15000;    

// ================= 硬件定义 (关键修改) =================
// 即使你只接了4根线，库也需要定义 IRQ 和 RESET 引脚
// 我们这里定义 D3 和 D4，即使没接线也没关系，库会使用 I2C 协议
#define PN532_IRQ   D3
#define PN532_RESET D4 

// I2C 引脚 (NodeMCU 默认就是 D2/D1)
#define PN532_SDA D2
#define PN532_SCL D1

#define RELAY_PIN D5

// 【核心修改】使用硬件 I2C 构造函数
// 这会告诉库："不要自己模拟引脚，直接用 Wire 库已经连好的通道"
Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET);

// ================= 全局变量 =================
String device_id = ""; 
unsigned long lastHeartbeat = 0;
unsigned long lastRegisterAttempt = 0;
bool isRegistered = false;

// ======= 辅助函数 =======
String getMacID() {
  String mac = WiFi.macAddress();
  mac.replace(':', '_');
  return mac;
}

String makeAuthHeader() {
  if (use_bearer && strlen(api_token) > 0) {
    return "Bearer " + String(api_token);
  }
  if (use_basic && strlen(basic_user) > 0) {
    // 简单实现，暂不处理 Base64
    return String(""); 
  }
  return String("");
}

String httpPostJson(const String& url, const String& jsonBody, int& outCode) {
  HTTPClient http;
  WiFiClient client;
  http.setTimeout(5000); 
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  
  String auth = makeAuthHeader();
  if (auth.length() > 0) {
    http.addHeader("Authorization", auth);
  }

  Serial.printf("[HTTP] POST %s ...", url.c_str());
  outCode = http.POST(jsonBody);
  Serial.printf(" code=%d", outCode);

  String payload = "";
  if (outCode > 0) {
    payload = http.getString();
  } else {
    Serial.print(" [ERR: connection/timeout]");
  }
  Serial.println();

  http.end();
  return payload;
}

// 注册设备
bool registerDevice() {
  if (isRegistered) return true;
  if (millis() - lastRegisterAttempt < REGISTER_RETRY_MS) return false;
  lastRegisterAttempt = millis();

  String url = String(server_base) + "/api/hardware/devices";
  
  // 适配 ArduinoJson V6/V7
  JsonDocument doc; 
  doc["device_id"] = device_id;
  doc["device_name"] = device_id;
  doc["device_type"] = "nfc_reader";
  doc["location"] = "Entrance";
  doc["ip_address"] = WiFi.localIP().toString();
  
  String body;
  serializeJson(doc, body);

  int code = 0;
  String resp = httpPostJson(url, body, code);
  if (code == 200 || code == 201) {
    isRegistered = true;
    Serial.println("注册成功!");
    return true;
  } else if (code == 400) {
    Serial.println("设备可能已存在 (400), 视为成功.");
    isRegistered = true;
    return true;
  } else {
    Serial.printf("注册失败: %d\n", code);
    return false;
  }
}

// 发送心跳
bool sendHeartbeat() {
  String url = String(server_base) + "/api/hardware/devices/" + device_id + "/heartbeat";
  
  JsonDocument doc;
  doc["connection_status"] = "online";
  doc["firmware_version"] = firmware_version;
  doc["ip_address"] = WiFi.localIP().toString();
  
  String body;
  serializeJson(doc, body);
  int code = 0;
  String resp = httpPostJson(url, body, code);
  if (code == 200) {
    lastHeartbeat = millis();
    return true;
  }
  return false;
}

// 上报 NFC 扫描
void reportNfcScan(const String& card_uid) {
  String url = String(server_base) + "/api/hardware/nfc-scan";
  
  JsonDocument doc;
  doc["card_uid"] = card_uid;
  doc["device_id"] = device_id;
  
  String body;
  serializeJson(doc, body);
  int code = 0;
  String resp = httpPostJson(url, body, code);
  
  if (code >= 200 && code < 300) {
    JsonDocument rdoc;
    DeserializationError err = deserializeJson(rdoc, resp);
    if (!err) {
      const char* action = rdoc["action"];
      if (action && strcmp(action, "OPEN") == 0) {
        Serial.println(">>> 指令: 开门! <<<");
        digitalWrite(RELAY_PIN, HIGH);
        delay(3000);
        digitalWrite(RELAY_PIN, LOW);
      }
    }
  }
}

// ======= setup =======
void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  // 1. 连接 WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("\nConnecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
  }
  Serial.println("\nWiFi connected.");
  Serial.print("IP: "); Serial.println(WiFi.localIP());

  device_id = getMacID();
  
  // 2. 【关键】启动硬件 I2C
  // 这行代码会强制锁定 D2(SDA) 和 D1(SCL)
  Serial.println("Init Hardware I2C (Wire)...");
  Wire.begin(PN532_SDA, PN532_SCL);

  // 3. 扫描一次总线确认（可选，但推荐）
  Serial.print("Scanning I2C... ");
  Wire.beginTransmission(0x24); // 0x24 是 PN532 默认地址
  if (Wire.endTransmission() == 0) {
    Serial.println("FOUND PN532 at 0x24!");
  } else {
    Serial.println("NOT FOUND at 0x24 (Check wiring!)");
  }

  // 4. 初始化 NFC 库
  // 因为使用了 (IRQ, RESET) 构造函数，这里 begin 会自动使用上面启动的 Wire
  nfc.begin();

  // 5. 检查固件版本
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("❌ 错误: 无法与 PN532 通信 (nfc.begin 失败)");
    // 如果 I2C 扫描到了但这里失败，通常是库的复位逻辑问题，或者供电不稳
    // 但硬件连接应该是对的
    while (1) {
      delay(1000);
      Serial.print("Retrying setup... ");
      // 可以在这里尝试软件复位
      ESP.restart(); 
    }
  }
  
  // 成功找到!
  Serial.print("✅ 成功! 发现芯片 PN5"); Serial.println((versiondata>>24) & 0xFF, HEX); 
  Serial.print("Firmware ver. "); Serial.print((versiondata>>16) & 0xFF, DEC); 
  Serial.print('.'); Serial.println((versiondata>>8) & 0xFF, DEC);
  
  // 配置读取 RFID
  nfc.SAMConfig();
  Serial.println("等待刷卡...");

  // 立即尝试注册
  registerDevice();
}

// ======= loop =======
void loop() {
  // 确保已注册
  if (!isRegistered) {
    registerDevice();
  }

  // 心跳
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL_MS) {
    if (sendHeartbeat()) {
      Serial.println("Heartbeat OK");
    }
  }

  // 读卡
  // readPassiveTargetID 是阻塞的，但设置了超时 100ms
  // 使用硬件 I2C 后，读取速度会变快很多
  uint8_t success;
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;
  
  success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100);
  
  if (success) {
    Serial.println("Found an NFC card!");
    
    String card_uid = "";
    for (uint8_t i = 0; i < uidLength; i++) {
      if (i > 0) card_uid += "-";
      if (uid[i] < 0x10) card_uid += "0";
      card_uid += String(uid[i], HEX);
    }
    card_uid.toUpperCase();
    Serial.println("UID: " + card_uid);
    
    // 上报
    reportNfcScan(card_uid);
    
    // 避免重复读取，稍微延时
    delay(2000);
  }
  
  // 小延时防止 CPU 占用过高
  delay(10);
}