/*
 * ESP8266 智能门禁控制器 (v4.0 统一开门接口版)
 * 功能特性：
 * 1. 远程开门 - 支持通过服务器指令控制
 * 2. 统一开门接口 - openDoor(doorId, source) 供所有模块调用
 * 3. NFC功能已禁用 - 可通过 ENABLE_NFC 重新启用
 * 4. 支持多模块触发 - 人脸识别、NFC、蓝牙、二维码等
 * 
 * 更新日志 v4.0:
 * - 新增统一开门接口 openDoor()
 * - 禁用NFC扫描功能（保留代码）
 * - 优化远程开门轮询机制
 */

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

// ==================== 1. 用户配置 ====================

// 功能开关
#define ENABLE_NFC false          // NFC功能开关（false=禁用，true=启用）

const char* SSID        = "lll";           // WiFi名称
const char* PASSWORD    = "12345678";      // WiFi密码
const char* SERVER_HOST = "192.168.188.116"; // 电脑IP
const int   SERVER_PORT = 8000;            // 端口

// 设备身份信息
const char* DEVICE_ID   = "nfc_reader_01";           // 设备唯一ID
const char* DEVICE_NAME = "门禁控制器-01";            // 设备名称
const char* DEVICE_TYPE = "door_controller";          // 设备类型
const char* DEVICE_LOC  = "实验室大门";               // 安装位置

// 硬件引脚
#define PN532_SDA D2   // GPIO4
#define PN532_SCL D1   // GPIO5
#define PN532_IRQ D3   // GPIO0 (IRQ必须接这个!)
#define PN532_RESET D0 // 没什么用，占位

// 门锁引脚
#define DOOR1_PIN D8
#define DOOR2_PIN D7
#define STATUS_LED D4  
const bool LED_INVERTED = true; // 板载LED通常是低电平亮

// ==================== 2. 全局变量 ====================

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET, &Wire);
WiFiClient client;

// 门锁计时器
unsigned long door1_close_time = 0; 
unsigned long door2_close_time = 0;

// NFC 状态机枚举
enum NFCState {
  NFC_IDLE,       // 空闲，准备发送扫描指令
  NFC_WAITING,    // 已发送指令，正在等 IRQ 变低
  NFC_COOLDOWN    // 刚读完卡，冷却一会防止连刷
};
NFCState nfcState = NFC_IDLE;
unsigned long nfc_timer = 0;
String last_uid = "";

// 网络轮询计时器
unsigned long last_poll_time = 0;

// ==================== 3. 硬件控制 (异步) ====================

void setLed(bool on) {
  if (LED_INVERTED) digitalWrite(STATUS_LED, on ? LOW : HIGH);
  else digitalWrite(STATUS_LED, on ? HIGH : LOW);
}

// ==================== 统一开门接口 ====================
/**
 * 统一开门接口 - 所有模块调用此接口开门
 * @param doorId 门编号 (1=门1, 2=门2)
 * @param source 触发来源 ("remote"=远程, "face"=人脸, "nfc"=NFC卡, "bluetooth"=蓝牙, "qrcode"=二维码)
 * @return bool 是否成功触发
 */
bool openDoor(int doorId, String source) {
  // 参数验证
  if (doorId != 1 && doorId != 2) {
    Serial.println("[Door] 错误: 无效的门编号 " + String(doorId));
    return false;
  }

  // 记录日志
  Serial.println("╔════════════════════════════════════╗");
  Serial.println("║     🔓 门禁开启                    ║");
  Serial.println("╠════════════════════════════════════╣");
  Serial.print("║  门编号: "); Serial.println(doorId == 1 ? "门1 (前门)      ║" : "门2 (后门)      ║");
  Serial.print("║  触发源: "); 
  if (source == "remote") Serial.println("远程指令        ║");
  else if (source == "face") Serial.println("人脸识别        ║");
  else if (source == "nfc") Serial.println("NFC刷卡         ║");
  else if (source == "bluetooth") Serial.println("蓝牙开门        ║");
  else if (source == "qrcode") Serial.println("二维码扫描      ║");
  else Serial.println(source + "                ║");
  Serial.println("║  开锁时长: 3秒                     ║");
  Serial.println("╚════════════════════════════════════╝");

  // 点亮状态灯
  setLed(true);

  // 执行开门操作
  if (doorId == 1) {
    digitalWrite(DOOR1_PIN, HIGH);
    door1_close_time = millis() + 3000; // 3秒后自动关闭
  } 
  else if (doorId == 2) {
    digitalWrite(DOOR2_PIN, HIGH);
    door2_close_time = millis() + 3000; // 3秒后自动关闭
  }

  return true;
}

// 兼容旧代码的包装函数（已废弃，建议使用 openDoor）
void triggerDoor(int doorId) {
  openDoor(doorId, "legacy");
}

