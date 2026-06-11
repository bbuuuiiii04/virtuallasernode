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

import math
from typing import Any

import numpy as np
from skimage.morphology import closing, disk, skeletonize

DEFAULT_DP_EPSILON = 0.75
DEFAULT_MIN_PATH_LEN = 3

# Structure submask extraction
STRUCTURE_SAT_MIN = 110.0     # below this max(min_ch), comp has no saturated structure
STRUCTURE_OTSU_CLAMP = (100.0, 200.0)
STRUCTURE_MIN_PX = 8          # submask smaller than this falls back to full comp
STRUCTURE_MIN_SUB_PX = 3      # ignore sub-fragments smaller than this

# Rectangle snap: p90 distance of centerline points to fitted rect
RECT_SNAP_RESIDUAL_P90 = 1.75

LINE_SNAP_RESIDUAL_P90 = 1.5
GROUP_LINE_RESIDUAL_P90 = 2.0
LINE_MIN_SPAN_PX = 25.0
QUAD_SNAP_RESIDUAL_P90 = 2.5
QUAD_MIN_EDGE_SUPPORT = 8
QUAD_MIN_HOLE_FRACTION = 0.25
QUAD_CLOSE_RADIUS = 5
CHAIN_BRIDGE_GLOW_MIN = 0.85
CHAIN_BRIDGE_MAX_LEN_FRAC = 0.45
CHAIN_BRIDGE_MAX_LEN_MIN = 18.0
CHAIN_MAX_SHARP_TURNS = 1
CHAIN_SHARP_TURN_DEG = 60.0
CHAIN_MEAN_TURN_DEG_MAX = 25.0
CHAIN_TOTAL_BRIDGE_FRAC_MAX = 0.35

# Substructure classification
RING_HOLE_FRACTION = 0.15
DASH_MAX_ASPECT = 2.0
DASH_MAX_AREA = 400

# In-component dashed-path acceptance: the chained path must honestly cover
# the structure skeleton, otherwise per-substructure vectorization is kept.
DASHED_PATH_MIN_COVERAGE = 0.8
DASHED_PATH_COVERAGE_RADIUS = 3.0


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
    if structure_mask is None:
        structure_mask = extract_structure_submask(comp_mask, img_rgb)

    subs = _structure_subcomponents(structure_mask, comp_mask)
    kinds = [_classify_substructure(m) for m in subs]

    polys: list[dict[str, Any]] = []
    if comp_class == "dot" and len(subs) == 1 and kinds[0] == "dash":
        return _vectorize_dot(subs[0], score_map, comp_id)

    if "ring" not in kinds and len(subs) >= 2:
        # Disjoint dashes/dots from one emission may form a dashed/dotted
        # path, but only when the chained ordering is geometrically sane
        # (turn gates) and the path honestly covers the structure skeleton.
        # Otherwise each substructure keeps its own geometry.
        segments = _dash_segments(subs, dp_epsilon)
        path, bridge_spans, bridges = _chain_segments(segments, glow_mask=None)
        turn_reasons = _path_turn_rejection_reasons(path)
        if len(path) >= 2 and not turn_reasons:
            candidate = {
                "component_id": comp_id,
                "geometry_kind": "dotted_arc_path",
                "closed": False,
                "ordered": True,
                "dash_count": len(subs),
                "bridge_spans": bridge_spans,
                "bridges": bridges,
                "points_px": path,
            }
            union_structure = np.zeros_like(structure_mask, dtype=bool)
            for m in subs:
                union_structure |= m
            if _path_structure_coverage([candidate], union_structure) >= DASHED_PATH_MIN_COVERAGE:
                polys.append(candidate)
    if not polys and len(subs) >= 1:
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


