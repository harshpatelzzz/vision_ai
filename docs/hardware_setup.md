# Hardware Security Layer Setup Guide

Complete guide for implementing tamper detection and secure zeroization in the PoseVision edge AI system using an ESP32 microcontroller, physical sensors, and a Raspberry Pi or NVIDIA Jetson host.

---

## 1. Overview

The Hardware Security Layer adds a physical tamper-detection perimeter around the PoseVision edge device. Its purpose is to detect unauthorized access to the enclosure (case opened, device moved, extreme temperature) and respond instantly by:

1. **Halting the AI pipeline** so no further frames are processed.
2. **Zeroizing sensitive data** — overwriting and deleting VPAP log chains, clearing RAM frame buffers, and optionally destroying model weights.
3. **Shutting down the system** to prevent further extraction.

The detection side runs on a dedicated microcontroller (ESP32 or STM32) that monitors physical sensors and raises an alarm signal. The host (Raspberry Pi / Jetson) receives this signal via GPIO or USB-serial and executes the emergency response.

```
┌──────────────────────────────────────────────────┐
│                  ENCLOSURE                       │
│                                                  │
│  ┌─────────┐    ┌─────────┐    ┌──────────────┐  │
│  │  Sensors │───▶│  ESP32  │───▶│  Raspberry   │  │
│  │  (LDR,   │    │         │    │  Pi / Jetson │  │
│  │  Switch, │    │  GPIO25 │───▶│  GPIO17      │  │
│  │  Temp)   │    │   or    │    │    or        │  │
│  │          │    │   USB   │───▶│  /dev/ttyUSB │  │
│  └─────────┘    └─────────┘    └──────┬───────┘  │
│                                       │          │
│                            ┌──────────▼────────┐ │
│                            │  HardwareMonitor  │ │
│                            │  → Stop Pipeline  │ │
│                            │  → Zeroization    │ │
│                            │  → Shutdown       │ │
│                            └───────────────────┘ │
└──────────────────────────────────────────────────┘
```

---

## 2. Components Required

| Component | Purpose | Quantity |
|---|---|---|
| ESP32 DevKit v1 (or STM32 Blue Pill) | Tamper signal processing | 1 |
| LDR (Light Dependent Resistor) | Detect enclosure opening (light ingress) | 1 |
| 10 kΩ resistor | Voltage divider for LDR | 1 |
| Limit switch (micro switch) | Detect enclosure lid removal | 1 |
| 10 kΩ resistor | Pull-down for limit switch | 1 |
| NTC thermistor or DS18B20 (optional) | Detect heat-based attacks | 1 |
| Jumper wires (M-M, M-F) | Connections | ~15 |
| Half-size breadboard | Prototyping | 1 |
| Raspberry Pi 4/5 or NVIDIA Jetson Nano | Edge host running PoseVision | 1 |
| USB-A to Micro-USB cable | ESP32 serial connection (if using serial mode) | 1 |
| Enclosure / project box | Physical housing | 1 |

---

## 3. System Architecture

### Signal Flow

```
┌─────────────┐       ┌────────────────┐       ┌──────────────────┐
│   SENSORS   │       │  ESP32 / STM32 │       │  EDGE HOST       │
│             │       │                │       │  (Pi / Jetson)   │
│  LDR ──────▶│ A0    │                │       │                  │
│  Switch ───▶│ D27   │  Firmware      │       │                  │
│  Temp ─────▶│ A35   │  evaluates     │       │                  │
│             │       │  thresholds    │       │                  │
│             │       │                │  GPIO │                  │
│             │       │  GPIO25 ──────▶│──▶17  │  HardwareMonitor │
│             │       │     or         │       │  ↓               │
│             │       │  USB TX ──────▶│ serial│  EventEngine     │
│             │       │  "TAMPER\n"    │       │  ↓               │
│             │       │                │       │  Zeroization     │
│             │       │                │       │  ↓               │
│             │       │                │       │  Shutdown        │
└─────────────┘       └────────────────┘       └──────────────────┘
```

### Decision Logic on the ESP32

The ESP32 firmware runs a tight loop (~100 ms interval) reading each sensor. A tamper condition is raised when **any** of the following is true:

- **LDR** — analog reading drops below threshold (enclosure opened, light floods the sensor).
- **Limit switch** — digital pin reads LOW (lid physically removed, switch released).
- **Temperature** — analog reading exceeds threshold (heat gun or thermal attack).