// 门卫任务：负责时间到了关门
void doorTask() {
  unsigned long now = millis();
  if (door1_close_time > 0 && now > door1_close_time) {
    digitalWrite(DOOR1_PIN, LOW); door1_close_time = 0; setLed(false);
    Serial.println("[Door] 门1 自动关闭");
  }
  if (door2_close_time > 0 && now > door2_close_time) {
    digitalWrite(DOOR2_PIN, LOW); door2_close_time = 0; setLed(false);
    Serial.println("[Door] 门2 自动关闭");
  }
}

// ==================== 4. 网络通信 (健壮版) ====================

String sendRequest(String method, String path, String jsonBody) {
  if (WiFi.status() != WL_CONNECTED) return "";
  
  // 确保连接干净
  client.stop();
  if (!client.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[NET] 连接失败");
    return "";
  }

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

  String response = "";
  unsigned long timeout = millis();
  while (client.connected() || client.available()) {
    if (client.available()) response += (char)client.read();
    if (millis() - timeout > 2000) break; // 2秒超时
  }
  client.stop();
  return response;
}

bool postJson(const String& path, const String& jsonBody) {
  if (WiFi.status() != WL_CONNECTED) return false;
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
  }
  http.end();
  return code > 0 && code < 300;
}

void registerDevice() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_name"] = DEVICE_NAME;
  doc["device_type"] = DEVICE_TYPE;
  doc["location"] = DEVICE_LOC;
  doc["ip_address"] = WiFi.localIP().toString();
  String body; serializeJson(doc, body);

  bool ok = postJson("/api/hardware/devices", body);
  if (ok) {
    Serial.println("[REG] 设备注册成功");
  } else {
    Serial.println("[REG] 设备注册可能已存在或失败，继续心跳...\n     如果已注册过可忽略此提示");
  }
}

void heartbeatTask() {
  static unsigned long lastHeartbeatAt = 0;
  if (millis() - lastHeartbeatAt < 30000) return; // 30秒一次
  lastHeartbeatAt = millis();

  StaticJsonDocument<192> doc;
  doc["connection_status"] = "online";
  doc["ip_address"] = WiFi.localIP().toString();
  doc["firmware_version"] = "v4.0";
  String body; serializeJson(doc, body);

  bool ok = postJson(String("/api/hardware/devices/") + DEVICE_ID + "/heartbeat", body);
  Serial.println(ok ? "💓 心跳: 成功" : "💔 心跳: 失败");
}

// ==================== 5. NFC扫描任务 (可选功能，已禁用) ====================

void nfcTask() {
  #if ENABLE_NFC  // 只有启用NFC时才编译此代码
  
  unsigned long now = millis();

  switch (nfcState) {
    
    // --- 状态1: 准备扫描 ---
    case NFC_IDLE:
      nfcState = NFC_WAITING;
      nfc_timer = now;
      break;

    // --- 状态2: 等待 IRQ 信号 ---
    case NFC_WAITING:
      if (digitalRead(PN532_IRQ) == LOW) {
        Serial.println("[NFC] IRQ 触发！读取卡片数据...");
        
        uint8_t uid[] = {0,0,0,0,0,0,0};
        uint8_t uidLen;
        
        if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLen, 100)) {
          String current_uid = "";
          for (uint8_t i = 0; i < uidLen; i++) {
            if (i) current_uid += "-";
            if (uid[i] < 0x10) current_uid += "0";
            current_uid += String(uid[i], HEX);
          }
          current_uid.toUpperCase();
          Serial.println("[NFC] 读到 UID: " + current_uid);

          // 上报服务器
          StaticJsonDocument<200> doc;
          doc["device_id"] = DEVICE_ID;
          doc["card_uid"] = current_uid;
          String json; serializeJson(doc, json);
          
          String resp = sendRequest("POST", "/api/hardware/nfc-scan", json);
          if (resp.indexOf("OPEN") != -1 || resp.indexOf("ALLOW") != -1) {
             int doorId = (resp.indexOf("door2") != -1) ? 2 : 1;
             openDoor(doorId, "nfc");  // 使用统一接口
          }
        }
        
        nfcState = NFC_COOLDOWN;
        nfc_timer = millis();
      } 
      else {
        if (now - nfc_timer > 5000) {
           nfcState = NFC_IDLE; 
        }
      }
      break;

    // --- 状态3: 冷却防抖 ---
    case NFC_COOLDOWN:
      if (now - nfc_timer > 2000) {
        nfcState = NFC_IDLE;
      }
      break;
  }
  
  #endif  // ENABLE_NFC
}

// ==================== 6. 远程开门轮询任务 ====================

