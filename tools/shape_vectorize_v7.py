"""V7 per-component vectorization: dot anchors, rectangles, centerlines, dashed-arc paths.

The vectorizer is structure-aware: within each CORE component it first
extracts the saturated laser structure (white-hot pixels), which separates
the true emission pattern from bright glow that the CORE threshold may
have merged in (glow bridges between shapes, glow halos around dashes).
Geometry is then derived from that structure:

- compact blob            -> dot_anchor (single weighted centroid)
- ring (enclosed hole)    -> rect_centerline when a min-area-rect fits the
                             centerline within tolerance, else closed_centerline
- >=2 disjoint dashes/dots -> dotted_arc_path: one ordered open polyline
                             chained through the dash centerlines
- elongated stroke        -> open_centerline (skeleton trace)
"""

from __future__ import annotations

from typing import Any

import numpy as np
from skimage.morphology import skeletonize

DEFAULT_DP_EPSILON = 0.75
DEFAULT_MIN_PATH_LEN = 3

# Structure submask extraction
STRUCTURE_SAT_MIN = 110.0     # below this max(min_ch), comp has no saturated structure
STRUCTURE_OTSU_CLAMP = (100.0, 200.0)
STRUCTURE_MIN_PX = 8          # submask smaller than this falls back to full comp
STRUCTURE_MIN_SUB_PX = 3      # ignore sub-fragments smaller than this

# Rectangle snap: p90 distance of centerline points to fitted rect
RECT_SNAP_RESIDUAL_P90 = 1.75

# Substructure classification
RING_HOLE_FRACTION = 0.15
DASH_MAX_ASPECT = 2.0
DASH_MAX_AREA = 400


