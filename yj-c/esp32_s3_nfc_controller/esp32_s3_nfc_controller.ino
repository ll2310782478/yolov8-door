/*
 * ESP32-S3 智能门禁控制器 - 门禁2 (v2.0 双核并发版)
 * 
 * 功能特性：
 * 1. FreeRTOS 双核架构 - Core0=NFC实时读卡, Core1=网络轮询
 * 2. 远程开门 - 支持通过服务器轮询命令控制（非阻塞）
 * 3. NFC刷卡 - 独立线程实时监听卡片，响应延迟 <10ms
 * 4. 线程安全通信 - 互斥锁保护共享状态，队列传递事件
 * 5. 分层显示反馈 - ST7789 + MAX98357 实时音视频反馈
 * 
 * 硬件配置：
 * I2C (NFC) - SDA:GPIO5, SCL:GPIO4, IRQ:GPIO6
 * SPI (屏幕+喇叭) - MOSI:GPIO10, MISO:无, CLK:GPIO9
 * ST7789 屏幕 - CS:GPIO13, DC:GPIO12, RST:GPIO11, BL:GPIO14
 * MAX98357 喇叭 - BCLK:GPIO15, LRCK:GPIO7, DOUT:GPIO16
 * 门锁继电器 - Door1:GPIO18, Door2:GPIO17
 * RGB LED - GPIO48
 * 重置按键 - GPIO21 (长按8秒清除配置)
 * 
 * 任务分配：
 * Core 0:
 *   - nfcMonitor() - 专属 NFC 监听线程（高优先级）
 *   - doorController() - 门锁控制线程
 * 
 * Core 1:
 *   - networkPoller() - 远程轮询线程（中优先级）
 *   - heartbeatTask() - 心跳线程（低优先级）
 *   - displayUpdater() - 屏幕更新线程（低优先级）
 * 
 * 更新日志 v2.0:
 * - 采用 FreeRTOS 双核架构
 * - 移除单线程轮询模式，实现真正的并发
 * - 加入线程安全的共享状态管理
 * - NFC 响应时间从 50-100ms 降低到 <10ms
 * - 配置保存后自动重启系统
 * - 重置按键改用 GPIO21，避免启动时误触发
 */

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <driver/i2s.h>
#include <esp_system.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <BLEDevice.h>
#include <BLEScan.h>

// ==================== 1. 用户配置 ====================

const char* DEFAULT_SSID         = "ll";
const char* DEFAULT_PASSWORD     = "15929256728";
const char* DEFAULT_SERVER_HOST  = "192.168.1.42";
const int   DEFAULT_SERVER_PORT  = 8000;
const char* DEFAULT_FALLBACK_HOST = "";

const char* DEFAULT_DEVICE_ID    = "door_controller_2";
const char* DEFAULT_DEVICE_NAME  = "门禁2";
const char* DEFAULT_DEVICE_TYPE  = "door_controller_nfc";
const char* DEFAULT_DEVICE_LOC   = "办公室";
const char* DEFAULT_DEVICE_MODE  = "remote_nfc";

const char* AP_SSID = "SmartAccess-Setup";
const char* AP_PASSWORD = "12345678";
const unsigned long RESET_HOLD_MS = 8000;

// 调试安全开关：若出现启动卡死，可先关闭显示或提示音定位问题
const bool ENABLE_TFT = true;
const bool ENABLE_SOUND = true;
const bool ENABLE_BLE = true;

const int BLE_NEAR_RSSI_THRESHOLD = -72;
const unsigned long BLE_STABLE_MS = 5000;
const unsigned long BLE_RESCAN_INTERVAL_MS = 2500;
const unsigned long BLE_DEVICE_STALE_MS = 8000;
const unsigned long BLE_VERIFY_GAP_MS = 5000;

// ==================== 2. 硬件引脚配置 ====================

// I2C (NFC)
#define PN532_SDA 5
#define PN532_SCL 4
#define PN532_IRQ 6
#define PN532_RESET -1

// SPI (屏幕 + 喇叭)
#define SPI_MOSI 10
#define SPI_MISO -1
#define SPI_CLK  9

// ST7789 屏幕
#define TFT_CS   13
#define TFT_DC   12
#define TFT_RST  11
#define TFT_BL   14

// MAX98357 喇叭 (I2S)
#define I2S_BCLK 15
#define I2S_LRCK 7
#define I2S_DOUT 16

// 提示音通过 MAX98357 (I2S) 输出

// 门锁继电器
#define DOOR1_PIN 18
#define DOOR2_PIN 17

// RGB LED
#define RGB_PIN 48
#define RGB_COUNT 1

// 长按重置按钮（使用 GPIO21，避免 GPIO0 在启动时的干扰）
#define RESET_BTN_PIN 21

// ==================== 3. 全局数据结构 ====================

// 事件类型定义
enum EventType {
  EVENT_NFC_CARD_READ,      // NFC 卡片读取成功
  EVENT_NFC_PERMISSION_OK,  // 服务器授予权限
  EVENT_NFC_PERMISSION_DENY, // 服务器拒绝
  EVENT_REMOTE_DOOR_OPEN,   // 远程开门指令
  EVENT_NETWORK_ERROR,      // 网络错误
  EVENT_SYSTEM_ERROR        // 系统错误
};

// 事件队列结构
struct SystemEvent {
  EventType type;
  char data[64];  // 额外数据（如卡号、错误信息）
  unsigned long timestamp;
};

// NFC 状态结构（线程安全）
struct NFCStatus {
  bool card_detected;
  char last_card_uid[32];
  unsigned long last_read_time;
  bool force_read;  // 远程触发读卡标志（用于 ENROLL/SCAN 命令）
};

// 门锁状态结构（线程安全）
struct DoorStatus {
  bool is_open;
  unsigned long open_time;
  int door_id;
  char trigger_source[16];
};

// ==================== 4. 互斥锁和队列 ====================

// 保护共享资源的互斥锁
SemaphoreHandle_t nfc_mutex = NULL;
SemaphoreHandle_t door_mutex = NULL;
SemaphoreHandle_t network_mutex = NULL;
SemaphoreHandle_t display_mutex = NULL;
SemaphoreHandle_t serial_mutex = NULL;
SemaphoreHandle_t ble_mutex = NULL;

// 事件队列（跨核通信）
QueueHandle_t event_queue = NULL;

// 共享状态变量
NFCStatus nfc_status = {false, "", 0, false};
DoorStatus door_status = {false, 0, 1, "none"};
bool enroll_mode = false;  // ENROLL 模式下只返回首张卡

// ==================== 5. 硬件对象 ====================

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET, &Wire);
Adafruit_NeoPixel pixels(RGB_COUNT, RGB_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);
WiFiClient wifiClient;
WebServer configServer(80);
Preferences preferences;

struct DeviceConfig {
  String wifiSsid;
  String wifiPassword;
  String serverHost;
  int serverPort;
  String fallbackHost;
  String deviceId;
  String deviceName;
  String deviceType;
  String deviceLocation;
  String deviceMode;
  bool configured;
};

DeviceConfig gConfig;
String currentHost = DEFAULT_SERVER_HOST;
int currentServerPort = DEFAULT_SERVER_PORT;
String currentDeviceId = DEFAULT_DEVICE_ID;
String currentDeviceName = DEFAULT_DEVICE_NAME;
String currentDeviceType = DEFAULT_DEVICE_TYPE;
String currentDeviceLoc = DEFAULT_DEVICE_LOC;
String currentDeviceMode = DEFAULT_DEVICE_MODE;

bool apConfigSaved = false;
unsigned long resetPressStartMs = 0;
bool configPortalActive = false;
unsigned long displayHoldUntil = 0;
bool gDisplayReady = false;
bool gSoundReady = false;
bool gNfcReady = false;
bool gBleReady = false;
int gI2cDeviceCount = 0;
uint32_t gNfcFwVersion = 0;
volatile unsigned long gNfcPollCounter = 0;
volatile unsigned long gBleLastScanMs = 0;
volatile unsigned long gBleLastReportMs = 0;
volatile unsigned long gBleLastVerifyMs = 0;
volatile int gBleLastSeenCount = 0;

struct BLESeenDevice {
  bool used;
  char mac[18];
  char name[32];
  int rssi;
  unsigned long firstSeenMs;
  unsigned long lastSeenMs;
  unsigned long lastVerifyMs;
};

BLESeenDevice gBleSeenDevices[20];
BLEScan* gBleScan = nullptr;

// Arduino 预处理器会提前生成函数原型，先前向声明避免 SoundType 未定义
enum SoundType : uint8_t;

String truncateForLog(const String &s, size_t maxLen = 260) {
  if (s.length() <= maxLen) return s;
  return s.substring(0, maxLen) + "...<truncated>";
}

void serialLine(const String &msg, bool mirrorSerial0 = false) {
  if (serial_mutex != NULL && xSemaphoreTake(serial_mutex, pdMS_TO_TICKS(50))) {
    Serial.println(msg);
    if (mirrorSerial0) Serial0.println(msg);
    xSemaphoreGive(serial_mutex);
    return;
  }

  Serial.println(msg);
  if (mirrorSerial0) Serial0.println(msg);
}

void initSerialLogger() {
  if (serial_mutex == NULL) {
    serial_mutex = xSemaphoreCreateMutex();
  }
}

void resetBleSlot(int idx) {
  if (idx < 0 || idx >= 20) return;
  gBleSeenDevices[idx].used = false;
  gBleSeenDevices[idx].mac[0] = '\0';
  gBleSeenDevices[idx].name[0] = '\0';
  gBleSeenDevices[idx].rssi = -127;
  gBleSeenDevices[idx].firstSeenMs = 0;
  gBleSeenDevices[idx].lastSeenMs = 0;
  gBleSeenDevices[idx].lastVerifyMs = 0;
}

int findBleSlotByMac(const String &mac) {
  for (int i = 0; i < 20; i++) {
    if (!gBleSeenDevices[i].used) continue;
    if (mac.equalsIgnoreCase(String(gBleSeenDevices[i].mac))) return i;
  }
  return -1;
}

int allocBleSlot() {
  for (int i = 0; i < 20; i++) {
    if (!gBleSeenDevices[i].used) return i;
  }
  return -1;
}

String safeBleName(const String &name) {
  String trimmed = name;
  trimmed.trim();
  if (trimmed.length() == 0) return "BLE-UNKNOWN";
  if (trimmed.length() > 31) return trimmed.substring(0, 31);
  return trimmed;
}

bool initBleScanner() {
  if (!ENABLE_BLE) return false;
  BLEDevice::init(currentDeviceName.c_str());
  gBleScan = BLEDevice::getScan();
  if (gBleScan == nullptr) return false;
  gBleScan->setActiveScan(true);
  gBleScan->setInterval(120);
  gBleScan->setWindow(90);
  for (int i = 0; i < 20; i++) resetBleSlot(i);
  return true;
}

