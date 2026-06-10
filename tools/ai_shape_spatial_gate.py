"""Spatial sanity checks for AI extraction authority against local laser pixels."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

from tools.shape_laser_maps import build_laser_maps

DEFAULT_GLOW_THRESHOLD_K = 3.5
DEFAULT_CORE_THRESHOLD_K = 5.2
DEFAULT_STRICT_CORE_DELTA_K = 2.0
DEFAULT_CORE_DILATE_RADIUS_PX = 3
DEFAULT_MIN_CORE_OVERLAP_RATIO = 0.45
DEFAULT_MIN_CLOSED_LOOP_CORE_OVERLAP_RATIO = 0.50
DEFAULT_MAX_Y_OFFSET_PX = 12.0
DEFAULT_Y_BBOX_TOLERANCE_PX = 8


@dataclass(frozen=True)
class LaserSpatialMasks:
    core: list[list[bool]]
    glow: list[list[bool]]
    strict_core: list[list[bool]]
    core_dilated: list[list[bool]]


def _score_masks(
    maps: Any,
    *,
    core_k: float,
    glow_k: float,
) -> tuple[list[list[bool]], list[list[bool]]]:
    w, h = maps.w, maps.h
    if not maps.values:
        empty = [[False] * w for _ in range(h)]
        return empty, empty
    core_thr = maps.med + core_k * maps.mad
    glow_thr = maps.med + glow_k * maps.mad
    core = [[maps.combined_laser_score[y][x] >= core_thr for x in range(w)] for y in range(h)]
    glow = [[maps.combined_laser_score[y][x] >= glow_thr for x in range(w)] for y in range(h)]
    return core, glow


def _dilate_mask(mask: list[list[bool]], radius: int) -> list[list[bool]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    if radius <= 0:
        return [row[:] for row in mask]
    out = [[False] * w for _ in range(h)]
    r2 = radius * radius
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy > r2:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        out[ny][nx] = True
    return out


def build_laser_spatial_masks(
    crop: Image.Image,
    *,
    core_k: float = DEFAULT_CORE_THRESHOLD_K,
    glow_k: float = DEFAULT_GLOW_THRESHOLD_K,
    strict_core_delta_k: float = DEFAULT_STRICT_CORE_DELTA_K,
    core_dilate_radius_px: int = DEFAULT_CORE_DILATE_RADIUS_PX,
) -> LaserSpatialMasks:
    """Build separate laser-core and glow masks; core_dilated supports closed-loop overlap."""
    w, h = crop.size
    pixels = crop.load()
    maps = build_laser_maps(pixels, w, h)
    core, glow = _score_masks(maps, core_k=core_k, glow_k=glow_k)
    if not maps.values:
        empty = [[False] * w for _ in range(h)]
        return LaserSpatialMasks(core=empty, glow=empty, strict_core=empty, core_dilated=empty)
    strict_thr = maps.med + (core_k + strict_core_delta_k) * maps.mad
    strict_core = [
        [maps.combined_laser_score[y][x] >= strict_thr for x in range(w)] for y in range(h)
    ]
    core_dilated = _dilate_mask(core, core_dilate_radius_px)
    return LaserSpatialMasks(core=core, glow=glow, strict_core=strict_core, core_dilated=core_dilated)


def build_laser_pixel_mask(
    crop: Image.Image,
    *,
    threshold_k: float = DEFAULT_GLOW_THRESHOLD_K,
) -> list[list[bool]]:
    """Backward-compatible glow mask accessor."""
    return build_laser_spatial_masks(crop, glow_k=threshold_k, core_k=DEFAULT_CORE_THRESHOLD_K).glow


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


def _mask_y_range(mask: list[list[bool]]) -> tuple[int, int] | None:
    ys = [y for y, row in enumerate(mask) for x, hit in enumerate(row) if hit]
    if not ys:
        return None
    return min(ys), max(ys)


def _mask_centroid(mask: list[list[bool]]) -> tuple[float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for y, row in enumerate(mask):
        for x, hit in enumerate(row):
            if hit:
                xs.append(float(x))
                ys.append(float(y))
    if not xs:
        return None
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _geometry_y_range(samples: list[tuple[float, float]]) -> tuple[float, float]:
    ys = [y for _, y in samples]
    return min(ys), max(ys)


def _point_on_mask(x: float, y: float, mask: list[list[bool]]) -> bool:
    h = len(mask)
    w = len(mask[0]) if h else 0
    xi = int(round(x))
    yi = int(round(y))
    return 0 <= xi < w and 0 <= yi < h and mask[yi][xi]


def explain_spatial_authority_mismatch(
    validated: dict[str, Any],
    spatial_masks: LaserSpatialMasks,
    *,
    min_core_overlap_ratio: float = DEFAULT_MIN_CORE_OVERLAP_RATIO,
    min_closed_loop_core_overlap_ratio: float = DEFAULT_MIN_CLOSED_LOOP_CORE_OVERLAP_RATIO,
    max_y_offset_px: float = DEFAULT_MAX_Y_OFFSET_PX,
    y_bbox_tolerance_px: int = DEFAULT_Y_BBOX_TOLERANCE_PX,
) -> str | None:
    """Return a spatial gate reason when geometry is not pixel-grounded on laser core."""
    samples = iter_geometry_sample_points(validated)
    if not samples:
        return None

    core = spatial_masks.core
    strict_core = spatial_masks.strict_core
    core_y_range = _mask_y_range(strict_core)
    if core_y_range is None:
        core_y_range = _mask_y_range(core)
    if core_y_range is None:
        return "spatial_mismatch_no_laser_overlap"

    core_y0, core_y1 = core_y_range
    geom_y0, geom_y1 = _geometry_y_range(samples)
    if geom_y0 > core_y1 + y_bbox_tolerance_px or geom_y1 < core_y0 - y_bbox_tolerance_px:
        return "spatial_mismatch_bbox_y_disjoint"

    core_centroid = _mask_centroid(strict_core) or _mask_centroid(core)
    if core_centroid is None:
        return "spatial_mismatch_no_laser_overlap"
    _, core_cy = core_centroid
    geom_cy = sum(y for _, y in samples) / len(samples)
    y_offset = abs(geom_cy - core_cy)
    if y_offset > max_y_offset_px:
        return f"spatial_mismatch_y_offset_px={y_offset:.1f}"

    overlap_mask = spatial_masks.core_dilated

    core_hits = sum(1 for x, y in samples if _point_on_mask(x, y, overlap_mask))
    if core_hits == 0:
        return "spatial_mismatch_no_laser_overlap"

    overlap_ratio = core_hits / len(samples)
    required_ratio = (
        min_closed_loop_core_overlap_ratio
        if validated.get("geometry_kind") == "closed_loop_contour"
        else min_core_overlap_ratio
    )
    if overlap_ratio < required_ratio:
        return f"spatial_mismatch_core_overlap_low={overlap_ratio:.3f}"

    return None
