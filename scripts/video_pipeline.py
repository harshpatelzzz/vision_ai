"""
Video file pipeline: PoseVision Edge (PPE + pose + tripwire + VPAP).

Uses ``core.pipeline.EdgeVisionPipeline`` and optional hash-chained logging.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Project root (parent of scripts/)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2

from core.config_loader import load_config
from core.event_engine import EventEngine
from core.pipeline import build_pipeline_from_config
from core.runner import run_edge_loop
from security.logger import SecureLogger, VPAPLogger


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PoseVision Edge — video file")
    p.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "config.yaml",
        help="Path to config.yaml",
    )
    p.add_argument("--input", type=Path, help="Input video (overrides config camera.source)")
    p.add_argument("--ppe-weights", type=Path, help="Override PPE model path")
    p.add_argument("--pose-weights", type=Path, help="Override pose model path")
    p.add_argument(
        "--save-video",
        type=Path,
        default=None,
        help="Write annotated MP4 to this path (opt-in; not stored by default)",
    )
    p.add_argument(
        "--vpap-log",
        type=Path,
        default=None,
        help="VPAP JSONL log path (default from config logging.vpap_log_path)",
    )
    p.add_argument("--no-view", action="store_true", help="Do not open preview window")
    p.add_argument("--log-structured", action="store_true", help="Log every per-frame JSON event")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    if args.ppe_weights:
        cfg.setdefault("models", {})["ppe_weights"] = str(args.ppe_weights)
    if args.pose_weights:
        cfg.setdefault("models", {})["pose_weights"] = str(args.pose_weights)

    video_path = args.input
    if video_path is None:
        src = cfg.get("camera", {}).get("source", "")
        if isinstance(src, str) and src.endswith((".mp4", ".avi", ".mkv", ".mov")):
            video_path = ROOT / src
        else:
            video_path = ROOT / "assets/videos/example_workers.mp4"

    video_path = Path(video_path)
    if not video_path.is_file():
        logging.error("Input video not found: %s", video_path)
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

    pipeline = build_pipeline_from_config(ROOT, cfg)
    debounce = int(cfg.get("event_engine", {}).get("debounce_frames", 15))
    event_engine = EventEngine(debounce_frames=debounce)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logging.error("Cannot open video: %s", video_path)
        sys.exit(1)

    save = args.save_video
    if save is None and cfg.get("privacy", {}).get("allow_video_export"):
        save = ROOT / "assets" / "outputs" / video_path.name

    run_edge_loop(
        cap,
        pipeline,
        event_engine,
        vpap,
        view=not args.no_view,
        window_name="PoseVision Edge — Video",
        save_video_path=save,
        log_debounced=True,
        log_structured=args.log_structured,
        config=cfg,
        project_root=ROOT,
    )


if __name__ == "__main__":
    main()