Once triggered, the ESP32 drives its output pin HIGH **and** sends `"TAMPER"` over USB-serial. The signal latches — it will not clear until the ESP32 is power-cycled.

---

## 4. Circuit Connections

### 4.1 ESP32 Pin Map

| Sensor / Signal | ESP32 Pin | Type | Notes |
|---|---|---|---|
| LDR voltage divider output | GPIO34 | Analog input | 12-bit ADC, 0–4095 |
| Limit switch | GPIO27 | Digital input | External 10 kΩ pull-down |
| NTC thermistor (optional) | GPIO35 | Analog input | Voltage divider like LDR |
| Tamper output to host | GPIO25 | Digital output | 3.3 V logic HIGH on tamper |
| GND (common) | GND | — | Shared with host GND |

### 4.2 LDR Circuit

The LDR forms a voltage divider with a 10 kΩ fixed resistor. In a sealed dark enclosure the LDR resistance is high (~100 kΩ+), producing a **high** analog reading. When the case is opened, light lowers the LDR resistance and the reading **drops**.

```
3.3V ──┬── LDR ──┬── 10kΩ ── GND
       │         │
       │     GPIO34 (ADC)
       │
```

### 4.3 Limit Switch Circuit

A normally-closed (NC) micro switch is mounted so the enclosure lid holds it pressed. When the lid is removed, the switch opens, and the GPIO reads LOW through the pull-down.

```
3.3V ── Limit Switch (NC) ──┬── GPIO27
                            │
                         10kΩ
                            │
                           GND
```

- **Lid closed** → switch closed → GPIO27 reads HIGH.
- **Lid removed** → switch open → GPIO27 reads LOW (pulled down by 10 kΩ).

### 4.4 Temperature Sensor Circuit (Optional)

An NTC thermistor in a voltage divider, identical topology to the LDR. Under normal conditions the reading stays within a known band; a heat-based attack pushes it outside.

```
3.3V ── NTC ──┬── 10kΩ ── GND
              │
          GPIO35 (ADC)
```

### 4.5 Output Signal to Host

The ESP32 output pin connects directly to the Raspberry Pi / Jetson GPIO header. Both boards use 3.3 V logic, so no level shifter is needed.

```
ESP32 GPIO25 ───────── Raspberry Pi GPIO17 (BCM)
ESP32 GND    ───────── Raspberry Pi GND (Pin 6)
```

> **Important:** Always connect a common ground between the ESP32 and the host board. Without it, the logic levels are undefined.

---

## 5. ESP32 Firmware

Flash the following sketch using the Arduino IDE (with the ESP32 board package installed) or PlatformIO.

### 5.1 Arduino Sketch

