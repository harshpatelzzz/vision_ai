# RFID Identity Verification + Role-Based Access Control (RBAC)

This module adds an **authorization layer** on top of the existing PoseVision
tripwire intrusion detector. Instead of flagging *every* person in a restricted
zone as an `INTRUSION`, the system now correlates the intrusion with an RFID tag
scan and decides whether the person is **authorized** for that specific zone.

It is **fully additive**: every existing capability — YOLOv8 PPE detection, pose
estimation, posture classification, tripwire, PrivacyGuard, VPAP, blockchain
logging, Merkle verification, RSA signatures, IPFS metadata, ESP32-CAM — is
untouched. When `rfid.enabled: false` (the default) behavior is identical to
before.

---

## 1. Workflow

```
Person enters restricted zone
        ↓
Tripwire triggered  (core.pipeline → intrusion=True)
        ↓
EventEngine._emit_intrusion  →  AccessControl.resolve_intrusion
        ↓
ZoneManager.zone_for_bbox        → which zone (ZoneA/B/C)?
RfidReader.read_uid              → which tag was just scanned?
UserDatabase.get_user            → who is this?
RBACEngine.is_allowed            → is the role permitted here?
        ↓
        ┌──────────────┴───────────────┐
   AUTHORIZED                      NOT AUTHORIZED
        ↓                               ↓
 AUTHORIZED_ACCESS      UNKNOWN_RFID / ZONE_VIOLATION /
                        UNAUTHORIZED_INTRUSION / ACCESS_DENIED
        ↓                               ↓
        └──────────────┬───────────────┘
                       ↓
        VPAP hash chain → Blockchain block
        (SHA256 + Merkle root + RSA signature + IPFS CID)
```

## 2. New event types

| Event | Meaning |
|-------|---------|
| `AUTHORIZED_ACCESS` | Known tag, role permitted in this zone. |
| `UNAUTHORIZED_INTRUSION` | Intrusion with **no** RFID presented (anonymous person). |
| `UNKNOWN_RFID` | A tag was scanned but is **not** in the database. |
| `ZONE_VIOLATION` | Known person, but their role/zone policy forbids this zone. |
| `ACCESS_DENIED` | Raised after `max_consecutive_failures` denials for one tag. |

The legacy `INTRUSION` event is still emitted when the RFID layer is disabled, or
as a defensive fallback if the resolver fails.

## 3. Architecture / files

| File | Responsibility |
|------|----------------|
| `data/authorized_users.json` | UID → `{name, role, allowed_zones}` database. |
| `data/roles.json` | Role → `{allowed_zones, restricted_zones}` policy. |
| `data/authorized_users.schema.json` | JSON Schema for the user database. |
| `security/zone_manager.py` | Maps tripwire polygons to named zones; resolves a bbox → zone. |
| `security/user_database.py` | Thread-safe, atomically-persisted user CRUD. |
| `security/rbac.py` | Role policy engine (`is_allowed`, wildcard `*`, restrictions). |
| `security/access_control.py` | Decision engine + `resolve_intrusion` resolver. |
| `hardware/rfid_reader.py` | MFRC522/ESP32 reader (serial / http / simulation). |
| `hardware/rfid_registry.py` | Process-wide hooks so the API reaches the live reader. |
| `hardware/esp32/rfid_access_control.ino` | ESP32 + MFRC522 firmware. |
| `core/event_engine.py` | New event types + `set_access_resolver` hook (non-breaking). |
| `core/runner.py` | `setup_rfid_stack()` wires the reader + resolver into the loop. |
| `security/logger.py` | `normalize_event_record` preserves the `access` block onto the chain. |
| `api/server.py` | `/rfid/*` REST endpoints. |

### Extensibility (no changes to existing modules)

The resolver hook is a plain callable `Callable[[event], Optional[decision]]`.
Future identity factors — **Face Recognition, MFA, QR access passes, biometrics**
— can be added by composing a new resolver that calls `AccessControl.evaluate`
with a UID obtained from any source, then `engine.set_access_resolver(...)`. The
camera pipeline, blockchain, and APIs require **no** modification.

## 4. Setup guide

1. Install deps (RFID over serial needs `pyserial`, already implied by the
   existing ESP32 telemetry stack):
   ```bash
   pip install -r requirements.txt
   pip install pyserial   # only if not already present
   ```
2. Edit `config/config.yaml` → `rfid:` section:
   ```yaml
   rfid:
     enabled: true
     mode: "serial"          # serial | http | simulation
     serial_port: "COM6"     # Windows; "/dev/ttyUSB1" on Linux
     baudrate: 115200
   ```
3. Define zones under `zones:` (or leave the legacy single `tripwire.polygon`,
   which maps to `default_zone`).
4. Populate `data/authorized_users.json` (directly, or via `POST /rfid/register`).
5. Run the pipeline as usual:
   ```bash
   python scripts/webcam_pipeline.py
   # or ESP32-CAM:
   python scripts/webcam_pipeline.py --source esp32cam --stream-url http://<cam-ip>:81/stream
   ```
6. Start the API for management/telemetry:
   ```bash
   python -m api.server
   ```

### Try it with no hardware

Set `mode: "simulation"` (default). The reader cycles through
`rfid.simulation_uids` (the last one is intentionally unregistered so you can see
an `UNKNOWN_RFID` event). Stand in the tripwire zone and watch the logs / events.