def _path_turn_rejection_reasons(path: list[list[float]]) -> list[str]:
    """Turn-shape gates for an in-component dashed chain.

    Bridge length/glow gates do not apply inside one CORE component: the
    component's own glow connectivity is the physical evidence that the
    fragments belong to one emission. Ordering sanity (no sharp zigzag)
    still must hold.
    """
    reasons: list[str] = []
    turns = _turn_angles_deg(_resample_path(path, spacing=6.0))
    if turns:
        sharp = sum(1 for a in turns if a > CHAIN_SHARP_TURN_DEG)
        mean_turn = float(np.mean(np.abs(turns)))
        if sharp > CHAIN_MAX_SHARP_TURNS:
            reasons.append("chain_sharp_turns_above_threshold")
        if mean_turn > CHAIN_MEAN_TURN_DEG_MAX:
            reasons.append("chain_mean_turn_above_threshold")
    return reasons


def _path_structure_coverage(
    polylines: list[dict[str, Any]], structure_mask: np.ndarray
) -> float:
    """Fraction of the structure skeleton within DASHED_PATH_COVERAGE_RADIUS
    of the sampled path (local copy to avoid importing validation here)."""
    from skimage.morphology import dilation, disk
    H, W = structure_mask.shape
    skel = skeletonize(structure_mask)
    skel_count = int(np.sum(skel))
    if skel_count == 0:
        return 1.0
    geom_pts = sample_geometry_points(polylines, spacing=1.0)
    if not geom_pts:
        return 0.0
    geom_mask = np.zeros((H, W), dtype=bool)
    for gx, gy in geom_pts:
        xi, yi = int(round(gx)), int(round(gy))
        if 0 <= yi < H and 0 <= xi < W:
            geom_mask[yi, xi] = True
    r = max(1, int(np.ceil(DASHED_PATH_COVERAGE_RADIUS)))
    covered = int(np.sum(skel & dilation(geom_mask, disk(r))))
    return covered / skel_count


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
    """'ring' (encloses a hole), 'dash' (compact), or 'stroke' (elongated).

    Elongation uses both the axis-aligned bbox aspect and the PCA principal
    extent ratio: a diagonal dash has a square bbox but is clearly elongated
    along its principal axis.
    """
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
    aspect = max(aspect, _pca_extent_ratio(xs, ys))
    if aspect < DASH_MAX_ASPECT and area < DASH_MAX_AREA:
        return "dash"
    return "stroke"


def _pca_extent_ratio(xs: np.ndarray, ys: np.ndarray) -> float:
    """Ratio of pixel extents along the two PCA axes (>= 1.0)."""
    if len(xs) < 3:
        return 1.0
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    centered = pts - pts.mean(axis=0)
    try:
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return 1.0
    proj_major = centered @ vh[0]
    proj_minor = centered @ vh[1] if vh.shape[0] > 1 else np.zeros(len(pts))
    len_major = float(proj_major.max() - proj_major.min()) + 1.0
    len_minor = float(proj_minor.max() - proj_minor.min()) + 1.0
    return len_major / max(len_minor, 1.0)


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

    qfit = _fit_quad([[float(p[1]), float(p[0])] for p in skel_pts])
    if qfit is not None:
        corners, residual = qfit
        if residual <= QUAD_SNAP_RESIDUAL_P90:
            pts = [[round(float(corners[i % 4][0]), 2),
                    round(float(corners[i % 4][1]), 2)] for i in range(5)]
            return [{
                "component_id": comp_id,
                "geometry_kind": "quad_centerline",
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


def _fit_line(
    pts_xy: list[list[float]] | np.ndarray,
) -> tuple[tuple[float, float], tuple[float, float], float] | None:
    """PCA line fit. Returns endpoints and p90 perpendicular residual."""
    pts = np.asarray(pts_xy, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] != 2:
        return None
    mean = pts.mean(axis=0)
    centered = pts - mean
    try:
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    axis = vh[0]
    norm = float(np.hypot(axis[0], axis[1]))
    if norm < 1e-9:
        return None
    axis = axis / norm
    proj = centered @ axis
    p0 = mean + axis * float(proj.min())
    p1 = mean + axis * float(proj.max())
    residuals = np.abs(centered[:, 0] * axis[1] - centered[:, 1] * axis[0])
    return (float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1])), float(np.percentile(residuals, 90))


