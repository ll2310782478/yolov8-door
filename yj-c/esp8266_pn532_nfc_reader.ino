/**
 * ESP8266 + PN532 NFC 读卡器固件
 * 
 * 功能：
 * 1. ESP8266 连接 WiFi
 * 2. 轮询后端 /api/hardware/nfc/command/poll 获取 SCAN 命令
 * 3. 执行 SCAN 命令时使用 PN532 读取 NFC 卡片
 * 4. 将读取到的卡号上报到后端 /api/hardware/nfc-scan
 * 5. 根据后端返回的 OPEN/DENY 控制继电器开门
 * 
 * 硬件连接：
 * - ESP8266 (ESP-12F)
 * - PN532 NFC 模块 (I2C 接口)
 *   - PN532 SDA -> ESP8266 GPIO4 (D2)
 *   - PN532 SCL -> ESP8266 GPIO5 (D1)
 * - 继电器模块 (GPIO 控制)
 *   - 继电器控制端 -> ESP8266 GPIO12 (D6) 或其他可用 GPIO
 * 
 * 库依赖：
 * - Adafruit_PN532 (https://github.com/adafruit/Adafruit-PN532)
 * - ESP8266WiFi (内置)
 * - Arduino_JSON 或 ArduinoJson (用于 JSON 解析)
 * 
 * 编译环境：Arduino IDE 1.8+
 * 开发板选择：NodeMCU 1.0 (ESP-12E Module) 或类似
 */

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>

// ==================== 配置 ====================

// WiFi 配置
const char* SSID = "your-wifi-ssid";              // 改为你的 WiFi SSID
const char* PASSWORD = "your-wifi-password";       // 改为你的 WiFi 密码

// 后端服务器配置
const char* SERVER_HOST = "192.168.1.100";        // 改为后端服务器 IP
const int SERVER_PORT = 8000;
const char* DEVICE_ID = "nfc_reader_01";          // 设备ID，需与后端注册一致
const char* API_ENDPOINT_POLL = "/api/hardware/nfc/command/poll";
const char* API_ENDPOINT_SCAN = "/api/hardware/nfc-scan";

// 轮询间隔（毫秒）
const unsigned long POLL_INTERVAL = 5000;  // 5 秒轮询一次

// ==================== 硬件 GPIO 引脚 ====================

// PN532 I2C 引脚（ESP8266 固定 I2C 端口）
#define PN532_SCL 5   // GPIO5 (D1)
#define PN532_SDA 4   // GPIO4 (D2)

// 继电器控制引脚
#define RELAY_PIN 12  // GPIO12 (D6) - 控制继电器

// 状态指示灯（可选）
#define LED_PIN 2     // GPIO2 (D4) - 内置 LED (低电平点亮)

// ==================== 全局对象 ====================

// PN532 NFC 读卡器（I2C 方式）
Adafruit_PN532 nfc(PN532_SCL, PN532_SDA);

// WiFi 客户端
WiFiClient wifiClient;

// ==================== 工具函数 ====================

/**
 * 初始化 LED（状态指示灯）
 */
void initLED() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // 初始关闭
}

/**
 * 控制 LED
 * on: true - 打开（低电平）, false - 关闭（高电平）
 */
void setLED(bool on) {
  digitalWrite(LED_PIN, on ? LOW : HIGH);
}

/**
 * 初始化继电器
 */
void initRelay() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);  // 初始关闭
}

/**
 * 控制继电器打开门
 * duration_ms: 继电器持续时间（毫秒）
 */
void openDoor(unsigned int duration_ms = 1000) {
  digitalWrite(RELAY_PIN, HIGH);  // 继电器打开
  setLED(true);
  delay(duration_ms);
  digitalWrite(RELAY_PIN, LOW);   // 继电器关闭
  setLED(false);
}

/**
 * 初始化 WiFi 连接
 */
void initWiFi() {
  Serial.println("[WiFi] 连接到 WiFi...");
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
    setLED(true);  // LED 亮表示连接成功
  } else {
    Serial.println();
    Serial.println("[WiFi] 连接失败");
  }
}

/**
 * 初始化 PN532 NFC 模块
 */
void initPN532() {
  Serial.println("[PN532] 初始化 NFC 模块...");
  
  nfc.begin();
  uint32_t versiondata = nfc.getFirmwareVersion();
  
  if (!versiondata) {
    Serial.println("[PN532] 未检测到 PN532 模块！");
    return;
  }
  
  Serial.print("[PN532] 固件版本: ");
  Serial.println((versiondata >> 24) & 0xFF);
  
  // 配置 PN532 为主动模式
  nfc.SAMConfig();
  Serial.println("[PN532] PN532 初始化完成");
}

/**
 * 从 PN532 读取 NFC 卡号
 * 返回卡号字符串（格式: "AA-BB-CC-DD"），失败返回空字符串
 */
String readNFCCard() {
  Serial.println("[NFC] 等待卡片...");
  setLED(true);  // LED 亮表示正在读卡
  
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;
  
  // 尝试读卡，超时 10 秒
  unsigned long start_time = millis();
  while (millis() - start_time < 10000) {
    bool success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength);
    
    if (success) {
      // 成功读到卡
      String card_uid = "";
      for (uint8_t i = 0; i < uidLength; i++) {
        if (i > 0) card_uid += "-";
        if (uid[i] < 0x10) card_uid += "0";
        card_uid += String(uid[i], HEX);
      }
      card_uid.toUpperCase();
      
      Serial.print("[NFC] 读到卡号: ");
      Serial.println(card_uid);
      setLED(false);  // LED 灭表示读卡完成
      
      return card_uid;
    }
    
    delay(100);
  }
  
  Serial.println("[NFC] 读卡超时");
  setLED(false);
  return "";
}