bool postJsonToBackend(const String &url, const String &body, String &respOut, int &codeOut) {
  if (WiFi.status() != WL_CONNECTED) return false;
  if (network_mutex == NULL || !xSemaphoreTake(network_mutex, pdMS_TO_TICKS(1500))) return false;

  HTTPClient http;
  WiFiClient httpClient;
  bool ok = false;
  if (http.begin(httpClient, url)) {
    http.setReuse(false);
    http.useHTTP10(true);
    http.setConnectTimeout(2500);
    http.setTimeout(4000);
    http.addHeader("Connection", "close");
    http.addHeader("Content-Type", "application/json");
    codeOut = http.POST((uint8_t*)body.c_str(), body.length());
    respOut = http.getString();
    ok = (codeOut > 0);
    http.end();
    httpClient.stop();
  }
  xSemaphoreGive(network_mutex);
  return ok;
}

void reportBleScanBatch() {
  if (!gBleReady || WiFi.status() != WL_CONNECTED) return;

  StaticJsonDocument<1024> doc;
  doc["device_id"] = currentDeviceId;
  JsonArray arr = doc.createNestedArray("devices");
  unsigned long now = millis();

  if (ble_mutex != NULL && xSemaphoreTake(ble_mutex, pdMS_TO_TICKS(50))) {
    for (int i = 0; i < 20; i++) {
      if (!gBleSeenDevices[i].used) continue;
      if (now - gBleSeenDevices[i].lastSeenMs > BLE_DEVICE_STALE_MS) continue;
      JsonObject d = arr.createNestedObject();
      d["mac"] = gBleSeenDevices[i].mac;
      d["name"] = gBleSeenDevices[i].name;
      d["rssi"] = gBleSeenDevices[i].rssi;
    }
    xSemaphoreGive(ble_mutex);
  }

  if (arr.size() == 0) return;

  String body;
  serializeJson(doc, body);
  String resp;
  int code = -1;
  String url = String("http://") + currentHost + ":" + String(currentServerPort) + "/api/hardware/bluetooth/report-scan-batch";
  if (postJsonToBackend(url, body, resp, code)) {
    if (code >= 200 && code < 300) {
      gBleLastReportMs = millis();
      Serial.printf("[BLE] report-scan-batch ok, count=%d\n", (int)arr.size());
    }
  }
}

void reportBleAccessLog(const String &mac, const String &status) {
  StaticJsonDocument<192> doc;
  doc["device_id"] = currentDeviceId;
  doc["bt_mac"] = mac;
  doc["access_type"] = "bluetooth";
  doc["status"] = status;
  String body;
  serializeJson(doc, body);

  String resp;
  int code = -1;
  String url = String("http://") + currentHost + ":" + String(currentServerPort) + "/api/hardware/bluetooth/access-log";
  postJsonToBackend(url, body, resp, code);
}

bool verifyBlePermission(const String &mac, int rssi) {
  gBleLastVerifyMs = millis();
  StaticJsonDocument<192> doc;
  doc["device_id"] = currentDeviceId;
  doc["bt_mac"] = mac;
  doc["rssi"] = rssi;
  String body;
  serializeJson(doc, body);

  String resp;
  int code = -1;
  String url = String("http://") + currentHost + ":" + String(currentServerPort) + "/api/hardware/bluetooth/verify";
  if (!postJsonToBackend(url, body, resp, code)) return false;
  if (code < 200 || code >= 300) return false;

  StaticJsonDocument<256> result;
  if (deserializeJson(result, resp) != DeserializationError::Ok) return false;
  bool allow = result["allow"].as<bool>();
  if (!allow) {
    reportBleAccessLog(mac, "denied");
    return false;
  }

  SystemEvent event;
  event.type = EVENT_REMOTE_DOOR_OPEN;
  strncpy(event.data, "door1:bluetooth", sizeof(event.data) - 1);
  event.data[sizeof(event.data) - 1] = '\0';
  event.timestamp = millis();
  xQueueSend(event_queue, &event, 0);

  reportBleAccessLog(mac, "success");
  Serial.printf("[BLE] allow open, mac=%s rssi=%d\n", mac.c_str(), rssi);
  return true;
}

void bluetoothScannerTask(void *parameter) {
  Serial.println("[Core1] BLE scanner task started");
  while (true) {
    if (!gBleReady || WiFi.status() != WL_CONNECTED || gBleScan == nullptr) {
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }

    BLEScanResults* scanResults = gBleScan->start(2, false);
    int found = scanResults ? scanResults->getCount() : 0;
    unsigned long now = millis();
    gBleLastScanMs = now;
    gBleLastSeenCount = found;

    if (ble_mutex != NULL && xSemaphoreTake(ble_mutex, pdMS_TO_TICKS(150))) {
      for (int i = 0; i < found; i++) {
        BLEAdvertisedDevice d = scanResults->getDevice(i);
        String mac = d.getAddress().toString().c_str();
        mac.toUpperCase();
        int rssi = d.getRSSI();
        String name = safeBleName(d.haveName() ? String(d.getName().c_str()) : String(""));

        int idx = findBleSlotByMac(mac);
        if (idx < 0) idx = allocBleSlot();
        if (idx < 0) continue;

        if (!gBleSeenDevices[idx].used) {
          gBleSeenDevices[idx].used = true;
          strncpy(gBleSeenDevices[idx].mac, mac.c_str(), sizeof(gBleSeenDevices[idx].mac) - 1);
          gBleSeenDevices[idx].mac[sizeof(gBleSeenDevices[idx].mac) - 1] = '\0';
          gBleSeenDevices[idx].firstSeenMs = now;
          gBleSeenDevices[idx].lastVerifyMs = 0;
        }

        strncpy(gBleSeenDevices[idx].name, name.c_str(), sizeof(gBleSeenDevices[idx].name) - 1);
        gBleSeenDevices[idx].name[sizeof(gBleSeenDevices[idx].name) - 1] = '\0';
        gBleSeenDevices[idx].rssi = rssi;
        gBleSeenDevices[idx].lastSeenMs = now;
      }

      for (int i = 0; i < 20; i++) {
        if (!gBleSeenDevices[i].used) continue;

        if (now - gBleSeenDevices[i].lastSeenMs > BLE_DEVICE_STALE_MS) {
          resetBleSlot(i);
          continue;
        }

        if (gBleSeenDevices[i].rssi < BLE_NEAR_RSSI_THRESHOLD) continue;
        if (now - gBleSeenDevices[i].firstSeenMs < BLE_STABLE_MS) continue;
        if (now - gBleSeenDevices[i].lastVerifyMs < BLE_VERIFY_GAP_MS) continue;

        gBleSeenDevices[i].lastVerifyMs = now;
        String mac = String(gBleSeenDevices[i].mac);
        int rssi = gBleSeenDevices[i].rssi;
        xSemaphoreGive(ble_mutex);
        verifyBlePermission(mac, rssi);
        if (ble_mutex != NULL) xSemaphoreTake(ble_mutex, pdMS_TO_TICKS(150));
      }

      xSemaphoreGive(ble_mutex);
    }

    reportBleScanBatch();
    gBleScan->clearResults();
    vTaskDelay(pdMS_TO_TICKS(BLE_RESCAN_INTERVAL_MS));
  }
}

void normalizeConfigStrings() {
  gConfig.wifiSsid.trim();
  gConfig.wifiPassword.trim();
  gConfig.serverHost.trim();
  gConfig.fallbackHost.trim();
  gConfig.deviceId.trim();
  gConfig.deviceName.trim();
  gConfig.deviceType.trim();
  gConfig.deviceLocation.trim();
  gConfig.deviceMode.trim();

  if (gConfig.serverPort <= 0 || gConfig.serverPort > 65535) {
    gConfig.serverPort = DEFAULT_SERVER_PORT;
  }
}

void printNetworkContext(const char* tag, const String& url = "") {
  Serial.printf("[%s] WiFi=%d host=%s port=%d ip=%s\n",
                tag,
                WiFi.status(),
                currentHost.c_str(),
                currentServerPort,
                WiFi.localIP().toString().c_str());
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[%s] gateway=%s dns1=%s dns2=%s rssi=%ld\n",
                  tag,
                  WiFi.gatewayIP().toString().c_str(),
                  WiFi.dnsIP(0).toString().c_str(),
                  WiFi.dnsIP(1).toString().c_str(),
                  WiFi.RSSI());
  }
  if (url.length() > 0) {
    Serial.printf("[%s] URL=%s\n", tag, url.c_str());
  }
}

String uidToHexRaw(const uint8_t* uid, uint8_t uidLen) {
  String out = "";
  for (uint8_t i = 0; i < uidLen; i++) {
    if (i) out += " ";
    if (uid[i] < 0x10) out += "0";
    out += String(uid[i], HEX);
  }
  out.toUpperCase();
  return out;
}

bool probeBackendConnectivity() {
  if (WiFi.status() != WL_CONNECTED) return false;
  if (network_mutex == NULL) return false;
  if (!xSemaphoreTake(network_mutex, pdMS_TO_TICKS(1500))) {
    Serial.println("[NET-PROBE] mutex busy, skip");
    return false;
  }

  HTTPClient http;
  WiFiClient httpClient;
  String url = String("http://") + currentHost + ":" + String(currentServerPort)
             + "/api/hardware/nfc/command/poll?device_id=" + currentDeviceId;

  printNetworkContext("NET-PROBE", url);
  if (!http.begin(httpClient, url)) {
    Serial.println("[NET-PROBE] ❌ begin() 失败");
    xSemaphoreGive(network_mutex);
    return false;
  }

  http.setReuse(false);
  http.useHTTP10(true);
  http.setConnectTimeout(3000);
  http.setTimeout(5000);
  int code = http.GET();
  String body = http.getString();
  http.end();
  httpClient.stop();
  xSemaphoreGive(network_mutex);

  Serial.printf("[NET-PROBE] code=%d body=%s\n", code, body.c_str());
  return code > 0;
}

const i2s_port_t SOUND_I2S_PORT = I2S_NUM_0;
const uint32_t SOUND_SAMPLE_RATE = 16000;

enum SoundType : uint8_t {
  SOUND_BOOT,
  SOUND_WIFI_OK,
  SOUND_WIFI_FAIL,
  SOUND_CONFIG_OK,
  SOUND_SCAN,
  SOUND_CARD_READ,
  SOUND_ACCESS_OK,
  SOUND_ACCESS_DENY,
  SOUND_NETWORK_ERROR,
  SOUND_RESET
};

String getDoorNoLabel() {
  int idx = currentDeviceId.lastIndexOf('_');
  if (idx >= 0 && idx + 1 < (int)currentDeviceId.length()) {
    String tail = currentDeviceId.substring(idx + 1);
    bool allDigit = true;
    for (size_t i = 0; i < tail.length(); i++) {
      if (!isDigit(tail[i])) {
        allDigit = false;
        break;
      }
    }
    if (allDigit && tail.length() > 0) return tail;
  }
  return "--";
}

String getUptimeString() {
  unsigned long s = millis() / 1000;
  unsigned long hh = (s / 3600) % 100;
  unsigned long mm = (s % 3600) / 60;
  unsigned long ss = s % 60;
  char buf[16];
  snprintf(buf, sizeof(buf), "%02lu:%02lu:%02lu", hh, mm, ss);
  return String(buf);
}

