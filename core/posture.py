"""Torso-angle posture classification from YOLO pose keypoints."""

from __future__ import annotations

import math
from typing import Any, List, Tuple

# COCO 17 keypoint indices (Ultralytics YOLO pose)
NOSE = 0
L_SHOULDER, R_SHOULDER = 5, 6
L_HIP, R_HIP = 11, 12
L_ANKLE, R_ANKLE = 15, 16


def euclidean(p1: Tuple[float, ...], p2: Tuple[float, ...]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def classify_posture(
    keypoints: List[List[float]],
    standing_min_deg: float = 60.0,
    standing_max_deg: float = 100.0,
    sitting_max_deg: float = 130.0,
) -> str:
    """
    Classify posture from 17 keypoints [[x,y], ...] using shoulder–hip torso angle.

    Returns one of: ``Standing``, ``Sitting``, ``Lying``, ``Unknown``.
    """
    try:
        l_shoulder = keypoints[L_SHOULDER]
        r_shoulder = keypoints[R_SHOULDER]
        l_hip = keypoints[L_HIP]
        r_hip = keypoints[R_HIP]

        shoulder_mid = [
            (l_shoulder[0] + r_shoulder[0]) / 2,
            (l_shoulder[1] + r_shoulder[1]) / 2,
        ]
        hip_mid = [
            (l_hip[0] + r_hip[0]) / 2,
            (l_hip[1] + r_hip[1]) / 2,
        ]

        dx = hip_mid[0] - shoulder_mid[0]
        dy = hip_mid[1] - shoulder_mid[1]
        torso_angle = abs(math.degrees(math.atan2(dy, dx)))

        if standing_min_deg <= torso_angle < standing_max_deg:
            return "Standing"
        if standing_max_deg <= torso_angle < sitting_max_deg:
            return "Sitting"
        if torso_angle >= sitting_max_deg:
            return "Lying"
        return "Unknown"
    except (IndexError, TypeError, ValueError, ZeroDivisionError):
        return "Unknown"


def normalize_posture_label(raw: str) -> str:
    """Map legacy labels to canonical names."""
    if raw in ("Lying/Fallen", "Lying"):
        return "Lying"
    return raw
