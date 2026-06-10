"""PR-G1 wall-space shape extraction utilities (local stills only)."""

from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import dataclass
from typing import Any

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore


ARTIFACT_VERSION = "shape-library-v1"
COORDINATE_SPACE = "wall_norm_per_fixture_calibration_box"
EXTRACTION_POLICY_VERSION = "v2"
DEFAULT_THRESHOLD_K = 4.0
DEFAULT_MIN_AREA_PX = 40
DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX = 1.5
DEFAULT_CONTOUR_SAMPLE_STEP = 3


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


def _component_aspect(comp: list[tuple[int, int]]) -> float:
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    return max(w, h) / max(1, min(w, h))


def _has_interior_hole(comp: list[tuple[int, int]]) -> bool:
    if len(comp) < 40:
        return False
    comp_set = set(comp)
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    cx = (min(xs) + max(xs)) // 2
    cy = (min(ys) + max(ys)) // 2
    return (cx, cy) not in comp_set


def classify_topology(components: list[list[tuple[int, int]]], min_area: int) -> str:
    major = [c for c in components if len(c) >= min_area]
    if not major:
        return "unknown"
    if len(major) == 1:
        comp = major[0]
        if _component_aspect(comp) >= 3.5:
            return "line"
        if _has_interior_hole(comp):
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
    # 8-connected clockwise from west
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


def _centerline_polyline(comp: list[tuple[int, int]], box: FixtureBox) -> list[list[float]]:
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    points: list[list[float]] = []
    if w >= h:
        by_x: dict[int, list[int]] = {}
        for x, y in comp:
            by_x.setdefault(x, []).append(y)
        for x in sorted(by_x):
            y = int(round(sum(by_x[x]) / len(by_x[x])))
            points.append(list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)))
    else:
        by_y: dict[int, list[int]] = {}
        for x, y in comp:
            by_y.setdefault(y, []).append(x)
        for y in sorted(by_y):
            x = int(round(sum(by_y[y]) / len(by_y[y])))
            points.append(list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)))
    return points


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
        simplified = _douglas_peucker(
            [(float(x), float(y)) for x, y in contour],
            simplify_epsilon,
        )
    else:
        simplified = [(float(x), float(y)) for x, y in contour]
    points = [list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)) for x, y in simplified]
    if closed and points and points[0] != points[-1]:
        points.append(points[0][:])
    return points


def _sampled_component_polyline(
    comp: list[tuple[int, int]],
    box: FixtureBox,
    *,
    sample_step: int,
) -> list[list[float]]:
    ordered = sorted(comp)
    sampled = ordered[:: max(1, sample_step)]
    return [list(pixel_to_wall_norm(x + box.x0, y + box.y0, box)) for x, y in sampled]


def _polylines_from_components(
    major: list[list[tuple[int, int]]],
    box: FixtureBox,
    topology: str,
    *,
    simplify_epsilon: float,
    sample_step: int,
) -> list[dict[str, Any]]:
    polylines: list[dict[str, Any]] = []
    sorted_major = sorted(major, key=len, reverse=True)
    for i, comp in enumerate(sorted_major):
        aspect = _component_aspect(comp)
        if topology == "line" and len(sorted_major) == 1 and aspect >= 3.0:
            points = _centerline_polyline(comp, box)
            source = "skeleton"
            closed = False
        elif topology == "two_clusters":
            if aspect >= 3.0:
                points = _centerline_polyline(comp, box)
                source = "skeleton"
                closed = False
            else:
                points = _contour_polyline(
                    comp, box, closed=False, simplify_epsilon=simplify_epsilon, sample_step=sample_step
                )
                source = "contour"
                closed = False
        elif topology in ("closed_loop", "complex_shape") and len(sorted_major) == 1:
            points = _contour_polyline(
                comp, box, closed=True, simplify_epsilon=simplify_epsilon, sample_step=sample_step
            )
            source = "contour"
            closed = True
        else:
            points = _contour_polyline(
                comp, box, closed=False, simplify_epsilon=simplify_epsilon, sample_step=sample_step
            )
            if len(points) < 4:
                points = _sampled_component_polyline(comp, box, sample_step=sample_step)
                source = "simplified_component"
            else:
                source = "contour"
            closed = False
        if len(points) < 2:
            points = _sampled_component_polyline(comp, box, sample_step=sample_step)
            source = "simplified_component"
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
    return polylines


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
) -> bool:
    h = len(mask)
    w = len(mask[0]) if h else 0
    others = other_boxes or {}
    full_px = full_image.load()
    fw, fh = full_image.size

    # Bright pixels inside selected crop touching the crop edge → leak outside calibration box.
    edge_hits = 0
    for x in range(w):
        for y in range(h):
            if not mask[y][x]:
                continue
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                edge_hits += 1
                if edge_hits >= 8:
                    return True

    # Full-image scan: outside selected box but not inside sibling fixture boxes.
    outside_hits = 0
    for fy in range(fh):
        for fx in range(fw):
            if box.contains_pixel(fx, fy):
                continue
            if _pixel_in_other_fixture_boxes(fx, fy, box, others):
                continue
            r, g, b = full_px[fx, fy]
            if _luma(r, g, b) >= threshold:
                outside_hits += 1
                if outside_hits >= 5:
                    return True
    return False