```cpp
// ============================================================
// PoseVision Tamper Detection Firmware — ESP32
// ============================================================
//
// Reads three sensor channels and raises a tamper alarm when
// any threshold is exceeded. The alarm is latching: once set,
// it stays active until power cycle.
//
// Output signals:
//   1. GPIO25 driven HIGH
//   2. "TAMPER" printed to Serial (USB) at 115200 baud
// ============================================================

// ----- Pin Definitions -----
const int PIN_LDR        = 34;   // Analog — light sensor
const int PIN_SWITCH     = 27;   // Digital — limit switch (NC, pulled down)
const int PIN_TEMP       = 35;   // Analog — NTC thermistor (optional)
const int PIN_ALARM_OUT  = 25;   // Digital — output to host GPIO

// ----- Thresholds -----
// LDR: in a dark enclosure the ADC reads ~3500+.
// When the case is opened, light drops the reading below this value.
const int LDR_TAMPER_THRESHOLD   = 1500;

// Temperature: NTC reading above this value implies abnormal heat.
const int TEMP_TAMPER_THRESHOLD  = 3200;

// ----- State -----
bool tamperLatched = false;

void setup() {
    Serial.begin(115200);
    while (!Serial) { delay(10); }

    pinMode(PIN_SWITCH,    INPUT);
    pinMode(PIN_ALARM_OUT, OUTPUT);
    digitalWrite(PIN_ALARM_OUT, LOW);

    Serial.println("TAMPER_MONITOR:INIT");
    Serial.println("Sensors: LDR, SWITCH, TEMP");
    Serial.println("Waiting for tamper events...");
}

void loop() {
    if (tamperLatched) {
        // Already triggered — keep alarm asserted and repeat serial message
        // so a late-connecting host still receives it.
        Serial.println("TAMPER");
        delay(1000);
        return;
    }

    // --- Read sensors ---
    int ldrValue    = analogRead(PIN_LDR);
    int switchValue = digitalRead(PIN_SWITCH);
    int tempValue   = analogRead(PIN_TEMP);

    // --- Evaluate tamper conditions ---
    bool tamper = false;
    String reason = "";

    if (ldrValue < LDR_TAMPER_THRESHOLD) {
        tamper = true;
        reason = "LIGHT";
    }

    // Switch is NC with pull-down: HIGH when lid is closed, LOW when opened.
    if (switchValue == LOW) {
        tamper = true;
        reason += (reason.length() > 0 ? "+" : "");
        reason += "SWITCH";
    }

    if (tempValue > TEMP_TAMPER_THRESHOLD) {
        tamper = true;
        reason += (reason.length() > 0 ? "+" : "");
        reason += "TEMP";
    }

    // --- Trigger alarm ---
    if (tamper) {
        tamperLatched = true;
        digitalWrite(PIN_ALARM_OUT, HIGH);

        Serial.print("TAMPER:");
        Serial.println(reason);

        // Rapid-fire the message so the host catches it immediately
        for (int i = 0; i < 5; i++) {
            Serial.println("TAMPER");
            delay(50);
        }
    }

    // --- Heartbeat (optional debug) ---
    // Uncomment the block below to print sensor values every cycle.
    // Serial.print("LDR="); Serial.print(ldrValue);
    // Serial.print(" SW=");  Serial.print(switchValue);
    // Serial.print(" TMP="); Serial.println(tempValue);

    delay(100);  // 10 Hz poll rate
}
```

### 5.2 Flashing Instructions

