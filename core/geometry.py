"""Geometry helpers: IoU and point-in-polygon for association and tripwire."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import cv2
import numpy as np

BBox = Tuple[float, float, float, float]


def bbox_area(box: BBox) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def intersection_area_xyxy(a: BBox, b: BBox) -> float:
    """Intersection area for axis-aligned boxes ``(x1,y1,x2,y2)``."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    return iw * ih


def inside_ratio_xyxy(outer: BBox, inner: BBox) -> float:
    """
    Ratio of ``inner`` covered by ``outer`` (intersection / area(inner)).

    Useful for tiny PPE boxes (helmet/vest) inside large person boxes where IoU
    alone is very small.
    """
    denom = bbox_area(inner)
    if denom <= 0:
        return 0.0
    return float(intersection_area_xyxy(outer, inner) / denom)


def iou_xyxy(a: BBox, b: BBox) -> float:
    """Intersection-over-union for axis-aligned boxes ``(x1,y1,x2,y2)``."""
    inter = intersection_area_xyxy(a, b)
    if inter <= 0:
        return 0.0
    area_a = bbox_area(a)
    area_b = bbox_area(b)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def bbox_center(box: BBox) -> Tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def point_inside_polygon(
    point: Tuple[float, float],
    polygon_xy: Sequence[Sequence[float]],
) -> bool:
    """
    Return True if ``point`` is inside or on the edge of ``polygon_xy``.

    Uses ``cv2.pointPolygonTest`` (positive = inside, zero = on edge).
    """
    if len(polygon_xy) < 3:
        return False
    cnt = np.array(polygon_xy, dtype=np.float32).reshape(-1, 1, 2)
    res = cv2.pointPolygonTest(cnt, (float(point[0]), float(point[1])), False)
    return res >= 0