def extract_shape_from_image(
    image: Image.Image,
    box: FixtureBox,
    *,
    threshold_k: float = DEFAULT_THRESHOLD_K,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
    simplify_epsilon: float = DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
    sample_step: int = DEFAULT_CONTOUR_SAMPLE_STEP,
    other_boxes: dict[str, FixtureBox] | None = None,
) -> dict[str, Any]:
    crop = image.crop((box.x0, box.y0, box.x1, box.y1)).convert("RGB")
    w, h = crop.size
    lumas: list[float] = []
    pixels = crop.load()
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            lumas.append(_luma(r, g, b))
    if not lumas:
        return _empty_extraction(box, threshold_k, min_area_px)

    med = statistics.median(lumas)
    mad = statistics.median([abs(v - med) for v in lumas]) or 1.0
    threshold = med + threshold_k * mad
    mask = [[(_luma(*pixels[x, y]) >= threshold) for x in range(w)] for y in range(h)]
    components = _connected_components(mask)
    major = [c for c in components if len(c) >= min_area_px]
    quality_flags: list[str] = []

    full = image.convert("RGB")
    full_px = full.load()
    if _detect_out_of_box_leak(mask, box, threshold, full, other_boxes):
        quality_flags.append("out_of_box")

    if not major:
        quality_flags.append("blank_still" if max(lumas) < threshold else "low_contrast")
    if len(components) > len(major) + 5:
        quality_flags.append("noisy_components")

    clusters: list[dict[str, Any]] = []
    all_points: list[tuple[float, float]] = []
    for i, comp in enumerate(sorted(major, key=len, reverse=True)):
        stats = _component_stats(comp, box)
        clusters.append({"cluster_id": f"c{i}", **stats})
        for px, py in comp:
            nx, ny = pixel_to_wall_norm(px + box.x0, py + box.y0, box)
            all_points.append((nx, ny))

    topology = classify_topology(components, min_area_px)
    if not major and max(lumas) < med + mad:
        topology = "unknown"

    polylines = _polylines_from_components(
        major,
        box,
        topology,
        simplify_epsilon=simplify_epsilon,
        sample_step=sample_step,
    )

    if clusters:
        xs = [c["source_pixel_bbox"][0] for c in clusters] + [c["source_pixel_bbox"][2] for c in clusters]
        ys = [c["source_pixel_bbox"][1] for c in clusters] + [c["source_pixel_bbox"][3] for c in clusters]
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
        "clusters": clusters,
        "polylines": polylines,
        "source_pixel_bbox": src_bbox,
        "bbox_wall_norm": bbox_norm,
        "centroid_wall_norm": centroid,
        "topology_class": topology,
        "shape_point_count": len(all_points),
        "quality_flags": quality_flags,
        "extraction_params": {
            "threshold_k": threshold_k,
            "min_area_px": min_area_px,
            "threshold_value": threshold,
            "background_median": med,
            "contour_simplify_epsilon_px": simplify_epsilon,
            "contour_sample_step": sample_step,
            "luma_source": "rec709",
        },
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
        "extraction_params": {
            "threshold_k": threshold_k,
            "min_area_px": min_area_px,
        },
    }


def render_overlay_image(image: Image.Image, extraction: dict[str, Any], box: FixtureBox) -> Image.Image:
    base = image.copy().convert("RGB")
    draw = ImageDraw.Draw(base)
    draw.rectangle([box.x0, box.y0, box.x1, box.y1], outline=(0, 255, 255), width=2)
    bb = extraction.get("source_pixel_bbox") or []
    if len(bb) == 4:
        draw.rectangle(bb, outline=(255, 64, 64), width=1)
    for poly in extraction.get("polylines") or []:
        pts = poly.get("points") or []
        if len(pts) < 2:
            continue
        pix_pts = [
            (
                box.x0 + ((x + 1.0) / 2.0) * box.width,
                box.y0 + ((1.0 - y) / 2.0) * box.height,
            )
            for x, y in pts
        ]
        draw.line(pix_pts, fill=(255, 255, 0), width=2)
    return base


def make_contact_sheet(still: Image.Image, overlay: Image.Image) -> Image.Image:
    still = still.copy().convert("RGB")
    overlay = overlay.copy().convert("RGB")
    h = max(still.height, overlay.height)
    w = still.width + overlay.width + 8
    sheet = Image.new("RGB", (w, h), (16, 16, 16))
    sheet.paste(still, (0, 0))
    sheet.paste(overlay, (still.width + 8, 0))
    return sheet