def vectorize_component(
    comp_mask: np.ndarray,
    comp_class: str,
    score_map: np.ndarray,
    comp_id: str,
    dp_epsilon: float = DEFAULT_DP_EPSILON,
    min_path_len: int = DEFAULT_MIN_PATH_LEN,
    img_rgb: np.ndarray | None = None,
    structure_mask: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """
    Returns list of polyline dicts for one component.

    Each dict has keys: geometry_kind, closed, ordered, points_px (list of [x,y]).
    `structure_mask` (precomputed via extract_structure_submask) avoids
    recomputing the saturated-structure threshold; when omitted it is derived
    from img_rgb, or falls back to comp_mask if no image is available.
    """
    if comp_class == "dot":
        return _vectorize_dot(comp_mask, score_map, comp_id)

    if structure_mask is None:
        structure_mask = extract_structure_submask(comp_mask, img_rgb)

    subs = _structure_subcomponents(structure_mask, comp_mask)
    kinds = [_classify_substructure(m) for m in subs]

    polys: list[dict[str, Any]] = []
    if "ring" not in kinds and len(subs) >= 2:
        # Disjoint dashes/dots from one emission: a dashed/dotted path.
        path = _trace_dashed_path(subs, dp_epsilon)
        if len(path) >= 2:
            polys.append({
                "component_id": comp_id,
                "geometry_kind": "dotted_arc_path",
                "closed": False,
                "ordered": True,
                "dash_count": len(subs),
                "points_px": path,
            })
    else:
        for m, k in zip(subs, kinds):
            if k == "ring":
                polys.extend(_vectorize_ring(m, comp_id, dp_epsilon, min_path_len))
            elif k == "dash":
                polys.extend(_vectorize_dot(m, score_map, comp_id))
            else:
                polys.extend(_vectorize_open_stroke(m, comp_id, dp_epsilon, min_path_len))

    if not polys:
        polys = _vectorize_open_stroke(comp_mask, comp_id, dp_epsilon, min_path_len)
    return polys


def extract_structure_submask(
    comp_mask: np.ndarray, img_rgb: np.ndarray | None
) -> np.ndarray:
    """Saturated laser structure within a CORE component.

    White-hot pixels (high min-channel) mark the actual beam trace; bright
    colored glow does not saturate all three channels. Threshold is Otsu on
    min_ch within the component, clamped to STRUCTURE_OTSU_CLAMP. Falls back
    to the full component when there is no saturated structure (colored
    low-exposure captures) or the submask is too small to be meaningful.
    """
    if img_rgb is None:
        return comp_mask.copy()
    min_ch = np.minimum(
        img_rgb[:, :, 0], np.minimum(img_rgb[:, :, 1], img_rgb[:, :, 2])
    ).astype(np.float32)
    vals = min_ch[comp_mask]
    if len(vals) == 0 or float(vals.max()) < STRUCTURE_SAT_MIN:
        return comp_mask.copy()
    try:
        from skimage.filters import threshold_otsu
        thresh = float(threshold_otsu(vals))
    except Exception:
        thresh = STRUCTURE_OTSU_CLAMP[0]
    thresh = min(max(thresh, STRUCTURE_OTSU_CLAMP[0]), STRUCTURE_OTSU_CLAMP[1])
    sub = comp_mask & (min_ch >= thresh)
    if int(sub.sum()) < STRUCTURE_MIN_PX:
        return comp_mask.copy()
    return sub


def _structure_subcomponents(
    structure_mask: np.ndarray, comp_mask: np.ndarray
) -> list[np.ndarray]:
    from skimage.measure import label as _label
    labeled, n = _label(structure_mask, connectivity=2, return_num=True)
    subs: list[np.ndarray] = []
    for i in range(1, n + 1):
        m = labeled == i
        if int(m.sum()) >= STRUCTURE_MIN_SUB_PX:
            subs.append(m)
    if not subs:
        return [comp_mask]
    subs.sort(key=lambda m: -int(m.sum()))
    return subs


def _classify_substructure(m: np.ndarray) -> str:
    """'ring' (encloses a hole), 'dash' (compact), or 'stroke' (elongated)."""
    from scipy.ndimage import binary_fill_holes
    ys, xs = np.where(m)
    area = int(len(ys))
    if area == 0:
        return "dash"
    filled = binary_fill_holes(m)
    hole_area = int(np.sum(filled)) - area
    if hole_area > RING_HOLE_FRACTION * area:
        return "ring"
    bbox_h = int(ys.max() - ys.min() + 1)
    bbox_w = int(xs.max() - xs.min() + 1)
    aspect = max(bbox_h, bbox_w) / max(1, min(bbox_h, bbox_w))
    if aspect < DASH_MAX_ASPECT and area < DASH_MAX_AREA:
        return "dash"
    return "stroke"


def _vectorize_dot(comp_mask: np.ndarray, score_map: np.ndarray, comp_id: str) -> list[dict[str, Any]]:
    ys, xs = np.where(comp_mask)
    weights = score_map[ys, xs].astype(np.float64)
    if weights.sum() < 1e-9:
        weights = np.ones(len(ys), dtype=np.float64)
    cx = float(np.average(xs, weights=weights))
    cy = float(np.average(ys, weights=weights))
    return [{
        "component_id": comp_id,
        "geometry_kind": "dot_anchor",
        "closed": False,
        "ordered": True,
        "points_px": [[round(cx, 2), round(cy, 2)]],
    }]


def _vectorize_ring(
    comp_mask: np.ndarray, comp_id: str, dp_epsilon: float, min_path_len: int
) -> list[dict[str, Any]]:
    """Closed stroke enclosing a hole: snap to a rectangle when it fits.

    The raw skeleton of a several-px-thick ring has +-1-2 px staircase
    wobble; rendering it directly produces squiggly outlines. A min-area
    rectangle is fitted to the skeleton centerline and, when the p90
    point-to-rect distance is within RECT_SNAP_RESIDUAL_P90, the clean
    4-corner rectangle is the render geometry. Non-rectangular rings keep
    a Douglas-Peucker-simplified closed contour centerline.
    """
    skel = skeletonize(comp_mask)
    skel_pts = list(map(tuple, np.argwhere(skel)))

    fit = _fit_rectangle(skel_pts)
    if fit is not None:
        corners, residual = fit
        if residual <= RECT_SNAP_RESIDUAL_P90:
            pts = [[round(float(corners[i % 4][0]), 2),
                    round(float(corners[i % 4][1]), 2)] for i in range(5)]
            return [{
                "component_id": comp_id,
                "geometry_kind": "rect_centerline",
                "closed": True,
                "ordered": True,
                "fit_residual_px_p90": round(residual, 3),
                "points_px": pts,
            }]

    # Not rectangle-like: closed centerline from the skeleton loop, or the
    # filled-component contour when the skeleton trace does not close.
    paths = trace_skeleton_paths(skel, min_path_len=min_path_len)
    closed_paths = [
        p for p in paths
        if len(p) > 2 and _pts_close(p[0], p[-1], tol=2.0)
        and len(p) >= max(min_path_len, int(len(skel_pts) * 0.05), 8)
    ]
    if closed_paths:
        best = max(closed_paths, key=len)
        pts = _douglas_peucker([[float(p[1]), float(p[0])] for p in best], dp_epsilon)
        if len(pts) >= min_path_len:
            return [{
                "component_id": comp_id,
                "geometry_kind": "closed_centerline",
                "closed": True,
                "ordered": True,
                "points_px": pts,
            }]

    from scipy.ndimage import binary_fill_holes
    from skimage.measure import find_contours
    filled = binary_fill_holes(comp_mask)
    contours = find_contours(filled.astype(float), 0.5)
    if contours:
        longest = max(contours, key=len)
        pts = _douglas_peucker([[float(p[1]), float(p[0])] for p in longest], dp_epsilon)
        if len(pts) >= min_path_len:
            return [{
                "component_id": comp_id,
                "geometry_kind": "closed_centerline",
                "closed": True,
                "ordered": True,
                "points_px": pts,
            }]
    return []


def _fit_rectangle(
    pts_yx: list[tuple[int, int]],
) -> tuple[np.ndarray, float] | None:
    """Fit a (rotated) rectangle to centerline points.

    Orientation from the min-area rectangle of the convex hull (rotating
    calipers); each edge position is then refined as the median coordinate
    of the points nearest that edge, which centers the fit on the wobbly
    centerline instead of its outer envelope.

    Returns (corners 4x2 [x, y], residual_p90) or None if degenerate.
    """
    if len(pts_yx) < 8:
        return None
    pts = np.array([[p[1], p[0]] for p in pts_yx], dtype=np.float64)  # (y,x) -> (x,y)
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(pts)
    except Exception:
        return None
    hp = pts[hull.vertices]

    best_rot: np.ndarray | None = None
    best_area = None
    for i in range(len(hp)):
        edge = hp[(i + 1) % len(hp)] - hp[i]
        norm = float(np.hypot(edge[0], edge[1]))
        if norm < 1e-9:
            continue
        ux, uy = edge / norm
        rot = np.array([[ux, uy], [-uy, ux]])
        rp = hp @ rot.T
        area = (rp[:, 0].max() - rp[:, 0].min()) * (rp[:, 1].max() - rp[:, 1].min())
        if best_area is None or area < best_area:
            best_area = area
            best_rot = rot
    if best_rot is None:
        return None

    rp = pts @ best_rot.T
    x0, x1 = float(rp[:, 0].min()), float(rp[:, 0].max())
    y0, y1 = float(rp[:, 1].min()), float(rp[:, 1].max())

    # Median-refine each edge from the points assigned (nearest) to it
    dists = np.stack([
        np.abs(rp[:, 0] - x0), np.abs(rp[:, 0] - x1),
        np.abs(rp[:, 1] - y0), np.abs(rp[:, 1] - y1),
    ], axis=1)
    edge_idx = dists.argmin(axis=1)

    def _median_or(sel: np.ndarray, coord: int, fallback: float) -> float:
        vals = rp[sel, coord]
        return float(np.median(vals)) if len(vals) >= 2 else fallback

    ex0 = _median_or(edge_idx == 0, 0, x0)
    ex1 = _median_or(edge_idx == 1, 0, x1)
    ey0 = _median_or(edge_idx == 2, 1, y0)
    ey1 = _median_or(edge_idx == 3, 1, y1)
    if ex1 - ex0 < 2.0 or ey1 - ey0 < 2.0:
        return None

    corners_rot = np.array([[ex0, ey0], [ex1, ey0], [ex1, ey1], [ex0, ey1]])
    corners = corners_rot @ best_rot  # inverse of orthonormal rotation

    # Residual: distance of each centerline point to the rect boundary
    out_dx = np.maximum.reduce([ex0 - rp[:, 0], rp[:, 0] - ex1, np.zeros(len(rp))])
    out_dy = np.maximum.reduce([ey0 - rp[:, 1], rp[:, 1] - ey1, np.zeros(len(rp))])
    inside_d = np.minimum(
        np.minimum(np.abs(rp[:, 0] - ex0), np.abs(rp[:, 0] - ex1)),
        np.minimum(np.abs(rp[:, 1] - ey0), np.abs(rp[:, 1] - ey1)),
    )
    outside = (out_dx > 0) | (out_dy > 0)
    residuals = np.where(outside, np.hypot(out_dx, out_dy), inside_d)
    return corners, float(np.percentile(residuals, 90))


def _trace_dashed_path(
    subs: list[np.ndarray], dp_epsilon: float
) -> list[list[float]]:
    """Single ordered open polyline through disjoint dash/dot substructures.

    Each dash contributes its skeleton centerline (or centroid when tiny);
    segments are then chained greedily by nearest endpoints starting from
    the leftmost segment, reversing segments as needed.
    """
    segments: list[list[list[float]]] = []
    for m in subs:
        ys, xs = np.where(m)
        if len(ys) <= 6:
            segments.append([[float(xs.mean()), float(ys.mean())]])
            continue
        skel = skeletonize(m)
        paths = trace_skeleton_paths(skel, min_path_len=2)
        if not paths:
            segments.append([[float(xs.mean()), float(ys.mean())]])
            continue
        best = max(paths, key=len)
        pts = _douglas_peucker([[float(p[1]), float(p[0])] for p in best], dp_epsilon)
        segments.append(pts)

    segments = [s for s in segments if s]
    if not segments:
        return []

    current = min(segments, key=lambda s: min(p[0] for p in s))
    remaining = [s for s in segments if s is not current]
    if current[0][0] > current[-1][0]:
        current = current[::-1]
    chained: list[list[float]] = list(current)

    while remaining:
        tail = chained[-1]
        best_seg = None
        best_d = None
        best_rev = False
        for seg in remaining:
            d_head = (seg[0][0] - tail[0]) ** 2 + (seg[0][1] - tail[1]) ** 2
            d_tail = (seg[-1][0] - tail[0]) ** 2 + (seg[-1][1] - tail[1]) ** 2
            d, rev = (d_head, False) if d_head <= d_tail else (d_tail, True)
            if best_d is None or d < best_d:
                best_seg, best_d, best_rev = seg, d, rev
        remaining.remove(best_seg)
        chained.extend(best_seg[::-1] if best_rev else best_seg)

    return [[round(p[0], 2), round(p[1], 2)] for p in chained]


def _vectorize_open_stroke(
    comp_mask: np.ndarray, comp_id: str, dp_epsilon: float, min_path_len: int
) -> list[dict[str, Any]]:
    skel = skeletonize(comp_mask)
    paths = trace_skeleton_paths(skel, min_path_len=min_path_len)

    if not paths:
        return []

    results = []
    for path in paths:
        pts = [[float(p[1]), float(p[0])] for p in path]  # (y,x) → [x,y]
        pts = _douglas_peucker(pts, dp_epsilon)
        if len(pts) >= min_path_len:
            closed = _pts_close(pts[0], pts[-1], tol=2.0)
            results.append({
                "component_id": comp_id,
                "geometry_kind": "open_centerline",
                "closed": closed,
                "ordered": True,
                "points_px": pts,
            })
    return results


def _pts_close(a: list[float], b: list[float], tol: float) -> bool:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= tol ** 2


def trace_skeleton_paths(skel: np.ndarray, min_path_len: int = DEFAULT_MIN_PATH_LEN) -> list[list[tuple[int, int]]]:
    """
    Trace skeleton into ordered pixel paths.

    Returns list of paths, each path is [(y, x), ...].
    Closed loops include the start pixel repeated at the end.
    All branches emitted as separate paths (kills single-path truncation).
    """
    pts: set[tuple[int, int]] = set(map(tuple, np.argwhere(skel)))  # type: ignore[arg-type]
    if not pts:
        return []

    def neighbors_8(pt: tuple[int, int]) -> list[tuple[int, int]]:
        y, x = pt
        return [(y + dy, x + dx)
                for dy, dx in [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                                (0, 1), (1, -1), (1, 0), (1, 1)]
                if (y + dy, x + dx) in pts]

    degrees = {pt: len(neighbors_8(pt)) for pt in pts}
    endpoints = sorted(pt for pt, d in degrees.items() if d <= 1)
    junctions = sorted(pt for pt, d in degrees.items() if d >= 3)
    special = set(endpoints) | set(junctions)

    used_edges: set[frozenset[tuple[int, int]]] = set()
    paths: list[list[tuple[int, int]]] = []

    def trace_edge(start: tuple[int, int], first_step: tuple[int, int]) -> list[tuple[int, int]]:
        path = [start, first_step]
        prev, cur = start, first_step
        while cur not in special:
            nbs = [n for n in neighbors_8(cur) if n != prev]
            if not nbs:
                break
            # Prefer direction aligned with previous step for smoother paths
            dy0, dx0 = cur[0] - prev[0], cur[1] - prev[1]
            nbs.sort(key=lambda n: -(( n[0] - cur[0]) * dy0 + (n[1] - cur[1]) * dx0))
            nxt = nbs[0]
            if nxt == start and len(path) > 2:
                path.append(nxt)
                return path
            prev, cur = cur, nxt
            path.append(cur)
        return path

    def record_edge_used(path: list[tuple[int, int]]) -> None:
        for i in range(len(path) - 1):
            used_edges.add(frozenset([path[i], path[i + 1]]))

    # Trace from each endpoint
    for start in endpoints:
        for step in neighbors_8(start):
            edge = frozenset([start, step])
            if edge in used_edges:
                continue
            path = trace_edge(start, step)
            record_edge_used(path)
            if len(path) >= min_path_len:
                paths.append(path)

    # Trace inter-junction and junction-to-endpoint edges
    for start in junctions:
        for step in neighbors_8(start):
            edge = frozenset([start, step])
            if edge in used_edges:
                continue
            path = trace_edge(start, step)
            record_edge_used(path)
            if len(path) >= min_path_len:
                paths.append(path)

    # Trace any remaining closed loops (no endpoints or junctions)
    for pt in sorted(pts):
        untraced = any(
            frozenset([pt, n]) not in used_edges for n in neighbors_8(pt)
        )
        if not untraced:
            continue
        nbs = [n for n in neighbors_8(pt) if frozenset([pt, n]) not in used_edges]
        if not nbs:
            continue
        path = trace_edge(pt, nbs[0])
        record_edge_used(path)
        if len(path) >= min_path_len:
            paths.append(path)

    return paths


def _douglas_peucker(points: list[list[float]], epsilon: float) -> list[list[float]]:
    """Simplify polyline using Douglas-Peucker algorithm."""
    if len(points) <= 2:
        return points

    def perp_dist(pt: list[float], start: list[float], end: list[float]) -> float:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if dx == 0 and dy == 0:
            return ((pt[0] - start[0]) ** 2 + (pt[1] - start[1]) ** 2) ** 0.5
        t = ((pt[0] - start[0]) * dx + (pt[1] - start[1]) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = start[0] + t * dx
        proj_y = start[1] + t * dy
        return ((pt[0] - proj_x) ** 2 + (pt[1] - proj_y) ** 2) ** 0.5

    def _dp(pts: list[list[float]], eps: float) -> list[list[float]]:
        if len(pts) <= 2:
            return pts
        max_dist = 0.0
        max_idx = 0
        for i in range(1, len(pts) - 1):
            d = perp_dist(pts[i], pts[0], pts[-1])
            if d > max_dist:
                max_dist = d
                max_idx = i
        if max_dist > eps:
            left = _dp(pts[: max_idx + 1], eps)
            right = _dp(pts[max_idx:], eps)
            return left[:-1] + right
        return [pts[0], pts[-1]]

    return _dp(points, epsilon)


def sample_geometry_points(polylines: list[dict[str, Any]], spacing: float = 1.0) -> list[list[float]]:
    """Sample polylines at ≤ spacing px intervals. Returns list of [x, y]."""
    pts: list[list[float]] = []
    for pl in polylines:
        pp = pl.get("points_px", [])
        if len(pp) == 0:
            continue
        if len(pp) == 1:
            pts.append(list(pp[0]))
            continue
        for i in range(len(pp) - 1):
            x0, y0 = pp[i][0], pp[i][1]
            x1, y1 = pp[i + 1][0], pp[i + 1][1]
            seg_len = max(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 1e-9)
            n_steps = max(1, int(seg_len / spacing))
            for k in range(n_steps):
                t = k / n_steps
                pts.append([x0 + t * (x1 - x0), y0 + t * (y1 - y0)])
        pts.append(list(pp[-1]))
    return pts
