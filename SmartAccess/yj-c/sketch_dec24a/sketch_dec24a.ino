#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

// ================= 配置区域 =================
const char* ssid = "你的WiFi名称";  
const char* password = "你的WiFi密码";
// 请确保 IP 地址正确，且电脑防火墙允许 8000 端口
String serverName = "http://192.168.1.100:8000/api/hardware/nfc-scan"; 
// ===========================================

#define PN532_SDA D2   
#define PN532_SCL D1   
#define RELAY_PIN D5   

Adafruit_PN532 nfc(PN532_SDA, PN532_SCL);

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); 

  WiFi.begin(ssid, password);
  Serial.println("\n正在连接 WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi 已连接");
  Serial.print("IP: "); Serial.println(WiFi.localIP());

  nfc.begin();
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.print("未找到 PN532！");
    while (1); 
  }
  nfc.SAMConfig(); 
  Serial.println("等待刷卡...");
}

void loop() {
  uint8_t success;
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 }; 
  uint8_t uidLength;                        

  success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100);

  if (success) {
    Serial.println("发现卡片!");
    String card_uid = "";
    for (uint8_t i = 0; i < uidLength; i++) {
      if(i > 0) card_uid += "-";
      if (uid[i] < 0x10) card_uid += "0";
      card_uid += String(uid[i], HEX);
    }
    card_uid.toUpperCase();
    Serial.print("卡号: "); Serial.println(card_uid);

    if(WiFi.status() == WL_CONNECTED){
      WiFiClient client;
      HTTPClient http;

      http.begin(client, serverName);
      http.addHeader("Content-Type", "application/json");

      String requestBody = "{\"card_uid\":\"" + card_uid + "\"}";
      int httpResponseCode = http.POST(requestBody);

      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.println(response);

        // === 针对 ArduinoJson V7 的修改 ===
        JsonDocument doc; 
        DeserializationError error = deserializeJson(doc, response);

        if (!error) {
          const char* action = doc["action"];
          if (strcmp(action, "OPEN") == 0) {
            openDoor();
          } else {
            blinkLed(3, 100);
          }
        }
      }
      http.end();
    }
    delay(2000); 
  }
}

void openDoor() {
  Serial.println("开门!");
  digitalWrite(RELAY_PIN, HIGH);
  delay(3000);                   
  digitalWrite(RELAY_PIN, LOW); 
}

void blinkLed(int times, int delayTime) {
  for(int i=0; i<times; i++){
    digitalWrite(RELAY_PIN, HIGH);
    delay(delayTime);
    digitalWrite(RELAY_PIN, LOW);
    delay(delayTime);
  }
}