/**
 * 轮询后端获取待执行命令
 * 返回任务 ID，如果没有任务返回 -1
 */
int pollCommand() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Poll] WiFi 未连接");
    return -1;
  }
  
  // 构建请求 URL
  String url = String(API_ENDPOINT_POLL) + "?device_id=" + DEVICE_ID;
  
  Serial.print("[Poll] 轮询命令: ");
  Serial.println(url);
  
  // 连接服务器
  if (!wifiClient.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[Poll] 连接服务器失败");
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
  
  // 解析响应（跳过 HTTP 头部）
  int body_start = response.indexOf("\r\n\r\n");
  if (body_start == -1) {
    body_start = response.indexOf("\n\n");
    if (body_start != -1) body_start += 2;
  } else {
    body_start += 4;
  }
  
  if (body_start == -1) {
    Serial.println("[Poll] 解析响应失败");
    return -1;
  }
  
  String json_body = response.substring(body_start);
  Serial.print("[Poll] 响应: ");
  Serial.println(json_body);
  
  // 解析 JSON
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, json_body);
  
  if (error) {
    Serial.print("[Poll] JSON 解析失败: ");
    Serial.println(error.c_str());
    return -1;
  }
  
  if (!doc["has_command"].is<bool>() || !doc["has_command"].as<bool>()) {
    // 没有命令
    return -1;
  }
  
  int task_id = doc["task_id"].as<int>();
  String command = doc["command"].as<String>();
  
  Serial.print("[Poll] 收到任务 ID: ");
  Serial.print(task_id);
  Serial.print(", 命令: ");
  Serial.println(command);
  
  return task_id;
}

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
    Serial.println("[Report] 连接服务器失败");
    return false;
  }
  
  // 发送 POST 请求
  wifiClient.print("POST ");
  wifiClient.print(API_ENDPOINT_SCAN);
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
    Serial.println("[Report] 解析响应失败");
    return false;
  }
  
  String json_body = response.substring(body_start);
  Serial.print("[Report] 响应: ");
  Serial.println(json_body);
  
  // 解析 JSON
  StaticJsonDocument<256> resp_doc;
  DeserializationError error = deserializeJson(resp_doc, json_body);
  
  if (error) {
    Serial.print("[Report] JSON 解析失败: ");
    Serial.println(error.c_str());
    return false;
  }
  
  String action = resp_doc["action"].as<String>();
  String msg = resp_doc["msg"].as<String>();
  
  Serial.print("[Report] 动作: ");
  Serial.print(action);
  Serial.print(", 消息: ");
  Serial.println(msg);
  
  return action == "OPEN";
}

// ==================== Arduino 主函数 ====================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("========== ESP8266 + PN532 NFC 读卡器 ==========");
  Serial.println("固件版本: 1.0");
  Serial.println("");
  
  // 初始化 GPIO
  initLED();
  initRelay();
  
  // 初始化 PN532
  initPN532();
  
  // 初始化 WiFi
  initWiFi();
  
  Serial.println("[Setup] 初始化完成，开始运行");
}

void loop() {
  // 检查 WiFi 连接
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Loop] WiFi 已断开，重新连接...");
    initWiFi();
  }
  
  // 轮询命令
  static unsigned long last_poll_time = 0;
  unsigned long now = millis();
  
  if (now - last_poll_time >= POLL_INTERVAL) {
    last_poll_time = now;
    
    int task_id = pollCommand();
    
    if (task_id >= 0) {
      // 收到 SCAN 命令，执行扫描
      Serial.print("[Loop] 执行 SCAN 命令 (task_id: ");
      Serial.print(task_id);
      Serial.println(")");
      
      String card_uid = readNFCCard();
      
      if (card_uid.length() > 0) {
        // 成功读到卡，上报给后端
        bool should_open = reportCard(card_uid);
        
        if (should_open) {
          Serial.println("[Loop] 后端允许开门，执行开门动作");
          openDoor(1500);  // 继电器持续 1.5 秒
        } else {
          Serial.println("[Loop] 后端拒绝开门");
        }
      } else {
        Serial.println("[Loop] 读卡失败或超时");
      }
    }
  }
  
  delay(100);  // 避免忙轮询
}

/**
 * 故障排查提示：
 * 
 * 1. 串口调试
 *    - 打开 Arduino IDE 串口监视器（波特率 115200）
 *    - 观察初始化信息和运行日志
 * 
 * 2. WiFi 连接问题
 *    - 确保 SSID 和密码正确
 *    - 检查 ESP8266 与路由器的信号强度
 *    - 尝试手动设置静态 IP
 * 
 * 3. PN532 识别问题
 *    - 检查 I2C 接线（SDA/SCL）
 *    - 确认 PN532 地址（通常为 0x48）
 *    - 使用 I2C Scanner 扫描设备
 * 
 * 4. 网络通信问题
 *    - 确保后端 IP 和端口正确
 *    - 在电脑上测试后端 API: curl http://192.168.1.100:8000/health
 *    - 检查防火墙设置
 * 
 * 5. 继电器不动作
 *    - 检查继电器接线
 *    - 测试 GPIO12 输出是否正常
 *    - 检查继电器是否需要外部电源
 */
