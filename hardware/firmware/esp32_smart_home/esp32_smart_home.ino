#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// -----------------------------
// Node #1 collector configuration
// -----------------------------
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* API_BASE = "http://192.168.1.100:8000";
const char* DEVICE_ID = "REPLACE_WITH_COLLECTOR_DEVICE_ID";

// -----------------------------
// Pin definitions (Node #1)
// -----------------------------
constexpr int DHT_PIN = 4;
constexpr int MQ2_PIN = 34;
constexpr int INMP441_BCLK_PIN = 26;
constexpr int INMP441_WS_PIN = 27;
constexpr int INMP441_SD_PIN = 33;
constexpr int STATUS_LED_PIN = 2;  // optional

constexpr uint32_t REPORT_INTERVAL_MS = 10000;

#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

uint32_t lastReportMs = 0;

void blinkLed(int times, int delayMs) {
  for (int i = 0; i < times; ++i) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(delayMs);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(delayMs);
  }
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
  blinkLed(2, 120);
}

void pushCollectorState() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  String url = String(API_BASE) + "/api/devices/" + DEVICE_ID + "/state";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<192> doc;
  doc["status"] = "online";
  JsonObject state = doc.createNestedObject("state");
  state["node_role"] = "collector";
  state["mic"] = "inmp441";
  state["sensor_pack"] = "dht22+mq2";

  String payload;
  serializeJson(doc, payload);
  int code = http.PATCH(payload);
  Serial.printf("[API] PATCH collector state code=%d\n", code);
  http.end();
}

void reportReading() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  int gasRaw = analogRead(MQ2_PIN);

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("[Sensor] DHT read failed.");
    return;
  }

  HTTPClient http;
  String url = String(API_BASE) + "/api/readings";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<224> doc;
  doc["device_id"] = DEVICE_ID;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["gas_ppm"] = gasRaw;

  String payload;
  serializeJson(doc, payload);
  int code = http.POST(payload);
  Serial.printf(
    "[API] POST readings code=%d temp=%.2f hum=%.2f gas=%d\n",
    code, temperature, humidity, gasRaw
  );
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(MQ2_PIN, INPUT);

  // Keep explicit pin ownership for INMP441 I2S RX lines.
  pinMode(INMP441_BCLK_PIN, INPUT);
  pinMode(INMP441_WS_PIN, INPUT);
  pinMode(INMP441_SD_PIN, INPUT);

  dht.begin();
  ensureWifi();
  pushCollectorState();
  Serial.println("[System] ESP32 collector node started.");
}

void loop() {
  ensureWifi();

  uint32_t now = millis();
  if (now - lastReportMs >= REPORT_INTERVAL_MS) {
    lastReportMs = now;
    reportReading();
  }
}
