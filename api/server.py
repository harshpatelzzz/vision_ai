"""FastAPI server: ingest VPAP events, attestation, verification, and hardware security status."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.registry import get_registered_store, get_registered_stream_url
from security.attestation import generate_attestation_report
from security.logger import SecureLogger, VPAPLogger
from security.verification import verify_chain_detail

app = FastAPI(title="PoseVision Edge API", version="1.0.0")

_vpap: Union[VPAPLogger, SecureLogger, None] = None
_hw_monitor: Optional[Any] = None
_logging_yaml_cache: Optional[Dict[str, Any]] = None


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
    """Reserved JSON feed for dashboard polling (populate via future event bus)."""
    _ = limit
    return {"events": [], "note": "Wire EventEngine.recent_events here when wiring dashboard."}


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
    """Placeholder stream hook for future annotated-frame metadata (no MJPEG binary here)."""
    await ws.accept()
    try:
        await ws.send_json({"topic": "live-events", "schema": "reserved"})
        while True:
            await asyncio.sleep(5.0)
            await ws.send_json({"heartbeat": True})
    except WebSocketDisconnect:
        return


def main() -> None:
    import uvicorn

    host = os.environ.get("POSEVISION_API_HOST", "127.0.0.1")
    port = int(os.environ.get("POSEVISION_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
