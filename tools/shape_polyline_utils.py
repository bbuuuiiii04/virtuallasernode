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
    if not polylines:
        return False
    anchor_kinds = {"dot_anchor_points", "segment_anchor_points"}
    if all((poly.get("geometry_kind") in anchor_kinds or len(poly.get("points") or []) == 1) for poly in polylines):
        return len(polylines) >= 2
    for poly in polylines:
        pts = poly.get("points") or []
        if len(pts) < 2:
            continue
        if not polyline_is_only_bbox_corners(pts, source_pixel_bbox, box):
            if len(pts) >= 3:
                return True
            if not poly.get("closed") and polyline_span_ratio(pts) >= 3.0:
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


def polyline_point_span(points: Sequence[Sequence[float]]) -> tuple[float, float]:
    xs = [p[0] for p in points if len(p) >= 2]
    ys = [p[1] for p in points if len(p) >= 2]
    if not xs:
        return 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys)


def polyline_is_broad_outer_contour(
    poly: dict[str, Any],
    *,
    core_span_x: float,
    core_span_y: float,
    soft_span_x: float,
    soft_span_y: float,
    min_ratio: float = 0.82,
) -> bool:
    """True when a closed contour spans nearly the full soft glow, not the tight core."""
    if not poly.get("closed"):
        return False
    if poly.get("source") == "skeleton":
        return False
    pts = poly.get("points") or []
    if len(pts) < 6:
        return False
    px, py = polyline_point_span(pts)
    if soft_span_x <= 0 or soft_span_y <= 0:
        return False
    if core_span_x <= 0 or core_span_y <= 0:
        return False
    x_fill = px / soft_span_x
    y_fill = py / soft_span_y
    core_vs_soft_x = core_span_x / max(soft_span_x, 1e-9)
    core_vs_soft_y = core_span_y / max(soft_span_y, 1e-9)
    return (
        x_fill >= min_ratio
        and y_fill >= min_ratio
        and (core_vs_soft_x < 0.72 or core_vs_soft_y < 0.72)
    )


def polyline_is_fat_closed_band(poly: dict[str, Any], *, max_cross_ratio: float = 0.35) -> bool:
    """True when a closed polyline spans both axes like a glow band, not a thin stroke."""
    if not poly.get("closed"):
        return False
    pts = poly.get("points") or []
    if len(pts) < 4:
        return False
    px, py = polyline_point_span(pts)
    long_side = max(px, py)
    if long_side <= 0:
        return False
    return min(px, py) / long_side >= max_cross_ratio


def polyline_is_thin_centerline(
    poly: dict[str, Any], *, max_cross_ratio: float = 0.28
) -> bool:
    pts = poly.get("points") or []
    if len(pts) < 2:
        return False
    if poly.get("closed"):
        return False
    px, py = polyline_point_span(pts)
    long_side = max(px, py)
    if long_side <= 0:
        return False
    return min(px, py) / long_side <= max_cross_ratio


def point_dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
