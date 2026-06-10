"""Snap Gemini topology hints to strict laser-core pixels for authority geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from tools.ai_shape_spatial_gate import LaserSpatialMasks, explain_spatial_authority_mismatch
from tools.shape_extraction import _connected_components
from tools.shape_skeleton_graph import skeletonize_support_mask

DEFAULT_MAX_COMPONENT_MATCH_PX = 96.0
DEFAULT_SNAP_RADIUS_PX = 24
DEFAULT_MIN_SNAP_RATIO = 0.70
DEFAULT_MIN_COMPONENT_STRICT_CORE_RATIO = 0.55
DEFAULT_MORPH_CLOSE_RADIUS_PX = 2
DEFAULT_MORPH_OPEN_RADIUS_PX = 0
DEFAULT_MIN_COMPONENT_AREA_PX = 6
DEFAULT_HINT_BBOX_MARGIN_PX = 10
DEFAULT_HINT_BBOX_EXPAND_PX = 6
POINT_LIKE_MAX_AREA = 12
POINT_LIKE_MAX_ASPECT = 2.0
PARTIAL_FRAGMENT_MAX_FILL = 0.42
PARTIAL_FRAGMENT_MIN_ASPECT = 2.2

COMPONENT_CLASS_POINT = "point_like"
COMPONENT_CLASS_LOOP = "loop_like"
COMPONENT_CLASS_PARTIAL = "partial_fragment"

RECON_CONNECTED = "connected_components"
RECON_HINT_GUIDED = "hint_guided_strict_core"
RECON_MERGED_SPLIT = "merged_component_split"

TOPOLOGY_MISMATCH_PARTIAL_LOOP = "topology_mismatch_partial_loop_candidate"
HALO_FLOOD_COMPONENT = "halo_flood_component"
RECONSTRUCTION_BLOB_TOO_FILLED = "reconstruction_blob_too_filled"

MAX_AUTHORITY_COMPONENT_FILL_RATIO = 0.32
HALO_FLOOD_FILL_RATIO = 0.45
MIN_STROKE_PERIMETER_RATIO = 2.8
MIN_X_VALLEY_DEPTH_RATIO = 0.12


@dataclass(frozen=True)
class SplitReconstructionDebug:
    parent_component_bbox: list[int]
    split_child_bboxes: list[list[int]]
    split_child_match_ids: list[int]


@dataclass(frozen=True)
class CoreComponent:
    component_id: int
    pixels: list[tuple[int, int]]
    centroid: tuple[float, float]
    bbox: tuple[int, int, int, int]
    component_class: str


@dataclass(frozen=True)
class CVRefinementResult:
    applied: bool
    reason: str
    paths_px: list[list[list[float]]]
    dot_anchors_px: list[list[float]]
    segment_anchors_px: list[list[list[float]]]
    raw_gemini_geometry: dict[str, Any]
    global_shift_px: tuple[float, float] | None = None
    matched_component_ids: list[int] | None = None
    core_component_bboxes: list[list[int]] | None = None
    core_component_classes: list[str] | None = None
    failure_modes: list[str] | None = None
    reconstruction_method: str | None = None
    strict_core_pixel_count: int | None = None
    split_debug: SplitReconstructionDebug | None = None
    rejected_debug_pixels: list[list[int]] | None = None


def extract_raw_gemini_geometry(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "paths_px": [list(path) for path in result.get("paths_px") or []],
        "dot_anchors_px": [list(pt) for pt in result.get("dot_anchors_px") or []],
        "segment_anchors_px": [list(seg) for seg in result.get("segment_anchors_px") or []],
        "geometry_kind": result.get("geometry_kind"),
    }


def collect_strict_core_pixels(spatial_masks: LaserSpatialMasks) -> list[list[int]]:
    """Return skeletonized strict-core pixels for debug overlay (not glow flood)."""
    mask = spatial_masks.strict_core
    if not any(any(row) for row in mask):
        mask = spatial_masks.core
    skel = skeletonize_support_mask(mask)
    pixels: list[list[int]] = []
    for y, row in enumerate(skel):
        for x, hit in enumerate(row):
            if hit:
                pixels.append([x, y])
    return pixels


def _component_fill_ratio(component: CoreComponent) -> float:
    x0, y0, x1, y1 = component.bbox
    bbox_area = max(1, (x1 - x0 + 1) * (y1 - y0 + 1))
    return len(component.pixels) / float(bbox_area)


def _boundary_pixel_count(pixels: list[tuple[int, int]]) -> int:
    pixel_set = set(pixels)
    count = 0
    for x, y in pixels:
        if any((x + dx, y + dy) not in pixel_set for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            count += 1
    return count


def component_stroke_failure(component: CoreComponent) -> str | None:
    """Return a rejection token when a component is glow/blob-like, not stroke-like."""
    fill = _component_fill_ratio(component)
    if fill > HALO_FLOOD_FILL_RATIO:
        return HALO_FLOOD_COMPONENT
    if fill > MAX_AUTHORITY_COMPONENT_FILL_RATIO:
        return RECONSTRUCTION_BLOB_TOO_FILLED
    area = len(component.pixels)
    if area < 4:
        return RECONSTRUCTION_BLOB_TOO_FILLED
    perimeter = _boundary_pixel_count(component.pixels)
    perimeter_ratio = perimeter / max(1.0, math.sqrt(float(area)))
    if perimeter_ratio < MIN_STROKE_PERIMETER_RATIO:
        return HALO_FLOOD_COMPONENT if fill > 0.18 else RECONSTRUCTION_BLOB_TOO_FILLED
    return None


def _pixels_to_mask(
    pixels: list[tuple[int, int]],
    *,
    width: int,
    height: int,
) -> list[list[bool]]:
    mask = [[False] * width for _ in range(height)]
    for x, y in pixels:
        if 0 <= x < width and 0 <= y < height:
            mask[y][x] = True
    return mask


def _stroke_authority_pixels(
    pixels: list[tuple[int, int]],
    strict_core: list[list[bool]],
) -> list[tuple[int, int]]:
    """Keep thin strict-core stroke evidence; reject filled glow blobs."""
    h = len(strict_core)
    w = len(strict_core[0]) if h else 0
    scoped = [
        (x, y)
        for x, y in pixels
        if 0 <= x < w and 0 <= y < h and strict_core[y][x]
    ]
    if len(scoped) < 4:
        return []
    candidate = _build_component(0, scoped)
    if component_stroke_failure(candidate) is not None:
        return []
    pixel_set = set(scoped)
    boundary = [
        p
        for p in scoped
        if any((p[0] + dx, p[1] + dy) not in pixel_set for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
    ]
    if len(boundary) >= max(4, int(0.5 * len(scoped))):
        return boundary
    skel = skeletonize_support_mask(_pixels_to_mask(scoped, width=w, height=h))
    stroke = [(x, y) for y, row in enumerate(skel) for x, hit in enumerate(row) if hit]
    if len(stroke) < 4:
        return []
    stroke_component = _build_component(0, stroke)
    if component_stroke_failure(stroke_component) is not None:
        return []
    return stroke


def _rejected_debug_pixels(component: CoreComponent) -> list[list[int]]:
    pixel_set = set(component.pixels)
    outline = [
        [x, y]
        for x, y in component.pixels
        if any((x + dx, y + dy) not in pixel_set for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
    ]
    return outline or [[x, y] for x, y in component.pixels[:64]]


def _classify_component(pixels: list[tuple[int, int]], bbox: tuple[int, int, int, int]) -> str:
    x0, y0, x1, y1 = bbox
    w = max(1, x1 - x0 + 1)
    h = max(1, y1 - y0 + 1)
    area = len(pixels)
    fill_ratio = area / float(w * h)
    aspect = max(w, h) / float(max(1, min(w, h)))
    if area <= POINT_LIKE_MAX_AREA and aspect <= POINT_LIKE_MAX_ASPECT:
        return COMPONENT_CLASS_POINT
    if fill_ratio <= PARTIAL_FRAGMENT_MAX_FILL and aspect >= PARTIAL_FRAGMENT_MIN_ASPECT:
        return COMPONENT_CLASS_PARTIAL
    return COMPONENT_CLASS_LOOP


def _build_component(component_id: int, pixels: list[tuple[int, int]]) -> CoreComponent:
    xs = [p[0] for p in pixels]
    ys = [p[1] for p in pixels]
    centroid = (sum(xs) / len(xs), sum(ys) / len(ys))
    bbox = (min(xs), min(ys), max(xs), max(ys))
    return CoreComponent(
        component_id=component_id,
        pixels=pixels,
        centroid=centroid,
        bbox=bbox,
        component_class=_classify_component(pixels, bbox),
    )


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


def _erode_mask(mask: list[list[bool]], radius: int) -> list[list[bool]]:
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
            keep = True
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy > r2:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < w and 0 <= ny < h and mask[ny][nx]):
                        keep = False
                        break
                if not keep:
                    break
            out[y][x] = keep
    return out


def _close_mask(mask: list[list[bool]], radius: int) -> list[list[bool]]:
    if radius <= 0:
        return [row[:] for row in mask]
    return _erode_mask(_dilate_mask(mask, radius), radius)


def _open_mask(mask: list[list[bool]], radius: int) -> list[list[bool]]:
    if radius <= 0:
        return [row[:] for row in mask]
    return _dilate_mask(_erode_mask(mask, radius), radius)


def _remove_small_components(mask: list[list[bool]], *, min_area_px: int) -> list[list[bool]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    out = [[False] * w for _ in range(h)]
    for pixels in _connected_components(mask):
        if len(pixels) < min_area_px:
            continue
        for x, y in pixels:
            out[y][x] = True
    return out


def _validation_mask(spatial_masks: LaserSpatialMasks) -> list[list[bool]]:
    mask = spatial_masks.strict_core
    if not any(any(row) for row in mask):
        mask = spatial_masks.core
    return mask


def build_morphology_candidate_mask(
    spatial_masks: LaserSpatialMasks,
    *,
    close_radius_px: int = DEFAULT_MORPH_CLOSE_RADIUS_PX,
    open_radius_px: int = DEFAULT_MORPH_OPEN_RADIUS_PX,
    min_area_px: int = DEFAULT_MIN_COMPONENT_AREA_PX,
) -> list[list[bool]]:
    """Morphology for matching candidates only; strict_core remains validation mask."""
    base = _validation_mask(spatial_masks)
    if not any(any(row) for row in base):
        base = spatial_masks.core
    closed = _close_mask(base, close_radius_px)
    opened = _open_mask(closed, open_radius_px) if open_radius_px > 0 else closed
    return _remove_small_components(opened, min_area_px=min_area_px)


def extract_strict_core_components(mask: list[list[bool]], *, min_area_px: int = 4) -> list[CoreComponent]:
    components: list[CoreComponent] = []
    for idx, pixels in enumerate(_connected_components(mask)):
        if len(pixels) < min_area_px:
            continue
        components.append(_build_component(idx, pixels))
    components.sort(key=lambda c: (c.centroid[1], c.centroid[0]))
    for idx, comp in enumerate(components):
        components[idx] = CoreComponent(
            component_id=idx,
            pixels=comp.pixels,
            centroid=comp.centroid,
            bbox=comp.bbox,
            component_class=comp.component_class,
        )
    return components


def _shifted_path_bbox(
    path: list[list[float]],
    shift: tuple[float, float],
    *,
    margin: int,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    xs = [float(p[0]) + shift[0] for p in path]
    ys = [float(p[1]) + shift[1] for p in path]
    return (
        max(0, int(min(xs)) - margin),
        max(0, int(min(ys)) - margin),
        min(width - 1, int(max(xs)) + margin),
        min(height - 1, int(max(ys)) + margin),
    )


def _collect_pixels_in_bbox(
    mask: list[list[bool]],
    assigned: list[list[bool]],
    bbox: tuple[int, int, int, int],
) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = bbox
    pixels: list[tuple[int, int]] = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if mask[y][x] and not assigned[y][x]:
                pixels.append((x, y))
    return pixels


def reconstruct_components_hint_guided(
    strict_core: list[list[bool]],
    paths: list[list[list[float]]],
    shift: tuple[float, float],
    *,
    dot_anchors: list[list[float]] | None = None,
    bbox_margin_px: int = DEFAULT_HINT_BBOX_MARGIN_PX,
    bbox_expand_px: int = DEFAULT_HINT_BBOX_EXPAND_PX,
    min_area_px: int = DEFAULT_MIN_COMPONENT_AREA_PX,
) -> list[CoreComponent]:
    """Assign strict-core pixels to shifted Gemini loops (handles merged blobs)."""
    h = len(strict_core)
    w = len(strict_core[0]) if h else 0
    if not paths or h == 0 or w == 0:
        return []

    reserved = [[False] * w for _ in range(h)]
    for pt in dot_anchors or []:
        sx = float(pt[0]) + shift[0]
        sy = float(pt[1]) + shift[1]
        for x, y in _collect_dot_component_pixels(strict_core, reserved, sx, sy):
            reserved[y][x] = True

    shifted_centroids = []
    for path in paths:
        cx, cy = _path_centroid(path)
        shifted_centroids.append((cx + shift[0], cy + shift[1]))

    buckets: list[list[tuple[int, int]]] = [[] for _ in paths]
    for y, row in enumerate(strict_core):
        for x, hit in enumerate(row):
            if not hit or reserved[y][x]:
                continue
            best_idx = 0
            best_dist = float("inf")
            for idx, (cx, cy) in enumerate(shifted_centroids):
                dist = (x - cx) ** 2 + (y - cy) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            buckets[best_idx].append((x, y))

    components: list[CoreComponent] = []
    for path_idx, pixels in enumerate(buckets):
        if len(pixels) < min_area_px:
            x0, y0, x1, y1 = _shifted_path_bbox(
                paths[path_idx], shift, margin=bbox_margin_px, width=w, height=h
            )
            expanded = [
                (x, y)
                for y in range(y0, y1 + 1)
                for x in range(x0, x1 + 1)
                if strict_core[y][x] and not reserved[y][x]
            ]
            if len(expanded) >= min_area_px:
                pixels = expanded
            else:
                return []
        components.append(_build_component(path_idx, pixels))

    return components


def _x_projection(parent: CoreComponent) -> tuple[int, list[int]]:
    x0, _, x1, _ = parent.bbox
    proj = [0] * (x1 - x0 + 1)
    for x, _y in parent.pixels:
        proj[x - x0] += 1
    return x0, proj


def _x_split_boundaries_from_valleys(
    parent: CoreComponent,
    shifted_centroids: list[tuple[float, float]],
) -> list[float] | None:
    """Find x-axis valley boundaries between expected loop centers; None when unclear."""
    n = len(shifted_centroids)
    if n < 2:
        return None
    ordered = sorted(shifted_centroids, key=lambda c: c[0])
    x0, proj = _x_projection(parent)
    x1 = parent.bbox[2]
    boundaries: list[float] = []
    for i in range(n - 1):
        left_x = ordered[i][0]
        right_x = ordered[i + 1][0]
        mid = (left_x + right_x) / 2.0
        seg_start = max(x0 + 1, int(math.floor(min(left_x, right_x))))
        seg_end = min(x1 - 1, int(math.ceil(max(left_x, right_x))))
        if seg_end <= seg_start:
            return None

        candidates: list[tuple[float, int, float]] = []
        for x in range(seg_start, seg_end + 1):
            val = proj[x - x0]
            if val > proj[x - 1 - x0] or val > proj[x + 1 - x0]:
                continue
            left_peak = max(proj[max(x0, x - 3) - x0 : x - x0 + 1] or [val])
            right_peak = max(proj[x - x0 : min(x1, x + 3) - x0 + 1] or [val])
            peak = max(left_peak, right_peak, 1)
            depth = (peak - val) / float(peak)
            candidates.append((abs(x - mid), x, depth))

        if not candidates:
            return None
        deep = [item for item in candidates if item[2] >= MIN_X_VALLEY_DEPTH_RATIO]
        if not deep:
            return None
        _, best_x, _ = min(deep, key=lambda item: (item[0], -item[2]))
        boundaries.append(float(best_x) + 0.5)
    return boundaries


def split_merged_loop_component(
    parent: CoreComponent,
    paths: list[list[list[float]]],
    shift: tuple[float, float],
    strict_core: list[list[bool]],
    *,
    dot_anchors: list[list[float]] | None = None,
    min_area_px: int = DEFAULT_MIN_COMPONENT_AREA_PX,
    min_inside_ratio: float = 0.35,
) -> tuple[list[CoreComponent], SplitReconstructionDebug] | None:
    """Split one merged strict-core loop into N stroke-like child components."""
    n = len(paths)
    if n < 2:
        return None
    if parent.component_class not in (COMPONENT_CLASS_LOOP, COMPONENT_CLASS_PARTIAL):
        return None
    if component_stroke_failure(parent) is not None:
        return None

    h = len(strict_core)
    w = len(strict_core[0]) if h else 0
    reserved: set[tuple[int, int]] = set()
    if w and h:
        assigned = [[False] * w for _ in range(h)]
        for pt in dot_anchors or []:
            sx = float(pt[0]) + shift[0]
            sy = float(pt[1]) + shift[1]
            for x, y in _collect_dot_component_pixels(strict_core, assigned, sx, sy):
                reserved.add((x, y))

    parent_pixels = [
        (x, y)
        for x, y in parent.pixels
        if (x, y) not in reserved and 0 <= x < w and 0 <= y < h and strict_core[y][x]
    ]
    if len(parent_pixels) < n * min_area_px:
        return None

    shifted_centroids: list[tuple[float, float]] = []
    for path in paths:
        cx, cy = _path_centroid(path)
        shifted_centroids.append((cx + shift[0], cy + shift[1]))

    temp_parent = _build_component(parent.component_id, parent_pixels)
    boundaries = _x_split_boundaries_from_valleys(temp_parent, shifted_centroids)
    if boundaries is None or len(boundaries) != n - 1:
        return None

    buckets: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for x, y in parent_pixels:
        bucket = 0
        for boundary in boundaries:
            if x >= boundary:
                bucket += 1
            else:
                break
        if bucket >= n:
            bucket = n - 1
        buckets[bucket].append((x, y))

    path_order = sorted(range(n), key=lambda i: shifted_centroids[i][0])
    children: list[CoreComponent | None] = [None] * n
    child_bboxes: list[list[int]] = []
    for bucket_idx, path_idx in enumerate(path_order):
        stroke_pixels = _stroke_authority_pixels(buckets[bucket_idx], strict_core)
        if len(stroke_pixels) < min_area_px:
            return None
        child = _build_component(path_idx, stroke_pixels)
        if component_stroke_failure(child) is not None:
            return None
        if not _component_matches_shifted_path(
            child,
            paths[path_idx],
            shift,
            min_inside_ratio=min_inside_ratio,
        ):
            return None
        children[path_idx] = child
        child_bboxes.append([child.bbox[0], child.bbox[1], child.bbox[2], child.bbox[3]])

    if any(child is None for child in children):
        return None

    resolved = [children[i] for i in range(n) if children[i] is not None]
    debug = SplitReconstructionDebug(
        parent_component_bbox=[parent.bbox[0], parent.bbox[1], parent.bbox[2], parent.bbox[3]],
        split_child_bboxes=child_bboxes,
        split_child_match_ids=list(range(n)),
    )
    return resolved, debug


def _stroke_valid_components(components: list[CoreComponent]) -> list[CoreComponent]:
    valid: list[CoreComponent] = []
    for comp in components:
        stroke_pixels = comp.pixels
        if component_stroke_failure(_build_component(comp.component_id, stroke_pixels)) is None:
            valid.append(comp)
    return valid


def _extract_authority_components(
    spatial_masks: LaserSpatialMasks,
    paths: list[list[list[float]]],
    shift: tuple[float, float],
    *,
    dot_anchors: list[list[float]] | None = None,
) -> tuple[list[CoreComponent], str, SplitReconstructionDebug | None]:
    strict_core = _validation_mask(spatial_masks)
    strict_loops = [
        c
        for c in extract_strict_core_components(strict_core)
        if c.component_class in (COMPONENT_CLASS_LOOP, COMPONENT_CLASS_PARTIAL)
    ]

    if len(paths) > 1 and len(strict_loops) == 1:
        split = split_merged_loop_component(
            strict_loops[0],
            paths,
            shift,
            strict_core,
            dot_anchors=dot_anchors,
        )
        if split is not None:
            children, split_debug = split
            if len(children) == len(paths):
                return children, RECON_MERGED_SPLIT, split_debug

    morph_mask = build_morphology_candidate_mask(spatial_masks)
    morph_components = extract_strict_core_components(morph_mask)
    morph_loops = _stroke_valid_components(
        [
            c
            for c in morph_components
            if c.component_class in (COMPONENT_CLASS_LOOP, COMPONENT_CLASS_PARTIAL)
        ]
    )
    if len(paths) > 1 and len(morph_loops) == 1:
        split = split_merged_loop_component(
            morph_loops[0],
            paths,
            shift,
            strict_core,
            dot_anchors=dot_anchors,
        )
        if split is not None:
            children, split_debug = split
            if len(children) == len(paths):
                return children, RECON_MERGED_SPLIT, split_debug

    if len(morph_loops) >= len(paths) and paths:
        return morph_loops, RECON_CONNECTED, None

    if morph_loops:
        return morph_loops, RECON_CONNECTED, None
    if strict_loops:
        return strict_loops, RECON_CONNECTED, None
    return [], RECON_CONNECTED, None


def _path_centroid(path: list[list[float]]) -> tuple[float, float]:
    if not path:
        return 0.0, 0.0
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _all_hint_points(result: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for path in result.get("paths_px") or []:
        for pt in path:
            points.append((float(pt[0]), float(pt[1])))
    for pt in result.get("dot_anchors_px") or []:
        points.append((float(pt[0]), float(pt[1])))
    for seg in result.get("segment_anchors_px") or []:
        if len(seg) == 2:
            points.append((float(seg[0][0]), float(seg[0][1])))
            points.append((float(seg[1][0]), float(seg[1][1])))
    return points


def _estimate_global_shift(
    hint_points: list[tuple[float, float]],
    components: list[CoreComponent],
) -> tuple[float, float]:
    if not hint_points or not components:
        return 0.0, 0.0
    gx = sum(x for x, _ in hint_points) / len(hint_points)
    gy = sum(y for _, y in hint_points) / len(hint_points)
    total = sum(len(c.pixels) for c in components)
    cx = sum(c.centroid[0] * len(c.pixels) for c in components) / total
    cy = sum(c.centroid[1] * len(c.pixels) for c in components) / total
    # Gemini is usually misplaced vertically; keep X unless the whole hint cloud is offset.
    shift_x = cx - gx
    shift_y = cy - gy
    if abs(shift_x) < 8.0:
        shift_x = 0.0
    return shift_x, shift_y


def _shifted_path_bbox_tight(
    path: list[list[float]],
    shift: tuple[float, float],
) -> tuple[float, float, float, float]:
    xs = [float(p[0]) + shift[0] for p in path]
    ys = [float(p[1]) + shift[1] for p in path]
    return min(xs), min(ys), max(xs), max(ys)


def _component_matches_shifted_path(
    component: CoreComponent,
    path: list[list[float]],
    shift: tuple[float, float],
    *,
    min_inside_ratio: float = 0.35,
    max_centroid_px: float = DEFAULT_MAX_COMPONENT_MATCH_PX,
) -> bool:
    x0, y0, x1, y1 = _shifted_path_bbox_tight(path, shift)
    inside = sum(1 for x, y in component.pixels if x0 <= x <= x1 and y0 <= y <= y1)
    if inside / max(1, len(component.pixels)) < min_inside_ratio:
        return False
    pcx, pcy = _path_centroid(path)
    sx, sy = pcx + shift[0], pcy + shift[1]
    return math.hypot(sx - component.centroid[0], sy - component.centroid[1]) <= max_centroid_px


def _snap_point(
    x: float,
    y: float,
    mask: list[list[bool]],
    *,
    radius: int = DEFAULT_SNAP_RADIUS_PX,
) -> list[float] | None:
    h = len(mask)
    w = len(mask[0]) if h else 0
    xi = int(round(x))
    yi = int(round(y))
    if 0 <= xi < w and 0 <= yi < h and mask[yi][xi]:
        return [float(xi), float(yi)]
    best: list[float] | None = None
    best_d2 = radius * radius + 1
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d2 = dx * dx + dy * dy
            if d2 > radius * radius:
                continue
            nx, ny = xi + dx, yi + dy
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx]:
                if d2 < best_d2:
                    best_d2 = d2
                    best = [float(nx), float(ny)]
    return best


def _bbox_loop(bbox: tuple[int, int, int, int]) -> list[list[float]]:
    x0, y0, x1, y1 = bbox
    return [
        [float(x0), float(y0)],
        [float(x1), float(y0)],
        [float(x1), float(y1)],
        [float(x0), float(y1)],
        [float(x0), float(y0)],
    ]


def _trace_component_contour(component: CoreComponent) -> list[list[float]]:
    """Trace an ordered boundary loop from stroke pixels."""
    pixel_set = set(component.pixels)
    boundary: list[tuple[int, int]] = []
    for x, y in component.pixels:
        if any((x + dx, y + dy) not in pixel_set for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            boundary.append((x, y))
    if len(boundary) < 3:
        return _bbox_loop(component.bbox)

    start = min(boundary, key=lambda p: (p[1], p[0]))
    ordered: list[tuple[int, int]] = [start]
    current = start
    prev = (start[0], start[1] - 1)
    boundary_set = set(boundary)
    neighbors = [
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
        (0, -1),
        (1, -1),
    ]

    for _ in range(len(boundary) + 4):
        cx, cy = current
        px, py = prev
        start_dir = 0
        for i, (dx, dy) in enumerate(neighbors):
            if cx + dx == px and cy + dy == py:
                start_dir = (i + 1) % len(neighbors)
                break
        found = False
        for step in range(len(neighbors)):
            dx, dy = neighbors[(start_dir + step) % len(neighbors)]
            nxt = (cx + dx, cy + dy)
            if nxt in boundary_set and nxt != ordered[0]:
                ordered.append(nxt)
                prev, current = current, nxt
                found = True
                break
            if nxt == ordered[0] and len(ordered) >= 3:
                loop = [[float(x), float(y)] for x, y in ordered]
                loop.append([loop[0][0], loop[0][1]])
                return loop
        if not found:
            break

    cx, cy = component.centroid
    boundary.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    loop = [[float(x), float(y)] for x, y in boundary]
    loop.append([loop[0][0], loop[0][1]])
    return loop


def _authority_contour_from_component(
    component: CoreComponent,
    strict_core: list[list[bool]],
) -> list[list[float]] | None:
    stroke_pixels = _stroke_authority_pixels(component.pixels, strict_core)
    if len(stroke_pixels) < 4:
        return None
    stroke_component = _build_component(component.component_id, stroke_pixels)
    if component_stroke_failure(stroke_component) is not None:
        return None
    return _trace_component_contour(stroke_component)


def _match_paths_to_components(
    paths: list[list[list[float]]],
    components: list[CoreComponent],
    shift: tuple[float, float],
    *,
    max_match_px: float,
    eligible_indices: list[int] | None = None,
) -> list[int] | None:
    pool = list(eligible_indices if eligible_indices is not None else range(len(components)))
    if len(paths) > len(pool):
        return None
    available = set(pool)
    matches: list[int] = []
    for path in paths:
        cx, cy = _path_centroid(path)
        sx, sy = cx + shift[0], cy + shift[1]
        best_idx: int | None = None
        best_dist = max_match_px + 1.0
        for idx in available:
            comp = components[idx]
            dist = math.hypot(sx - comp.centroid[0], sy - comp.centroid[1])
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is None or best_dist > max_match_px:
            return None
        matches.append(best_idx)
        available.remove(best_idx)
    return matches


def _nearest_component_index(
    x: float,
    y: float,
    components: list[CoreComponent],
    *,
    exclude: set[int] | None = None,
) -> tuple[int, float]:
    blocked = exclude or set()
    best_idx = -1
    best_dist = float("inf")
    for idx, comp in enumerate(components):
        if idx in blocked:
            continue
        dist = math.hypot(x - comp.centroid[0], y - comp.centroid[1])
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx, best_dist


def _point_on_mask(x: float, y: float, mask: list[list[bool]]) -> bool:
    h = len(mask)
    w = len(mask[0]) if h else 0
    xi = int(round(x))
    yi = int(round(y))
    return 0 <= xi < w and 0 <= yi < h and mask[yi][xi]


def _path_strict_core_coverage(path: list[list[float]], strict_core: list[list[bool]]) -> float:
    if len(path) < 2:
        if not path:
            return 0.0
        return 1.0 if _point_on_mask(path[0][0], path[0][1], strict_core) else 0.0
    samples: list[tuple[float, float]] = []
    for idx in range(len(path)):
        samples.append((float(path[idx][0]), float(path[idx][1])))
        if idx + 1 < len(path):
            x0, y0 = float(path[idx][0]), float(path[idx][1])
            x1, y1 = float(path[idx + 1][0]), float(path[idx + 1][1])
            span = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, int(span // 2))
            for step in range(steps + 1):
                t = step / steps
                samples.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    hits = sum(1 for x, y in samples if _point_on_mask(x, y, strict_core))
    return hits / max(1, len(samples))


def _component_metadata(components: list[CoreComponent]) -> tuple[list[list[int]], list[str]]:
    bboxes = [[c.bbox[0], c.bbox[1], c.bbox[2], c.bbox[3]] for c in components]
    classes = [c.component_class for c in components]
    return bboxes, classes


def _failure_result(
    *,
    reason: str,
    raw: dict[str, Any],
    shift: tuple[float, float] | None = None,
    matched_ids: list[int] | None = None,
    components: list[CoreComponent] | None = None,
    failure_modes: list[str] | None = None,
    reconstruction_method: str | None = None,
    strict_core_pixel_count: int | None = None,
    split_debug: SplitReconstructionDebug | None = None,
    rejected_debug_pixels: list[list[int]] | None = None,
) -> CVRefinementResult:
    bboxes, classes = _component_metadata(components) if components else (None, None)
    return CVRefinementResult(
        applied=False,
        reason=reason,
        paths_px=list(raw["paths_px"]),
        dot_anchors_px=list(raw["dot_anchors_px"]),
        segment_anchors_px=list(raw["segment_anchors_px"]),
        raw_gemini_geometry=raw,
        global_shift_px=shift,
        matched_component_ids=matched_ids,
        core_component_bboxes=bboxes,
        core_component_classes=classes,
        failure_modes=failure_modes,
        reconstruction_method=reconstruction_method,
        strict_core_pixel_count=strict_core_pixel_count,
        split_debug=split_debug,
        rejected_debug_pixels=rejected_debug_pixels,
    )


def _collect_dot_component_pixels(
    strict_core: list[list[bool]],
    assigned: list[list[bool]],
    sx: float,
    sy: float,
    *,
    radius: int = 10,
    min_area_px: int = 2,
) -> list[tuple[int, int]]:
    h = len(strict_core)
    w = len(strict_core[0]) if h else 0
    xi, yi = int(round(sx)), int(round(sy))
    seeds: list[tuple[int, int]] = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            nx, ny = xi + dx, yi + dy
            if 0 <= nx < w and 0 <= ny < h and strict_core[ny][nx] and not assigned[ny][nx]:
                seeds.append((nx, ny))
    if not seeds:
        return []

    seed = min(seeds, key=lambda p: (p[0] - sx) ** 2 + (p[1] - sy) ** 2)
    stack = [seed]
    pixels: list[tuple[int, int]] = []
    seen = {seed}
    while stack:
        x, y = stack.pop()
        if assigned[y][x]:
            continue
        pixels.append((x, y))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and strict_core[ny][nx] and (nx, ny) not in seen:
                if (nx - sx) ** 2 + (ny - sy) ** 2 <= (radius + 2) ** 2:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
    return pixels if len(pixels) >= min_area_px else []


def _resolve_dot_anchors_from_components(
    raw: dict[str, Any],
    raw_dots: list[list[float]],
    components: list[CoreComponent],
    shift: tuple[float, float],
    *,
    matched_path_ids: set[int],
    strict_core: list[list[bool]],
) -> tuple[list[list[float]], list[str]] | CVRefinementResult:
    refined_dots: list[list[float]] = []
    failure_modes: list[str] = []
    h = len(strict_core)
    w = len(strict_core[0]) if h else 0
    assigned = [[False] * w for _ in range(h)]
    for comp_idx in matched_path_ids:
        if comp_idx < len(components):
            for x, y in components[comp_idx].pixels:
                assigned[y][x] = True

    for pt in raw_dots:
        sx = float(pt[0]) + shift[0]
        sy = float(pt[1]) + shift[1]
        dot_pixels = _collect_dot_component_pixels(strict_core, assigned, sx, sy)
        if dot_pixels:
            dot_comp = _build_component(-1, dot_pixels)
            if dot_comp.component_class != COMPONENT_CLASS_POINT:
                failure_modes.append(TOPOLOGY_MISMATCH_PARTIAL_LOOP)
                continue
            for x, y in dot_pixels:
                assigned[y][x] = True
            snapped = _snap_point(dot_comp.centroid[0], dot_comp.centroid[1], strict_core, radius=4)
            if snapped is None:
                px, py = dot_pixels[0]
                snapped = [float(px), float(py)]
            refined_dots.append(snapped)
            continue

        idx, _ = _nearest_component_index(sx, sy, components, exclude=matched_path_ids)
        if idx < 0:
            failure_modes.append(TOPOLOGY_MISMATCH_PARTIAL_LOOP)
            continue
        comp = components[idx]
        if comp.component_class != COMPONENT_CLASS_POINT:
            failure_modes.append(TOPOLOGY_MISMATCH_PARTIAL_LOOP)
            continue
        snapped = _snap_point(comp.centroid[0], comp.centroid[1], strict_core, radius=4)
        if snapped is None and comp.pixels:
            px, py = comp.pixels[0]
            snapped = [float(px), float(py)]
        if snapped is None:
            return _failure_result(
                reason="dot_snap_failed",
                raw=raw,
                shift=shift,
                failure_modes=failure_modes,
            )
        refined_dots.append(snapped)
    return refined_dots, failure_modes


def _snap_path_points(
    path: list[list[float]],
    mask: list[list[bool]],
    shift: tuple[float, float],
    *,
    snap_radius_px: int = DEFAULT_SNAP_RADIUS_PX,
) -> list[list[float]] | None:
    snapped: list[list[float]] = []
    for x, y in path:
        pt = _snap_point(x + shift[0], y + shift[1], mask, radius=snap_radius_px)
        if pt is None:
            return None
        snapped.append(pt)
    return snapped


def refine_ai_geometry_against_core(
    result: dict[str, Any],
    spatial_masks: LaserSpatialMasks,
    *,
    max_component_match_px: float = DEFAULT_MAX_COMPONENT_MATCH_PX,
    snap_radius_px: int = DEFAULT_SNAP_RADIUS_PX,
    min_snap_ratio: float = DEFAULT_MIN_SNAP_RATIO,
    min_component_strict_core_ratio: float = DEFAULT_MIN_COMPONENT_STRICT_CORE_RATIO,
) -> CVRefinementResult:
    """Use Gemini geometry as topology hints; emit CV-refined pixel coordinates."""
    raw = extract_raw_gemini_geometry(result)
    empty = CVRefinementResult(
        applied=False,
        reason="not_extracted",
        paths_px=list(raw["paths_px"]),
        dot_anchors_px=list(raw["dot_anchors_px"]),
        segment_anchors_px=list(raw["segment_anchors_px"]),
        raw_gemini_geometry=raw,
    )
    if result.get("status") != "extracted":
        return empty

    strict_core = _validation_mask(spatial_masks)
    strict_core_count = sum(1 for row in strict_core for hit in row if hit)
    morph_seed = extract_strict_core_components(build_morphology_candidate_mask(spatial_masks))
    if not morph_seed:
        morph_seed = extract_strict_core_components(strict_core)
    if not morph_seed:
        return _failure_result(
            reason="no_core_components",
            raw=raw,
            strict_core_pixel_count=strict_core_count,
        )

    paths_in = list(raw["paths_px"])
    geometry_kind = result.get("geometry_kind")
    hint_points = _all_hint_points(result)
    if geometry_kind == "closed_loop_contour" and paths_in:
        hint_points = [
            (float(pt[0]), float(pt[1]))
            for path in paths_in
            for pt in path
        ]
    hints = hint_points
    shift = _estimate_global_shift(hint_points, morph_seed)

    matched_ids: list[int] | None = None
    refined_paths: list[list[list[float]]] = []
    refined_dots: list[list[float]] = []
    refined_segments: list[list[list[float]]] = []
    extra_failure_modes: list[str] = []
    reconstruction_method: str | None = None
    split_debug: SplitReconstructionDebug | None = None
    components: list[CoreComponent] = []

    if geometry_kind == "closed_loop_contour" and paths_in:
        components, reconstruction_method, split_debug = _extract_authority_components(
            spatial_masks,
            paths_in,
            shift,
            dot_anchors=list(raw["dot_anchors_px"]),
        )
        bboxes, classes = _component_metadata(components)

        if len(components) == 1 and len(paths_in) > 1:
            parent = components[0]
            stroke_fail = component_stroke_failure(parent)
            if stroke_fail is not None:
                return _failure_result(
                    reason=stroke_fail,
                    raw=raw,
                    shift=shift,
                    components=components,
                    reconstruction_method=reconstruction_method,
                    strict_core_pixel_count=strict_core_count,
                    split_debug=split_debug,
                    failure_modes=[stroke_fail],
                    rejected_debug_pixels=_rejected_debug_pixels(parent),
                )
            return _failure_result(
                reason="merged_component_split_required",
                raw=raw,
                shift=shift,
                components=components,
                reconstruction_method=reconstruction_method,
                strict_core_pixel_count=strict_core_count,
                split_debug=split_debug,
                rejected_debug_pixels=_rejected_debug_pixels(parent),
            )

        if reconstruction_method == RECON_MERGED_SPLIT and len(components) == len(paths_in):
            matched_ids = list(range(len(paths_in)))
        else:
            loop_indices = [
                idx
                for idx, comp in enumerate(components)
                if comp.component_class in (COMPONENT_CLASS_LOOP, COMPONENT_CLASS_PARTIAL)
                and component_stroke_failure(comp) is None
            ]
            matched_ids = _match_paths_to_components(
                paths_in,
                components,
                shift,
                max_match_px=max_component_match_px,
                eligible_indices=loop_indices or None,
            )

        if matched_ids is None or len(matched_ids) != len(paths_in):
            rejected_pixels = None
            if components:
                rejected_pixels = _rejected_debug_pixels(components[0])
            return _failure_result(
                reason="component_match_failed",
                raw=raw,
                shift=shift,
                components=components,
                reconstruction_method=reconstruction_method,
                strict_core_pixel_count=strict_core_count,
                rejected_debug_pixels=rejected_pixels,
            )

        for comp_idx in matched_ids:
            stroke_fail = component_stroke_failure(components[comp_idx])
            if stroke_fail is not None:
                return _failure_result(
                    reason=stroke_fail,
                    raw=raw,
                    shift=shift,
                    matched_ids=matched_ids,
                    components=components,
                    reconstruction_method=reconstruction_method,
                    strict_core_pixel_count=strict_core_count,
                    failure_modes=[stroke_fail],
                    rejected_debug_pixels=_rejected_debug_pixels(components[comp_idx]),
                )

        for comp_idx in matched_ids:
            contour = _authority_contour_from_component(components[comp_idx], strict_core)
            if contour is None:
                return _failure_result(
                    reason=RECONSTRUCTION_BLOB_TOO_FILLED,
                    raw=raw,
                    shift=shift,
                    matched_ids=matched_ids,
                    components=components,
                    reconstruction_method=reconstruction_method,
                    strict_core_pixel_count=strict_core_count,
                    failure_modes=[RECONSTRUCTION_BLOB_TOO_FILLED],
                    rejected_debug_pixels=_rejected_debug_pixels(components[comp_idx]),
                )
            coverage = _path_strict_core_coverage(contour, strict_core)
            if coverage < min_component_strict_core_ratio:
                return _failure_result(
                    reason=f"component_strict_core_low={coverage:.3f}",
                    raw=raw,
                    shift=shift,
                    matched_ids=matched_ids,
                    components=components,
                    reconstruction_method=reconstruction_method,
                    strict_core_pixel_count=strict_core_count,
                    rejected_debug_pixels=_rejected_debug_pixels(components[comp_idx]),
                )
            refined_paths.append(contour)

        if raw["dot_anchors_px"]:
            dot_result = _resolve_dot_anchors_from_components(
                raw,
                raw["dot_anchors_px"],
                components,
                shift,
                matched_path_ids=set(matched_ids),
                strict_core=strict_core,
            )
            if isinstance(dot_result, CVRefinementResult):
                return CVRefinementResult(
                    applied=dot_result.applied,
                    reason=dot_result.reason,
                    paths_px=list(raw["paths_px"]),
                    dot_anchors_px=list(raw["dot_anchors_px"]),
                    segment_anchors_px=list(raw["segment_anchors_px"]),
                    raw_gemini_geometry=raw,
                    global_shift_px=shift,
                    matched_component_ids=matched_ids,
                    core_component_bboxes=bboxes,
                    core_component_classes=classes,
                    failure_modes=dot_result.failure_modes,
                    reconstruction_method=reconstruction_method,
                    strict_core_pixel_count=strict_core_count,
                )
            refined_dots, extra_failure_modes = dot_result

    elif geometry_kind == "closed_loop_contour":
        return _failure_result(
            reason="component_match_failed",
            raw=raw,
            shift=shift,
            strict_core_pixel_count=strict_core_count,
        )
    else:
        components = morph_seed
        bboxes, classes = _component_metadata(components)
        snap_mask = spatial_masks.core_dilated
        for path in paths_in:
            snapped = _snap_path_points(path, snap_mask, shift, snap_radius_px=snap_radius_px)
            if snapped is None:
                return _failure_result(
                    reason="path_snap_failed",
                    raw=raw,
                    shift=shift,
                    components=components,
                    strict_core_pixel_count=strict_core_count,
                )
            refined_paths.append(snapped)

        for pt in raw["dot_anchors_px"]:
            snapped = _snap_point(
                float(pt[0]) + shift[0],
                float(pt[1]) + shift[1],
                snap_mask,
                radius=snap_radius_px,
            )
            if snapped is None:
                return _failure_result(
                    reason="dot_snap_failed",
                    raw=raw,
                    shift=shift,
                    components=components,
                    strict_core_pixel_count=strict_core_count,
                )
            refined_dots.append(snapped)

        for seg in raw["segment_anchors_px"]:
            if len(seg) != 2:
                continue
            a = _snap_point(
                float(seg[0][0]) + shift[0],
                float(seg[0][1]) + shift[1],
                snap_mask,
                radius=snap_radius_px,
            )
            b = _snap_point(
                float(seg[1][0]) + shift[0],
                float(seg[1][1]) + shift[1],
                snap_mask,
                radius=snap_radius_px,
            )
            if a is None or b is None:
                return _failure_result(
                    reason="segment_snap_failed",
                    raw=raw,
                    shift=shift,
                    components=components,
                    strict_core_pixel_count=strict_core_count,
                )
            refined_segments.append([a, b])

    candidate = dict(result)
    candidate["paths_px"] = refined_paths
    candidate["dot_anchors_px"] = refined_dots
    candidate["segment_anchors_px"] = refined_segments

    if geometry_kind != "closed_loop_contour":
        hint_count = max(1, len(hints))
        snapped_count = sum(len(p) for p in refined_paths) + len(refined_dots) + 2 * len(refined_segments)
        if snapped_count / hint_count < min_snap_ratio:
            return _failure_result(
                reason="snap_coverage_low",
                raw=raw,
                shift=shift,
                components=components,
                strict_core_pixel_count=strict_core_count,
            )

    spatial_reason = explain_spatial_authority_mismatch(
        candidate,
        spatial_masks,
        min_closed_loop_core_overlap_ratio=0.55,
    )
    if spatial_reason is not None:
        return _failure_result(
            reason=f"spatial_gate_failed:{spatial_reason}",
            raw=raw,
            shift=shift,
            matched_ids=matched_ids,
            components=components,
            reconstruction_method=reconstruction_method,
            strict_core_pixel_count=strict_core_count,
        )

    bboxes, classes = _component_metadata(components)
    return CVRefinementResult(
        applied=True,
        reason="core_component_matched",
        paths_px=refined_paths,
        dot_anchors_px=refined_dots,
        segment_anchors_px=refined_segments,
        raw_gemini_geometry=raw,
        global_shift_px=shift,
        matched_component_ids=matched_ids,
        core_component_bboxes=bboxes,
        core_component_classes=classes,
        failure_modes=extra_failure_modes or None,
        reconstruction_method=reconstruction_method,
        strict_core_pixel_count=strict_core_count,
        split_debug=split_debug,
    )


def apply_cv_refinement_to_result(result: dict[str, Any], spatial_masks: LaserSpatialMasks) -> dict[str, Any]:
    """Mutate result with CV-refined authority geometry; preserve raw Gemini separately."""
    refinement = refine_ai_geometry_against_core(result, spatial_masks)
    result["gemini_raw_geometry"] = refinement.raw_gemini_geometry
    result["cv_refinement"] = {
        "applied": refinement.applied,
        "reason": refinement.reason,
        "global_shift_px": list(refinement.global_shift_px) if refinement.global_shift_px else None,
        "matched_component_ids": refinement.matched_component_ids,
        "core_component_bboxes": refinement.core_component_bboxes,
        "core_component_classes": refinement.core_component_classes,
        "reconstruction_method": refinement.reconstruction_method,
        "strict_core_pixel_count": refinement.strict_core_pixel_count,
    }
    if refinement.split_debug is not None:
        result["cv_refinement"]["parent_component_bbox"] = list(refinement.split_debug.parent_component_bbox)
        result["cv_refinement"]["split_child_bboxes"] = [
            list(bbox) for bbox in refinement.split_debug.split_child_bboxes
        ]
        result["cv_refinement"]["split_child_match_ids"] = list(
            refinement.split_debug.split_child_match_ids
        )
    if refinement.failure_modes:
        result["cv_refinement"]["dot_topology_warnings"] = list(refinement.failure_modes)
        if not refinement.applied:
            modes = list(result.get("failure_modes") or [])
            for mode in refinement.failure_modes:
                if mode not in modes:
                    modes.append(mode)
            result["failure_modes"] = modes
    if refinement.rejected_debug_pixels:
        result["cv_refinement"]["rejected_debug_pixels"] = [
            list(pt) for pt in refinement.rejected_debug_pixels
        ]
    if refinement.applied:
        result["paths_px"] = refinement.paths_px
        result["dot_anchors_px"] = refinement.dot_anchors_px
        result["segment_anchors_px"] = refinement.segment_anchors_px
        result["geometry_source"] = "cv_refined_from_gemini"
    else:
        result["geometry_source"] = "gemini_raw_unrefined"
    return result
