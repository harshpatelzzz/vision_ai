"""
Webcam pipeline: PoseVision Edge (PPE + pose + tripwire + VPAP).

Frames stay in RAM except optional explicit ``--save-video`` export.

Supports ``--source esp32cam`` with ``--stream-url`` for ESP32-CAM MJPEG (OpenCV FFMPEG).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2

from core.config_loader import load_config
from core.event_engine import EventEngine
from core.pipeline import build_pipeline_from_config
from core.runner import run_edge_loop
from core.stream_capture import RobustHttpStreamCapture
from security.logger import SecureLogger, VPAPLogger


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PoseVision Edge — webcam / ESP32-CAM")
    p.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "config.yaml",
        help="Path to config.yaml",
    )
    p.add_argument(
        "--source",
        type=str,
        default=None,
        help='Camera index (int), or "esp32cam" for HTTP MJPEG stream',
    )
    p.add_argument(
        "--stream-url",
        type=str,
        default=None,
        help="ESP32-CAM MJPEG URL e.g. http://192.168.1.42:81/stream",
    )
    p.add_argument("--ppe-weights", type=Path, help="Override PPE model path")
    p.add_argument("--pose-weights", type=Path, help="Override pose model path")
    p.add_argument(
        "--save-video",
        type=Path,
        default=None,
        help="Optional path to save annotated stream (opt-in)",
    )
    p.add_argument(
        "--vpap-log",
        type=Path,
        default=None,
        help="VPAP JSONL log path",
    )
    p.add_argument("--no-view", action="store_true", help="Do not show preview window")
    p.add_argument("--log-structured", action="store_true", help="Log per-frame JSON events")
    p.add_argument(
        "--target-fps",
        type=float,
        default=None,
        help="Cap processing FPS for latency-stable ESP32 streams",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if args.ppe_weights:
        cfg.setdefault("models", {})["ppe_weights"] = str(args.ppe_weights)
    if args.pose_weights:
        cfg.setdefault("models", {})["pose_weights"] = str(args.pose_weights)

    cam_cfg = cfg.get("camera", {})
    src_arg = args.source if args.source is not None else cam_cfg.get("source", 0)

    stream_url = args.stream_url or os.environ.get("POSEVISION_ESP32_STREAM_URL")
    use_esp32 = str(src_arg).lower() == "esp32cam"

    if use_esp32:
        if not stream_url:
            stream_url = cam_cfg.get("esp32_stream_url")
        if not stream_url:
            logging.error("ESP32-CAM requires --stream-url or camera.esp32_stream_url in config")
            sys.exit(1)
        try:
            from hardware.registry import register_live_hardware

            register_live_hardware(store=None, stream_url=str(stream_url))
        except Exception:
            pass
        cap: cv2.VideoCapture = RobustHttpStreamCapture(  # type: ignore[assignment]
            str(stream_url),
            reconnect_delay_s=float(cam_cfg.get("esp32_reconnect_delay_s", 2.0)),
            open_timeout_ms=int(cam_cfg.get("esp32_open_timeout_ms", 8000)),
            read_retries=int(cam_cfg.get("esp32_read_retries", 5)),
            buffer_size=int(cam_cfg.get("esp32_buffer_size", 1)),
        )
    else:
        try:
            src = int(src_arg)
        except (TypeError, ValueError):
            src = 0
        use_dshow = bool(cam_cfg.get("prefer_dshow", True)) and sys.platform == "win32"
        api = cv2.CAP_DSHOW if use_dshow else cv2.CAP_ANY
        cap = cv2.VideoCapture(src, api)
        if not cap.isOpened() and use_dshow:
            logging.warning("Webcam failed with DirectShow; retrying default backend")
            cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        logging.error("Cannot open video source")
        sys.exit(1)

    log_cfg = cfg.get("logging", {})
    if bool(log_cfg.get("secure", False)):
        log_path = args.vpap_log or (ROOT / log_cfg.get("log_file", "logs/secure_log.jsonl"))
        vpap = SecureLogger(
            Path(log_path),
            debounce_seconds=float(log_cfg.get("debounce_seconds", 2.0)),
        )
    else:
        legacy = args.vpap_log or (ROOT / log_cfg.get("vpap_log_path", "logs/vpap_events.jsonl"))
        vpap = VPAPLogger(Path(legacy))

    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    root_log = logging.getLogger()
    root_log.setLevel(logging.INFO)
    root_log.handlers.clear()
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(log_format))
    root_log.addHandler(sh)
    fh = logging.FileHandler(ROOT / "logs" / "posevision_console.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(log_format))
    root_log.addHandler(fh)

    if not args.no_view:
        win = "PoseVision Edge — Webcam"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        ret0, warm = cap.read()
        if ret0 and warm is not None:
            msg = "Loading YOLO models (first time can take 30-90s)..."
            cv2.putText(
                warm,
                msg,
                (10, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 220, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(win, warm)
            cv2.waitKey(1)
            logging.info("%s Preview will update after models load.", msg)
        else:
            logging.warning("Could not read warmup frame; preview may delay until first inference.")

    pipeline = build_pipeline_from_config(ROOT, cfg)
    debounce = int(cfg.get("event_engine", {}).get("debounce_frames", 15))
    event_engine = EventEngine(debounce_frames=debounce)

    save = args.save_video
    if save is None and cfg.get("privacy", {}).get("allow_video_export"):
        save = ROOT / "assets" / "outputs" / "webcam_session.mp4"

    tf = args.target_fps
    if tf is None and use_esp32:
        tf = float(cam_cfg.get("esp32_target_fps", 12.0))

    run_edge_loop(
        cap,
        pipeline,
        event_engine,
        vpap,
        view=not args.no_view,
        window_name="PoseVision Edge — Webcam",
        save_video_path=save,
        log_debounced=True,
        log_structured=args.log_structured,
        config=cfg,
        project_root=ROOT,
        target_fps=tf,
    )


if __name__ == "__main__":
    main()
