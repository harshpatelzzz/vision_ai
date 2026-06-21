"""FastAPI server: ingest VPAP events, attestation, verification, and hardware security status."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.registry import get_registered_store, get_registered_stream_url
from hardware.rfid_registry import get_access_control, get_or_build_access_control, get_rfid_reader
from security.attestation import generate_attestation_report
from security.logger import SecureLogger, VPAPLogger, normalize_event_record
from security.verification import verify_chain_detail

app = FastAPI(title="PoseVision Edge API", version="1.0.0")

# Allow the command-center dashboard (Vite dev server / static build) to call the
# edge node from the browser. Override the allowed origins via
# POSEVISION_CORS_ORIGINS (comma-separated) in production; defaults are permissive
# for local/LAN demos. In dev the Vite proxy keeps requests same-origin anyway.
_cors_env = os.environ.get("POSEVISION_CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_vpap: Union[VPAPLogger, SecureLogger, None] = None
_hw_monitor: Optional[Any] = None
_logging_yaml_cache: Optional[Dict[str, Any]] = None
_full_config_cache: Optional[Dict[str, Any]] = None


def _logging_section() -> Dict[str, Any]:
    """Load ``logging`` subsection from ``config/config.yaml`` (cached)."""
    global _logging_yaml_cache
    if _logging_yaml_cache is None:
        cfg_path = ROOT / "config" / "config.yaml"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            _logging_yaml_cache = data.get("logging") or {}
        except (OSError, yaml.YAMLError):
            _logging_yaml_cache = {}
    return _logging_yaml_cache


def _full_config() -> Dict[str, Any]:
    """Load and cache the entire ``config/config.yaml`` (for RFID/zones)."""
    global _full_config_cache
    if _full_config_cache is None:
        cfg_path = ROOT / "config" / "config.yaml"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                _full_config_cache = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            _full_config_cache = {}
    return _full_config_cache


def _access_control() -> Any:
    """Live AccessControl from the running pipeline, else a file-backed instance."""
    return get_or_build_access_control(ROOT, _full_config())


def _live_service() -> Any:
    """Process-wide live vision service (camera -> YOLO -> tracker -> broadcast)."""
    from core.live_service import get_live_service

    return get_live_service(_full_config(), ROOT, vpap=get_vpap())


def _resolve_log_path() -> Path:
    env = os.environ.get("POSEVISION_VPAP_LOG") or os.environ.get("POSEVISION_SECURE_LOG")
    if env:
        return Path(env)
    lg = _logging_section()
    if lg.get("secure"):
        return ROOT / lg.get("log_file", "logs/secure_log.jsonl")
    return ROOT / lg.get("vpap_log_path", "logs/vpap_events.jsonl")


def get_vpap() -> Union[VPAPLogger, SecureLogger]:
    """Singleton logger aligned with ``config.yaml`` secure / legacy settings."""
    global _vpap
    if _vpap is None:
        path = _resolve_log_path()
        lg = _logging_section()
        if lg.get("secure"):
            _vpap = SecureLogger(
                path,
                debounce_seconds=float(lg.get("debounce_seconds", 2.0)),
            )
        else:
            _vpap = VPAPLogger(path)
    return _vpap


def set_hardware_monitor(monitor: Any) -> None:
    """Called at startup to share the HardwareMonitor instance with the API."""
    global _hw_monitor
    _hw_monitor = monitor


@app.post("/event")
def post_event(body: Dict[str, Any]) -> Dict[str, Any]:
    """Append a client-supplied event to the VPAP hash chain."""
    try:
        vp = get_vpap()
        if isinstance(vp, SecureLogger):
            rec = vp.log_event(body, force=True)
        else:
            rec = vp.append(body)
        return {"status": "ok", "record": rec}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/verify")
def verify_chain() -> Dict[str, Any]:
    """Verify the on-disk VPAP / secure JSONL chain for tampering."""
    vp = get_vpap()
    log_path = vp.log_path
    ok, corrupt_idx, n = verify_chain_detail(log_path)
    out: Dict[str, Any] = {
        "status": "valid" if ok else "tampered",
        "checked_entries": n,
    }
    if not ok and corrupt_idx is not None:
        out["corrupt_line_index"] = corrupt_idx
    return out


@app.get("/blockchain")
def blockchain_summary() -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    return vp.blockchain_summary()


@app.get("/blockchain/verify")
def blockchain_verify() -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    return vp.verify_blockchain()


@app.get("/block/{index}")
def get_block(index: int) -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    block = vp.get_block(index)
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")
    return block


@app.get("/merkle/root")
def get_merkle_root() -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    return {"merkle_root": vp.latest_merkle_root()}


@app.get("/nodes")
def get_nodes() -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    return vp.node_status()


@app.get("/ipfs/{cid}")
def get_ipfs(cid: str) -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    try:
        return vp.get_ipfs_metadata(cid)
    except KeyError:
        raise HTTPException(status_code=404, detail="CID not found") from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/tamper/simulate")
def tamper_simulate() -> Dict[str, Any]:
    vp = get_vpap()
    if not isinstance(vp, SecureLogger):
        raise HTTPException(status_code=400, detail="blockchain available only in secure logging mode")
    try:
        return vp.simulate_tamper()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/attestation")
def get_attestation() -> Dict[str, Any]:
    """Return SHA-256 integrity report for models and pipeline scripts."""
    cfg_att = os.environ.get("POSEVISION_ATTEST_GLOB_MODELS")
    models = None
    scripts = None
    if cfg_att:
        models = [cfg_att]
    return generate_attestation_report(ROOT, model_globs=models, script_globs=scripts)


@app.get("/security/status")
def security_status() -> Dict[str, Any]:
    """Return hardware tamper detection status."""
    if _hw_monitor is None:
        return {
            "tamper_detected": False,
            "hardware_security_enabled": False,
            "last_event": None,
        }

    status = _hw_monitor.get_status()
    return {
        "tamper_detected": status["tamper_detected"],
        "hardware_security_enabled": True,
        "mode": status["mode"],
        "monitor_running": status["monitor_running"],
        "last_event": status["last_tamper_time"],
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------------
# RFID / RBAC access control
# --------------------------------------------------------------------------
@app.get("/rfid/status")
def rfid_status() -> Dict[str, Any]:
    """Reader connectivity + access-control statistics."""
    reader = get_rfid_reader()
    ac = get_access_control()
    return {
        "reader": reader.status() if reader is not None else {"running": False, "mode": "offline"},
        "access_control": ac.stats() if ac is not None else _access_control().stats(),
    }


@app.get("/rfid/users")
def rfid_users() -> Dict[str, Any]:
    """List the authorized-personnel database (UID -> profile)."""
    ac = _access_control()
    users = ac.user_db.all_users()
    return {"count": len(users), "users": users}


@app.get("/rfid/access-log")
def rfid_access_log(limit: int = 100) -> Dict[str, Any]:
    """Recent access decisions (AUTHORIZED_ACCESS / ZONE_VIOLATION / ...)."""
    ac = _access_control()
    return {"events": ac.recent_access_log(limit=limit)}


@app.get("/rfid/last-scan")
def rfid_last_scan() -> Dict[str, Any]:
    """Most recent tag scanned by the live reader."""
    reader = get_rfid_reader()
    if reader is None:
        return {"last_scan": None, "reader_running": False}
    return {"last_scan": reader.last_scan(), "reader_running": True}


@app.post("/rfid/register")
def rfid_register(body: Dict[str, Any]) -> Dict[str, Any]:
    """Register / update a tag. Body: {uid, name, role, allowed_zones:[...]}.

    When ``uid`` is omitted, the last tag scanned by the live reader is used
    (hardware enrollment flow: present card, then POST name/role/zones).
    """
    ac = _access_control()
    uid = body.get("uid")
    if not uid:
        reader = get_rfid_reader()
        scan = reader.last_scan() if reader is not None else None
        uid = scan.get("uid") if scan else None
    if not uid:
        raise HTTPException(status_code=400, detail="uid required (or scan a card first)")
    try:
        user = ac.user_db.add_user(
            uid=str(uid),
            name=str(body.get("name", "")),
            role=str(body.get("role", "")),
            allowed_zones=[str(z) for z in (body.get("allowed_zones") or [])],
            overwrite=bool(body.get("overwrite", True)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    user_out = {**user.to_dict(), "uid": user.uid}
    record = _audit_registration("RFID_REGISTER", dict(user_out))
    return {"status": "ok", "user": user_out, "audit": record}


@app.post("/rfid/remove")
def rfid_remove(body: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a tag from the database. Body: {uid}."""
    ac = _access_control()
    uid = body.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="uid required")
    removed = ac.user_db.remove_user(str(uid))
    if not removed:
        raise HTTPException(status_code=404, detail="uid not found")
    record = _audit_registration("RFID_REMOVE", {"uid": str(uid)})
    return {"status": "ok", "removed": str(uid), "audit": record}


