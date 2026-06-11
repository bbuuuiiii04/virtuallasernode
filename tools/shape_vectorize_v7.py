"""V7 per-component vectorization: dot anchors, closed centerlines, open paths."""

from __future__ import annotations

from typing import Any

import numpy as np
from skimage.morphology import skeletonize

DEFAULT_DP_EPSILON = 0.75
DEFAULT_MIN_PATH_LEN = 3


def vectorize_component(
    comp_mask: np.ndarray,
    comp_class: str,
    score_map: np.ndarray,
    comp_id: str,
    dp_epsilon: float = DEFAULT_DP_EPSILON,
    min_path_len: int = DEFAULT_MIN_PATH_LEN,
) -> list[dict[str, Any]]:
    """
    Returns list of polyline dicts for one component.

    Each dict has keys: geometry_kind, closed, ordered, points_px (list of [x,y]).
    """
    if comp_class == "dot":
        return _vectorize_dot(comp_mask, score_map, comp_id)
    elif comp_class == "closed_stroke":
        return _vectorize_closed_stroke(comp_mask, comp_id, dp_epsilon, min_path_len, score_map)
    else:
        return _vectorize_open_stroke(comp_mask, comp_id, dp_epsilon, min_path_len)


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


def _vectorize_closed_stroke(
    comp_mask: np.ndarray, comp_id: str, dp_epsilon: float, min_path_len: int,
    score_map: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    skel = skeletonize(comp_mask)
    paths = trace_skeleton_paths(skel, min_path_len=min_path_len)

    skel_pts = np.sum(skel)
    # Prefer closed paths; fall back to longest open path
    # Ignore micro-loops that are tiny relative to the component skeleton
    closed_paths = [
        p for p in paths 
        if len(p) > 2 and _pts_close(p[0], p[-1], tol=2.0)
        and len(p) >= max(min_path_len, int(skel_pts * 0.05), 8)
    ]
    open_paths = [p for p in paths if p not in closed_paths]

    if not closed_paths and open_paths:
        # Skeleton trace didn't close — use contour of filled component as fallback
        from scipy.ndimage import binary_fill_holes
        from skimage.measure import find_contours
        filled = binary_fill_holes(comp_mask)
        contours = find_contours(filled.astype(float), 0.5)
        if contours:
            longest = max(contours, key=len)
            path_xy = [[float(pt[1]), float(pt[0])] for pt in longest]
            path_xy = _douglas_peucker(path_xy, dp_epsilon)
            if len(path_xy) >= min_path_len:
                return [{
                    "component_id": comp_id,
                    "geometry_kind": "closed_centerline",
                    "closed": True,
                    "ordered": True,
                    "points_px": path_xy,
                }]
        # Last resort: use any traced paths
        if open_paths:
            best = max(open_paths, key=len)
            pts = _douglas_peucker([[float(p[1]), float(p[0])] for p in best], dp_epsilon)
            return [{
                "component_id": comp_id,
                "geometry_kind": "closed_centerline",
                "closed": False,
                "ordered": True,
                "points_px": pts,
            }]
        return []

    results = []
    for path in (closed_paths if closed_paths else open_paths[:1]):
        pts = [[float(p[1]), float(p[0])] for p in path]  # (y,x) → [x,y]
        pts = _douglas_peucker(pts, dp_epsilon)
        if len(pts) >= min_path_len:
            results.append({
                "component_id": comp_id,
                "geometry_kind": "closed_centerline",
                "closed": True,
                "ordered": True,
                "points_px": pts,
            })

    # Peak-contour fallback for compact blobs where the skeleton centerline
    # is uninformative (e.g. a tiny closed loop inside a filled laser spot).
    # Instead of tracing the full outer mask boundary (which extends into
    # the glow), threshold the score_map at p75 within the mask to reveal
    # the peak-intensity arc/crescent structure inside.
    if results and score_map is not None:
        best_pl = max(results, key=lambda r: len(r["points_px"]))
        best_pts = best_pl["points_px"]
        path_len = sum(
            ((best_pts[i][0] - best_pts[i+1][0])**2 + (best_pts[i][1] - best_pts[i+1][1])**2)**0.5
            for i in range(len(best_pts) - 1)
        )
        path_len += ((best_pts[-1][0] - best_pts[0][0])**2 + (best_pts[-1][1] - best_pts[0][1])**2)**0.5

        from skimage.measure import perimeter as _mask_perimeter
        mask_perim = _mask_perimeter(comp_mask)

        # Only trigger for compact blobs: short skeleton + high solidity
        ys, xs = np.where(comp_mask)
        area = len(ys)
        bbox_h = int(ys.max() - ys.min() + 1)
        bbox_w = int(xs.max() - xs.min() + 1)
        solidity = area / max(1, bbox_h * bbox_w)

        if path_len < mask_perim * 0.5 and solidity > 0.65:
            peak_result = _peak_contour_fallback(
                comp_mask, score_map, comp_id, dp_epsilon, min_path_len
            )
            if peak_result:
                return peak_result

    return results


def _peak_contour_fallback(
    comp_mask: np.ndarray,
    score_map: np.ndarray,
    comp_id: str,
    dp_epsilon: float,
    min_path_len: int,
) -> list[dict[str, Any]]:
    """Trace contours of peak-intensity pixels within a compact CORE blob.

    For compact blobs where the skeleton produces a tiny uninformative loop,
    threshold the score_map at p75 within the mask to reveal internal
    arc/crescent features. Returns the largest contour as a peak_contour
    polyline, which traces the actual laser pattern rather than the
    full outer mask boundary (which extends into the glow region).
    """
    from skimage.measure import find_contours

    # Compute p75 threshold of score within this component
    scores_in_mask = score_map[comp_mask]
    if len(scores_in_mask) == 0:
        return []
    thresh = float(np.percentile(scores_in_mask, 75))

    # Create sub-mask of peak pixels
    sub_mask = np.zeros_like(comp_mask)
    sub_mask[comp_mask] = score_map[comp_mask] >= thresh

    if np.sum(sub_mask) < 5:
        return []

    # Trace contours of the sub-mask
    contours = find_contours(sub_mask.astype(float), 0.5)
    if not contours:
        return []

    # Use the longest contour (the main arc feature)
    longest = max(contours, key=len)
    pts = [[float(pt[1]), float(pt[0])] for pt in longest]  # (y,x) → [x,y]
    pts = _douglas_peucker(pts, dp_epsilon)

    if len(pts) < min_path_len:
        return []

    return [{
        "component_id": comp_id,
        "geometry_kind": "peak_contour",
        "closed": True,
        "ordered": True,
        "points_px": pts,
    }]


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