1. Install the [Arduino IDE](https://www.arduino.cc/en/software) or [PlatformIO](https://platformio.org/).
2. In Arduino IDE, go to **File > Preferences** and add the ESP32 board manager URL:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Install the **esp32** board package from **Tools > Board > Boards Manager**.
4. Select **ESP32 Dev Module** from the board menu.
5. Connect the ESP32 via USB, select the correct COM port.
6. Click **Upload**.

### 5.3 Tuning Thresholds

The ADC thresholds (`LDR_TAMPER_THRESHOLD`, `TEMP_TAMPER_THRESHOLD`) depend on your specific sensor components and enclosure. To calibrate:

1. Uncomment the heartbeat debug block in `loop()`.
2. Open the Serial Monitor at 115200 baud.
3. Record baseline values with the enclosure sealed.
4. Open the enclosure and note the LDR value change.
5. Set `LDR_TAMPER_THRESHOLD` midway between sealed and open readings.
6. Repeat for the temperature sensor if used.

---

## 6. Raspberry Pi / Jetson Integration

PoseVision supports two communication modes between the ESP32 and the host. Choose one based on your wiring preference.

### 6.1 Option A: GPIO Mode (Recommended for Production)

The ESP32 drives a single wire HIGH on tamper. The Raspberry Pi detects the rising edge via interrupt.

**Physical connection:**

```
ESP32 GPIO25  ────────  RPi GPIO17 (BCM) / Pin 11
ESP32 GND     ────────  RPi GND         / Pin 6
```

**Python verification script** (standalone test, not part of the main repo):

```python
import RPi.GPIO as GPIO
import time

TAMPER_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(TAMPER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def on_tamper(channel):
    print(f"TAMPER DETECTED on GPIO {channel}!")

GPIO.add_event_detect(TAMPER_PIN, GPIO.RISING, callback=on_tamper, bouncetime=300)

print("Listening for tamper on GPIO17... (Ctrl+C to exit)")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
```

**config.yaml settings:**

```yaml
hardware_security:
  enabled: true
  mode: "gpio"
  gpio_pin: 17
```

### 6.2 Option B: Serial Mode (USB)

The ESP32 sends `"TAMPER"` over its USB-serial connection. No additional wiring beyond the USB cable is needed, making this the easier option for prototyping.

**Identify the serial port:**

```bash
# Linux / Raspberry Pi
ls /dev/ttyUSB*
# Typical output: /dev/ttyUSB0

# Jetson Nano
ls /dev/ttyACM*
# Typical output: /dev/ttyACM0
```

**Python verification script:**

```python
import serial
import time

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)
print("Listening for tamper on serial... (Ctrl+C to exit)")

try:
    while True:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if line:
            print(f"Received: {line}")
        if "TAMPER" in line.upper():
            print("*** TAMPER DETECTED ***")
            break
except KeyboardInterrupt:
    pass
finally:
    ser.close()
```

**config.yaml settings:**

```yaml
hardware_security:
  enabled: true
  mode: "serial"
  serial_port: "/dev/ttyUSB0"
  baudrate: 115200
```

---

## 7. Zeroization Procedure

When a tamper event fires, the system executes a multi-step zeroization sequence defined in `security/zeroization.py`. Each step is designed to be fail-safe — if one step errors, the remaining steps still execute.

### 7.1 Sequence

```
TAMPER DETECTED
  │
  ├─ 1. Wipe Logs
  │     Overwrite every .jsonl, .log, .txt file in logs/ with null bytes,
  │     flush to disk (fsync), then unlink.
  │
  ├─ 2. Clear RAM Buffers
  │     Call VolatileFrameStore.clear() to release all in-memory frames.
  │
  ├─ 3. Wipe Models (optional, off by default)
  │     Securely delete .pt, .onnx, .engine files from models/.
  │     Only runs when config: zeroization.delete_models = true.
  │
  └─ 4. Emergency Shutdown
        Execute "sudo shutdown now" (Linux) or equivalent.
        Only runs when config: zeroization.shutdown_on_tamper = true.
```

### 7.2 Secure Deletion Detail

Standard file deletion (`os.unlink`) merely removes the directory entry — the data remains on disk until overwritten. The zeroization module performs a best-effort secure delete:

```python
# From security/zeroization.py — _secure_delete()
size = path.stat().st_size
with open(path, "r+b") as f:
    f.write(b"\x00" * size)   # Overwrite with null bytes
    f.flush()
    os.fsync(f.fileno())      # Force write to physical storage
path.unlink()                 # Remove directory entry
```

This is effective on traditional HDDs and most eMMC / SD card controllers. On SSDs with wear-leveling, full erasure requires vendor-specific secure-erase commands — see [Section 11](#11-future-improvements) for notes.

### 7.3 Config Options

```yaml
zeroization:
  delete_models: false         # Set true only if models are easily re-provisioned
  log_dir: "logs/"             # Path relative to project root
  shutdown_on_tamper: false    # Set true in production deployments
```

---

## 8. Integration with Existing Repo

The hardware security layer is already wired into the codebase. This section explains the architecture for anyone modifying or extending it.

### 8.1 File Map

```
pose-vision/
├── core/
│   ├── hardware_monitor.py    ← HardwareMonitor class (GPIO / Serial / Simulation)
│   ├── runner.py              ← setup_hardware_monitor() + run_edge_loop()
│   └── event_engine.py        ← TAMPER_DETECTED event type
├── security/
│   └── zeroization.py         ← wipe_logs, wipe_models, emergency_shutdown
├── api/
│   └── server.py              ← GET /security/status endpoint
└── config/
    └── config.yaml            ← hardware_security + zeroization sections
```

### 8.2 Initialization Flow

The `run_edge_loop()` function in `core/runner.py` handles everything automatically when the `config` and `project_root` arguments are provided:

```python
from core.runner import run_edge_loop

run_edge_loop(
    cap=capture,
    pipeline=pipeline,
    event_engine=event_engine,
    vpap=vpap_logger,
    config=config,               # Pass the loaded config dict
    project_root=project_root,   # Path to pose-vision/
)
```

Internally, `setup_hardware_monitor()` is called, which:

1. Reads `hardware_security` from the config dict.
2. Instantiates `HardwareMonitor` with the configured mode, pin, and port.
3. Registers a callback that executes the full tamper response.
4. Starts the monitor thread.

### 8.3 Callback Chain

When `HardwareMonitor.trigger_tamper()` fires:

```
trigger_tamper()
  │
  ├─ Set threading.Event stop_flag → main loop exits on next iteration
  │
  ├─ EventEngine.emit_tamper_event()
  │   └─ Appended to event deque (available via API recent_events)
  │
  ├─ VPAPLogger.append({alert_type: "TAMPER_DETECTED", ...})
  │   └─ Tamper event is now part of the SHA-256 hash chain
  │
  ├─ Log to logs/tamper.log (dedicated tamper file logger)
  │
  └─ full_zeroization(...)
      ├─ wipe_logs()
      ├─ wipe_temp_frames()
      ├─ wipe_models()       [if delete_models=true]
      └─ emergency_shutdown() [if shutdown_on_tamper=true]
```

### 8.4 API Endpoint

While the system is running, query the hardware security status:

```bash
curl http://127.0.0.1:8000/security/status
```

Response when no tamper has occurred:

```json
{
  "tamper_detected": false,
  "hardware_security_enabled": true,
  "mode": "gpio",
  "monitor_running": true,
  "last_event": null
}
```

Response after a tamper event:

```json
{
  "tamper_detected": true,
  "hardware_security_enabled": true,
  "mode": "gpio",
  "monitor_running": true,
  "last_event": "2026-04-30T12:45:01.234567+00:00"
}
```

---

## 9. Testing Without Hardware (Simulation Mode)

You do not need physical sensors or an ESP32 to test the tamper response. The `simulation` mode lets you trigger tamper from the console.

### 9.1 Enable Simulation

In `config/config.yaml`:

```yaml
hardware_security:
  enabled: true
  mode: "simulation"

zeroization:
  delete_models: false
  shutdown_on_tamper: false    # KEEP FALSE during testing
```

### 9.2 Trigger a Tamper Event

1. Start the PoseVision pipeline normally.
2. In the terminal where the pipeline is running, you will see:
   ```
   Simulation mode: press 'T' + Enter in the console to trigger tamper
   ```
3. Type `T` and press **Enter**.
4. The console will print:
   ```
   CRITICAL TAMPER DETECTED [mode=simulation]
   CRITICAL Pipeline halted by tamper detection
   ```
5. The pipeline window will close and logs will be wiped.

### 9.3 Programmatic Trigger (Unit Tests)

You can also trigger tamper from Python code without any user input:

```python
from core.hardware_monitor import HardwareMonitor

monitor = HardwareMonitor(mode="simulation")

triggered = []
monitor.register_callback(lambda: triggered.append(True))
monitor.start()

# Programmatic trigger — no stdin needed
monitor.trigger_tamper()

assert monitor.is_tamper_detected()
assert len(triggered) == 1

# Second call is a no-op (latching behavior)
monitor.trigger_tamper()
assert len(triggered) == 1

monitor.stop()
```

### 9.4 Verify Logging

After a simulated tamper, check that the event was recorded:

```bash
# Tamper-specific log (if not wiped by zeroization)
cat logs/tamper.log

# VPAP chain (if not wiped)
tail -1 logs/vpap_events.jsonl | python -m json.tool
```

> **Note:** If `shutdown_on_tamper` is `false` and `delete_models` is `false`, only log files are deleted during zeroization. The tamper.log entry is written *before* zeroization runs, so you may see a race where the file is created then immediately deleted.

---

## 10. Safety Notes

### Do Not Enable Shutdown During Development

The `shutdown_on_tamper` flag will immediately power off the system. During development and testing, always set it to `false`:

```yaml
zeroization:
  shutdown_on_tamper: false
```

Only enable it in final production deployments where the device is physically sealed.

### Do Not Enable Model Deletion Unless Necessary

Model weights are large files that require re-download or re-training to restore. Keep `delete_models: false` unless your threat model requires destroying the AI models on tamper:

```yaml
zeroization:
  delete_models: false
```

### GPIO Fallback Behavior

If the config is set to `mode: "gpio"` but the system does not have RPi.GPIO installed (e.g., running on a desktop for development), the hardware monitor automatically falls back to serial mode. If pyserial is also unavailable, an error is logged and the monitor does not start — but the pipeline continues to run normally.

### Latching Behavior

Tamper detection is a one-shot latch. Once triggered:

- The `is_tamper_detected()` flag stays `True` permanently.
- Callbacks fire exactly once.
- The pipeline loop exits and cannot be restarted without a process restart.

This prevents repeated trigger loops and ensures the zeroization sequence runs to completion.

### Power Considerations

If the attacker cuts power to the device, the software response cannot execute. For high-security deployments, add a UPS or supercapacitor to provide enough runtime (~5 seconds) for the zeroization sequence to complete.

---

## 11. Future Improvements

### Battery / UPS Backup

Add a small UPS HAT (e.g., PiSugar, Waveshare UPS HAT) to the Raspberry Pi. Detect power loss as an additional tamper signal and use the battery window to complete zeroization before the system dies.

### Full-Disk Encryption

Use LUKS (Linux Unified Key Setup) for the root filesystem. On tamper, destroy the LUKS header or key slots instead of deleting individual files. This renders the entire disk unrecoverable in one operation, regardless of wear-leveling.

```bash
# Example: destroy LUKS key slot (irreversible)
cryptsetup luksKillSlot /dev/mmcblk0p2 0
```

### Secure Memory Wipe

For RAM-resident secrets (API keys, session tokens), use `ctypes` or `mmap` to explicitly zero memory regions before releasing them. Python's garbage collector does not guarantee immediate memory clearing.

### Hardware Security Module (HSM)

For production deployments handling classified data, integrate a hardware security module (e.g., ATECC608A on I2C) to store encryption keys. The HSM can be configured to auto-zeroize its key storage on tamper, providing hardware-level key destruction independent of the host OS.

### Encrypted Log Storage

Encrypt VPAP log chains at rest using AES-256-GCM with a key stored in the HSM. On tamper, destroying the HSM key renders all historical logs unreadable without needing to overwrite every file.

### Mesh Tamper Detection

For multi-device deployments, add a mesh network (ESP-NOW or BLE) between devices. If one device detects tamper, it broadcasts a tamper alert to all peers, triggering fleet-wide zeroization.

---

## Appendix A: Bill of Materials

| # | Item | Approx. Cost (USD) | Source |
|---|---|---|---|
| 1 | ESP32 DevKit v1 | $4–8 | AliExpress, Amazon |
| 2 | LDR (GL5528 or similar) | $0.50 | Electronics store |
| 3 | 10 kΩ resistors (x3) | $0.30 | Electronics store |
| 4 | Micro limit switch (KW12) | $1.00 | Amazon, AliExpress |
| 5 | NTC 10 kΩ thermistor | $0.50 | Electronics store |
| 6 | Breadboard (half-size) | $2.00 | Amazon |
| 7 | Jumper wire kit | $3.00 | Amazon |
| 8 | Micro-USB cable | $1.50 | Any |
| | **Total** | **~$13** | |

> The Raspberry Pi / Jetson and enclosure are assumed to already be part of your PoseVision deployment.

## Appendix B: Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `RPi.GPIO unavailable — falling back to serial` | Running on non-Pi hardware or `RPi.GPIO` not installed | Install `RPi.GPIO` on Pi, or switch to `mode: "serial"` |
| `pyserial unavailable — cannot start serial monitor` | `pyserial` package not installed | Run `pip install pyserial` |
| Serial port permission denied | User not in `dialout` group | Run `sudo usermod -aG dialout $USER` and re-login |
| ESP32 not detected on `/dev/ttyUSB0` | Wrong port or missing driver | Check `dmesg | tail` after plugging in; install CP2102 driver if needed |
| LDR triggers immediately on boot | Threshold too high for your sensor | Calibrate — see [Section 5.3](#53-tuning-thresholds) |
| Tamper fires but logs are not deleted | `log_dir` path is wrong in config | Verify the path is relative to project root |
| System shuts down during testing | `shutdown_on_tamper` is `true` | Set to `false` — see [Section 10](#10-safety-notes) |
| Callbacks fire but pipeline keeps running | `config` or `project_root` not passed to `run_edge_loop()` | Ensure both keyword arguments are provided |

## Appendix C: Pin Reference Quick Card

```
ESP32 DevKit v1                    Raspberry Pi (BCM)
┌──────────────┐                   ┌──────────────────┐
│              │                   │                  │
│   GPIO34 ◄── LDR divider        │   GPIO17 ◄────── ESP32 GPIO25
│   GPIO27 ◄── Limit switch       │   GND    ◄────── ESP32 GND
│   GPIO35 ◄── Temp sensor        │                  │
│   GPIO25 ──► To RPi GPIO17      │                  │
│   GND    ──► To RPi GND         │                  │
│              │                   │                  │
└──────────────┘                   └──────────────────┘
```
