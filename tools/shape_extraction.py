"""PR-G1 wall-space shape extraction utilities (local stills only)."""

from __future__ import annotations

import hashlib
import math
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Any

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore


ARTIFACT_VERSION = "shape-library-v1"
COORDINATE_SPACE = "wall_norm_per_fixture_calibration_box"
EXTRACTION_POLICY_VERSION = "v6"
DEFAULT_GLOW_THRESHOLD_K = 3.5
DEFAULT_CORE_THRESHOLD_K = 4.8
DEFAULT_MIN_AREA_PX = 40
DEFAULT_MIN_CORE_AREA_PX = 4
DEFAULT_HOLE_MIN_AREA_PX = 24
DEFAULT_GLOW_CONNECT_DILATE = 1
DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX = 1.5
DEFAULT_CONTOUR_SAMPLE_STEP = 3
DEFAULT_CORE_PERCENTILE = 90.0
DEFAULT_GLOW_AREA_RATIO = 3.0
DEFAULT_THIN_POLYLINE_MAX_CROSS = 0.28


@dataclass(frozen=True)
class FixtureBox:
    label: str
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return max(1, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(1, self.y1 - self.y0)

    def contains_pixel(self, fx: int, fy: int) -> bool:
        return self.x0 <= fx < self.x1 and self.y0 <= fy < self.y1


def load_fixture_boxes(analysis_geometry: dict[str, Any]) -> dict[str, FixtureBox]:
    out: dict[str, FixtureBox] = {}
    for box in analysis_geometry.get("boxes") or []:
        if not isinstance(box, dict):
            continue
        label = str(box.get("label") or "")
        bbox = box.get("bbox")
        if not (label and isinstance(bbox, list) and len(bbox) == 4):
            continue
        x0, y0, x1, y1 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        out[label] = FixtureBox(label=label, x0=x0, y0=y0, x1=x1, y1=y1)
    return out


def pixel_to_wall_norm(px: float, py: float, box: FixtureBox) -> tuple[float, float]:
    x_norm = 2.0 * ((px - box.x0) / box.width) - 1.0
    y_norm = 1.0 - 2.0 * ((py - box.y0) / box.height)
    return x_norm, y_norm


def bbox_wall_norm_from_pixel_bbox(
    px0: float, py0: float, px1: float, py1: float, box: FixtureBox
) -> list[float]:
    corners = [
        pixel_to_wall_norm(px0, py0, box),
        pixel_to_wall_norm(px1, py0, box),
        pixel_to_wall_norm(px1, py1, box),
        pixel_to_wall_norm(px0, py1, box),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return [min(xs), min(ys), max(xs), max(ys)]


def compute_shape_ref(
    artifact_version: str,
    vector_key: str,
    capture_path: str,
    fixture_box_label: str,
) -> str:
    payload = f"{artifact_version}|{vector_key}|{capture_path}|{fixture_box_label}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"sh1_{digest}"


def _luma(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _laser_brightness(r: int, g: int, b: int) -> float:
    """Color-aware laser score: max_rgb + saturation bonus; blue/purple/magenta safe."""
    mx = float(max(r, g, b))
    mn = float(min(r, g, b))
    sat = mx - mn
    base = mx + 0.72 * sat

    candidates = [base, max(mx, _luma(r, g, b)) * (0.5 + 0.5 * (sat / mx if mx else 0.0))]

    if b >= r * 0.85 and b >= g * 0.75:
        candidates.append(b + 0.58 * max(0.0, b - min(r, g)) + 0.22 * g)
    if r >= g * 1.05 and b >= g * 0.9 and g <= min(r, b) * 0.82:
        candidates.append((r + b) * 0.52 + 0.42 * sat)
    if r >= b * 1.05 and r >= g * 1.05:
        candidates.append(r + 0.48 * max(0.0, r - g))
    if g >= r * 0.9 and g >= b * 0.9:
        candidates.append(g + 0.35 * max(0.0, g - max(r, b)))

    return max(candidates)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(len(ordered) - 1, idx))]


def _connected_components(mask: list[list[bool]]) -> list[list[tuple[int, int]]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    seen = [[False] * w for _ in range(h)]
    components: list[list[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y][x] or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            comp: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            components.append(comp)
    return components


def _component_stats(comp: list[tuple[int, int]], box: FixtureBox) -> dict[str, Any]:
    xs = [p[0] + box.x0 for p in comp]
    ys = [p[1] + box.y0 for p in comp]
    px0, px1 = min(xs), max(xs)
    py0, py1 = min(ys), max(ys)
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    cnx, cny = pixel_to_wall_norm(cx, cy, box)
    return {
        "source_pixel_bbox": [px0, py0, px1, py1],
        "bbox_wall_norm": bbox_wall_norm_from_pixel_bbox(px0, py0, px1, py1, box),
        "centroid_wall_norm": [cnx, cny],
        "area_px": len(comp),
        "point_count": len(comp),
    }


def _component_span(comp: list[tuple[int, int]]) -> tuple[float, float]:
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    return float(max(xs) - min(xs) + 1), float(max(ys) - min(ys) + 1)


def _component_aspect(comp: list[tuple[int, int]]) -> float:
    w, h = _component_span(comp)
    return max(w, h) / max(1.0, min(w, h))


def _dilate_mask(mask: list[list[bool]], iterations: int = 1) -> list[list[bool]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    cur = mask
    for _ in range(max(0, iterations)):
        nxt = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if cur[y][x]:
                    nxt[y][x] = True
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dy == 0 and dx == 0:
                            continue
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and cur[ny][nx]:
                            nxt[y][x] = True
                            break
                    if nxt[y][x]:
                        break
        cur = nxt
    return cur


def _has_interior_hole(comp: list[tuple[int, int]]) -> bool:
    if len(comp) < 40:
        return False
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w = x1 - x0 + 1
    h = y1 - y0 + 1
    if w < 5 or h < 5:
        return False
    comp_set = set(comp)
    pad = 1
    gw, gh = w + 2 * pad, h + 2 * pad
    exterior = [[False] * gw for _ in range(gh)]
    q: deque[tuple[int, int]] = deque()
    for gx in range(gw):
        for gy in (0, gh - 1):
            exterior[gy][gx] = True
            q.append((gx, gy))
    for gy in range(gh):
        for gx in (0, gw - 1):
            if not exterior[gy][gx]:
                exterior[gy][gx] = True
                q.append((gx, gy))
    while q:
        gx, gy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = gx + dx, gy + dy
            if not (0 <= nx < gw and 0 <= ny < gh) or exterior[ny][nx]:
                continue
            rx, ry = nx - pad + x0, ny - pad + y0
            if (rx, ry) in comp_set:
                continue
            exterior[ny][nx] = True
            q.append((nx, ny))
    hole_area = 0
    for ry in range(y0, y1 + 1):
        for rx in range(x0, x1 + 1):
            if (rx, ry) in comp_set:
                continue
            gx, gy = rx - x0 + pad, ry - y0 + pad
            if not exterior[gy][gx]:
                hole_area += 1
                if hole_area >= DEFAULT_HOLE_MIN_AREA_PX:
                    return True
    return False


def _is_thin_core_ring(comp: list[tuple[int, int]]) -> bool:
    if not _has_interior_hole(comp):
        return False
    w, h = _component_span(comp)
    perimeter_est = 2.0 * (w + h)
    thickness = len(comp) / max(1.0, perimeter_est)
    return thickness <= 4.5


def _is_line_like(comp: list[tuple[int, int]]) -> bool:
    w, h = _component_span(comp)
    short_side = min(w, h)
    long_side = max(w, h)
    if short_side <= 4.0 and long_side / max(1.0, short_side) >= 3.0:
        return True
    return _component_aspect(comp) >= 3.0


def _forms_rectangular_frame(components: list[list[tuple[int, int]]]) -> bool:
    if len(components) != 4:
        return False
    if not all(_is_line_like(c) for c in components):
        return False
    xs0 = [min(p[0] for p in c) for c in components]
    ys0 = [min(p[1] for p in c) for c in components]
    xs1 = [max(p[0] for p in c) for c in components]
    ys1 = [max(p[1] for p in c) for c in components]
    outer_w = max(xs1) - min(xs0) + 1
    outer_h = max(ys1) - min(ys0) + 1
    if outer_w < 12 or outer_h < 12:
        return False
    return outer_w / max(1.0, outer_h) <= 4.0 and outer_h / max(1.0, outer_w) <= 4.0


def classify_topology(components: list[list[tuple[int, int]]], min_area: int) -> str:
    major = [c for c in components if len(c) >= min_area]
    if not major:
        return "unknown"
    compact = [c for c in major if not _is_line_like(c) and _component_aspect(c) < 2.2]
    if len(major) >= 4 and len(compact) >= 3 and all(len(c) <= 80 for c in compact):
        return "multi_cluster"
    if len(major) == 1:
        comp = major[0]
        if _is_line_like(comp):
            return "line"
        if _is_thin_core_ring(comp) or _has_interior_hole(comp):
            return "closed_loop"
        perimeter = len(comp)
        area = len(comp)
        if perimeter > 0 and (perimeter * perimeter) / max(1, area) < 20:
            return "closed_loop"
        return "complex_shape"
    if len(major) == 2:
        return "two_clusters"
    if len(major) >= 3:
        return "multi_cluster"
    return "unknown"


def _point_line_dist(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    if a == b:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    num = abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1]))
    den = math.hypot(b[0] - a[0], b[1] - a[1])
    return num / den


def _douglas_peucker(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points[:]
    start, end = points[0], points[-1]
    max_dist = 0.0
    idx = 0
    for i in range(1, len(points) - 1):
        d = _point_line_dist(points[i], start, end)
        if d > max_dist:
            max_dist = d
            idx = i
    if max_dist <= epsilon:
        return [start, end]
    left = _douglas_peucker(points[: idx + 1], epsilon)
    right = _douglas_peucker(points[idx:], epsilon)
    return left[:-1] + right


def _boundary_pixels(comp_set: set[tuple[int, int]]) -> list[tuple[int, int]]:
    boundary: list[tuple[int, int]] = []
    for x, y in comp_set:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in comp_set:
                boundary.append((x, y))
                break
    return boundary


def _trace_boundary_contour(comp: list[tuple[int, int]]) -> list[tuple[int, int]]:
    comp_set = set(comp)
    boundary = _boundary_pixels(comp_set)
    if not boundary:
        return comp[:]
    start = min(boundary, key=lambda p: (p[1], p[0]))
    contour = [start]
    current = start
    directions = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    prev_dir = 0
    for _ in range(len(boundary) * 8 + 8):
        found = False
        for step in range(8):
            d = (prev_dir + step) % 8
            dx, dy = directions[d]
            nxt = (current[0] + dx, current[1] + dy)
            if nxt in comp_set:
                current = nxt
                prev_dir = (d + 6) % 8
                if current == start:
                    return contour
                if current not in contour:
                    contour.append(current)
                found = True
                break
        if not found:
            break
    return contour if len(contour) >= 3 else boundary


def _neighbor_count(comp_set: set[tuple[int, int]], x: int, y: int) -> int:
    n = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            if (x + dx, y + dy) in comp_set:
                n += 1
    return n


def _trace_core_path(
    comp: list[tuple[int, int]], scores: list[list[float]]
) -> list[tuple[int, int]]:
    if len(comp) < 2:
        return comp[:]
    comp_set = set(comp)
    endpoints = [p for p in comp if _neighbor_count(comp_set, p[0], p[1]) <= 2]
    if len(endpoints) >= 2:
        start = min(endpoints, key=lambda p: (p[1], p[0]))
    else:
        start = max(comp, key=lambda p: scores[p[1]][p[0]])
    path = [start]
    visited = {start}
    current = start
    for _ in range(len(comp) + 4):
        cx, cy = current
        candidates = [
            (cx + dx, cy + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (dx or dy) and (cx + dx, cy + dy) in comp_set and (cx + dx, cy + dy) not in visited
        ]
        if not candidates:
            break
        nxt = max(
            candidates,
            key=lambda p: scores[p[1]][p[0]] - 0.08 * math.hypot(p[0] - cx, p[1] - cy),
        )
        path.append(nxt)
        visited.add(nxt)
        current = nxt
    if len(path) < 3 and len(comp) >= 3:
        ordered = sorted(comp, key=lambda p: (p[0], p[1]))
        return ordered
    return path


def _brightest_ridge_core(
    comp: list[tuple[int, int]], scores: list[list[float]]
) -> list[tuple[int, int]]:
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    if w >= h:
        by_x: dict[int, tuple[int, float]] = {}
        for x, y in comp:
            s = scores[y][x]
            if x not in by_x or s > by_x[x][1]:
                by_x[x] = (y, s)
        return [(x, y) for x, (y, _) in sorted(by_x.items())]
    by_y: dict[int, tuple[int, float]] = {}
    for x, y in comp:
        s = scores[y][x]
        if y not in by_y or s > by_y[y][1]:
            by_y[y] = (x, s)
    return [(x, y) for y, (x, _) in sorted(by_y.items())]


def _medial_ridge_points(comp: list[tuple[int, int]]) -> list[tuple[int, int]]:
    comp_set = set(comp)
    if not comp_set:
        return []
    dist: dict[tuple[int, int], int] = {}
    q: deque[tuple[int, int]] = deque()
    for x, y in comp_set:
        if any((x + dx, y + dy) not in comp_set for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            dist[(x, y)] = 0
            q.append((x, y))
    while q:
        x, y = q.popleft()
        d0 = dist[(x, y)]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt in comp_set and nxt not in dist:
                dist[nxt] = d0 + 1
                q.append(nxt)
    if not dist:
        return comp[:]
    max_d = max(dist.values())
    ridge = [p for p, d in dist.items() if d >= max(1, max_d - 1)]
    if len(ridge) < 2:
        ridge = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[: max(2, len(comp) // 8)]
        ridge = [p for p, _ in ridge]
    return ridge


def _order_path(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) < 3:
        return points[:]
    remaining = points[:]
    start = min(remaining, key=lambda p: (p[0], p[1]))
    ordered = [start]
    remaining.remove(start)
    while remaining:
        last = ordered[-1]
        nxt = min(remaining, key=lambda p: (p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2)
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


def _pixels_to_polyline(
    pixels: list[tuple[int, int]], box: FixtureBox, *, epsilon: float = 1.0
) -> list[list[float]]:
    if len(pixels) < 2:
        return [list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)) for x, y in pixels]
    ordered = _order_path(pixels) if len(pixels) < 80 else pixels
    simplified = _douglas_peucker([(float(x), float(y)) for x, y in ordered], epsilon)
    return [list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)) for x, y in simplified]


def _contour_polyline(
    comp: list[tuple[int, int]],
    box: FixtureBox,
    *,
    closed: bool,
    simplify_epsilon: float,
    sample_step: int,
) -> list[list[float]]:
    contour = _trace_boundary_contour(comp)
    if sample_step > 1:
        contour = contour[::sample_step]
    if len(contour) >= 3:
        simplified = _douglas_peucker([(float(x), float(y)) for x, y in contour], simplify_epsilon)
    else:
        simplified = [(float(x), float(y)) for x, y in contour]
    points = [list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)) for x, y in simplified]
    if closed and points and points[0] != points[-1]:
        points.append(points[0][:])
    return points


def _polyline_cross_span_norm(points: list[list[float]]) -> float:
    xs = [p[0] for p in points if len(p) >= 2]
    ys = [p[1] for p in points if len(p) >= 2]
    if not xs:
        return 1.0
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return min(w, h) / max(1e-9, max(w, h))


def _polyline_from_core_component(
    comp: list[tuple[int, int]],
    box: FixtureBox,
    scores: list[list[float]],
    topology: str,
    *,
    simplify_epsilon: float,
    sample_step: int,
) -> tuple[list[list[float]], str, bool, list[str]]:
    flags: list[str] = []
    if _is_thin_core_ring(comp):
        points = _contour_polyline(
            comp, box, closed=True, simplify_epsilon=simplify_epsilon, sample_step=sample_step
        )
        return points, "contour", True, flags

    ridge = _brightest_ridge_core(comp, scores)
    path = _trace_core_path(comp, scores)
    if _is_line_like(comp) and len(ridge) >= 3:
        pix = ridge
        source = "skeleton"
    elif len(path) >= 3:
        pix = path
        source = "skeleton"
    else:
        medial = _medial_ridge_points(comp)
        pix = medial if len(medial) >= 2 else comp[:: max(1, sample_step)]
        source = "core_samples"

    points = _pixels_to_polyline(pix, box, epsilon=simplify_epsilon)
    closed = False
    flags.append("core_mask_used")
    flags.append("skeleton_centerline_used")

    if closed or (len(points) >= 4 and points[0] == points[-1]):
        flags.append("halo_contour_rejected")
        closed = False
        if points and points[0] == points[-1]:
            points = points[:-1]

    cross = _polyline_cross_span_norm(points)
    if cross > DEFAULT_THIN_POLYLINE_MAX_CROSS and _is_line_like(comp):
        flags.append("broad_glow_rejected")
        thin_ridge = _brightest_ridge_core(comp, scores)
        points = _pixels_to_polyline(thin_ridge, box, epsilon=simplify_epsilon)
        cross = _polyline_cross_span_norm(points)

    if cross > DEFAULT_THIN_POLYLINE_MAX_CROSS:
        flags.append("low_shape_confidence")
        flags.append("visual_review_required")

    return points, source, closed, flags


def _core_pixels_in_glow(
    glow_comp: list[tuple[int, int]],
    core_mask: list[list[bool]],
    scores: list[list[float]],
    *,
    global_core_thr: float,
) -> list[tuple[int, int]]:
    core_px = [(x, y) for x, y in glow_comp if core_mask[y][x]]
    if len(core_px) >= DEFAULT_MIN_CORE_AREA_PX:
        return core_px
    vals = [scores[y][x] for x, y in glow_comp]
    if not vals:
        return []
    local_thr = max(global_core_thr, _percentile(vals, DEFAULT_CORE_PERCENTILE))
    core_px = [(x, y) for x, y in glow_comp if scores[y][x] >= local_thr]
    if len(core_px) >= DEFAULT_MIN_CORE_AREA_PX:
        return core_px
    local_thr = _percentile(vals, max(78.0, DEFAULT_CORE_PERCENTILE - 10.0))
    return [(x, y) for x, y in glow_comp if scores[y][x] >= local_thr]


def _split_core_mask_components(
    core_px: list[tuple[int, int]], w: int, h: int
) -> list[list[tuple[int, int]]]:
    if not core_px:
        return []
    local_mask = [[False] * w for _ in range(h)]
    for x, y in core_px:
        local_mask[y][x] = True
    return _connected_components(local_mask)


def _extract_core_components_from_glow(
    glow_comp: list[tuple[int, int]],
    core_mask: list[list[bool]],
    scores: list[list[float]],
    w: int,
    h: int,
    *,
    global_core_thr: float,
) -> list[list[tuple[int, int]]]:
    core_px = _core_pixels_in_glow(glow_comp, core_mask, scores, global_core_thr=global_core_thr)
    parts = _split_core_mask_components(core_px, w, h)
    major = [p for p in parts if len(p) >= DEFAULT_MIN_CORE_AREA_PX]
    if major:
        return major
    if len(core_px) >= DEFAULT_MIN_CORE_AREA_PX:
        return [core_px]
    return []


def _polylines_from_core_components(
    core_major: list[list[tuple[int, int]]],
    glow_major: list[list[tuple[int, int]]],
    box: FixtureBox,
    scores: list[list[float]],
    topology: str,
    *,
    simplify_epsilon: float,
    sample_step: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    polylines: list[dict[str, Any]] = []
    flags: list[str] = []
    sorted_core = sorted(core_major, key=len, reverse=True)
    sorted_glow = sorted(glow_major, key=len, reverse=True)

    for i, comp in enumerate(sorted_core):
        points, source, closed, comp_flags = _polyline_from_core_component(
            comp,
            box,
            scores,
            topology,
            simplify_epsilon=simplify_epsilon,
            sample_step=sample_step,
        )
        for f in comp_flags:
            if f not in flags:
                flags.append(f)
        if len(points) < 2:
            continue
        if closed and topology != "closed_loop":
            flags.append("halo_contour_rejected")
            closed = False
        polylines.append(
            {
                "polyline_id": f"p{i}",
                "points": points,
                "source": source,
                "closed": closed,
                "point_count": len(points),
            }
        )

    for core, glow in zip(sorted_core, sorted_glow[: len(sorted_core)]):
        if len(glow) > 0 and len(core) > 0:
            ratio = len(glow) / max(1, len(core))
            if ratio >= DEFAULT_GLOW_AREA_RATIO:
                if "broad_glow_rejected" not in flags:
                    flags.append("broad_glow_rejected")

    if topology in ("multi_cluster", "complex_shape") and len(sorted_core) >= 3:
        flags.append("colored_core_recovered")
    elif len(sorted_core) >= 2:
        flags.append("colored_core_recovered")

    if topology in ("complex_shape", "multi_cluster") and len(polylines) <= 1 and len(sorted_glow) >= 2:
        flags.append("internal_strokes_missing")
        flags.append("low_shape_confidence")
        flags.append("visual_review_required")

    if not sorted_core:
        flags.append("low_shape_confidence")
        flags.append("visual_review_required")

    return polylines, flags


def _pixel_in_other_fixture_boxes(fx: int, fy: int, box: FixtureBox, other_boxes: dict[str, FixtureBox]) -> bool:
    for label, ob in other_boxes.items():
        if label == box.label:
            continue
        if ob.contains_pixel(fx, fy):
            return True
    return False


def _detect_out_of_box_leak(
    mask: list[list[bool]],
    box: FixtureBox,
    threshold: float,
    full_image: Image.Image,
    other_boxes: dict[str, FixtureBox] | None,
    brightness_fn: Any,
) -> bool:
    h = len(mask)
    w = len(mask[0]) if h else 0
    others = other_boxes or {}
    full_px = full_image.load()
    fw, fh = full_image.size

    edge_hits = 0
    for x in range(w):
        for y in range(h):
            if not mask[y][x]:
                continue
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                edge_hits += 1
                if edge_hits >= 8:
                    return True

    outside_hits = 0
    for fy in range(fh):
        for fx in range(fw):
            if box.contains_pixel(fx, fy):
                continue
            if _pixel_in_other_fixture_boxes(fx, fy, box, others):
                continue
            r, g, b = full_px[fx, fy]
            if brightness_fn(r, g, b) >= threshold:
                outside_hits += 1
                if outside_hits >= 5:
                    return True
    return False


def extract_shape_from_image(
    image: Image.Image,
    box: FixtureBox,
    *,
    threshold_k: float | None = None,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
    simplify_epsilon: float = DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
    sample_step: int = DEFAULT_CONTOUR_SAMPLE_STEP,
    other_boxes: dict[str, FixtureBox] | None = None,
) -> dict[str, Any]:
    from tools.shape_hysteresis_support import build_hysteresis_support
    from tools.shape_laser_maps import build_laser_maps
    from tools.shape_stroke_vectorization import (
        classify_shape_type,
        run_typed_vectorization,
    )

    glow_k = threshold_k if threshold_k is not None else DEFAULT_GLOW_THRESHOLD_K
    crop = image.crop((box.x0, box.y0, box.x1, box.y1)).convert("RGB")
    w, h = crop.size
    pixels = crop.load()
    maps = build_laser_maps(pixels, w, h)
    if not maps.values:
        return _empty_extraction(box, glow_k, min_area_px)

    support = build_hysteresis_support(maps, min_area_px=min_area_px)
    shape_type = classify_shape_type(support, maps)
    best, cand_meta = run_typed_vectorization(maps, support, box, shape_type)

    glow_thr = maps.med + glow_k * maps.mad
    glow_mask = [[maps.combined_laser_score[y][x] >= glow_thr for x in range(w)] for y in range(h)]
    quality_flags: list[str] = ["hysteresis_support", "typed_stroke_v6"]
    full = image.convert("RGB")
    if _detect_out_of_box_leak(glow_mask, box, glow_thr, full, other_boxes, _laser_brightness):
        quality_flags.append("out_of_box")

    hard_geom_fail = {
        "filled_band_geometry",
        "unordered_pixel_cloud",
        "dense_mask_pixels_as_polyline",
        "dotted_pattern_smear",
        "dense_branch_scribble",
        "branch_mask_fill_like",
    }
    if any(r in hard_geom_fail for r in (best.reject_reasons or [])):
        best.polylines = []

    if not best.polylines:
        quality_flags.append("blank_still" if max(maps.values) < glow_thr else "low_contrast")
        quality_flags.append("low_shape_confidence")
        quality_flags.append("visual_review_required")
        return {
            "clusters": [],
            "polylines": [],
            "source_pixel_bbox": [box.x0, box.y0, box.x1, box.y1],
            "bbox_wall_norm": [-1.0, -1.0, 1.0, 1.0],
            "centroid_wall_norm": [0.0, 0.0],
            "topology_class": "unknown",
            "shape_point_count": 0,
            "quality_flags": quality_flags,
            **cand_meta,
            "extraction_params": {
                "glow_threshold_k": glow_k,
                "min_area_px": min_area_px,
                "background_median": maps.med,
                "extraction_policy": "typed_stroke_v6",
                "shape_type": shape_type,
            },
        }

    for flag in best.quality_flags:
        if flag not in quality_flags:
            quality_flags.append(flag)
    if cand_meta.get("selected_extractor") == "closed_loop_contour":
        for poly in best.polylines:
            if best.topology == "closed_loop" and len(poly.get("points") or []) >= 4:
                poly["closed"] = True
                if poly["points"] and poly["points"][0] != poly["points"][-1]:
                    poly["points"] = poly["points"] + [poly["points"][0][:]]
    for flag in best.reject_reasons:
        if flag == "internal_strokes_missing" and flag not in quality_flags:
            quality_flags.append(flag)
        if flag in ("fragment_only", "missing_color_span", "geometry_off_support"):
            quality_flags.append("visual_review_required")

    from tools.shape_geometry_kind import compute_geometry_point_count

    if best.clusters:
        xs = [c["source_pixel_bbox"][0] for c in best.clusters] + [c["source_pixel_bbox"][2] for c in best.clusters]
        ys = [c["source_pixel_bbox"][1] for c in best.clusters] + [c["source_pixel_bbox"][3] for c in best.clusters]
        px0, px1 = min(xs), max(xs)
        py0, py1 = min(ys), max(ys)
        src_bbox = [px0, py0, px1, py1]
        bbox_norm = bbox_wall_norm_from_pixel_bbox(px0, py0, px1, py1, box)
        cx = (px0 + px1) / 2.0
        cy = (py0 + py1) / 2.0
        centroid = list(pixel_to_wall_norm(cx, cy, box))
    else:
        src_bbox = [box.x0, box.y0, box.x1, box.y1]
        bbox_norm = [-1.0, -1.0, 1.0, 1.0]
        centroid = [0.0, 0.0]

    return {
        "clusters": best.clusters,
        "polylines": best.polylines,
        "source_pixel_bbox": src_bbox,
        "bbox_wall_norm": bbox_norm,
        "centroid_wall_norm": centroid,
        "topology_class": best.topology,
        "shape_point_count": compute_geometry_point_count(best.polylines),
        "geometry_kind": best.geometry_kind,
        "ordered": best.ordered,
        "rejection_reasons": list(best.rejection_reasons or best.reject_reasons or []),
        "quality_flags": quality_flags,
        **cand_meta,
        "extraction_params": {
            "glow_threshold_k": glow_k,
            "min_area_px": min_area_px,
            "background_median": maps.med,
            "contour_simplify_epsilon_px": simplify_epsilon,
            "contour_sample_step": sample_step,
            "brightness_source": "per_channel_laser_maps",
            "geometry_mask": "hysteresis_support_mask",
            "diagnostic_mask": "high_core_mask",
            "extraction_policy": "typed_stroke_v6",
            "shape_type": shape_type,
            "selected_vectorizer": cand_meta.get("selected_vectorizer"),
            "geometry_scores": cand_meta.get("geometry_scores") or {},
            "selected_extractor": cand_meta.get("selected_extractor"),
        },
        "geometry_scores": cand_meta.get("geometry_scores") or {},
        "shape_type": shape_type,
    }


def _empty_extraction(box: FixtureBox, threshold_k: float, min_area_px: int) -> dict[str, Any]:
    return {
        "clusters": [],
        "polylines": [],
        "source_pixel_bbox": [box.x0, box.y0, box.x1, box.y1],
        "bbox_wall_norm": [-1.0, -1.0, 1.0, 1.0],
        "centroid_wall_norm": [0.0, 0.0],
        "topology_class": "unknown",
        "shape_point_count": 0,
        "quality_flags": ["blank_still"],
        "extraction_candidates_tried": [],
        "selected_extractor": "none",
        "selected_vectorizer": "none",
        "selected_extractor_reason": "blank still",
        "candidate_scores": {},
        "geometry_scores": {},
        "rejected_candidate_reasons": {},
        "shape_type": "unknown",
        "extraction_params": {
            "glow_threshold_k": threshold_k,
            "min_area_px": min_area_px,
            "extraction_policy": "typed_stroke_v6",
        },
    }


def _wall_norm_to_pixel(x: float, y: float, box: FixtureBox) -> tuple[float, float]:
    return (
        box.x0 + ((x + 1.0) / 2.0) * box.width,
        box.y0 + ((1.0 - y) / 2.0) * box.height,
    )


def render_overlay_image(image: Image.Image, extraction: dict[str, Any], box: FixtureBox) -> Image.Image:
    base = image.copy().convert("RGB")
    draw = ImageDraw.Draw(base)
    draw.rectangle([box.x0, box.y0, box.x1, box.y1], outline=(0, 255, 255), width=2)
    bb = extraction.get("source_pixel_bbox") or []
    if len(bb) == 4:
        draw.rectangle(bb, outline=(255, 64, 64), width=1)
    for poly in extraction.get("polylines") or []:
        kind = poly.get("geometry_kind") or extraction.get("geometry_kind") or "centerline_polyline"
        if kind in ("rejected_mask_area", "mask_area", "unordered_pixel_cloud"):
            continue
        pts = poly.get("points") or []
        if not pts:
            continue
        if kind in ("dot_anchor_points",):
            for p in pts:
                if len(p) < 2:
                    continue
                cx, cy = _wall_norm_to_pixel(p[0], p[1], box)
                r = 2
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 0), outline=(255, 255, 0))
            continue
        if kind == "segment_anchor_points" and len(pts) == 1:
            cx, cy = _wall_norm_to_pixel(pts[0][0], pts[0][1], box)
            draw.line([cx - 2, cy, cx + 2, cy], fill=(255, 255, 0), width=1)
            continue
        if len(pts) < 2:
            cx, cy = _wall_norm_to_pixel(pts[0][0], pts[0][1], box)
            draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 0))
            continue
        pix_pts = [_wall_norm_to_pixel(p[0], p[1], box) for p in pts if len(p) >= 2]
        if kind == "closed_loop_contour" or poly.get("closed"):
            if len(pix_pts) >= 3:
                draw.line(pix_pts + [pix_pts[0]], fill=(255, 255, 0), width=1)
        else:
            draw.line(pix_pts, fill=(255, 255, 0), width=1)
    return base


def make_contact_sheet(still: Image.Image, overlay: Image.Image) -> Image.Image:
    still = still.copy().convert("RGB")
    overlay = overlay.copy().convert("RGB")
    sheet_h = max(still.height, overlay.height)
    sheet_w = still.width + overlay.width + 8
    sheet = Image.new("RGB", (sheet_w, sheet_h), (16, 16, 16))
    sheet.paste(still, (0, 0))
    sheet.paste(overlay, (still.width + 8, 0))
    return sheet