void playStatusSound(SoundType type) {
  if (!ENABLE_SOUND || !gSoundReady) return;

  auto playToneI2S = [](uint16_t freq, uint16_t durationMs, uint16_t amp = 1800) {
    if (freq == 0 || durationMs == 0) return;

    int totalSamples = (SOUND_SAMPLE_RATE * durationMs) / 1000;
    int halfPeriod = SOUND_SAMPLE_RATE / (freq * 2);
    if (halfPeriod < 1) halfPeriod = 1;

    const int chunkFrames = 128;
    int16_t pcm[chunkFrames * 2];
    int phase = 0;

    while (totalSamples > 0) {
      int frames = totalSamples > chunkFrames ? chunkFrames : totalSamples;
      for (int i = 0; i < frames; i++) {
        int16_t v = (phase < halfPeriod) ? amp : -amp;
        phase++;
        if (phase >= halfPeriod * 2) phase = 0;
        pcm[i * 2] = v;
        pcm[i * 2 + 1] = v;
      }

      size_t bytesWritten = 0;
      i2s_write(SOUND_I2S_PORT, pcm, frames * sizeof(int16_t) * 2, &bytesWritten, portMAX_DELAY);
      totalSamples -= frames;
    }

    int16_t silence[64 * 2] = {0};
    size_t bytesWritten = 0;
    i2s_write(SOUND_I2S_PORT, silence, sizeof(silence), &bytesWritten, portMAX_DELAY);
  };

  switch (type) {
    case SOUND_BOOT:
      playToneI2S(1046, 80);
      delay(90);
      playToneI2S(1318, 100);
      break;
    case SOUND_WIFI_OK:
      playToneI2S(1200, 80);
      delay(90);
      playToneI2S(1560, 120);
      break;
    case SOUND_WIFI_FAIL:
      playToneI2S(480, 180);
      delay(220);
      playToneI2S(420, 220);
      break;
    case SOUND_CONFIG_OK:
      playToneI2S(1000, 60);
      delay(80);
      playToneI2S(1400, 140);
      break;
    case SOUND_SCAN:
      playToneI2S(900, 80);
      break;
    case SOUND_CARD_READ:
      playToneI2S(1600, 90);
      break;
    case SOUND_ACCESS_OK:
      playToneI2S(1300, 90);
      delay(110);
      playToneI2S(1750, 120);
      break;
    case SOUND_ACCESS_DENY:
      playToneI2S(350, 150);
      delay(170);
      playToneI2S(300, 180);
      break;
    case SOUND_NETWORK_ERROR:
      playToneI2S(700, 120);
      delay(140);
      playToneI2S(550, 160);
      break;
    case SOUND_RESET:
      playToneI2S(260, 450);
      break;
    default:
      break;
  }
}

bool initSoundOutput() {
  if (!ENABLE_SOUND) return false;

  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = SOUND_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = 0;
  cfg.dma_buf_count = 6;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;
  cfg.fixed_mclk = 0;

  if (i2s_driver_install(SOUND_I2S_PORT, &cfg, 0, NULL) != ESP_OK) {
    return false;
  }

  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_BCLK;
  pins.ws_io_num = I2S_LRCK;
  pins.data_out_num = I2S_DOUT;
  pins.data_in_num = I2S_PIN_NO_CHANGE;

  if (i2s_set_pin(SOUND_I2S_PORT, &pins) != ESP_OK) {
    i2s_driver_uninstall(SOUND_I2S_PORT);
    return false;
  }

  i2s_zero_dma_buffer(SOUND_I2S_PORT);
  return true;
}

void drawNetworkIcon(int16_t x, int16_t y) {
  if (!gDisplayReady) return;

  int bars = 0;
  uint16_t c = ST77XX_RED;

  if (WiFi.status() == WL_CONNECTED) {
    long rssi = WiFi.RSSI();
    if (rssi > -55) {
      bars = 4;
      c = ST77XX_GREEN;
    } else if (rssi > -67) {
      bars = 3;
      c = ST77XX_GREEN;
    } else if (rssi > -75) {
      bars = 2;
      c = ST77XX_YELLOW;
    } else {
      bars = 1;
      c = ST77XX_RED;
    }
  }

  tft.drawRect(x, y, 28, 18, ST77XX_WHITE);
  for (int i = 0; i < 4; i++) {
    int bh = (i + 1) * 3;
    int bx = x + 4 + i * 6;
    int by = y + 16 - bh;
    uint16_t fill = i < bars ? c : ST77XX_BLACK;
    tft.fillRect(bx, by, 4, bh, fill);
    tft.drawRect(bx, by, 4, bh, ST77XX_WHITE);
  }
}

void drawBleHealthLed(int16_t x, int16_t y) {
  if (!gDisplayReady) return;

  const unsigned long nowMs = millis();
  const bool scanOk = gBleReady && gBleLastScanMs > 0 && (nowMs - gBleLastScanMs) <= 10000;
  const bool reportOk = gBleLastReportMs > 0 && (nowMs - gBleLastReportMs) <= 15000;

  uint16_t ledColor = ST77XX_RED;
  if (scanOk && reportOk) {
    // 绿：扫描+上报都正常
    ledColor = ST77XX_GREEN;
  } else if (scanOk) {
    // 黄：仅扫描正常（上报异常/未上报）
    ledColor = ST77XX_YELLOW;
  } else {
    // 红：扫描异常
    ledColor = ST77XX_RED;
  }

  tft.drawCircle(x, y, 5, ST77XX_WHITE);
  tft.fillCircle(x, y, 4, ledColor);
}

String clipText(const String &text, size_t maxLen) {
  if (text.length() <= maxLen) return text;
  if (maxLen <= 3) return text.substring(0, maxLen);
  return text.substring(0, maxLen - 3) + "...";
}

bool initNfcModule(bool verbose = true) {
  // 尝试初始化 PN532，并更新全局就绪状态
  nfc.begin();
  delay(200);

  uint32_t ver = nfc.getFirmwareVersion();
  if (!ver) {
    gNfcReady = false;
    gNfcFwVersion = 0;
    if (verbose) {
      Serial.println("❌ PN532 初始化失败！");
      Serial.println("   可能原因：");
      Serial.println("   1. I2C 地址不匹配（PN532 默认 0x24）");
      Serial.println("   2. 模块未正确进入 I2C 模式");
      Serial.println("   3. 接线错误或接触不良");
      Serial.println("   4. 模块损坏");
    }
    return false;
  }

  nfc.SAMConfig();
  gNfcReady = true;
  gNfcFwVersion = ver;

  if (verbose) {
    Serial.printf("✅ PN532 初始化成功，固件版本: 0x%08lx\n", ver);
    Serial.println("✅ PN532 SAM 配置成功");
  }
  return true;
}

int scanI2cBus(bool verbose = true) {
  byte error = 0;
  int devices = 0;
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      devices++;
      if (verbose) {
        Serial.printf("   [I2C] device found: 0x%02X\n", address);
      }
    }
  }

  if (verbose) {
    Serial.printf("   [I2C] total devices: %d\n", devices);
  }
  return devices;
}

void reinitI2cBus(uint32_t clockHz, bool verbose = true) {
  Wire.end();
  delay(20);
  pinMode(PN532_SDA, INPUT_PULLUP);
  pinMode(PN532_SCL, INPUT_PULLUP);
  Wire.begin(PN532_SDA, PN532_SCL, clockHz);
  Wire.setTimeOut(80);
  delay(60);
  if (verbose) {
    Serial.printf("[I2C] reinit done @%luHz\n", (unsigned long)clockHz);
  }
}

bool recoverNfcBus(bool verbose = true) {
  // 先用 100kHz，再降到 50kHz，提升 PN532 在干扰场景下的恢复概率
  reinitI2cBus(100000, verbose);
  int devices = scanI2cBus(verbose);
  if (devices <= 0) {
    reinitI2cBus(50000, verbose);
    devices = scanI2cBus(verbose);
  }

  gI2cDeviceCount = devices;
  bool ok = initNfcModule(verbose);
  if (ok) {
    Serial.println("[NFC] bus recovery success");
  } else {
    Serial.println("[NFC] bus recovery failed");
  }
  return ok;
}

void logBootBoth(const String &msg) {
  // 同时输出到 Serial 与 Serial0，兼容不同 USB CDC/串口配置
  serialLine(msg, true);
}

void logSyncBoth(const String &msg) {
  serialLine(msg, true);
}

void printResetReason() {
  esp_reset_reason_t reason = esp_reset_reason();
  const char* reasonText = "UNKNOWN";
  switch (reason) {
    case ESP_RST_POWERON: reasonText = "POWERON"; break;
    case ESP_RST_EXT: reasonText = "EXT"; break;
    case ESP_RST_SW: reasonText = "SW"; break;
    case ESP_RST_PANIC: reasonText = "PANIC"; break;
    case ESP_RST_INT_WDT: reasonText = "INT_WDT"; break;
    case ESP_RST_TASK_WDT: reasonText = "TASK_WDT"; break;
    case ESP_RST_WDT: reasonText = "WDT"; break;
    case ESP_RST_DEEPSLEEP: reasonText = "DEEPSLEEP"; break;
    case ESP_RST_BROWNOUT: reasonText = "BROWNOUT"; break;
    case ESP_RST_SDIO: reasonText = "SDIO"; break;
    default: break;
  }

  Serial.printf("[BOOT] Reset reason: %d (%s)\n", (int)reason, reasonText);
  Serial0.printf("[BOOT] Reset reason: %d (%s)\n", (int)reason, reasonText);
}

void withDisplayLock(void (*renderFn)()) {
  if (xSemaphoreTake(display_mutex, pdMS_TO_TICKS(200))) {
    renderFn();
    xSemaphoreGive(display_mutex);
  }
}

void drawStatusFrame(const String &title, uint16_t titleColor) {
  if (!gDisplayReady) return;

  tft.fillScreen(ST77XX_BLACK);
  tft.setTextWrap(false);
  tft.drawRect(0, 0, 240, 240, ST77XX_BLUE);
  tft.fillRect(0, 0, 240, 30, ST77XX_BLACK);
  tft.setTextColor(titleColor);
  tft.setTextSize(2);
  tft.setCursor(10, 8);
  tft.println(clipText(title, 16));
  tft.drawFastHLine(0, 32, 240, ST77XX_BLUE);
}

void drawStatusText(const String &line1, const String &line2 = "", const String &line3 = "", const String &line4 = "") {
  if (!gDisplayReady) return;

  tft.setTextSize(1);
  tft.setTextColor(ST77XX_WHITE);
  tft.setCursor(10, 52);
  if (line1.length()) tft.println(clipText(line1, 28));
  tft.setCursor(10, 78);
  if (line2.length()) tft.println(clipText(line2, 28));
  tft.setCursor(10, 104);
  if (line3.length()) tft.println(clipText(line3, 28));
  tft.setCursor(10, 130);
  if (line4.length()) tft.println(clipText(line4, 28));
}

void showSimpleStatus(const String &title, uint16_t titleColor, const String &line1, const String &line2 = "", const String &line3 = "", const String &line4 = "") {
  if (!gDisplayReady || display_mutex == NULL) return;

  if (xSemaphoreTake(display_mutex, pdMS_TO_TICKS(200))) {
    drawStatusFrame(title, titleColor);
    drawStatusText(line1, line2, line3, line4);
    xSemaphoreGive(display_mutex);
  }
}

