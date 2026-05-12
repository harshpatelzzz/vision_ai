/**
 * PoseVision — ESP32 sensor telemetry for enclosure / thermal / proximity security.
 *
 * Outputs one JSON object per line on Serial at 115200 baud.
 * Optional HTTP POST when USE_SENSOR_STUBS is 0 and WiFi + libraries are available.
 *
 * Sensors (I2C unless noted):
 *   BNO055 — orientation / sudden tilt (0x28)
 *   MLX90614 — non-contact temperature (0x5A)
 *   VL53L0X — time-of-flight distance (0x29)
 *   LDR — ADC light ingress (GPIO34)
 *   Limit switch — enclosure tamper (GPIO27)
 *
 * Set USE_SENSOR_STUBS to 0 and install Adafruit BNO055, MLX90614, Pololu VL53L0X.
 */

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>

const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char *EDGE_TELEMETRY_URL = "";

#define USE_SENSOR_STUBS 1

const int PIN_LDR = 34;
const int PIN_LIMIT = 27;

const float TEMP_HIGH_C = 55.0f;
const uint16_t DIST_CLOSE_MM = 80;
const int LDR_LIGHT_BURST = 3800;

unsigned long lastPublish = 0;
const unsigned long PUBLISH_MS = 200;

#if !USE_SENSOR_STUBS
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_MLX90614.h>
#include <VL53L0X.h>

Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
Adafruit_MLX90614 mlx = Adafruit_MLX90614();
VL53L0X vl53;
#endif

static float stub_temp = 28.0f;
static uint16_t stub_dist = 400;
static int stub_heading = 0;
static bool wifiOk = false;

static bool readSensors(float &tempC, uint16_t &distMm, float &headingDeg, int &lightAdc,
                        bool &switchClosed, float &qx, float &qy, float &qz, float &qw) {
#if USE_SENSOR_STUBS
  lightAdc = analogRead(PIN_LDR);
  switchClosed = digitalRead(PIN_LIMIT) == HIGH;
  stub_heading = (stub_heading + 2) % 360;
  headingDeg = (float)stub_heading;
  stub_temp += 0.01f;
  if (stub_temp > 60.0f)
    stub_temp = 25.0f;
  tempC = stub_temp;
  stub_dist = (uint16_t)(380 + (millis() / 50) % 120);
  distMm = stub_dist;
  qx = qy = qz = 0.0f;
  qw = 1.0f;
  return true;
#else
  sensors_event_t ev;
  bno.getEvent(&ev);
  headingDeg = (float)ev.orientation.x;
  imu::Quaternion q = bno.getQuat();
  qx = q.x();
  qy = q.y();
  qz = q.z();
  qw = q.w();
  tempC = mlx.readObjectTempC();
  distMm = (uint16_t)vl53.readRangeContinuousMillimeters();
  lightAdc = analogRead(PIN_LDR);
  switchClosed = digitalRead(PIN_LIMIT) == HIGH;
  return true;
#endif
}

static bool evalTamper(float tempC, uint16_t distMm, int lightAdc, bool switchClosed) {
  if (!switchClosed)
    return true;
  if (tempC >= TEMP_HIGH_C)
    return true;
  if (distMm > 0 && distMm < DIST_CLOSE_MM)
    return true;
  if (lightAdc >= LDR_LIGHT_BURST)
    return true;
  return false;
}

static void printJsonLine(float tempC, uint16_t distMm, float headingDeg, int lightAdc,
                          bool tamper, bool switchClosed, float qx, float qy, float qz,
                          float qw) {
  char buf[384];
  snprintf(buf, sizeof(buf),
           "{\"temperature\":%.2f,\"distance\":%u,\"light\":%d,\"tamper\":%s,"
           "\"orientation\":%.2f,\"quat\":[%.4f,%.4f,%.4f,%.4f],"
           "\"limit_switch_closed\":%s,\"wifi\":%s,\"uptime_ms\":%lu}",
           tempC, (unsigned)distMm, lightAdc, tamper ? "true" : "false", headingDeg, qx, qy, qz,
           qw, switchClosed ? "true" : "false", wifiOk ? "true" : "false", millis());
  Serial.println(buf);
}

void setup() {
  Serial.begin(115200);
  delay(100);
  pinMode(PIN_LIMIT, INPUT);
#if !USE_SENSOR_STUBS
  Wire.begin();
  if (!bno.begin())
    Serial.println("BNO055 init failed");
  if (!mlx.begin())
    Serial.println("MLX90614 init failed");
  vl53.init();
  vl53.setTimeout(500);
  vl53.startContinuous();
#endif

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(300);
  }
  wifiOk = (WiFi.status() == WL_CONNECTED);
}

void loop() {
  unsigned long now = millis();
  if (now - lastPublish < PUBLISH_MS) {
    delay(2);
    return;
  }
  lastPublish = now;

  float tempC, headingDeg, qx, qy, qz, qw;
  uint16_t distMm;
  int lightAdc;
  bool switchClosed;

  readSensors(tempC, distMm, headingDeg, lightAdc, switchClosed, qx, qy, qz, qw);
  bool tamper = evalTamper(tempC, distMm, lightAdc, switchClosed);

  printJsonLine(tempC, distMm, headingDeg, lightAdc, tamper, switchClosed, qx, qy, qz, qw);

  if (tamper)
    Serial.println("TAMPER");

#if !USE_SENSOR_STUBS
  if (wifiOk && EDGE_TELEMETRY_URL != nullptr && EDGE_TELEMETRY_URL[0] != '\0') {
    HTTPClient http;
    if (http.begin(EDGE_TELEMETRY_URL)) {
      http.addHeader("Content-Type", "application/json");
      char body[400];
      snprintf(body, sizeof(body),
               "{\"temperature\":%.2f,\"distance\":%u,\"light\":%d,\"tamper\":%s,"
               "\"orientation\":%.2f}",
               tempC, (unsigned)distMm, lightAdc, tamper ? "true" : "false", headingDeg);
      http.POST(body);
      http.end();
    }
  }
#endif
}
