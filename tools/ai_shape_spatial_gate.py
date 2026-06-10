"""Spatial sanity checks for AI extraction authority against local laser pixels."""

from __future__ import annotations

import math
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

from tools.shape_laser_maps import build_laser_maps

DEFAULT_SPATIAL_LASER_THRESHOLD_K = 3.5
DEFAULT_MIN_OVERLAP_RATIO = 0.30
DEFAULT_PROXIMITY_RADIUS_PX = 10
DEFAULT_MAX_CENTER_DISTANCE_RATIO = 0.18
DEFAULT_MIN_CENTER_DISTANCE_PX = 48


def build_laser_pixel_mask(
    crop: Image.Image,
    *,
    threshold_k: float = DEFAULT_SPATIAL_LASER_THRESHOLD_K,
) -> list[list[bool]]:
    """Bright/saturated laser mask inside crop; ignores dark wall background."""
    w, h = crop.size
    pixels = crop.load()
    maps = build_laser_maps(pixels, w, h)
    if not maps.values:
        return [[False] * w for _ in range(h)]
    threshold = maps.med + threshold_k * maps.mad
    return [[maps.combined_laser_score[y][x] >= threshold for x in range(w)] for y in range(h)]


def iter_geometry_sample_points(validated: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for path in validated.get("paths_px") or []:
        if not path:
            continue
        for pt in path:
            points.append((float(pt[0]), float(pt[1])))
        for idx in range(len(path) - 1):
            x0, y0 = float(path[idx][0]), float(path[idx][1])
            x1, y1 = float(path[idx + 1][0]), float(path[idx + 1][1])
            span = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, int(span // 4))
            for step in range(steps + 1):
                t = step / steps
                points.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    for pt in validated.get("dot_anchors_px") or []:
        points.append((float(pt[0]), float(pt[1])))
    for segment in validated.get("segment_anchors_px") or []:
        if len(segment) != 2:
            continue
        a = (float(segment[0][0]), float(segment[0][1]))
        b = (float(segment[1][0]), float(segment[1][1]))
        points.extend([a, b, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)])
    return points


def _mask_centroid_and_count(mask: list[list[bool]]) -> tuple[float, float, int] | None:
    xs: list[float] = []
    ys: list[float] = []
    for y, row in enumerate(mask):
        for x, hit in enumerate(row):
            if hit:
                xs.append(float(x))
                ys.append(float(y))
    if not xs:
        return None
    return sum(xs) / len(xs), sum(ys) / len(ys), len(xs)


def _point_near_mask(x: float, y: float, mask: list[list[bool]], radius: int) -> bool:
    h = len(mask)
    w = len(mask[0]) if h else 0
    xi = int(round(x))
    yi = int(round(y))
    if 0 <= xi < w and 0 <= yi < h and mask[yi][xi]:
        return True
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > r2:
                continue
            nx, ny = xi + dx, yi + dy
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx]:
                return True
    return False


def explain_spatial_authority_mismatch(
    validated: dict[str, Any],
    laser_mask: list[list[bool]],
    *,
    min_overlap_ratio: float = DEFAULT_MIN_OVERLAP_RATIO,
    proximity_radius_px: int = DEFAULT_PROXIMITY_RADIUS_PX,
    max_center_distance_ratio: float = DEFAULT_MAX_CENTER_DISTANCE_RATIO,
    min_center_distance_px: int = DEFAULT_MIN_CENTER_DISTANCE_PX,
) -> str | None:
    """Return a spatial gate reason when geometry does not overlap local laser pixels."""
    samples = iter_geometry_sample_points(validated)
    if not samples:
        return None

    h = len(laser_mask)
    w = len(laser_mask[0]) if h else 0
    mask_stats = _mask_centroid_and_count(laser_mask)
    if mask_stats is None:
        return "spatial_mismatch_no_laser_overlap"

    near_count = sum(
        1 for x, y in samples if _point_near_mask(x, y, laser_mask, proximity_radius_px)
    )
    if near_count == 0:
        return "spatial_mismatch_no_laser_overlap"

    overlap_ratio = near_count / len(samples)
    if overlap_ratio < min_overlap_ratio:
        return f"spatial_mismatch_low_overlap_ratio={overlap_ratio:.3f}"

    laser_cx, laser_cy, _ = mask_stats
    geom_cx = sum(x for x, _ in samples) / len(samples)
    geom_cy = sum(y for _, y in samples) / len(samples)
    center_dist = math.hypot(geom_cx - laser_cx, geom_cy - laser_cy)
    max_center_dist = max(min_center_distance_px, max_center_distance_ratio * min(w, h))
    if center_dist > max_center_dist:
        return "spatial_mismatch_bbox_far_from_laser"
    return None