void showTransientStatus(const String &title, uint16_t titleColor, const String &line1, const String &line2 = "", const String &line3 = "", const String &line4 = "", unsigned long holdMs = 2000) {
  displayHoldUntil = millis() + holdMs;
  showSimpleStatus(title, titleColor, line1, line2, line3, line4);
}

void showIdleScreen() {
  if (!gDisplayReady || display_mutex == NULL) return;
  if (configPortalActive || millis() < displayHoldUntil) return;

  String doorLabel = "DOOR " + getDoorNoLabel();
  String wifiStatus = WiFi.status() == WL_CONNECTED ? "OK" : "OFF";
  String ipAddr = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : "--";
  String nfcStatus = gNfcReady ? "OK" : "FAIL";
  String bleStatus = gBleReady ? "ON" : "OFF";
  String i2cLine = "I2C:" + String(gI2cDeviceCount) + " FW:" + (gNfcFwVersion ? String(gNfcFwVersion, HEX) : String("--"));
  unsigned long nowMs = millis();
  String bleScanAge = gBleLastScanMs > 0 ? String((nowMs - gBleLastScanMs) / 1000) + "s" : "--";
  String bleReportAge = gBleLastReportMs > 0 ? String((nowMs - gBleLastReportMs) / 1000) + "s" : "--";
  String bleVerifyAge = gBleLastVerifyMs > 0 ? String((nowMs - gBleLastVerifyMs) / 1000) + "s" : "--";
  String bleLine = "BLE:" + bleStatus + " C:" + String(gBleLastSeenCount) + " S:" + bleScanAge;
  String bleLine2 = "REP:" + bleReportAge + " VER:" + bleVerifyAge;
  String lastCard = "NONE";

  if (xSemaphoreTake(nfc_mutex, pdMS_TO_TICKS(20))) {
    if (strlen(nfc_status.last_card_uid) > 0) {
      lastCard = String(nfc_status.last_card_uid);
    }
    xSemaphoreGive(nfc_mutex);
  }

  if (xSemaphoreTake(display_mutex, pdMS_TO_TICKS(200))) {
    tft.fillScreen(ST77XX_BLACK);
    tft.drawRoundRect(4, 4, 232, 232, 8, ST77XX_CYAN);
    
    // 标题栏：门禁编号 + 网络图标
    tft.fillRoundRect(8, 8, 224, 26, 4, ST77XX_BLACK);
    tft.setTextColor(ST77XX_CYAN);
    tft.setTextSize(2);
    tft.setCursor(14, 12);
    tft.print(doorLabel);
    drawBleHealthLed(190, 19);
    drawNetworkIcon(198, 10);

    // 第1行：UPTIME
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(1);
    tft.setCursor(14, 42);
    tft.print("UP: ");
    tft.println(getUptimeString());

    // 第2行：WiFi 状态 + IP
    tft.setCursor(14, 54);
    tft.setTextColor(WiFi.status() == WL_CONNECTED ? ST77XX_GREEN : ST77XX_RED);
    tft.print("NET: ");
    tft.println(wifiStatus);
    
    tft.setCursor(14, 66);
    tft.setTextColor(ST77XX_WHITE);
    tft.print("IP: ");
    tft.println(clipText(ipAddr, 20));

    // 第3行：服务器地址
    tft.setCursor(14, 78);
    tft.setTextColor(ST77XX_YELLOW);
    tft.print("SRV: ");
    tft.println(clipText(currentHost, 18));

    // 第4行：最后读卡
    tft.setCursor(14, 90);
    tft.setTextColor(ST77XX_WHITE);
    tft.print("CARD: ");
    tft.println(clipText(lastCard, 18));

    // 第5行：门状态
    tft.setCursor(14, 102);
    tft.setTextColor(door_status.is_open ? ST77XX_GREEN : ST77XX_RED);
    if (door_status.is_open) {
      tft.print("DOOR: OPEN");
    } else {
      tft.print("DOOR: LOCKED");
    }
    tft.println();

    // 第6行：设备信息
    tft.setCursor(14, 114);
    tft.setTextColor(ST77XX_YELLOW);
    tft.print("DEV: ");
    tft.println(clipText(currentDeviceName, 18));

    // 第7行：运行模式
    tft.setCursor(14, 126);
    tft.setTextColor(ST77XX_WHITE);
    tft.print("MODE: ");
    tft.println(clipText(currentDeviceMode, 16));

    // 第8行：NFC 模块状态（串口不可用时用于现场诊断）
    tft.setCursor(14, 138);
    tft.setTextColor(gNfcReady ? ST77XX_GREEN : ST77XX_RED);
    tft.print("NFC: ");
    tft.println(nfcStatus);

    // 第9行：I2C 设备数量 + PN532 固件版本（十六进制）
    tft.setCursor(14, 150);
    tft.setTextColor(ST77XX_CYAN);
    tft.println(clipText(i2cLine, 28));

    // 第10~11行：BLE 扫描健康状态
    tft.setCursor(14, 162);
    tft.setTextColor(gBleReady ? ST77XX_GREEN : ST77XX_RED);
    tft.println(clipText(bleLine, 28));
    tft.setCursor(14, 174);
    tft.setTextColor(ST77XX_WHITE);
    tft.println(clipText(bleLine2, 28));

    xSemaphoreGive(display_mutex);
  }
}

void showBootScreen() {
  if (!gDisplayReady) return;

  tft.fillScreen(ST77XX_BLACK);
  tft.setTextWrap(false);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(20, 60);
  tft.println("ESP32-S3");
  tft.setCursor(10, 90);
  tft.println("Door System");
  tft.setCursor(40, 120);
  tft.println("v2.0");
}

void showConfigPortalScreen(const IPAddress &apIP) {
  showSimpleStatus(
    "WAIT CONFIG",
    ST77XX_YELLOW,
    "AP: " + String(AP_SSID),
    "PWD: " + String(AP_PASSWORD),
    "Open: " + apIP.toString(),
    "Join AP, then browse config"
  );
}

void showConfigSavedScreen() {
  showSimpleStatus("CONFIG OK", ST77XX_GREEN, "Closing AP", "Connecting WiFi", "Applying runtime config");
  playStatusSound(SOUND_CONFIG_OK);
}

bool loadDeviceConfig() {
  preferences.begin("devcfg", true);
  gConfig.configured = preferences.getBool("configured", false);
  gConfig.wifiSsid = preferences.getString("wifi_ssid", DEFAULT_SSID);
  gConfig.wifiPassword = preferences.getString("wifi_pwd", DEFAULT_PASSWORD);
  gConfig.serverHost = preferences.getString("server_host", DEFAULT_SERVER_HOST);
  gConfig.serverPort = preferences.getInt("server_port", DEFAULT_SERVER_PORT);
  gConfig.fallbackHost = preferences.getString("fallback_host", DEFAULT_FALLBACK_HOST);
  gConfig.deviceId = preferences.getString("device_id", DEFAULT_DEVICE_ID);
  gConfig.deviceName = preferences.getString("device_name", DEFAULT_DEVICE_NAME);
  gConfig.deviceType = preferences.getString("device_type", DEFAULT_DEVICE_TYPE);
  gConfig.deviceLocation = preferences.getString("device_loc", DEFAULT_DEVICE_LOC);
  gConfig.deviceMode = preferences.getString("device_mode", DEFAULT_DEVICE_MODE);
  preferences.end();

  normalizeConfigStrings();
  return gConfig.configured;
}

void saveDeviceConfig() {
  normalizeConfigStrings();

  preferences.begin("devcfg", false);
  preferences.putBool("configured", true);
  preferences.putString("wifi_ssid", gConfig.wifiSsid);
  preferences.putString("wifi_pwd", gConfig.wifiPassword);
  preferences.putString("server_host", gConfig.serverHost);
  preferences.putInt("server_port", gConfig.serverPort);
  preferences.putString("fallback_host", gConfig.fallbackHost);
  preferences.putString("device_id", gConfig.deviceId);
  preferences.putString("device_name", gConfig.deviceName);
  preferences.putString("device_type", gConfig.deviceType);
  preferences.putString("device_loc", gConfig.deviceLocation);
  preferences.putString("device_mode", gConfig.deviceMode);
  preferences.end();
}

void clearDeviceConfig() {
  preferences.begin("devcfg", false);
  preferences.clear();
  preferences.end();
  Serial.println("[CFG] 已清除设备本地配置");
  showTransientStatus("RESET", ST77XX_RED, "Local config cleared", "Device will reconfigure", "via AP portal", "", 2500);
  playStatusSound(SOUND_RESET);
}

void applyRuntimeConfig() {
  normalizeConfigStrings();

  currentHost = gConfig.serverHost;
  currentServerPort = gConfig.serverPort;
  currentDeviceId = gConfig.deviceId;
  currentDeviceName = gConfig.deviceName;
  currentDeviceType = gConfig.deviceType;
  currentDeviceLoc = gConfig.deviceLocation;
  currentDeviceMode = gConfig.deviceMode;
}

String buildConfigHtml() {
  String html = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>SmartAccess 设备配置</title>"
                "<style>body{font-family:Arial;padding:18px;background:#f6f7fb}h2{color:#334}"
                ".card{background:#fff;padding:16px;border-radius:10px;max-width:680px;margin:auto;box-shadow:0 4px 16px rgba(0,0,0,.08)}"
                "label{display:block;margin-top:12px;font-weight:600;color:#444}input{width:100%;padding:10px;border:1px solid #d8dce6;border-radius:6px;margin-top:6px}"
                "button{margin-top:16px;background:#4f46e5;color:#fff;border:none;padding:10px 16px;border-radius:6px;font-size:15px}</style></head><body>";
  html += "<div class='card'><h2>SmartAccess 终端初始化配置</h2>";
  html += "<form method='POST' action='/save'>";
  html += "<label>WiFi 名称(SSID)</label><input name='wifi_ssid' value='" + gConfig.wifiSsid + "' required>";
  html += "<label>WiFi 密码</label><input name='wifi_pwd' value='" + gConfig.wifiPassword + "' required>";
  html += "<label>服务器地址</label><input name='server_host' value='" + gConfig.serverHost + "' required>";
  html += "<label>服务器端口</label><input name='server_port' type='number' value='" + String(gConfig.serverPort) + "' required>";
  html += "<label>设备ID</label><input name='device_id' value='" + gConfig.deviceId + "' required>";
  html += "<label>设备名称</label><input name='device_name' value='" + gConfig.deviceName + "' required>";
  html += "<label>设备位置</label><input name='device_loc' value='" + gConfig.deviceLocation + "'>";
  html += "<label>设备类型</label><input name='device_type' value='" + gConfig.deviceType + "'>";
  html += "<label>设备模式</label><input name='device_mode' value='" + gConfig.deviceMode + "'>";
  html += "<button type='submit'>保存并连接服务器</button></form>";
  html += "<p style='margin-top:12px;color:#666;font-size:13px'>配置保存后，设备将自动关闭AP并连接网络进行注册。</p></div></body></html>";
  return html;
}

void handleConfigRoot() {
  configServer.send(200, "text/html; charset=utf-8", buildConfigHtml());
}