def _audit_registration(action: str, detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Append registration changes to the VPAP hash chain + blockchain ledger."""
    try:
        vp = get_vpap()
        observation = {
            "timestamp": "",
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "ppe": {"helmet": False, "vest": False},
            "posture": "Unknown",
            "intrusion": False,
            "access": {**detail, "action": action},
        }
        rec = normalize_event_record(alert_type=action, person_id=-1, observation=observation)
        if isinstance(vp, SecureLogger):
            return vp.log_event(rec, force=True)
        return vp.append(rec)
    except Exception:
        return None


@app.get("/hardware/status")
def hardware_status() -> Dict[str, Any]:
    """Combined edge snapshot: VPAP tip hash, optional ESP32 telemetry registration."""
    vp = get_vpap()
    tip = ""
    try:
        tip = str(getattr(vp, "prev_hash", "") or "")
    except Exception:
        tip = ""
    store = get_registered_store()
    env_stream = os.environ.get("POSEVISION_ESP32_STREAM_URL", "")
    return {
        "prev_hash_prefix": tip[:24],
        "telemetry_registered": store is not None,
        "stream_url_configured": bool(get_registered_stream_url() or env_stream),
        "websocket_hooks": ["/ws/telemetry", "/ws/live-events"],
    }


@app.get("/hardware/sensors")
def hardware_sensors() -> Dict[str, Any]:
    store = get_registered_store()
    if store is None:
        return {"connected": False, "last": {}}
    snap = store.snapshot()
    return {"connected": bool(snap.get("_connected")), "last": snap}


@app.get("/hardware/stream")
def hardware_stream() -> Dict[str, str]:
    env_u = os.environ.get("POSEVISION_ESP32_STREAM_URL", "")
    reg = get_registered_stream_url()
    url = env_u or reg
    return {"stream_url": url, "hint": "OpenCV captures MJPEG from this HTTP URL (ESP32-CAM). "}


@app.get("/hardware/tamper")
def hardware_tamper() -> Dict[str, Any]:
    sec = security_status()
    store = get_registered_store()
    tel_tamper = None
    if store is not None:
        tel_tamper = store.snapshot().get("tamper")
    return {
        "hardware_monitor": sec,
        "sensor_telemetry_tamper": tel_tamper,
    }


@app.post("/hardware/reset")
def hardware_reset() -> Dict[str, str]:
    store = get_registered_store()
    if store is not None:
        store.reset()
    return {"status": "ok"}


@app.post("/hardware/telemetry-ingest")
def hardware_telemetry_ingest(body: Dict[str, Any]) -> Dict[str, str]:
    """Push JSON sensor samples into the registered :class:`TelemetryStore` (edge daemon)."""
    store = get_registered_store()
    if store is None:
        raise HTTPException(status_code=503, detail="telemetry store not registered")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    store.update(body)
    return {"status": "ok"}


@app.get("/hardware/live-events")
def hardware_live_events(limit: int = 50) -> Dict[str, Any]:
    """Live detections snapshot (JSON poll fallback for the WebSocket feed)."""
    _ = limit
    return _live_service().detections_payload()


# --------------------------------------------------------------------------
# Live vision pipeline (real YOLO + tracker) — drives the dashboard Live page.
# --------------------------------------------------------------------------
@app.post("/live/start")
def live_start(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start the camera→AI→tracker loop. Body: {source:"webcam"|"esp32", stream_url?}."""
    body = body or {}
    source = str(body.get("source", "webcam"))
    stream_url = body.get("stream_url")
    try:
        return _live_service().start(source=source, stream_url=stream_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/live/stop")
def live_stop() -> Dict[str, Any]:
    return _live_service().stop()


@app.get("/live/status")
def live_status() -> Dict[str, Any]:
    return _live_service().status()


@app.get("/live/detections")
def live_detections() -> Dict[str, Any]:
    return _live_service().detections_payload()


@app.get("/video/stream")
def video_stream() -> StreamingResponse:
    """MJPEG stream of the annotated live frame (memory-only; nothing persisted).

    Does NOT start the camera itself — the dashboard calls /live/start with the
    chosen source first, so webcam/ESP32 selection is never overridden here.
    """
    svc = _live_service()

    def gen():
        boundary = b"--frame"
        idle = 0
        while True:
            jpeg = svc.latest_jpeg()
            if jpeg is None:
                idle += 1
                # give up after ~12s of no frames (service idle / camera busy)
                if idle > 240 and not svc.is_running():
                    break
                time.sleep(0.05)
                continue
            idle = 0
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            time.sleep(1.0 / 20.0)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            store = get_registered_store()
            payload: Dict[str, Any] = {"telemetry": {}}
            if store is not None:
                payload["telemetry"] = store.snapshot()
            payload["stream_url"] = os.environ.get("POSEVISION_ESP32_STREAM_URL", get_registered_stream_url())
            await ws.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/live-events")
async def ws_live_events(ws: WebSocket) -> None:
    """Real-time per-person detections from the live vision service (tracked IDs)."""
    await ws.accept()
    svc = _live_service()
    try:
        while True:
            await ws.send_json(svc.detections_payload())
            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        return
    except Exception:
        return


def main() -> None:
    import uvicorn

    host = os.environ.get("POSEVISION_API_HOST", "127.0.0.1")
    port = int(os.environ.get("POSEVISION_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