void pollTask() {
  if (millis() - last_poll_time > 2000) { // 2秒轮询一次
    last_poll_time = millis();
    
    // 构造心跳包
    StaticJsonDocument<64> doc;
    doc["device_id"] = DEVICE_ID;
    String json; serializeJson(doc, json);

    // 发送轮询请求
    String resp = sendRequest("POST", "/api/hardware/nfc/command/poll", json);
    
    // 解析响应
    if (resp.length() > 0) {
      // 检查是否有开门指令
      if (resp.indexOf("OPEN") != -1) {
        Serial.println("╔════════════════════════════════════╗");
        Serial.println("║  📡 收到远程开门指令               ║");
        Serial.println("╚════════════════════════════════════╝");
        
        // 解析门编号
        int doorId = 1;  // 默认门1
        String source = "remote";  // 默认来源
        
        if (resp.indexOf("door2") != -1) {
          doorId = 2;
        }
        
        // 尝试解析触发来源（人脸/蓝牙/二维码等）
        if (resp.indexOf("face") != -1) source = "face";
        else if (resp.indexOf("bluetooth") != -1) source = "bluetooth";
        else if (resp.indexOf("qrcode") != -1) source = "qrcode";
        
        // 调用统一开门接口
        openDoor(doorId, source);
      }
    }
  }
}

// ==================== 7. 主程序 ====================

void setup() {
  Serial.begin(115200);
  delay(500);
  
  // 显示启动信息
  Serial.println("\n╔════════════════════════════════════════════╗");
  Serial.println("║   ESP8266 智能门禁控制器 v4.0             ║");
  Serial.println("╠════════════════════════════════════════════╣");
  Serial.println("║  功能: 远程开门 + 统一接口                ║");
  Serial.print("║  NFC功能: ");
  Serial.println(ENABLE_NFC ? "已启用                         ║" : "已禁用                         ║");
  Serial.println("╚════════════════════════════════════════════╝\n");

  // 初始化硬件引脚
  pinMode(DOOR1_PIN, OUTPUT);
  pinMode(DOOR2_PIN, OUTPUT);
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(DOOR1_PIN, LOW);
  digitalWrite(DOOR2_PIN, LOW);
  setLed(false);
  
  #if ENABLE_NFC
  // 只在启用NFC时初始化PN532
  pinMode(PN532_IRQ, INPUT_PULLUP);
  Wire.begin(PN532_SDA, PN532_SCL);
  nfc.begin();
  
  uint32_t ver = nfc.getFirmwareVersion();
  if (!ver) {
    Serial.println("⚠️  警告: 未找到 PN532 模块");
  } else {
    nfc.SAMConfig();
    Serial.println("✅ PN532 初始化成功 (IRQ 模式)");
  }
  #else
  Serial.println("ℹ️  NFC功能已禁用，跳过PN532初始化");
  #endif

  // 连接WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  Serial.print("🔌 正在连接WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n✅ WiFi已连接");
  Serial.println("📍 IP地址: " + WiFi.localIP().toString());
  Serial.println("🌐 服务器: " + String(SERVER_HOST) + ":" + String(SERVER_PORT));

  // 设备注册（已存在会返回失败，忽略即可）
  registerDevice();
  
  Serial.println("\n✨ 系统启动完成，等待指令...\n");
}

void loop() {
  static unsigned long last_heartbeat = 0;
  
  // 每30秒输出一次心跳日志
  if (millis() - last_heartbeat > 30000) {
    last_heartbeat = millis();
    Serial.println("💓 系统运行正常 | 在线时长: " + String(millis()/1000) + "秒");
    #if ENABLE_NFC
    Serial.print("   NFC状态: ");
    Serial.println(nfcState == NFC_IDLE ? "空闲" : (nfcState == NFC_WAITING ? "等待" : "冷却"));
    #endif
  }
  
  // === 任务调度 ===
  
  #if ENABLE_NFC
  // 1. NFC扫描任务 (仅在启用时运行)
  nfcTask();
  #endif

  // 2. 远程开门轮询 (主要功能)
  pollTask();

  // 3. 心跳上报（含IP/固件版本）
  heartbeatTask();

  // 4. 门锁自动关闭管理
  doorTask();

  // 5. CPU休息
  delay(10);
}

/*
 * ==================== API使用说明 ====================
 * 
 * 统一开门接口:
 *   bool openDoor(int doorId, String source)
 * 
 * 参数:
 *   doorId - 门编号 (1或2)
 *   source - 触发来源:
 *     "remote"    - 远程控制
 *     "face"      - 人脸识别
 *     "nfc"       - NFC刷卡
 *     "bluetooth" - 蓝牙开门
 *     "qrcode"    - 二维码扫描
 * 
 * 使用示例:
 *   openDoor(1, "face");       // 人脸识别开门1
 *   openDoor(2, "remote");     // 远程开门2
 *   openDoor(1, "bluetooth");  // 蓝牙开门1
 * 
 * 服务器端调用示例:
 *   POST /api/hardware/nfc/command/poll
 *   响应: {"command": "OPEN", "door": "door1", "source": "face"}
 * 
 * ====================================================
 */
