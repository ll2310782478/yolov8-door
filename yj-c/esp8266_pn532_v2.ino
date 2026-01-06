/*
 * ESP8266 智能门禁控制器 - 门禁1 (v5.0 纯远程控制版)
 * 
 * 功能特性：
 * 1. 远程开门 - 支持通过服务器轮询命令控制
 * 2. 统一开门接口 - openDoor(doorId, source) 供所有模块调用
 * 3. 设备标识：门禁1（此设备仅支持远程开门，不支持NFC）
 * 4. 支持多源触发 - 远程、人脸识别、蓝牙、二维码等（由服务器端区分）
 * 
 * 更新日志 v5.0:
 * - 完全移除NFC相关功能和代码（PN532库及初始化）
 * - 保留纯远程开门轮询机制
 * - 添加设备标识支持（用于多设备区分）
 * - NFC功能由门禁2(ESP32-S3)接手
 */

#include <Wire.h>
#include <SPI.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266mDNS.h>
#include <ArduinoJson.h>

// ==================== 1. 用户配置 ====================

const char* SSID        = "安居门业";           // WiFi名称
const char* PASSWORD    = "15929256728";      // WiFi密码

// mDNS自动发现服务器（推荐）- 无需手动配置IP
const char* SERVER_HOST = "smartaccess.local"; // 服务器域名（mDNS自动解析）
const int   SERVER_PORT = 8000;            // 端口

// 如果mDNS不可用，可回退到手动配置IP（取消下方注释）
// const char* SERVER_HOST = "192.168.188.116"; // 手动配置服务器IP

// 设备身份信息 - 门禁1
const char* DEVICE_ID   = "door_controller_1";     // 设备唯一ID
const char* DEVICE_NAME = "门禁1";                   // 设备名称（用户可读）
const char* DEVICE_TYPE = "door_controller";        // 设备类型
const char* DEVICE_LOC  = "实验室大门";              // 安装位置
const char* DEVICE_MODE = "remote_only";            // 设备模式：remote_only (仅远程开门)

// 硬件引脚
#define DOOR1_PIN D8
#define DOOR2_PIN D7
#define STATUS_LED D4  
const bool LED_INVERTED = true; // 板载LED通常是低电平亮

// ==================== 2. 全局变量 ====================

WiFiClient client;

// 门锁计时器
unsigned long door1_close_time = 0; 
unsigned long door2_close_time = 0;

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

// ==================== 5. 远程开门轮询任务 ====================

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
  Serial.println("║   ESP8266 智能门禁控制器 v5.0             ║");
  Serial.println("║   模式: 门禁1 - 纯远程控制                ║");
  Serial.println("╠════════════════════════════════════════════╣");
  Serial.println("║  功能: 远程开门 + 统一接口                ║");
  Serial.println("║  备注: 不支持 NFC 功能                    ║");
  Serial.println("╚════════════════════════════════════════════╝\n");

  // 初始化硬件引脚
  pinMode(DOOR1_PIN, OUTPUT);
  pinMode(DOOR2_PIN, OUTPUT);
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(DOOR1_PIN, LOW);
  digitalWrite(DOOR2_PIN, LOW);
  setLed(false);

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
  
  // 启动mDNS客户端（用于自动发现服务器）
  if (!MDNS.begin("door-controller-1")) {
    Serial.println("⚠️  mDNS启动失败，将尝试直接连接服务器");
  } else {
    Serial.println("✅ mDNS客户端已启动");
    Serial.println("💡 可使用域名 'smartaccess.local' 自动发现服务器");
  }

  // 设备注册（已存在会返回失败，忽略即可）
  registerDevice();
  
  Serial.println("\n✨ 系统启动完成，等待远程指令...\n");
}

void loop() {
  static unsigned long last_heartbeat = 0;
  
  // 每30秒输出一次心跳日志
  if (millis() - last_heartbeat > 30000) {
    last_heartbeat = millis();
    Serial.println("💓 系统运行正常 | 在线时长: " + String(millis()/1000) + "秒");
  }
  
  // === 任务调度 ===
  
  // 1. 远程开门轮询 (主要功能)
  pollTask();

  // 2. 心跳上报（含IP/固件版本）
  heartbeatTask();

  // 3. 门锁自动关闭管理
  doorTask();

  // 4. CPU休息
  delay(10);
}

/*
 * ==================== API使用说明 ====================
 * 
 * 【门禁1 (ESP8266)】- 纯远程控制设备
 * 
 * 统一开门接口:
 *   bool openDoor(int doorId, String source)
 * 
 * 参数:
 *   doorId - 门编号 (1=门1, 2=门2)
 *   source - 触发来源:
 *     "remote"    - 远程控制（主要）
 *     "face"      - 人脸识别
 *     "bluetooth" - 蓝牙开门
 *     "qrcode"    - 二维码扫描
 * 
 * 使用示例:
 *   openDoor(1, "remote");     // 远程开门1
 *   openDoor(2, "remote");     // 远程开门2
 *   openDoor(1, "face");       // 人脸识别触发远程开门1
 * 
 * 服务器端轮询流程:
 *   1. 设备 POST /api/hardware/nfc/command/poll，获取待执行命令
 *   2. 若响应包含 "OPEN" 字段，解析 door 和 source，调用 openDoor()
 *   3. 设备执行开门后自动关闭
 * 
 * 注：此设备不支持 NFC 刷卡，NFC 功能由门禁2(ESP32-S3)提供
 * 
 * ====================================================
 */
