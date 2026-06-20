/**
 * PoseVision — ESP32 + MFRC522 RFID access-control reader.
 *
 * Reads a tag UID and reports it to the PoseVision edge node by BOTH:
 *   1. Serial   — one JSON object per scan at 115200 baud (always on, primary
 *                 fallback). Consumed by hardware/rfid_reader.py (mode "serial").
 *   2. WiFi API — HTTP POST of the same JSON to EDGE_RFID_URL, and a tiny HTTP
 *                 server exposing GET /rfid/last-scan for poll mode
 *                 (hardware/rfid_reader.py mode "http").
 *
 * JSON line format (matches RfidReader._parse_and_ingest):
 *   {"type":"rfid","uid":"A1:B2:C3:D4","reader":"gate-1","rssi":0,"uptime_ms":12345}
 *
 * Libraries: MFRC522 by GithubCommunity (Arduino Library Manager).
 *
 * Wiring (MFRC522 SPI -> ESP32):
 *   SDA/SS  -> GPIO5      SCK  -> GPIO18
 *   MOSI    -> GPIO23     MISO -> GPIO19
 *   RST     -> GPIO27     3.3V -> 3V3 (NOT 5V)   GND -> GND
 */

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>

// ----- configuration --------------------------------------------------------
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";
// Edge node ingest endpoint (FastAPI). Leave "" to disable HTTP push.
const char *EDGE_RFID_URL = ""; // e.g. "http://192.168.1.10:8000/hardware/telemetry-ingest"
const char *READER_ID = "gate-1";

#define SS_PIN 5
#define RST_PIN 27

// Re-report the same card no faster than this (ms); the edge also de-dups.
const unsigned long REPEAT_SUPPRESS_MS = 1200;

MFRC522 mfrc522(SS_PIN, RST_PIN);
WebServer server(80);

static bool wifiOk = false;
static String lastUid = "";
static unsigned long lastUidMs = 0;
static String lastJson = "{}";

// ----- helpers --------------------------------------------------------------
static String uidToString(const MFRC522::Uid &uid) {
  String out = "";
  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] < 0x10) out += "0";
    out += String(uid.uidByte[i], HEX);
    if (i + 1 < uid.size) out += ":";
  }
  out.toUpperCase();
  return out;
}

static String buildJson(const String &uid) {
  String j = "{\"type\":\"rfid\",\"uid\":\"";
  j += uid;
  j += "\",\"reader\":\"";
  j += READER_ID;
  j += "\",\"rssi\":0,\"uptime_ms\":";
  j += String(millis());
  j += "}";
  return j;
}

static void pushHttp(const String &json) {
  if (!wifiOk || EDGE_RFID_URL == nullptr || EDGE_RFID_URL[0] == '\0') return;
  HTTPClient http;
  if (http.begin(EDGE_RFID_URL)) {
    http.addHeader("Content-Type", "application/json");
    http.POST((uint8_t *)json.c_str(), json.length());
    http.end();
  }
}

static void reportScan(const String &uid) {
  String json = buildJson(uid);
  lastJson = json;
  Serial.println(json); // primary serial fallback
  pushHttp(json);
}

// ----- HTTP server (poll mode) ---------------------------------------------
static void handleLastScan() { server.send(200, "application/json", lastJson); }
static void handleRoot() {
  server.send(200, "text/plain", "PoseVision RFID reader OK. GET /rfid/last-scan");
}

static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(300);
  }
  wifiOk = (WiFi.status() == WL_CONNECTED);
  if (wifiOk) {
    Serial.print("{\"type\":\"status\",\"wifi\":\"connected\",\"ip\":\"");
    Serial.print(WiFi.localIP());
    Serial.println("\"}");
    server.on("/", handleRoot);
    server.on("/rfid/last-scan", handleLastScan);
    server.begin();
  } else {
    Serial.println("{\"type\":\"status\",\"wifi\":\"failed\",\"fallback\":\"serial\"}");
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  SPI.begin();
  mfrc522.PCD_Init();
  delay(50);
  connectWifi();
  Serial.println("{\"type\":\"status\",\"msg\":\"rfid_reader_ready\"}");
}

void loop() {
  // Keep WiFi alive; auto-reconnect.
  if (wifiOk && WiFi.status() != WL_CONNECTED) {
    wifiOk = false;
  }
  if (!wifiOk && WiFi.status() != WL_CONNECTED) {
    static unsigned long lastTry = 0;
    if (millis() - lastTry > 10000) {
      lastTry = millis();
      connectWifi();
    }
  }
  if (wifiOk) server.handleClient();

  // Poll for a new card.
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    delay(40);
    return;
  }

  String uid = uidToString(mfrc522.Uid);
  unsigned long now = millis();
  if (uid == lastUid && (now - lastUidMs) < REPEAT_SUPPRESS_MS) {
    mfrc522.PICC_HaltA();
    return;
  }
  lastUid = uid;
  lastUidMs = now;

  reportScan(uid);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}
