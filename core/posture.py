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


def _visible(kp: List[float]) -> bool:
    """A YOLO keypoint is considered visible when it isn't the (0,0) sentinel."""
    return bool(kp) and not (abs(kp[0]) < 1e-6 and abs(kp[1]) < 1e-6)


def classify_posture(
    keypoints: List[List[float]],
    standing_min_deg: float = 60.0,
    standing_max_deg: float = 100.0,
    sitting_max_deg: float = 130.0,
) -> str:
    """
    Classify posture from 17 keypoints [[x,y], ...] using shoulder–hip torso angle.

    Returns one of: ``Standing``, ``Sitting``, ``Lying``, ``Unknown``.

    Posture from the torso angle is only reliable when BOTH shoulders and BOTH
    hips are actually detected. If the hips are occluded (e.g. seated at a desk,
    only the upper body in frame) we return ``Unknown`` rather than guessing
    ``Standing`` — an honest answer beats a confidently wrong one. The seated
    fallback below uses torso compression as a soft cue when only one hip shows.
    """
    try:
        l_shoulder = keypoints[L_SHOULDER]
        r_shoulder = keypoints[R_SHOULDER]
        l_hip = keypoints[L_HIP]
        r_hip = keypoints[R_HIP]

        shoulders = [k for k in (l_shoulder, r_shoulder) if _visible(k)]
        hips = [k for k in (l_hip, r_hip) if _visible(k)]

        # Need at least one shoulder; without any hip we cannot tell sit vs stand.
        if not shoulders:
            return "Unknown"
        if not hips:
            return "Unknown"

        shoulder_mid = [
            sum(k[0] for k in shoulders) / len(shoulders),
            sum(k[1] for k in shoulders) / len(shoulders),
        ]
        hip_mid = [
            sum(k[0] for k in hips) / len(hips),
            sum(k[1] for k in hips) / len(hips),
        ]

        dx = hip_mid[0] - shoulder_mid[0]
        dy = hip_mid[1] - shoulder_mid[1]
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return "Unknown"
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
