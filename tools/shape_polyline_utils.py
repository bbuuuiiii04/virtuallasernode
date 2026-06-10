"""PR-G1 polyline quality helpers (shared by tests and extraction)."""

from __future__ import annotations

import math
from typing import Any, Sequence

from tools.shape_extraction import FixtureBox, bbox_wall_norm_from_pixel_bbox, pixel_to_wall_norm


def bbox_corner_points_wall_norm(
    px0: float, py0: float, px1: float, py1: float, box: FixtureBox
) -> list[list[float]]:
    return [
        list(pixel_to_wall_norm(px0, py0, box)),
        list(pixel_to_wall_norm(px1, py0, box)),
        list(pixel_to_wall_norm(px1, py1, box)),
        list(pixel_to_wall_norm(px0, py1, box)),
        list(pixel_to_wall_norm(px0, py0, box)),
    ]


def polyline_is_only_bbox_corners(
    points: Sequence[Sequence[float]],
    source_pixel_bbox: Sequence[float],
    box: FixtureBox,
    *,
    tol: float = 1e-3,
) -> bool:
    if len(points) < 4:
        return False
    if len(source_pixel_bbox) != 4:
        return False
    px0, py0, px1, py1 = source_pixel_bbox
    corners = bbox_corner_points_wall_norm(px0, py0, px1, py1, box)
    if len(points) not in (4, 5):
        return False
    for pt, corner in zip(points, corners):
        if len(pt) < 2:
            return False
        if abs(pt[0] - corner[0]) > tol or abs(pt[1] - corner[1]) > tol:
            return False
    return True


def polylines_are_real_geometry(
    polylines: list[dict[str, Any]],
    source_pixel_bbox: Sequence[float],
    box: FixtureBox,
) -> bool:
    """Return True when at least one polyline is not bbox-corner-only."""
    if not polylines:
        return False
    for poly in polylines:
        pts = poly.get("points") or []
        if len(pts) < 3:
            continue
        if not polyline_is_only_bbox_corners(pts, source_pixel_bbox, box):
            return True
    return False


def polyline_span_ratio(points: Sequence[Sequence[float]]) -> float:
    xs = [p[0] for p in points if len(p) >= 2]
    ys = [p[1] for p in points if len(p) >= 2]
    if not xs:
        return 0.0
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return max(w, h) / max(1e-9, min(w, h))

def point_dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