## 5. Wiring guide — ESP32 + MFRC522

MFRC522 is a **3.3 V** SPI device. Do **not** power it from 5 V.

| MFRC522 pin | ESP32 pin |
|-------------|-----------|
| SDA / SS    | GPIO5     |
| SCK         | GPIO18    |
| MOSI        | GPIO23    |
| MISO        | GPIO19    |
| RST         | GPIO27    |
| 3.3V        | 3V3       |
| GND         | GND       |
| IRQ         | (unused)  |

```
 ESP32                    MFRC522
 ┌────────┐              ┌────────┐
 │ 3V3 ●──┼──────────────┤ 3.3V   │
 │ GND ●──┼──────────────┤ GND    │
 │ G5  ●──┼──────────────┤ SDA/SS │
 │ G18 ●──┼──────────────┤ SCK    │
 │ G23 ●──┼──────────────┤ MOSI   │
 │ G19 ●──┼──────────────┤ MISO   │
 │ G27 ●──┼──────────────┤ RST    │
 └────────┘              └────────┘
```

Flash `hardware/esp32/rfid_access_control.ino` (Arduino IDE → board "ESP32 Dev
Module", install the **MFRC522** library). Set `WIFI_SSID`/`WIFI_PASS` and
optionally `EDGE_RFID_URL`. The firmware always prints JSON to Serial as a
fallback and, when WiFi is up, also serves `GET /rfid/last-scan` and POSTs scans
to the edge.

## 6. Communication formats

**Serial / HTTP scan line (ESP32 → edge):**
```json
{"type":"rfid","uid":"A1:B2:C3:D4","reader":"gate-1","rssi":0,"uptime_ms":12345}
```

**Blockchain `access` block (edge → ledger):**
```json
{
  "uid": "A1:B2:C3:D4",
  "name": "Security Guard",
  "role": "Guard",
  "zone": "ZoneA",
  "authorized": true,
  "decision": "AUTHORIZED",
  "event_type": "AUTHORIZED_ACCESS",
  "reason": "role_and_zone_ok",
  "timestamp": "2026-06-20T10:43:32Z"
}
```

## 7. API reference

| Method & path | Description |
|---------------|-------------|
| `GET /rfid/status` | Reader connectivity + access-control statistics. |
| `GET /rfid/users` | The authorized-personnel database. |
| `GET /rfid/access-log?limit=N` | Recent access decisions. |
| `GET /rfid/last-scan` | Most recent tag scanned by the live reader. |
| `POST /rfid/register` | Add/update a tag: `{uid?, name, role, allowed_zones[]}`. Omit `uid` to enroll the last scanned card. |
| `POST /rfid/remove` | Remove a tag: `{uid}`. |

Registration and removal are themselves committed to the VPAP hash chain +
blockchain ledger (`RFID_REGISTER` / `RFID_REMOVE` audit events).

### Registration (enrollment) flow

```
1. Present a new card to the reader.
2. POST /rfid/register  {"name":"Jane","role":"Engineer","allowed_zones":["ZoneA","ZoneB"]}
   (uid is taken from the last scan automatically)
3. The user is persisted to data/authorized_users.json and audited on-chain.
```

## 8. RBAC policy

`allowed_zones` on the **user** is intersected with the **role** policy:

```
effective = user.allowed_zones  (or role.allowed_zones if user lists none)
effective -= role.restricted_zones
authorized = zone in effective        (or role grants "*")
```

| Role | Allowed | Restricted |
|------|---------|-----------|
| Admin | `*` (all) | — |
| Guard | ZoneA, ZoneB, ZoneC | — |
| Engineer | ZoneA, ZoneB | ZoneC |
| Worker | ZoneA | ZoneB, ZoneC |
| Visitor | — | ZoneA, ZoneB, ZoneC |

## 9. Tamper / security alerts

- **Unknown RFID** → `UNKNOWN_RFID` event (logged + on-chain).
- **Zone violation** → `ZONE_VIOLATION` event.
- **Repeated failures** (≥ `max_consecutive_failures` for one tag) →
  `ACCESS_DENIED`, force-appended to the VPAP chain and `logs/tamper.log`.
- **Reader disconnect** → reflected in `GET /rfid/status` (`connected:false`,
  `last_error`); the reader auto-reconnects with backoff.

## 10. Test cases

`tests/test_rfid_access.py` (run `pytest tests/test_rfid_access.py -v`) covers:

- UID normalization (`a1:b2`, `A1-B2`, `A1B2…` → canonical).
- RBAC: worker restriction, admin wildcard, role-restriction overriding personal allow.
- Decisions: authorized, zone violation, unknown tag, anonymous intrusion.
- `ACCESS_DENIED` after repeated failures.
- ZoneManager from config + legacy tripwire fallback.
- Reader dedup + correlation-window expiry + verify/get_user.
- **EventEngine is unchanged without a resolver** (regression guard for the
  "do not break existing functionality" requirement).
- EventEngine refines intrusion → AUTHORIZED_ACCESS / UNKNOWN_RFID with a resolver.
- User DB CRUD + persistence + invalid-role rejection.

Manual end-to-end check (decision → SHA256 + Merkle + RSA + IPFS CID on-chain) is
documented in the project README and verified via `GET /blockchain/verify`.
