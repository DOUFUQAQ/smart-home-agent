#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// -----------------------------
// Node #2 executor configuration
// -----------------------------
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* API_BASE = "http://192.168.1.100:8000";
const char* DEVICE_ID = "REPLACE_WITH_EXECUTOR_DEVICE_ID";

// -----------------------------
// Pin definitions (Node #2)
// -----------------------------
constexpr int RELAY_LIGHT_PIN = 16;
constexpr int RELAY_SOCKET_PIN = 17;
constexpr int RELAY_FAN_PIN = 18;

constexpr int I2S_BCLK_PIN = 26;
constexpr int I2S_LRCLK_PIN = 25;
constexpr int I2S_DIN_PIN = 22;
constexpr int AMP_SD_PIN = 21;

constexpr int STATUS_LED_PIN = 2;  // optional
constexpr uint32_t CONTROL_POLL_MS = 3000;

uint32_t lastPollMs = 0;
bool lightState = false;
bool socketState = false;
bool fanState = false;

void setRelay(int pin, bool on) {
  // Common low-level trigger relay module.
  digitalWrite(pin, on ? LOW : HIGH);
}

void setLight(bool on) {
  lightState = on;
  setRelay(RELAY_LIGHT_PIN, on);
}

void setSocket(bool on) {
  socketState = on;
  setRelay(RELAY_SOCKET_PIN, on);
}

void setFan(bool on) {
  fanState = on;
  setRelay(RELAY_FAN_PIN, on);
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
}

void pushExecutorState() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  String url = String(API_BASE) + "/api/devices/" + DEVICE_ID + "/state";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<224> doc;
  doc["status"] = "online";
  JsonObject state = doc.createNestedObject("state");
  state["node_role"] = "executor";
  state["light"] = lightState ? "on" : "off";
  state["socket"] = socketState ? "on" : "off";
  state["fan"] = fanState ? "on" : "off";

  String payload;
  serializeJson(doc, payload);
  int code = http.PATCH(payload);
  Serial.printf("[API] PATCH executor state code=%d\n", code);
  http.end();
}

void applyTargetState(JsonObject state) {
  const char* light = state["light"] | "";
  const char* socket = state["socket"] | "";
  const char* fan = state["fan"] | "";

  if (strlen(light) > 0) {
    setLight(String(light) == "on");
  }
  if (strlen(socket) > 0) {
    setSocket(String(socket) == "on");
  }
  if (strlen(fan) > 0) {
    setFan(String(fan) == "on");
  }
}

void pollControl() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  String url = String(API_BASE) + "/api/devices";
  http.begin(url);
  int code = http.GET();
  if (code != 200) {
    Serial.printf("[API] GET devices failed: %d\n", code);
    http.end();
    return;
  }

  String body = http.getString();
  http.end();

  DynamicJsonDocument doc(6144);
  auto err = deserializeJson(doc, body);
  if (err) {
    Serial.printf("[JSON] parse failed: %s\n", err.c_str());
    return;
  }

  for (JsonObject device : doc.as<JsonArray>()) {
    const char* id = device["id"] | "";
    if (String(id) != DEVICE_ID) {
      continue;
    }
    JsonObject state = device["state"];
    applyTargetState(state);
    Serial.printf(
      "[Control] light=%s socket=%s fan=%s\n",
      lightState ? "on" : "off",
      socketState ? "on" : "off",
      fanState ? "on" : "off"
    );
    break;
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(RELAY_LIGHT_PIN, OUTPUT);
  pinMode(RELAY_SOCKET_PIN, OUTPUT);
  pinMode(RELAY_FAN_PIN, OUTPUT);
  pinMode(AMP_SD_PIN, OUTPUT);

  // Keep explicit pin ownership for MAX98357 I2S output lines.
  pinMode(I2S_BCLK_PIN, OUTPUT);
  pinMode(I2S_LRCLK_PIN, OUTPUT);
  pinMode(I2S_DIN_PIN, OUTPUT);

  // Enable amplifier.
  digitalWrite(AMP_SD_PIN, HIGH);

  setLight(false);
  setSocket(false);
  setFan(false);

  ensureWifi();
  pushExecutorState();
  Serial.println("[System] ESP32 executor node started.");
}

void loop() {
  ensureWifi();

  uint32_t now = millis();
  if (now - lastPollMs >= CONTROL_POLL_MS) {
    lastPollMs = now;
    pollControl();
    pushExecutorState();
  }
}