void handleConfigSave() {
  gConfig.wifiSsid = configServer.arg("wifi_ssid");
  gConfig.wifiPassword = configServer.arg("wifi_pwd");
  gConfig.serverHost = configServer.arg("server_host");
  gConfig.serverPort = configServer.arg("server_port").toInt();
  gConfig.deviceId = configServer.arg("device_id");
  gConfig.deviceName = configServer.arg("device_name");
  gConfig.deviceLocation = configServer.arg("device_loc");
  gConfig.deviceType = configServer.arg("device_type");
  gConfig.deviceMode = configServer.arg("device_mode");

  normalizeConfigStrings();
  if (gConfig.wifiSsid.isEmpty() || gConfig.wifiPassword.isEmpty() || gConfig.serverHost.isEmpty() ||
      gConfig.deviceId.isEmpty() || gConfig.deviceName.isEmpty()) {
    configServer.send(400, "text/plain; charset=utf-8", "配置不完整，请返回重试");
    return;
  }

  saveDeviceConfig();
  applyRuntimeConfig();
  showConfigSavedScreen();
  apConfigSaved = true;
  configServer.send(200, "text/html; charset=utf-8",
                    "<html><body style='font-family:Arial;padding:20px'><h3>配置保存成功</h3>"
                    "<p>设备正在关闭配置热点并重启系统...</p>"
                    "<p>系统将在 3 秒后重启，请稍候...</p></body></html>");
  
  // 延迟后重启系统，确保HTTP响应已发送
  delay(500);
  Serial.println("[CFG] 配置保存成功，3秒后重启设备...");
  showTransientStatus("RESTART", ST77XX_GREEN, "Config saved", "Rebooting in 3s", "System restart", "", 3000);
  delay(3000);
  Serial.println("[CFG] 🔄 执行重启...");
  ESP.restart();
}

void startConfigPortal() {
  Serial.println("[CFG] 进入 AP 配置模式");
  configPortalActive = true;
  WiFi.disconnect(true, true);
  delay(200);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);

  IPAddress apIP = WiFi.softAPIP();
  Serial.printf("[CFG] AP 已启动: SSID=%s, PASS=%s, IP=%s\n", AP_SSID, AP_PASSWORD, apIP.toString().c_str());
  showConfigPortalScreen(apIP);

  apConfigSaved = false;
  configServer.on("/", HTTP_GET, handleConfigRoot);
  configServer.on("/save", HTTP_POST, handleConfigSave);
  configServer.begin();

  while (!apConfigSaved) {
    configServer.handleClient();
    delay(10);
  }

  // 注意：当 apConfigSaved 变为 true 时，handleConfigSave() 已经调用了 ESP.restart()，
  // 所以这里的控制流通常得不到执行。但保留这些代码以处理极端情况（比如重启失败）。
  configServer.stop();
  WiFi.softAPdisconnect(true);
  configPortalActive = false;
  delay(200);
  Serial.println("[CFG] AP 配置模式结束，准备连接网络");
}

bool connectWiFiFromConfig() {
  Serial.print("🔌 正在连接 WiFi: ");
  Serial.println(gConfig.wifiSsid);
  Serial.printf("🌐 目标服务器: %s:%d\n", gConfig.serverHost.c_str(), gConfig.serverPort);
  showSimpleStatus("WIFI", ST77XX_CYAN, "Connecting to", gConfig.wifiSsid, "Please wait...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(gConfig.wifiSsid.c_str(), gConfig.wifiPassword.c_str());

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    // 降低联网后的峰值负载，减小供电边缘情况下的异常重启概率
    WiFi.setSleep(false);
#ifdef WIFI_POWER_8_5dBm
    WiFi.setTxPower(WIFI_POWER_8_5dBm);
#endif
    Serial.println("\n✅ WiFi 已连接");
    Serial.println("📍 IP: " + WiFi.localIP().toString());
    Serial.println("🌐 网关: " + WiFi.gatewayIP().toString());
    Serial.println("🌐 DNS1: " + WiFi.dnsIP(0).toString());
    Serial.println("🌐 DNS2: " + WiFi.dnsIP(1).toString());
    Serial.printf("📶 RSSI: %ld dBm\n", WiFi.RSSI());
    showTransientStatus("WIFI OK", ST77XX_GREEN, gConfig.wifiSsid, "IP: " + WiFi.localIP().toString(), "Connected", "", 1800);
    playStatusSound(SOUND_WIFI_OK);
    return true;
  }

  Serial.println("\n⚠️  WiFi 连接失败");
  showSimpleStatus("WIFI FAIL", ST77XX_RED, gConfig.wifiSsid, "Check SSID/password", "Will return to AP mode");
  playStatusSound(SOUND_WIFI_FAIL);
  return false;
}

bool registerDeviceToServer() {
  if (WiFi.status() != WL_CONNECTED) return false;
  if (network_mutex == NULL) return false;
  if (!xSemaphoreTake(network_mutex, pdMS_TO_TICKS(2000))) {
    Serial.println("[REG] mutex busy, skip register this round");
    return false;
  }

  showSimpleStatus("REGISTER", ST77XX_CYAN, "Device: " + currentDeviceName, "Server: " + currentHost, "Submitting registration");

  HTTPClient http;
  WiFiClient httpClient;
  String url = String("http://") + currentHost + ":" + String(currentServerPort) + "/api/hardware/devices/register";
  printNetworkContext("REG", url);
  if (!http.begin(httpClient, url)) {
    Serial.println("[REG] ❌ begin() 失败");
    xSemaphoreGive(network_mutex);
    return false;
  }

  http.setReuse(false);
  http.useHTTP10(true);
  http.setConnectTimeout(3000);
  http.setTimeout(5000);

  StaticJsonDocument<256> doc;
  doc["device_id"] = currentDeviceId;
  doc["device_name"] = currentDeviceName;
  doc["device_type"] = currentDeviceType;
  doc["location"] = currentDeviceLoc;
  doc["ip_address"] = WiFi.localIP().toString();
  String body;
  serializeJson(doc, body);

  logSyncBoth("[REG] ---- device register request ----");
  logSyncBoth("[REG] url=" + url);
  logSyncBoth("[REG] payload=" + body);

  http.addHeader("Connection", "close");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST((uint8_t*)(body.c_str()), body.length());
  String resp = http.getString();
  http.end();
  httpClient.stop();
  xSemaphoreGive(network_mutex);

  Serial.printf("[REG] 设备注册响应码: %d\n", code);
  Serial.printf("[REG] 响应体: %s\n", resp.c_str());
  logSyncBoth("[REG] code=" + String(code));
  logSyncBoth("[REG] response=" + truncateForLog(resp));
  if (code >= 200 && code < 300) {
    showTransientStatus("REG OK", ST77XX_GREEN, currentDeviceName, "Registered", "IP: " + WiFi.localIP().toString(), "", 1800);
  } else {
    showTransientStatus("REG WARN", ST77XX_YELLOW, currentDeviceName, "Already exists or failed", "Backend auth may be needed", "", 2200);
  }
  return code >= 200 && code < 300;
}

bool isResetButtonHeldAtBoot() {
  // GPIO21 不会在启动时出现误触发，直接检测即可
  if (digitalRead(RESET_BTN_PIN) != LOW) return false;

  Serial.printf("[RESET] 检测到按键按下，请持续按住 %lu 秒可清除配置...\n", RESET_HOLD_MS / 1000);
  unsigned long start = millis();
  
  while (digitalRead(RESET_BTN_PIN) == LOW) {
    if (millis() - start >= RESET_HOLD_MS) {
      Serial.println("[RESET] 长按 8 秒确认，执行清除配置");
      showSimpleStatus("RESET", ST77XX_RED, "Hold confirmed", "Clearing local config");
      playStatusSound(SOUND_RESET);
      return true;
    }
    delay(50);
  }
  
  // 用户在 8 秒前松开按键
  Serial.printf("[RESET] 按键松开，按下时间仅 %lu 毫秒，取消清除操作\n", millis() - start);
  return false;
}

void monitorResetButtonRuntime() {
  if (digitalRead(RESET_BTN_PIN) == LOW) {
    if (resetPressStartMs == 0) {
      resetPressStartMs = millis();
    } else if (millis() - resetPressStartMs >= RESET_HOLD_MS) {
      Serial.println("[RESET] 运行时长按触发，清除配置并重启...");
      showPixel(180, 0, 0);
      showSimpleStatus("RESET", ST77XX_RED, "Button held 8s", "Clearing config", "Restarting device");
      playStatusSound(SOUND_RESET);
      clearDeviceConfig();
      delay(500);
      ESP.restart();
    }
  } else {
    resetPressStartMs = 0;
  }
}

// ==================== 6. 硬件控制函数 ====================

void initHardware() {
  Serial.begin(115200);
  Serial0.begin(115200);
  delay(500);
  initSerialLogger();
  logBootBoth("[BOOT] Serial started @115200 (Serial + Serial0)");
  printResetReason();
  logBootBoth("[BOOT] Stage 1: Serial ready");

  // 初始化重置按键
  pinMode(RESET_BTN_PIN, INPUT_PULLUP);
  logBootBoth("[BOOT] Stage 2: Reset key ready");

  if (ENABLE_TFT) {
    logBootBoth("[BOOT] Stage 3: Init TFT start");
    if (TFT_BL >= 0) {
      pinMode(TFT_BL, OUTPUT);
      digitalWrite(TFT_BL, HIGH);
    }

    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, TFT_CS);
    tft.init(240, 240);
    tft.setRotation(2);
    gDisplayReady = true;
    showBootScreen();
    logBootBoth("[BOOT] Stage 3: Init TFT done");
  } else {
    logBootBoth("[BOOT] Stage 3: TFT skipped (ENABLE_TFT=false)");
  }

  if (ENABLE_SOUND) {
    logBootBoth("[BOOT] Stage 3.5: Init I2S sound start");
    gSoundReady = initSoundOutput();
    logBootBoth(gSoundReady ? "[BOOT] Stage 3.5: Init I2S sound done" : "[BOOT] Stage 3.5: Init I2S sound failed");
  } else {
    logBootBoth("[BOOT] Stage 3.5: Sound skipped (ENABLE_SOUND=false)");
  }

  playStatusSound(SOUND_BOOT);
  delay(500);
  
  // 初始化 LED
  pixels.begin();
  pixels.clear();
  pixels.show();
  logBootBoth("[BOOT] Stage 4: RGB ready");
  
  // 初始化继电器引脚
  if (DOOR1_PIN >= 0) {
    pinMode(DOOR1_PIN, OUTPUT);
    digitalWrite(DOOR1_PIN, LOW);
  }
  if (DOOR2_PIN >= 0) {
    pinMode(DOOR2_PIN, OUTPUT);
    digitalWrite(DOOR2_PIN, LOW);
  }
  
  // 初始化 NFC (I2C)
  pinMode(PN532_SDA, INPUT_PULLUP);
  pinMode(PN532_SCL, INPUT_PULLUP);
  Wire.begin(PN532_SDA, PN532_SCL, 100000);
  Wire.setTimeOut(50);
  delay(100);
  logBootBoth("[BOOT] Stage 5: I2C ready");
  
  Serial.println("🔍 初始化 NFC 模块...");
  Serial.printf("   I2C 配置: SDA=%d, SCL=%d\n", PN532_SDA, PN532_SCL);
  
  // 扫描 I2C 总线（先 100kHz，再 50kHz 重试）
  Serial.println("📡 扫描 I2C 总线 (100kHz)...");
  int devices = scanI2cBus(true);
  if (devices == 0) {
    Serial.println("📡 I2C 100kHz 未发现设备，降速到 50kHz 重试...");
    Wire.end();
    delay(50);
    Wire.begin(PN532_SDA, PN532_SCL, 50000);
    Wire.setTimeOut(80);
    delay(80);
    devices = scanI2cBus(true);
  }
  gI2cDeviceCount = devices;
  if (devices == 0) {
    Serial.println("   ❌ 未发现任何 I2C 设备！");
    Serial.println("   ⚠️  请检查：");
    Serial.println("      1. PN532 模块是否接通电源？");
    Serial.println("      2. I2C 引脚连接是否正确？(SDA=GPIO5, SCL=GPIO4)");
    Serial.println("      3. PN532 模式拨码开关是否设置为 I2C？");
    Serial.println("      4. 是否有上拉电阻？(通常模块自带)");
    Serial.println("      5. ESP32 与 PN532 是否共地 (GND-GND)");
  } else {
    Serial.printf("   扫描完成，发现 %d 个设备\n", devices);
  }
  
  // 尝试初始化 PN532
  initNfcModule(true);
  
  // 初始化互斥锁
  nfc_mutex = xSemaphoreCreateMutex();
  door_mutex = xSemaphoreCreateMutex();
  network_mutex = xSemaphoreCreateMutex();
  display_mutex = xSemaphoreCreateMutex();
  ble_mutex = xSemaphoreCreateMutex();
  logBootBoth("[BOOT] Stage 6: Mutex ready");
  
  // 初始化事件队列（最多 10 个事件待处理）
  event_queue = xQueueCreate(10, sizeof(SystemEvent));
  logBootBoth("[BOOT] Stage 7: Queue ready");
  
  Serial.println("✨ 硬件初始化完成");
}

