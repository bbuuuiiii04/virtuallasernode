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
EXTRACTION_POLICY_VERSION = "v1"
DEFAULT_THRESHOLD_K = 4.0
DEFAULT_MIN_AREA_PX = 40


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


def classify_topology(components: list[list[tuple[int, int]]], min_area: int) -> str:
    major = [c for c in components if len(c) >= min_area]
    if not major:
        return "unknown"
    if len(major) == 1:
        comp = major[0]
        xs = [p[0] for p in comp]
        ys = [p[1] for p in comp]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        aspect = max(w, h) / max(1, min(w, h))
        if aspect >= 3.5:
            return "line"
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


def _trace_border_polyline(comp: list[tuple[int, int]], box: FixtureBox) -> list[list[float]]:
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    px0, px1 = min(xs) + box.x0, max(xs) + box.x0
    py0, py1 = min(ys) + box.y0, max(ys) + box.y0
    corners = [
        pixel_to_wall_norm(px0, py0, box),
        pixel_to_wall_norm(px1, py0, box),
        pixel_to_wall_norm(px1, py1, box),
        pixel_to_wall_norm(px0, py1, box),
        pixel_to_wall_norm(px0, py0, box),
    ]
    return corners


def extract_shape_from_image(
    image: Image.Image,
    box: FixtureBox,
    *,
    threshold_k: float = DEFAULT_THRESHOLD_K,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
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

    med = statistics.median(lumas)
    mad = statistics.median([abs(v - med) for v in lumas]) or 1.0
    threshold = med + threshold_k * mad
    mask = [[(_luma(*pixels[x, y]) >= threshold) for x in range(w)] for y in range(h)]
    components = _connected_components(mask)
    major = [c for c in components if len(c) >= min_area_px]
    quality_flags: list[str] = []

    # Bright pixels outside fixture calibration box (full still, not cropped).
    full = image.convert("RGB")
    full_px = full.load()
    fw, fh = full.size
    outside_hits = 0
    for fy in range(fh):
        for fx in range(fw):
            if box.x0 <= fx < box.x1 and box.y0 <= fy < box.y1:
                continue
            if _luma(*full_px[fx, fy]) >= threshold:
                outside_hits += 1
                if outside_hits >= 5:
                    quality_flags.append("out_of_box")
                    break
        if "out_of_box" in quality_flags:
            break

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
            if nx < -1.0 or nx > 1.0 or ny < -1.0 or ny > 1.0:
                if "out_of_box" not in quality_flags:
                    quality_flags.append("out_of_box")

    polylines: list[dict[str, Any]] = []
    if major:
        pts = _trace_border_polyline(major[0], box)
        polylines.append(
            {
                "polyline_id": "p0",
                "points": pts,
                "source": "simplified_component",
                "closed": True,
                "point_count": len(pts),
            }
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

    topology = classify_topology(components, min_area_px)
    if not major and max(lumas) < med + mad:
        topology = "unknown"

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
        },
    }


def render_overlay_image(image: Image.Image, extraction: dict[str, Any], box: FixtureBox) -> Image.Image:
    base = image.copy().convert("RGB")
    draw = ImageDraw.Draw(base)
    draw.rectangle([box.x0, box.y0, box.x1, box.y1], outline=(0, 255, 255), width=2)
    bb = extraction.get("source_pixel_bbox") or []
    if len(bb) == 4:
        draw.rectangle(bb, outline=(255, 64, 64), width=2)
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