def _fit_quad(
    pts_xy: list[list[float]] | np.ndarray,
) -> tuple[np.ndarray, float] | None:
    """Fit a convex 4-edge centerline polygon to structure points."""
    pts = np.asarray(pts_xy, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[0] < 12 or pts.shape[1] != 2:
        return None
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(pts)
    except Exception:
        return None
    poly = [pts[i].copy() for i in hull.vertices]
    if len(poly) < 4:
        return None

    while len(poly) > 4:
        areas: list[tuple[float, int]] = []
        n = len(poly)
        for i in range(n):
            a, b, c = poly[(i - 1) % n], poly[i], poly[(i + 1) % n]
            ab = b - a
            bc = c - b
            area = abs(float(ab[0] * bc[1] - ab[1] * bc[0])) * 0.5
            areas.append((area, i))
        _, remove_idx = min(areas, key=lambda item: (item[0], item[1]))
        poly.pop(remove_idx)
    if len(poly) != 4:
        return None

    hull4 = np.asarray(poly, dtype=np.float64)
    dists = np.stack([
        _point_segment_distances(pts, hull4[i], hull4[(i + 1) % 4])
        for i in range(4)
    ], axis=1)
    edge_idx = dists.argmin(axis=1)
    if any(int(np.sum(edge_idx == i)) < QUAD_MIN_EDGE_SUPPORT for i in range(4)):
        return None

    lines: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(4):
        edge_pts = pts[edge_idx == i]
        line = _tls_line(edge_pts)
        if line is None:
            return None
        lines.append(line)

    corners: list[np.ndarray] = []
    for i in range(4):
        inter = _line_intersection(lines[i], lines[(i + 1) % 4])
        if inter is None or not np.all(np.isfinite(inter)):
            return None
        corners.append(inter)
    corners_arr = np.asarray(corners, dtype=np.float64)

    if not _is_convex_quad(corners_arr):
        return None
    edge_lens = [
        float(np.linalg.norm(corners_arr[(i + 1) % 4] - corners_arr[i]))
        for i in range(4)
    ]
    if min(edge_lens) < 3.0:
        return None

    residuals = np.min(np.stack([
        _point_segment_distances(pts, corners_arr[i], corners_arr[(i + 1) % 4])
        for i in range(4)
    ], axis=1), axis=1)
    return corners_arr, float(np.percentile(residuals, 90))


def _point_segment_distances(pts: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-9:
        return np.linalg.norm(pts - a, axis=1)
    t = ((pts - a) @ ab) / denom
    t = np.clip(t, 0.0, 1.0)
    proj = a + t[:, None] * ab
    return np.linalg.norm(pts - proj, axis=1)


def _tls_line(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    if pts.shape[0] < 2:
        return None
    mean = pts.mean(axis=0)
    centered = pts - mean
    try:
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    direction = vh[0]
    norm = float(np.linalg.norm(direction))
    if norm < 1e-9:
        return None
    return mean, direction / norm


def _line_intersection(
    line_a: tuple[np.ndarray, np.ndarray],
    line_b: tuple[np.ndarray, np.ndarray],
) -> np.ndarray | None:
    p, r = line_a
    q, s = line_b
    cross = float(r[0] * s[1] - r[1] * s[0])
    if abs(cross) < 1e-6:
        return None
    qp = q - p
    t = float((qp[0] * s[1] - qp[1] * s[0]) / cross)
    return p + t * r


def _is_convex_quad(corners: np.ndarray) -> bool:
    signs = []
    for i in range(4):
        a = corners[i]
        b = corners[(i + 1) % 4]
        c = corners[(i + 2) % 4]
        ab = b - a
        bc = c - b
        cross = float(ab[0] * bc[1] - ab[1] * bc[0])
        if abs(cross) < 1e-6:
            return False
        signs.append(cross > 0)
    return all(s == signs[0] for s in signs)


def _dash_segments(subs: list[np.ndarray], dp_epsilon: float) -> list[list[list[float]]]:
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
    return [s for s in segments if s]


def _chain_segments(
    segments: list[list[list[float]]],
    glow_mask: np.ndarray | None,
) -> tuple[list[list[float]], list[list[int]], list[dict[str, Any]]]:
    if not segments:
        return [], [], []

    current = min(segments, key=lambda s: min(p[0] for p in s))
    remaining = [s for s in segments if s is not current]
    if current[0][0] > current[-1][0]:
        current = current[::-1]
    chained: list[list[float]] = list(current)
    bridge_spans: list[list[int]] = []
    bridges: list[dict[str, Any]] = []

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
        next_seg = best_seg[::-1] if best_rev else best_seg
        bridge_idx = len(chained) - 1
        bridge_len = _point_distance(tail, next_seg[0])
        glow_cov = _line_glow_coverage(tail, next_seg[0], glow_mask) if glow_mask is not None else 1.0
        bridge_spans.append([bridge_idx, bridge_idx + 1])
        bridges.append({
            "from": bridge_idx,
            "to": bridge_idx + 1,
            "length_px": round(bridge_len, 3),
            "glow_coverage": round(glow_cov, 4),
        })
        chained.extend(next_seg)

    return [[round(p[0], 2), round(p[1], 2)] for p in chained], bridge_spans, bridges


def vectorize_group(
    member_masks: list[np.ndarray],
    member_structures: list[np.ndarray],
    member_classes: list[str],
    comp_ids: list[str],
    score_map: np.ndarray,
    glow_mask: np.ndarray,
    img_rgb: np.ndarray,
    dp_epsilon: float = DEFAULT_DP_EPSILON,
) -> list[dict[str, Any]] | None:
    """Vectorize a multi-component glow group as one canonical primitive."""
    if len(member_masks) < 2:
        return None
    union_structure = np.zeros_like(member_structures[0], dtype=bool)
    for m in member_structures:
        union_structure |= m
    fragments = _structure_subcomponents(union_structure, union_structure)
    kinds = [_classify_substructure(m) for m in fragments]
    anchor_id = comp_ids[int(np.argmax([int(m.sum()) for m in member_masks]))]
    members = list(comp_ids)

    if len(fragments) == 2 and all(k == "dash" for k in kinds):
        return None

    ys, xs = np.where(union_structure)
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    if len(pts) >= 2:
        line = _fit_line(pts)
        if line is not None:
            p0, p1, residual = line
            span = _point_distance(p0, p1)
            if residual <= GROUP_LINE_RESIDUAL_P90 and span >= LINE_MIN_SPAN_PX:
                return [{
                    "component_id": anchor_id,
                    "member_component_ids": members,
                    "geometry_kind": "line_centerline",
                    "closed": False,
                    "ordered": True,
                    "fit_residual_px_p90": round(residual, 3),
                    "points_px": [[round(p0[0], 2), round(p0[1], 2)],
                                  [round(p1[0], 2), round(p1[1], 2)]],
                }]

    from scipy.ndimage import binary_fill_holes
    closed = closing(union_structure, disk(QUAD_CLOSE_RADIUS))
    filled = binary_fill_holes(closed)
    filled_px = int(np.sum(filled))
    if filled_px > 0:
        hole_fraction = (filled_px - int(np.sum(closed))) / filled_px
        if hole_fraction >= QUAD_MIN_HOLE_FRACTION:
            qfit = _fit_quad(pts)
            if qfit is not None:
                corners, residual = qfit
                if residual <= QUAD_SNAP_RESIDUAL_P90:
                    qpts = [[round(float(corners[i % 4][0]), 2),
                             round(float(corners[i % 4][1]), 2)] for i in range(5)]
                    return [{
                        "component_id": anchor_id,
                        "member_component_ids": members,
                        "geometry_kind": "quad_centerline",
                        "closed": True,
                        "ordered": True,
                        "fit_residual_px_p90": round(residual, 3),
                        "points_px": qpts,
                    }]

    if len(fragments) >= 2:
        segments = _dash_segments(fragments, dp_epsilon)
        path, bridge_spans, bridges = _chain_segments(segments, glow_mask=glow_mask)
        if len(path) >= 2 and _chain_passes_gates(path, bridges):
            return [{
                "component_id": anchor_id,
                "member_component_ids": members,
                "geometry_kind": "dotted_arc_path",
                "closed": False,
                "ordered": True,
                "dash_count": len(fragments),
                "bridge_spans": bridge_spans,
                "bridges": bridges,
                "points_px": path,
            }]
    return None


def group_chain_rejection_reasons(
    member_structures: list[np.ndarray],
    glow_mask: np.ndarray,
    dp_epsilon: float = DEFAULT_DP_EPSILON,
) -> list[str]:
    if len(member_structures) < 2:
        return []
    union_structure = np.zeros_like(member_structures[0], dtype=bool)
    for m in member_structures:
        union_structure |= m
    fragments = _structure_subcomponents(union_structure, union_structure)
    kinds = [_classify_substructure(m) for m in fragments]
    if len(fragments) == 2 and all(k == "dash" for k in kinds):
        return ["two_compact_dots"]
    if len(fragments) < 2:
        return []
    segments = _dash_segments(fragments, dp_epsilon)
    path, _, bridges = _chain_segments(segments, glow_mask=glow_mask)
    return _chain_rejection_reasons(path, bridges)


def _chain_passes_gates(path: list[list[float]], bridges: list[dict[str, Any]]) -> bool:
    return not _chain_rejection_reasons(path, bridges)


def _chain_rejection_reasons(path: list[list[float]], bridges: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if not bridges:
        return reasons
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    span = max(float(np.hypot(max(xs) - min(xs), max(ys) - min(ys))), 1e-9)
    max_bridge = max(CHAIN_BRIDGE_MAX_LEN_MIN, CHAIN_BRIDGE_MAX_LEN_FRAC * span)
    total_bridge = 0.0
    for b in bridges:
        length = float(b["length_px"])
        total_bridge += length
        if float(b["glow_coverage"]) < CHAIN_BRIDGE_GLOW_MIN:
            reasons.append("chain_bridge_glow_below_threshold")
        if length > max_bridge:
            reasons.append("chain_bridge_length_above_threshold")
    path_len = max(_path_length(path), 1e-9)
    if total_bridge > CHAIN_TOTAL_BRIDGE_FRAC_MAX * path_len:
        reasons.append("chain_total_bridge_fraction_above_threshold")
    turns = _turn_angles_deg(_resample_path(path, spacing=6.0))
    if turns:
        sharp = sum(1 for a in turns if a > CHAIN_SHARP_TURN_DEG)
        mean_turn = float(np.mean(np.abs(turns)))
        if sharp > CHAIN_MAX_SHARP_TURNS:
            reasons.append("chain_sharp_turns_above_threshold")
        if mean_turn > CHAIN_MEAN_TURN_DEG_MAX:
            reasons.append("chain_mean_turn_above_threshold")
    return reasons


def _point_distance(a: list[float] | tuple[float, float], b: list[float] | tuple[float, float]) -> float:
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))


def _path_length(path: list[list[float]]) -> float:
    return sum(_point_distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def _line_glow_coverage(a: list[float], b: list[float], glow_mask: np.ndarray | None) -> float:
    if glow_mask is None:
        return 1.0
    H, W = glow_mask.shape
    length = max(_point_distance(a, b), 1e-9)
    n = max(1, int(math.ceil(length)))
    inside = 0
    total = 0
    for k in range(n + 1):
        t = k / n
        x = a[0] + t * (b[0] - a[0])
        y = a[1] + t * (b[1] - a[1])
        xi, yi = int(round(x)), int(round(y))
        if 0 <= yi < H and 0 <= xi < W:
            total += 1
            if glow_mask[yi, xi]:
                inside += 1
    return inside / total if total else 0.0


def _resample_path(path: list[list[float]], spacing: float) -> list[list[float]]:
    if len(path) <= 1:
        return path
    out = [list(path[0])]
    carry = 0.0
    prev = list(path[0])
    for cur in path[1:]:
        cur = list(cur)
        seg_len = _point_distance(prev, cur)
        if seg_len < 1e-9:
            prev = cur
            continue
        direction = [(cur[0] - prev[0]) / seg_len, (cur[1] - prev[1]) / seg_len]
        dist = spacing - carry
        while dist <= seg_len:
            out.append([prev[0] + direction[0] * dist, prev[1] + direction[1] * dist])
            dist += spacing
        carry = max(0.0, seg_len - (dist - spacing))
        prev = cur
    if _point_distance(out[-1], path[-1]) > 1e-6:
        out.append(list(path[-1]))
    return out


def _turn_angles_deg(path: list[list[float]]) -> list[float]:
    turns: list[float] = []
    for i in range(1, len(path) - 1):
        a = np.array(path[i], dtype=np.float64) - np.array(path[i - 1], dtype=np.float64)
        b = np.array(path[i + 1], dtype=np.float64) - np.array(path[i], dtype=np.float64)
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na < 1e-9 or nb < 1e-9:
            continue
        cosv = float(np.clip((a @ b) / (na * nb), -1.0, 1.0))
        turns.append(math.degrees(math.acos(cosv)))
    return turns


def _vectorize_open_stroke(
    comp_mask: np.ndarray, comp_id: str, dp_epsilon: float, min_path_len: int
) -> list[dict[str, Any]]:
    skel = skeletonize(comp_mask)
    paths = trace_skeleton_paths(skel, min_path_len=min_path_len)

    if not paths:
        return []

    if len(paths) == 1 and _is_non_branching_skeleton(skel):
        raw_pts = [[float(p[1]), float(p[0])] for p in paths[0]]
        fit = _fit_line(raw_pts)
        if fit is not None:
            p0, p1, residual = fit
            if residual <= LINE_SNAP_RESIDUAL_P90:
                return [{
                    "component_id": comp_id,
                    "geometry_kind": "line_centerline",
                    "closed": False,
                    "ordered": True,
                    "fit_residual_px_p90": round(residual, 3),
                    "points_px": [[round(p0[0], 2), round(p0[1], 2)],
                                  [round(p1[0], 2), round(p1[1], 2)]],
                }]

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


def _is_non_branching_skeleton(skel: np.ndarray) -> bool:
    from scipy.ndimage import convolve
    kernel = np.ones((3, 3), dtype=np.int32)
    kernel[1, 1] = 0
    neighbor_count = convolve(skel.astype(np.int32), kernel, mode="constant", cval=0)
    return not bool(np.any(skel & (neighbor_count >= 3)))


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


def sample_geometry_points_with_bridge_flags(
    polylines: list[dict[str, Any]], spacing: float = 1.0
) -> tuple[list[list[float]], list[bool]]:
    """Sample polylines and mark samples that lie on accepted bridge spans."""
    pts: list[list[float]] = []
    bridge_flags: list[bool] = []
    for pl in polylines:
        pp = pl.get("points_px", [])
        if len(pp) == 0:
            continue
        if len(pp) == 1:
            pts.append(list(pp[0]))
            bridge_flags.append(False)
            continue
        bridge_segments = {
            (int(span[0]), int(span[1]))
            for span in pl.get("bridge_spans", [])
            if isinstance(span, list) and len(span) == 2
        }
        last_flag = False
        for i in range(len(pp) - 1):
            x0, y0 = pp[i][0], pp[i][1]
            x1, y1 = pp[i + 1][0], pp[i + 1][1]
            seg_len = max(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 1e-9)
            n_steps = max(1, int(seg_len / spacing))
            is_bridge = (i, i + 1) in bridge_segments
            for k in range(n_steps):
                t = k / n_steps
                pts.append([x0 + t * (x1 - x0), y0 + t * (y1 - y0)])
                bridge_flags.append(is_bridge)
            last_flag = is_bridge
        pts.append(list(pp[-1]))
        bridge_flags.append(last_flag)
    return pts, bridge_flags


def sample_geometry_points(polylines: list[dict[str, Any]], spacing: float = 1.0) -> list[list[float]]:
    """Sample polylines at ≤ spacing px intervals. Returns list of [x, y]."""
    pts, _ = sample_geometry_points_with_bridge_flags(polylines, spacing=spacing)
    return pts