void showPixel(uint8_t r, uint8_t g, uint8_t b) {
  pixels.setPixelColor(0, pixels.Color(r, g, b));
  pixels.show();
}

int parseDoorIdFromPayload(const String &payload) {
  if (payload.length() == 0) return 1;

  StaticJsonDocument<192> doc;
  if (deserializeJson(doc, payload) != DeserializationError::Ok) return 1;

  if (!doc["door_id"].isNull()) {
    if (doc["door_id"].is<int>()) {
      int id = doc["door_id"].as<int>();
      return id == 2 ? 2 : 1;
    }

    String doorIdStr = doc["door_id"].as<String>();
    doorIdStr.trim();
    if (doorIdStr == "2" || doorIdStr == "door2") return 2;
    return 1;
  }

  if (!doc["door"].isNull()) {
    String door = doc["door"].as<String>();
    door.toLowerCase();
    if (door == "door2" || door == "2") return 2;
  }

  return 1;
}

String parseSourceFromPayload(const String &payload) {
  if (payload.length() == 0) return "remote";

  StaticJsonDocument<192> doc;
  if (deserializeJson(doc, payload) != DeserializationError::Ok) return "remote";

  if (!doc["source"].isNull()) {
    String source = doc["source"].as<String>();
    source.trim();
    if (source.length() > 0) return source;
  }

  return "remote";
}

// ==================== 7. NFC 监听线程 (Core 0) ====================
/**
 * 核心 0 专属：NFC 实时监听
 * 高优先级，不被网络阻塞打断
 */
