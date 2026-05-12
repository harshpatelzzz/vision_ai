# ESP32-CAM — PoseVision Wireless Edge Camera

AI Thinker ESP32-CAM firmware for MJPEG streaming (`:81/stream`) and companion sensor telemetry sketches.

## Contents

| File | Purpose |
|------|---------|
| `esp32cam_stream.ino` | WiFi MJPEG HTTP server, flash LED, resolution switching |
| `sensor_monitor.ino` | BNO055, MLX90614, VL53L0X, LDR, limit switch → Serial JSON + optional HTTP POST |

## Requirements

- Arduino IDE 2.x or PlatformIO  
- **ESP32** board package (Espressif)  
- USB cable with **data** lines (charge-only cables will not work)  
- **5 V** supply adequate for WiFi + camera peaks (unstable power causes brownouts / reboots)

### Arduino IDE board setup

1. **File → Preferences → Additional Board URLs**:  
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
2. **Tools → Board → Boards Manager**: install **esp32**.
3. Select **AI Thinker ESP32-CAM** (or **ESP32 Wrover Module** if exact entry unavailable).

### Streaming sketch (`esp32cam_stream.ino`)

1. Edit `WIFI_SSID` / `WIFI_PASS`.
2. Upload.  
3. Open Serial Monitor **115200 baud** — note printed **LAN IP**.  
4. Browser: `http://<IP>:81/stream` — MJPEG for OpenCV.  
5. Optional: `/`, `/size?f=qvga`, `/flash?on=1`.

**Resolution defaults**: QVGA (stable real-time inference). Change `DEFAULT_FRAME_SIZE` to `FRAMESIZE_QQVGA`, `FRAMESIZE_VGA`, or `FRAMESIZE_SVGA` as needed.

### Sensor sketch (`sensor_monitor.ino`)

1. Set `USE_SENSOR_STUBS` to `0` when real sensors and Adafruit / Pololu libraries are installed.  
2. Wire per project `docs/hardware_setup.md` (LDR, limit switch). I2C sensors share **GPIO21 (SDA)** / **GPIO22 (SCL)** on ESP32 (verify your module silkscreen).  
3. Serial JSON lines feed `hardware/sensor_daemon.py` on the host (`esp32_telemetry.serial_port` in `config.yaml`).

### USB-UART (CP2102 / CH340) for flashing

| Adapter | ESP32-CAM |
|---------|-----------|
| **TX** | **RX** (UART0 RX — typically **GPIO3 U0RXD**) |
| **RX** | **TX** (**GPIO1 U0TXD**) |
| **GND** | **GND** |

Cross **TX/RX** between USB-UART and ESP32 UART0.

### Boot / flash mode

- **GPIO0** held **LOW** (GND) during **RESET** enters UART download mode (erase flash / upload).  
- After flashing, disconnect GPIO0 from GND and press reset so the firmware runs.

### Power warning

Use a **stable 5 V** supply (AMS1117 on module drops to 3.3 V). Weak USB ports may reboot during WiFi association or JPEG encode.

## Host (PoseVision)

```bash
python scripts/webcam_pipeline.py --source esp32cam --stream-url http://192.168.x.x:81/stream
```

Environment alternative:

```bash
set POSEVISION_ESP32_STREAM_URL=http://192.168.x.x:81/stream
```

Optional telemetry daemon: enable `esp32_telemetry` in `config/config.yaml` and set `serial_port`.

## Troubleshooting

| Symptom | Mitigation |
|---------|------------|
| Upload fails | GPIO0 → GND for flash; correct COM port; drivers for CP2102/CH340 |
| Brownout loop | Stronger 5 V supply; shorter USB cable; add bulk capacitance near module |
| No IP / WiFi | 2.4 GHz only; correct SSID/password; RSSI weak |
| OpenCV cannot open URL | FFmpeg build in OpenCV; try LAN ping; verify `:81/stream` in browser |
| Garbled Serial JSON | Match baud 115200; one sketch using UART0 at a time |

See also `docs/hardware_setup.md` for enclosure sensors and host GPIO/serial tamper paths.
