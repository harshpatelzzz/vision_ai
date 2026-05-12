/**
 * PoseVision — ESP32-CAM (AI Thinker) MJPEG HTTP streamer on port 81.
 *
 * Board: AI Thinker ESP32-CAM
 * Framework: Arduino-ESP32 + esp_camera.h + WiFi.h
 *
 * Stream URL (after WiFi connect): http://<device-ip>:81/stream
 * Root status page: http://<device-ip>:81/
 */

#include "esp_camera.h"
#include <WiFi.h>

// -----------------------------------------------------------------------------
// WiFi — set before flashing or use WiFiManager in production
// -----------------------------------------------------------------------------
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASS = "YOUR_WIFI_PASSWORD";

// -----------------------------------------------------------------------------
// Camera model: AI Thinker
// -----------------------------------------------------------------------------
#define CAMERA_MODEL_AI_THINKER
#ifdef CAMERA_MODEL_AI_THINKER
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22
#define LED_FLASH_GPIO 4
#endif

// Default: QVGA @ moderate JPEG quality for stable edge inference
#define DEFAULT_FRAME_SIZE FRAMESIZE_QVGA
#define DEFAULT_JPEG_QUALITY 12

// Two frame buffers + PSRAM preferred for streaming stability
#define FB_COUNT 2

WiFiServer httpServer(81);

static bool initCamera(framesize_t fs, int jpeg_q) {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = fs;
    config.jpeg_quality = jpeg_q;
    config.fb_count = FB_COUNT;
    config.grab_mode = CAMERA_GRAB_LATEST;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = jpeg_q + 3;
    config.fb_count = 1;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    s->set_framesize(s, fs);
    s->set_quality(s, jpeg_q);
    if (psramFound()) {
      s->set_raw_gma(s, 1);
    }
  }

  pinMode(LED_FLASH_GPIO, OUTPUT);
  digitalWrite(LED_FLASH_GPIO, LOW);
  return true;
}

static void sendHttp(WiFiClient &c, int code, const char *ctype, const uint8_t *body,
                     size_t len) {
  c.printf("HTTP/1.1 %d OK\r\n", code);
  c.printf("Connection: close\r\n");
  if (ctype)
    c.printf("Content-Type: %s\r\n", ctype);
  c.printf("Content-Length: %u\r\n", (unsigned)len);
  c.printf("\r\n");
  if (body && len)
    c.write(body, len);
}

static void handleRoot(WiFiClient &c) {
  const char *html =
      "<!DOCTYPE html><html><head><meta charset='utf-8'><title>PoseVision ESP32-CAM</title></head>"
      "<body><h1>PoseVision ESP32-CAM</h1>"
      "<p>MJPEG: <a href=\"/stream\">/stream</a></p>"
      "<p>Flash LED: <a href=\"/flash?on=1\">on</a> | <a href=\"/flash?on=0\">off</a></p>"
      "<p>Resolution: <a href=\"/size?f=qqvga\">QQVGA</a> "
      "<a href=\"/size?f=qvga\">QVGA</a> <a href=\"/size?f=vga\">VGA</a> "
      "<a href=\"/size?f=svga\">SVGA</a></p>"
      "</body></html>";
  sendHttp(c, 200, "text/html", (const uint8_t *)html, strlen(html));
}

static framesize_t frameSizeFromName(const String &n) {
  if (n == "qqvga")
    return FRAMESIZE_QQVGA;
  if (n == "qvga")
    return FRAMESIZE_QVGA;
  if (n == "vga")
    return FRAMESIZE_VGA;
  if (n == "svga")
    return FRAMESIZE_SVGA;
  return DEFAULT_FRAME_SIZE;
}

static void handleSize(WiFiClient &c, const String &query) {
  int q = query.indexOf('f=');
  framesize_t fs = DEFAULT_FRAME_SIZE;
  if (q >= 0) {
    String v = query.substring(q + 2);
    int amp = v.indexOf('&');
    if (amp > 0)
      v = v.substring(0, amp);
    fs = frameSizeFromName(v);
  }
  sensor_t *s = esp_camera_sensor_get();
  if (s)
    s->set_framesize(s, fs);
  const char *ok = "OK\n";
  sendHttp(c, 200, "text/plain", (const uint8_t *)ok, strlen(ok));
}

static void handleFlash(WiFiClient &c, const String &query) {
  int on = query.indexOf("on=1") >= 0 ? HIGH : LOW;
  digitalWrite(LED_FLASH_GPIO, on);
  const char *ok = "OK\n";
  sendHttp(c, 200, "text/plain", (const uint8_t *)ok, strlen(ok));
}

static void streamMjpeg(WiFiClient &client) {
  client.println("HTTP/1.1 200 OK");
  client.println("Access-Control-Allow-Origin: *");
  client.println(
      "Content-Type: multipart/x-mixed-replace; boundary=frame");
  client.println();

  const char *boundary = "--frame\r\n";
  unsigned long last = millis();

  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      delay(10);
      continue;
    }

    client.write((const uint8_t *)boundary, strlen(boundary));
    client.println("Content-Type: image/jpeg");
    client.printf("Content-Length: %u\r\n\r\n", fb->len);
    client.write(fb->buf, fb->len);
    client.println("\r\n");
    esp_camera_fb_return(fb);

    // crude FPS throttle ~15fps max to reduce WiFi contention (tune as needed)
    unsigned long now = millis();
    unsigned long dt = now - last;
    if (dt < 60)
      delay(60 - dt);
    last = millis();
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  delay(200);

  if (!initCamera(DEFAULT_FRAME_SIZE, DEFAULT_JPEG_QUALITY)) {
    Serial.println("Fatal: camera");
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected. IP: ");
  Serial.println(WiFi.localIP());
  Serial.println("MJPEG stream: http://<IP>:81/stream");

  httpServer.begin();
}

void loop() {
  WiFiClient client = httpServer.available();
  if (!client)
    return;

  unsigned long tmo = millis() + 3000;
  String req;
  while (client.connected() && millis() < tmo) {
    if (client.available()) {
      req = client.readStringUntil('\n');
      break;
    }
    delay(1);
  }

  String path = "/";
  String query = "";
  int sp = req.indexOf(' ');
  if (sp > 0) {
    int sp2 = req.indexOf(' ', sp + 1);
    if (sp2 > sp) {
      String u = req.substring(sp + 1, sp2);
      int qm = u.indexOf('?');
      if (qm >= 0) {
        path = u.substring(0, qm);
        query = u.substring(qm + 1);
      } else {
        path = u;
      }
    }
  }

  while (client.available())
    client.read();

  if (path == "/stream") {
    streamMjpeg(client);
  } else if (path == "/") {
    handleRoot(client);
  } else if (path == "/size") {
    handleSize(client, query);
  } else if (path == "/flash") {
    handleFlash(client, query);
  } else {
    const char *nf = "Not Found\n";
    sendHttp(client, 404, "text/plain", (const uint8_t *)nf, strlen(nf));
  }

  client.stop();
}