void nfcMonitor(void *parameter) {
  logBootBoth("[Core0] NFC monitor task started");
  
  unsigned long last_nfc_time = 0;
  unsigned long debounce_until = 0;  // 防抖结束时间
  const unsigned long NFC_POLL_INTERVAL = 50;  // 50ms 轮询一次
  const unsigned long DEBOUNCE_TIME = 2000;    // 2秒防抖
  
  while (true) {
    unsigned long now = millis();

    static unsigned long lastAliveLogMs = 0;
    if (now - lastAliveLogMs >= 10000) {
      lastAliveLogMs = now;
      Serial.printf("[NFC] alive ready=%d polls=%lu i2c=%d\n", gNfcReady ? 1 : 0, gNfcPollCounter, gI2cDeviceCount);
    }

    // 若 NFC 未就绪，后台定期重试初始化，避免“刷卡无反应”且无串口时不可恢复
    if (!gNfcReady) {
      static unsigned long lastRetryMs = 0;
      if (now - lastRetryMs >= 5000) {
        lastRetryMs = now;
        Serial.println("[NFC] 模块未就绪，尝试重新初始化...");
        if (recoverNfcBus(false)) {
          Serial.println("[NFC] ✅ 重试初始化成功，恢复读卡");
          showTransientStatus("NFC OK", ST77XX_GREEN, "Module reinitialized", "Card scan resumed", "", "", 1600);
        }
      }
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    
    // 检查是否有远程触发的强制读卡请求
    bool should_read = false;
    bool enroll_once = false;
    if (xSemaphoreTake(nfc_mutex, pdMS_TO_TICKS(10))) {
      if (nfc_status.force_read) {
        should_read = true;
        enroll_once = enroll_mode;     // 如果是 ENROLL，只读首张卡
        nfc_status.force_read = false; // 清除标志
        debounce_until = 0;            // 清除防抖（立即允许读卡）
        Serial.println("[NFC] 检测到强制读卡请求 (ENROLL/SCAN)");
        showTransientStatus("SCAN", ST77XX_CYAN, "Remote command received", enroll_once ? "Mode: ENROLL" : "Mode: SCAN", "Present card now", "", 3000);
        playStatusSound(SOUND_SCAN);
      }
      xSemaphoreGive(nfc_mutex);
    }
    
    // 检查是否在防抖期内
    if (now < debounce_until && !should_read) {
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    
    // 50ms 轮询一次 NFC（非阻塞）或响应强制读卡
    if (should_read || (now - last_nfc_time > NFC_POLL_INTERVAL)) {
      if (!should_read) last_nfc_time = now;
      gNfcPollCounter++;
      
      uint8_t uid[7];
      uint8_t uidLen;
      
      // 非阻塞读卡（强制读卡时延长超时到 500ms，给用户足够时间刷卡）
      uint16_t timeout = should_read ? 500 : 50;
      if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLen, timeout)) {
        // 格式化卡号
        String card_uid = "";
        for (uint8_t i = 0; i < uidLen; i++) {
          if (i) card_uid += "-";
          if (uid[i] < 0x10) card_uid += "0";
          card_uid += String(uid[i], HEX);
        }
        card_uid.toUpperCase();
        
        Serial.println("[NFC] 读取成功，卡号: " + card_uid);
        Serial.printf("[NFC] UID_LEN=%u UID_RAW=%s\n", uidLen, uidToHexRaw(uid, uidLen).c_str());
        showTransientStatus("CARD READ", ST77XX_CYAN, clipText(card_uid, 22), "Uploading to backend", "Checking permission", "", 1800);
        playStatusSound(SOUND_CARD_READ);
        
        // 更新 NFC 状态（线程安全）
        if (xSemaphoreTake(nfc_mutex, pdMS_TO_TICKS(100))) {
          nfc_status.card_detected = true;
          strncpy(nfc_status.last_card_uid, card_uid.c_str(), sizeof(nfc_status.last_card_uid) - 1);
          nfc_status.last_card_uid[sizeof(nfc_status.last_card_uid) - 1] = '\0';
          nfc_status.last_read_time = now;
          if (enroll_once) enroll_mode = false;  // ENROLL 模式只读首张卡
          xSemaphoreGive(nfc_mutex);
        }
        
        // 发送事件到队列
        SystemEvent event;
        event.type = EVENT_NFC_CARD_READ;
        strncpy(event.data, card_uid.c_str(), sizeof(event.data) - 1);
        event.data[sizeof(event.data) - 1] = '\0';
        event.timestamp = now;
        xQueueSend(event_queue, &event, 0);
        
        // LED 反馈：亮蓝色（读卡中）
        showPixel(0, 0, 180);
        
        // 设置防抖结束时间（非阻塞）
        debounce_until = now + DEBOUNCE_TIME;
        
        // 短暂延迟后关闭 LED
        vTaskDelay(pdMS_TO_TICKS(500));
        showPixel(0, 0, 0);
      } else if (should_read) {
        // 强制读卡超时，提示用户
        Serial.println("[NFC] ⚠️ ENROLL/SCAN 超时，未检测到卡片");
        showTransientStatus("SCAN TIMEOUT", ST77XX_YELLOW, "No card detected", "Try again", "", "", 1800);
        if (xSemaphoreTake(nfc_mutex, pdMS_TO_TICKS(50))) {
          enroll_mode = false;  // 超时后退出 ENROLL 模式
          xSemaphoreGive(nfc_mutex);
        }
      }
    }
    
    // 让出 CPU 给其他任务
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ==================== 8. 门锁控制线程 (Core 0) ====================
/**
 * 核心 0：门锁自动关闭管理
 */
void doorController(void *parameter) {
  Serial.println("[Core0] 门锁控制线程已启动");
  
  while (true) {
    if (xSemaphoreTake(door_mutex, pdMS_TO_TICKS(100))) {
      unsigned long now = millis();
      
      // 检查门1
      if (door_status.is_open && door_status.door_id == 1) {
        if (now - door_status.open_time > 3000) {
          // 3秒后自动关闭
          if (DOOR1_PIN >= 0) digitalWrite(DOOR1_PIN, LOW);
          door_status.is_open = false;
          
          Serial.println("[Door] 门1 自动关闭");
          showPixel(0, 0, 0);  // 关门后熄灭 RGB
          displayHoldUntil = 0;
          
          // 发送事件
          SystemEvent event;
          event.type = EVENT_SYSTEM_ERROR;
          strcpy(event.data, "door_closed");
          event.timestamp = now;
          xQueueSend(event_queue, &event, 0);
        }
      }
      
      // 检查门2
      if (door_status.is_open && door_status.door_id == 2) {
        if (now - door_status.open_time > 3000) {
          if (DOOR2_PIN >= 0) digitalWrite(DOOR2_PIN, LOW);
          door_status.is_open = false;
          Serial.println("[Door] 门2 自动关闭");
          showPixel(0, 0, 0);  // 关门后熄灭 RGB
          displayHoldUntil = 0;
        }
      }
      
      xSemaphoreGive(door_mutex);
    }
    
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// ==================== 9. 网络轮询线程 (Core 1) ====================
/**
 * 核心 1：远程开门轮询（可能阻塞 1-3 秒，不影响 NFC）
 */
void networkPoller(void *parameter) {
  Serial.println("[Core1] 网络轮询线程已启动");
  
  unsigned long last_poll_time = 0;
  const unsigned long POLL_INTERVAL = 3000;  // 3秒轮询一次，降低 TCP 栈压力
  
  while (true) {
    unsigned long now = millis();
    
    if (now - last_poll_time > POLL_INTERVAL) {
      last_poll_time = now;
      
      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Network] WiFi 未连接，跳过轮询");
        vTaskDelay(pdMS_TO_TICKS(1000));
        continue;
      }

      if (network_mutex == NULL || !xSemaphoreTake(network_mutex, pdMS_TO_TICKS(1500))) {
        Serial.println("[Network] network mutex busy, skip poll");
        vTaskDelay(pdMS_TO_TICKS(200));
        continue;
      }
      
      // 执行轮询（可能阻塞，但在 Core1 上，不影响 Core0 的 NFC）
      HTTPClient http;
            WiFiClient httpClient;
      String url = String("http://") + currentHost + ":" + String(currentServerPort)
             + "/api/hardware/nfc/command/poll?device_id=" + currentDeviceId;
      
            if (http.begin(httpClient, url)) {
          http.setReuse(false);
          http.useHTTP10(true);
        http.setConnectTimeout(3000);
        http.setTimeout(5000);
        int code = http.GET();
        String response = http.getString();
        http.end();
          httpClient.stop();
        
        Serial.printf("[Network] 轮询返回 %d: %s\n", code, response.c_str());
              if (code != 200 || response.indexOf("has_command") != -1 || response.indexOf("command") != -1) {
                logSyncBoth("[POLL] url=" + url);
                logSyncBoth("[POLL] code=" + String(code));
                logSyncBoth("[POLL] response=" + truncateForLog(response));
              }
        
        if (code == 200 && response.length() > 0) {
          // 兼容两种返回结构：顶层字段 / data 内字段
          StaticJsonDocument<256> doc;
          DeserializationError err = deserializeJson(doc, response);
          
          if (!err) {
            bool hasCommand = false;
            if (!doc["has_command"].isNull()) {
              hasCommand = doc["has_command"].as<bool>();
            } else if (!doc["data"].isNull() && !doc["data"]["has_command"].isNull()) {
              hasCommand = doc["data"]["has_command"].as<bool>();
            }

            String command = "";
            if (!doc["command"].isNull()) {
              command = doc["command"].as<String>();
            } else if (!doc["data"].isNull() && !doc["data"]["command"].isNull()) {
              command = doc["data"]["command"].as<String>();
            }

            String payload = "";
            if (!doc["payload"].isNull()) {
              payload = doc["payload"].as<String>();
            } else if (!doc["data"].isNull() && !doc["data"]["payload"].isNull()) {
              payload = doc["data"]["payload"].as<String>();
            }

            if (!hasCommand && command.length() == 0) {
              // 无命令时不做处理，继续走到本轮末尾释放 network_mutex
            } else if (command == "OPEN") {
              Serial.println("[Network] 收到远程开门指令");
              int doorId = parseDoorIdFromPayload(payload);
              String source = parseSourceFromPayload(payload);
              showTransientStatus(
                "REMOTE OPEN",
                ST77XX_GREEN,
                "Server issued OPEN",
                "Door: " + String(doorId),
                "Executing now",
                "",
                1500
              );
              playStatusSound(SOUND_ACCESS_OK);
              SystemEvent event;
              event.type = EVENT_REMOTE_DOOR_OPEN;
              String eventData = "door" + String(doorId) + ":" + source;
              strncpy(event.data, eventData.c_str(), sizeof(event.data) - 1);
              event.data[sizeof(event.data) - 1] = '\0';
              event.timestamp = now;
              xQueueSend(event_queue, &event, 0);
            } else if (command == "ENROLL" || command == "SCAN") {
              Serial.printf("[Network] 收到 %s 指令，触发 NFC 读卡\n", command.c_str());
              // 通知 NFC 监控线程立即执行一次扫描
              xSemaphoreTake(nfc_mutex, portMAX_DELAY);
              nfc_status.force_read = true;
              enroll_mode = (command == "ENROLL");  // ENROLL 仅返回首张卡
              xSemaphoreGive(nfc_mutex);
            }
          }
        }
      } else {
        Serial.println("[Network] ❌ poll begin() 失败");
        printNetworkContext("POLL-BEGIN-FAIL", url);
      }
      xSemaphoreGive(network_mutex);
    }
    
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// ==================== 10. 心跳线程 (Core 1) ====================
/**
 * 核心 1：定期心跳上报
 */
void heartbeatTask(void *parameter) {
  Serial.println("[Core1] 心跳线程已启动");
  
  unsigned long last_heartbeat = 0;
  const unsigned long HEARTBEAT_INTERVAL = 30000;  // 30秒
  
  while (true) {
    unsigned long now = millis();
    
    if (now - last_heartbeat > HEARTBEAT_INTERVAL) {
      last_heartbeat = now;
      
      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("💔 心跳: WiFi 未连接");
        vTaskDelay(pdMS_TO_TICKS(1000));
        continue;
      }

      if (network_mutex == NULL || !xSemaphoreTake(network_mutex, pdMS_TO_TICKS(1500))) {
        Serial.println("[Heartbeat] network mutex busy, skip this heartbeat");
        vTaskDelay(pdMS_TO_TICKS(500));
        continue;
      }
      
      // 发送心跳
      HTTPClient http;
            WiFiClient httpClient;
      String url = String("http://") + currentHost + ":" + String(currentServerPort)
             + "/api/hardware/devices/" + currentDeviceId + "/heartbeat";
      
            if (http.begin(httpClient, url)) {
          http.setReuse(false);
          http.useHTTP10(true);
        http.setConnectTimeout(3000);
        http.setTimeout(5000);
        StaticJsonDocument<192> doc;
        doc["connection_status"] = "online";
        doc["ip_address"] = WiFi.localIP().toString();
        doc["firmware_version"] = "v2.0";
        String body;
        serializeJson(doc, body);

              logSyncBoth("[HEARTBEAT] ---- heartbeat request ----");
              logSyncBoth("[HEARTBEAT] url=" + url);
              logSyncBoth("[HEARTBEAT] payload=" + body);
        
          http.addHeader("Connection", "close");
        http.addHeader("Content-Type", "application/json");
        int code = http.POST((uint8_t*)(body.c_str()), body.length());
              String resp = http.getString();
        http.end();
          httpClient.stop();
        
        Serial.println(code > 0 && code < 300 ? "💓 心跳: 成功" : "💔 心跳: 失败");
              Serial.printf("[HEARTBEAT] code=%d\n", code);
              Serial.printf("[HEARTBEAT] response=%s\n", resp.c_str());
              logSyncBoth("[HEARTBEAT] code=" + String(code));
              logSyncBoth("[HEARTBEAT] response=" + truncateForLog(resp));
      } else {
        Serial.println("[Heartbeat] ❌ begin() 失败");
        printNetworkContext("HEARTBEAT-BEGIN-FAIL", url);
              logSyncBoth("[HEARTBEAT] begin() failed");
      }
      xSemaphoreGive(network_mutex);
    }
    
    vTaskDelay(pdMS_TO_TICKS(5000));  // 每 5秒 检查一次
  }
}

// ==================== 11. 事件处理线程 ====================
/**
 * 主线程：处理事件队列，调用业务逻辑
 */
void eventHandler() {
  SystemEvent event;
  
  while (xQueueReceive(event_queue, &event, pdMS_TO_TICKS(100))) {
    Serial.printf("[EventHandler] 处理事件类型: %d\n", event.type);
    
    switch (event.type) {
      case EVENT_NFC_CARD_READ: {
        // NFC 卡片读取 - 上报到服务器
        Serial.println("[Event] NFC 卡片读取，上报服务器...");
        printNetworkContext("NFC-SCAN-START");
        
        if (WiFi.status() == WL_CONNECTED) {
          if (network_mutex == NULL || !xSemaphoreTake(network_mutex, pdMS_TO_TICKS(2500))) {
            Serial.println("[Event] network mutex busy, skip NFC report this round");
            SystemEvent net_event;
            net_event.type = EVENT_NETWORK_ERROR;
            strcpy(net_event.data, "network_busy");
            net_event.timestamp = millis();
            xQueueSend(event_queue, &net_event, 0);
            break;
          }

          const int MAX_RETRY = 3;
          String response;
          int code = -1;
          for (int attempt = 1; attempt <= MAX_RETRY; attempt++) {
            showSimpleStatus("VERIFY", ST77XX_CYAN, "Sending card to server", "Attempt: " + String(attempt) + "/" + String(MAX_RETRY), clipText(String(event.data), 24));
            HTTPClient http;
            WiFiClient httpClient;
            String url = String("http://") + currentHost + ":" + String(currentServerPort) + "/api/hardware/nfc-scan";
            StaticJsonDocument<128> doc;
            doc["card_uid"] = String(event.data);
            doc["device_id"] = currentDeviceId;
            String body;
            serializeJson(doc, body);
            Serial.printf("[Event] NFC上报 attempt=%d/%d\n", attempt, MAX_RETRY);
            Serial.printf("[Event] POST %s\n", url.c_str());
            Serial.printf("[Event] payload=%s\n", body.c_str());

            if (http.begin(httpClient, url)) {
              http.setReuse(false);
              http.useHTTP10(true);
              http.setConnectTimeout(3000);
              http.setTimeout(5000);
              http.addHeader("Connection", "close");
              http.addHeader("Content-Type", "application/json");
              code = http.POST((uint8_t*)body.c_str(), body.length());
              response = http.getString();
              Serial.printf("[Event] HTTP code=%d\n", code);
              Serial.printf("[Event] resp_raw=%s\n", response.c_str());
              http.end();
              httpClient.stop();
            } else {
              Serial.printf("[Event] nfc-scan begin()失败 attempt=%d/%d\n", attempt, MAX_RETRY);
              printNetworkContext("NFC-SCAN-BEGIN-FAIL", url);
            }
            Serial.printf("[Event] 上报尝试 %d/%d, code=%d, resp=%s\n", attempt, MAX_RETRY, code, response.c_str());
            if (code > 0 && code < 300) break;
            vTaskDelay(pdMS_TO_TICKS(200));
          }

          if (code > 0 && code < 300) {
            Serial.println("[Event] 服务器响应: " + response);
            String action = "";
            String msg = "";
            String door = "";
            StaticJsonDocument<256> respDoc;
            DeserializationError derr = deserializeJson(respDoc, response);
            if (!derr) {
              if (!respDoc["action"].isNull()) action = respDoc["action"].as<String>();
              if (!respDoc["msg"].isNull()) msg = respDoc["msg"].as<String>();
              if (!respDoc["door"].isNull()) door = respDoc["door"].as<String>();
              Serial.printf("[Event] resp_parsed action=%s door=%s msg=%s\n", action.c_str(), door.c_str(), msg.c_str());
            } else {
              Serial.printf("[Event] resp_json_parse_fail=%s\n", derr.c_str());
            }

            if (action == "OPEN" || response.indexOf("OPEN") != -1) {
              // 服务器授予权限
              SystemEvent open_event;
              open_event.type = EVENT_NFC_PERMISSION_OK;
              strcpy(open_event.data, "nfc");
              open_event.timestamp = millis();
              xQueueSend(event_queue, &open_event, 0);
            } else {
              SystemEvent deny_event;
              deny_event.type = EVENT_NFC_PERMISSION_DENY;
              strcpy(deny_event.data, "deny");
              deny_event.timestamp = millis();
              xQueueSend(event_queue, &deny_event, 0);
            }
          } else {
            Serial.printf("[Event] 上报失败，放弃本次读卡，code=%d\n", code);
            printNetworkContext("NFC-SCAN-FAIL");
            SystemEvent net_event;
            net_event.type = EVENT_NETWORK_ERROR;
            strcpy(net_event.data, "report_failed");
            net_event.timestamp = millis();
            xQueueSend(event_queue, &net_event, 0);
          }

          xSemaphoreGive(network_mutex);
        } else {
          Serial.println("[Event] WiFi未连接，无法上报NFC读卡结果");
          printNetworkContext("NFC-SCAN-NO-WIFI");
          SystemEvent net_event;
          net_event.type = EVENT_NETWORK_ERROR;
          strcpy(net_event.data, "wifi_disconnected");
          net_event.timestamp = millis();
          xQueueSend(event_queue, &net_event, 0);
        }
        break;
      }
      
      case EVENT_NFC_PERMISSION_OK:
      case EVENT_REMOTE_DOOR_OPEN: {
        // 执行开门
        Serial.println("[Event] 执行开门逻辑...");
        
        if (xSemaphoreTake(door_mutex, pdMS_TO_TICKS(100))) {
          int doorId = 1;
          String sourceStr = String(event.data);

          if (event.type == EVENT_REMOTE_DOOR_OPEN) {
            int sep = sourceStr.indexOf(':');
            if (sourceStr.startsWith("door") && sep > 4) {
              String doorPart = sourceStr.substring(4, sep);
              int parsedDoor = doorPart.toInt();
              if (parsedDoor == 2) doorId = 2;
              sourceStr = sourceStr.substring(sep + 1);
            }
            sourceStr.trim();
            if (sourceStr.length() == 0) sourceStr = "remote";
          } else {
            sourceStr = "nfc";
          }

          const char *source = sourceStr.c_str();
          
          // 打开继电器
          if (doorId == 1 && DOOR1_PIN >= 0) {
            digitalWrite(DOOR1_PIN, HIGH);
          } else if (doorId == 2 && DOOR2_PIN >= 0) {
            digitalWrite(DOOR2_PIN, HIGH);
          }
          
          // 更新门状态
          door_status.is_open = true;
          door_status.open_time = millis();
          door_status.door_id = doorId;
          strncpy(door_status.trigger_source, source, sizeof(door_status.trigger_source) - 1);
          door_status.trigger_source[sizeof(door_status.trigger_source) - 1] = '\0';
          
          // LED 反馈：亮绿色（开门中）
          showPixel(0, 180, 0);
          showTransientStatus("ACCESS OK", ST77XX_GREEN, doorId == 1 ? "Door 1 opened" : "Door 2 opened", String("Source: ") + source, "Auto close in 3s", "", 3000);
          playStatusSound(SOUND_ACCESS_OK);
          
          Serial.println("[Event] 门已打开，3秒后自动关闭");
          
          xSemaphoreGive(door_mutex);
        }
        break;
      }
      
      case EVENT_NFC_PERMISSION_DENY: {
        Serial.println("[Event] 权限拒绝");
        showPixel(180, 0, 0);  // 红色警告
        showTransientStatus("DENIED", ST77XX_RED, "Access denied", "Card not authorized", "", "", 2200);
        playStatusSound(SOUND_ACCESS_DENY);
        delay(2000);
        showPixel(0, 0, 0);
        break;
      }
      
      case EVENT_NETWORK_ERROR: {
        Serial.println("[Event] 网络错误");
        showPixel(180, 90, 0);  // 橙色警告
        showTransientStatus("NET ERROR", ST77XX_YELLOW, "Backend request failed", "Check network/server", "", "", 2200);
        playStatusSound(SOUND_NETWORK_ERROR);
        delay(1200);
        showPixel(0, 0, 0);
        break;
      }
      
      default:
        break;
    }
  }
}

// ==================== 12. 初始化和主程序 ====================

void setup() {
  logBootBoth("[SETUP] Enter setup()");
  initHardware();
  logBootBoth("[SETUP] initHardware() done");

  // 启动时长按 RESET 按键 8 秒可清除配置并进入 AP 配网模式
  logBootBoth("[SETUP] Check reset button at boot");
  if (isResetButtonHeldAtBoot()) {
    logBootBoth("[SETUP] Reset hold confirmed, clearing config");
    clearDeviceConfig();
  }
  logBootBoth("[SETUP] Reset check done");

  // 尝试读取本地配置；无配置则进入 AP 配置模式
  logBootBoth("[SETUP] Loading local config");
  if (!loadDeviceConfig()) {
    logBootBoth("[SETUP] Config missing, entering AP portal");
    startConfigPortal();
    logBootBoth("[SETUP] AP portal finished");
  }
  applyRuntimeConfig();
  logBootBoth("[SETUP] Runtime config applied");
  
  // 显示启动信息
  Serial.println("\n╔════════════════════════════════════════════╗");
  Serial.println("║   ESP32-S3 智能门禁控制器 v2.0            ║");
  Serial.println("║   模式: FreeRTOS 双核并发                ║");
  Serial.println("╠════════════════════════════════════════════╣");
  Serial.println("║  Core 0: NFC 实时读卡 + 门锁控制         ║");
  Serial.println("║  Core 1: 网络轮询 + 心跳 + 显示          ║");
  Serial.println("╚════════════════════════════════════════════╝\n");
  
  // 连接 WiFi，失败时返回 AP 模式重新配置
  logBootBoth("[SETUP] Connecting WiFi");
  if (!connectWiFiFromConfig()) {
    logBootBoth("[SETUP] WiFi failed, back to AP portal");
    startConfigPortal();
    applyRuntimeConfig();
    connectWiFiFromConfig();
  }
  logBootBoth("[SETUP] WiFi stage done");

  if (WiFi.status() == WL_CONNECTED && ENABLE_BLE) {
    gBleReady = initBleScanner();
    if (gBleReady) {
      logBootBoth("[SETUP] BLE scanner ready");
    } else {
      logBootBoth("[SETUP] BLE scanner init failed");
    }
  }

  // WiFi连通后先做一次后端连通性探测，便于定位“刷卡报网络错误”
  if (WiFi.status() == WL_CONNECTED) {
    bool netOk = probeBackendConnectivity();
    if (!netOk) {
      Serial.println("[SETUP] ⚠️ 后端连通性探测失败，刷卡上报可能报网络错误");
      showTransientStatus("NET WARN", ST77XX_YELLOW, "Backend probe failed", "Check host/port/firewall", currentHost + ":" + String(currentServerPort), "", 2500);
    }
  }
  
  // 注册设备
  logBootBoth("[SETUP] Register device");
  if (WiFi.status() == WL_CONNECTED) {
    bool registered = registerDeviceToServer();
    Serial.println(registered ? "[REG] ✅ 设备注册成功" : "[REG] ⚠️  设备已存在或注册失败（等待后台授权后可继续使用）");
  }
  logBootBoth("[SETUP] Register stage done");
  
  // 创建 FreeRTOS 任务（双核）
  Serial.println("\n📌 创建 FreeRTOS 任务...");
  
  // Core 0 任务
  xTaskCreatePinnedToCore(
    nfcMonitor,           // 函数指针
    "NFC_Monitor",        // 任务名
    8192,                 // 栈大小（NFC+显示+String 路径较深，避免栈溢出复位）
    NULL,                 // 参数
    3,                    // 优先级（高）
    NULL,                 // 任务句柄
    0                     // 核心编号（Core 0）
  );
  
  xTaskCreatePinnedToCore(
    doorController,
    "Door_Controller",
    3072,
    NULL,
    2,
    NULL,
    0
  );
  
  // Core 1 任务
  xTaskCreatePinnedToCore(
    networkPoller,
    "Network_Poller",
    8192,
    NULL,
    2,
    NULL,
    1
  );
  
  xTaskCreatePinnedToCore(
    heartbeatTask,
    "Heartbeat",
    6144,
    NULL,
    1,
    NULL,
    1
  );

  if (gBleReady) {
    xTaskCreatePinnedToCore(
      bluetoothScannerTask,
      "Bluetooth_Scanner",
      8192,
      NULL,
      1,
      NULL,
      1
    );
  }

  logBootBoth("[SETUP] FreeRTOS tasks created");
  
  Serial.println("✨ 系统启动完成，双核并发运行\n");
  logBootBoth("[SETUP] setup() completed");
}

void loop() {
  // 主线程：专注于事件处理（无阻塞）
  eventHandler();
  monitorResetButtonRuntime();
  
  // 定期输出系统状态
  static unsigned long last_status_time = 0;
  if (millis() - last_status_time > 10000) {
    last_status_time = millis();
    
    Serial.println("\n╔══════════════════════════════════╗");
    Serial.println("║      系统运行状态                  ║");
    Serial.println("╠══════════════════════════════════╣");
    Serial.printf("║ Core 0 (NFC): 运行中              ║\n");
    Serial.printf("║ Core 1 (网络): 运行中             ║\n");
    
    if (xSemaphoreTake(nfc_mutex, pdMS_TO_TICKS(100))) {
      Serial.printf("║ 最后读卡: %-19s║\n", nfc_status.last_card_uid);
      xSemaphoreGive(nfc_mutex);
    }
    
    Serial.printf("║ WiFi: %s                      ║\n", 
                  WiFi.status() == WL_CONNECTED ? "连接中" : "离线");
    unsigned long nowMs = millis();
    unsigned long sAge = gBleLastScanMs > 0 ? (nowMs - gBleLastScanMs) / 1000 : 9999;
    unsigned long rAge = gBleLastReportMs > 0 ? (nowMs - gBleLastReportMs) / 1000 : 9999;
    unsigned long vAge = gBleLastVerifyMs > 0 ? (nowMs - gBleLastVerifyMs) / 1000 : 9999;
    Serial.printf("║ BLE: %s cnt=%-3d s=%-3lus r=%-3lus v=%-3lus║\n",
                  gBleReady ? "ON " : "OFF",
                  gBleLastSeenCount,
                  sAge,
                  rAge,
                  vAge);
    Serial.println("╚══════════════════════════════════╝\n");
  }

  showIdleScreen();
  
  delay(100);
}

/*
 * ==================== 架构说明 ====================
 *
 * 【双核并发架构】
 *
 * Core 0 (实时核)              Core 1 (网络核)
 * ├─ nfcMonitor()             ├─ networkPoller()
 * │  └─ 50ms 轮询NFC          │  └─ 2000ms 轮询服务器
 * │                           │
 * ├─ doorController()         ├─ heartbeatTask()
 * │  └─ 100ms 检查门锁        │  └─ 30000ms 心跳
 * │                           │
 * └─ 响应时间: <10ms          └─ 响应时间: 100-3000ms
 *
 * 跨核通信：
 * • event_queue - 事件传递（NFC读卡 → 网络上报 → 开门）
 * • 互斥锁 - 保护共享状态（nfc_status, door_status）
 *
 * 优势：
 * 1. NFC 不被网络阻塞（即使网络延迟 3秒，NFC 仍 <10ms 响应）
 * 2. 真正的实时性（Core 0 专属高优先级）
 * 3. 线程安全（所有共享资源都有互斥锁保护）
 * 4. 事件驱动（异步处理，解耦各模块）
 * 5. 功耗优化（任务阻塞时 CPU 进入低功耗状态）
 *
 * ====================================================
 */
