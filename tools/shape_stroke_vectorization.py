"""PR-G1 v6: typed stroke-vectorization pipeline."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from tools.shape_extraction import (
    DEFAULT_CONTOUR_SAMPLE_STEP,
    DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
    DEFAULT_MIN_CORE_AREA_PX,
    FixtureBox,
    _component_aspect,
    _component_span,
    _component_stats,
    _contour_polyline,
    _forms_rectangular_frame,
    _has_interior_hole,
    _is_line_like,
    _is_thin_core_ring,
    _percentile,
    _pixels_to_polyline,
    _trace_boundary_contour,
    bbox_wall_norm_from_pixel_bbox,
    classify_topology,
    pixel_to_wall_norm,
)
from tools.shape_hysteresis_support import SupportMasks, build_hysteresis_support
from tools.shape_laser_maps import LaserMaps, build_laser_maps
from tools.shape_skeleton_graph import (
    build_skeleton_graph,
    longest_geodesic_path,
    path_length_px,
    skeletonize_support_mask,
    split_skeleton_paths,
    trace_skeleton_from_mask,
)

SHAPE_TYPES = (
    "continuous_stroke",
    "dotted_pattern",
    "dot_cluster",
    "closed_loop",
    "branched_complex",
    "unknown",
)

VECTORIZER_NAMES = (
    "skeleton_graph_stroke",
    "dotted_component_vectorizer",
    "dot_cluster_vectorizer",
    "closed_loop_contour",
    "skeleton_branch_vectorizer",
)

VECTORIZER_ELIGIBILITY: dict[str, tuple[str, ...]] = {
    "continuous_stroke": ("skeleton_graph_stroke",),
    "dotted_pattern": ("dotted_component_vectorizer",),
    "dot_cluster": ("dot_cluster_vectorizer",),
    "closed_loop": ("closed_loop_contour",),
    "branched_complex": ("skeleton_branch_vectorizer", "skeleton_graph_stroke"),
    "unknown": ("skeleton_graph_stroke", "dotted_component_vectorizer", "dot_cluster_vectorizer"),
}


@dataclass
class VectorResult:
    vectorizer: str
    shape_type: str
    clusters: list[dict[str, Any]] = field(default_factory=list)
    polylines: list[dict[str, Any]] = field(default_factory=list)
    support_components: list[list[tuple[int, int]]] = field(default_factory=list)
    topology: str = "unknown"
    quality_flags: list[str] = field(default_factory=list)
    geometry_scores: dict[str, float] = field(default_factory=dict)
    reject_reasons: list[str] = field(default_factory=list)
    score: float = -9999.0


def _mask_to_pixels(mask: list[list[bool]]) -> list[tuple[int, int]]:
    return [(x, y) for y in range(len(mask)) for x in range(len(mask[0])) if mask[y][x]]


def _component_centroid(comp: list[tuple[int, int]]) -> tuple[float, float]:
    return sum(p[0] for p in comp) / len(comp), sum(p[1] for p in comp) / len(comp)


def _components_form_broken_stroke(components: list[list[tuple[int, int]]]) -> bool:
    """True when separated support blobs still belong to one U/arc/line stroke."""
    if len(components) < 2 or len(components) > 5:
        return False
    cents = [_component_centroid(c) for c in components]
    xs = [c[0] for c in cents]
    ys = [c[1] for c in cents]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    if len(components) == 2:
        if all(len(c) < 220 and _component_aspect(c) < 2.8 for c in components):
            return False
        if all(_component_aspect(c) < 2.5 for c in components) and span_y < 25:
            return False
        return span_x >= 18 and (span_x + span_y) >= 40
    return span_x >= 18 and span_y >= 18 and (span_x + span_y) >= 50


def _components_along_arc(components: list[list[tuple[int, int]]]) -> bool:
    if len(components) < 3:
        return False
    cents = [_component_centroid(c) for c in components]
    xs = [c[0] for c in cents]
    ys = [c[1] for c in cents]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    return span_x > 20 and span_y > 8 and max(span_x, span_y) / max(1.0, min(span_x, span_y)) >= 1.4


def _is_ring_topology(comp: list[tuple[int, int]]) -> bool:
    if not (_is_thin_core_ring(comp) or _has_interior_hole(comp)):
        return False
    w, h = _component_span(comp)
    aspect = max(w, h) / max(1.0, min(w, h))
    return aspect < 2.4 and min(w, h) >= 12


def _count_branch_points_on_support(support_mask: list[list[bool]]) -> int:
    skel = skeletonize_support_mask(support_mask)
    graph = build_skeleton_graph(skel)
    return len(graph.branch_points())


def classify_shape_type(support: SupportMasks, maps: LaserMaps) -> str:
    comps = support.support_components
    if not comps:
        return "unknown"

    major = sorted(comps, key=len, reverse=True)
    if _forms_rectangular_frame(major):
        return "closed_loop"
    if len(major) >= 4 and sum(1 for c in major if _is_line_like(c)) >= 3:
        return "closed_loop"
    if len(major) == 2:
        if _components_form_broken_stroke(major):
            return "continuous_stroke"
        c0 = _component_centroid(major[0])
        c1 = _component_centroid(major[1])
        dist = math.hypot(c0[0] - c1[0], c0[1] - c1[1])
        if dist >= maps.w * 0.28 and all(len(c) < 220 and _component_aspect(c) < 2.8 for c in major):
            return "dot_cluster"
        if dist >= maps.w * 0.28 and all(len(c) >= 80 and _component_aspect(c) < 3.2 for c in major):
            return "dot_cluster"
    if len(major) == 1:
        comp = major[0]
        if _is_line_like(comp):
            return "continuous_stroke"
        if _is_ring_topology(comp):
            return "closed_loop"
        branches = _count_branch_points_on_support(support.support_mask)
        w, h = _component_span(comp)
        aspect = max(w, h) / max(1.0, min(w, h))
        if branches >= 4 and aspect < 1.8 and len(comp) >= 400:
            return "branched_complex"
        return "continuous_stroke"

    compact = [c for c in major if len(c) <= 140 and _component_aspect(c) < 2.8]
    if len(compact) >= 3:
        if _components_along_arc(compact):
            return "dotted_pattern"
        return "dot_cluster"

    if len(major) >= 2:
        if _components_form_broken_stroke(major):
            return "continuous_stroke"
        all_pts = [p for c in major for p in c]
        w, h = _component_span(all_pts)
        aspect = max(w, h) / max(1.0, min(w, h))
        if aspect >= 1.6 and len(major) <= 5:
            return "continuous_stroke"
        if _count_branch_points_on_support(support.support_mask) >= 4 and aspect < 2.0:
            return "branched_complex"

    return "unknown"


def _polyline_from_path(
    path: list[tuple[int, int]],
    box: FixtureBox,
    poly_id: str,
    *,
    closed: bool = False,
    source: str = "skeleton",
) -> dict[str, Any] | None:
    if len(path) < 1:
        return None
    if len(path) == 1:
        x, y = path[0]
        pt = list(pixel_to_wall_norm(x + box.x0, y + box.y0, box))
        return {
            "polyline_id": poly_id,
            "points": [pt],
            "source": source,
            "closed": False,
            "point_count": 1,
        }
    points = _pixels_to_polyline(path, box, epsilon=0.4)
    if len(points) < 2:
        return None
    return {
        "polyline_id": poly_id,
        "points": points,
        "source": source,
        "closed": closed,
        "point_count": len(points),
    }


def vectorize_continuous_stroke(
    support: SupportMasks,
    box: FixtureBox,
    maps: LaserMaps,
) -> VectorResult:
    skel = skeletonize_support_mask(support.support_mask)
    graph = build_skeleton_graph(skel)
    main_path = longest_geodesic_path(graph)
    paths = [main_path] if len(main_path) >= 2 else trace_skeleton_from_mask(support.support_mask)
    polylines: list[dict[str, Any]] = []
    for i, path in enumerate(paths[:1]):
        poly = _polyline_from_path(path, box, f"p{i}")
        if poly:
            polylines.append(poly)
    clusters = [
        {"cluster_id": f"c{i}", **_component_stats(comp, box)}
        for i, comp in enumerate(support.support_components)
    ]
    topology = classify_topology(support.support_components, DEFAULT_MIN_CORE_AREA_PX)
    return VectorResult(
        vectorizer="skeleton_graph_stroke",
        shape_type="continuous_stroke",
        clusters=clusters,
        polylines=polylines,
        support_components=support.support_components,
        topology=topology,
        quality_flags=["skeleton_graph_used", "hysteresis_support", "multi_candidate_v6"]
        + (["colored_core_recovered"] if len(_active_color_components(maps, support)) >= 2 else []),
    )


def vectorize_dotted_pattern(
    support: SupportMasks,
    box: FixtureBox,
    maps: LaserMaps,
) -> VectorResult:
    polylines: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    for i, comp in enumerate(sorted(support.support_components, key=len)):
        if len(comp) < DEFAULT_MIN_CORE_AREA_PX:
            continue
        cx, cy = _component_centroid(comp)
        pt = list(pixel_to_wall_norm(cx + box.x0, cy + box.y0, box))
        polylines.append(
            {
                "polyline_id": f"dot{i}",
                "points": [pt],
                "source": "dot_centroid",
                "closed": False,
                "point_count": 1,
            }
        )
        clusters.append({"cluster_id": f"c{i}", **_component_stats(comp, box)})
    topology = "multi_cluster" if len(polylines) >= 3 else "two_clusters"
    return VectorResult(
        vectorizer="dotted_component_vectorizer",
        shape_type="dotted_pattern",
        clusters=clusters,
        polylines=polylines,
        support_components=support.support_components,
        topology=topology,
        quality_flags=["dotted_pattern_preserved", "hysteresis_support", "multi_candidate_v6"],
    )


def vectorize_dot_cluster(
    support: SupportMasks,
    box: FixtureBox,
    maps: LaserMaps,
) -> VectorResult:
    base = vectorize_dotted_pattern(support, box, maps)
    base.vectorizer = "dot_cluster_vectorizer"
    base.shape_type = "dot_cluster"
    base.quality_flags = ["dot_cluster_preserved", "hysteresis_support", "multi_candidate_v6"]
    return base


def vectorize_closed_loop(
    support: SupportMasks,
    box: FixtureBox,
    maps: LaserMaps,
) -> VectorResult:
    polylines: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    for i, comp in enumerate(support.support_components):
        if not _is_ring_topology(comp):
            continue
        points = _contour_polyline(
            comp,
            box,
            closed=True,
            simplify_epsilon=DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
            sample_step=DEFAULT_CONTOUR_SAMPLE_STEP,
        )
        if len(points) >= 4:
            polylines.append(
                {
                    "polyline_id": f"ring{i}",
                    "points": points,
                    "source": "contour",
                    "closed": True,
                    "point_count": len(points),
                }
            )
            clusters.append({"cluster_id": f"c{i}", **_component_stats(comp, box)})
    if not polylines and len(support.support_pixels) >= 40:
        contour = _trace_boundary_contour(support.support_pixels)
        points = _contour_polyline(
            contour,
            box,
            closed=True,
            simplify_epsilon=DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
            sample_step=DEFAULT_CONTOUR_SAMPLE_STEP,
        )
        if len(points) >= 4:
            polylines.append(
                {
                    "polyline_id": "ring0",
                    "points": points,
                    "source": "contour",
                    "closed": True,
                    "point_count": len(points),
                }
            )
            clusters.append(
                {
                    "cluster_id": "c0",
                    **_component_stats(support.support_pixels, box),
                }
            )
    return VectorResult(
        vectorizer="closed_loop_contour",
        shape_type="closed_loop",
        clusters=clusters,
        polylines=polylines,
        support_components=support.support_components,
        topology="closed_loop",
        quality_flags=["contour_ring_only", "hysteresis_support", "multi_candidate_v6"],
    )


def vectorize_branched_complex(
    support: SupportMasks,
    box: FixtureBox,
    maps: LaserMaps,
) -> VectorResult:
    paths = split_skeleton_paths(build_skeleton_graph(skeletonize_support_mask(support.support_mask)))
    polylines: list[dict[str, Any]] = []
    for i, path in enumerate(paths):
        poly = _polyline_from_path(path, box, f"branch{i}")
        if poly:
            polylines.append(poly)
    clusters = [
        {"cluster_id": f"c{i}", **_component_stats(comp, box)}
        for i, comp in enumerate(support.support_components)
    ]
    return VectorResult(
        vectorizer="skeleton_branch_vectorizer",
        shape_type="branched_complex",
        clusters=clusters,
        polylines=polylines,
        support_components=support.support_components,
        topology="complex_shape",
        quality_flags=["skeleton_branches_used", "hysteresis_support", "multi_candidate_v6"],
    )


VECTORIZER_FUNCS = {
    "skeleton_graph_stroke": vectorize_continuous_stroke,
    "dotted_component_vectorizer": vectorize_dotted_pattern,
    "dot_cluster_vectorizer": vectorize_dot_cluster,
    "closed_loop_contour": vectorize_closed_loop,
    "skeleton_branch_vectorizer": vectorize_branched_complex,
}


def _wall_to_crop_px(x_norm: float, y_norm: float, box: FixtureBox) -> tuple[float, float]:
    px = ((x_norm + 1.0) / 2.0) * box.width
    py = ((1.0 - y_norm) / 2.0) * box.height
    return px, py


def _sample_polyline_pixels(polylines: list[dict[str, Any]], box: FixtureBox) -> list[tuple[float, float]]:
    samples: list[tuple[float, float]] = []
    for poly in polylines:
        pts = poly.get("points") or []
        for i, p in enumerate(pts):
            if len(p) < 2:
                continue
            samples.append(_wall_to_crop_px(p[0], p[1], box))
            if i + 1 < len(pts) and len(pts[i + 1]) >= 2:
                a = samples[-1]
                b = _wall_to_crop_px(pts[i + 1][0], pts[i + 1][1], box)
                steps = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1])))
                for t in range(1, steps):
                    f = t / steps
                    samples.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
    return samples


def _near_sample(px: float, py: float, samples: list[tuple[float, float]], radius: float) -> bool:
    r2 = radius * radius
    for sx, sy in samples:
        dx = sx - px
        dy = sy - py
        if dx * dx + dy * dy <= r2:
            return True
    return False


def _active_color_components(maps: LaserMaps, support: SupportMasks) -> list[tuple[str, list[tuple[int, int]]]]:
    active: list[tuple[str, list[tuple[int, int]]]] = []
    for name, cmap in maps.color_maps.items():
        pts = [
            (x, y)
            for y in range(maps.h)
            for x in range(maps.w)
            if support.support_mask[y][x] and cmap[y][x] >= maps.med + 1.5 * maps.mad
        ]
        if len(pts) >= 4:
            active.append((name, pts))
    return active


def score_geometry_fit(
    result: VectorResult,
    support: SupportMasks,
    maps: LaserMaps,
    box: FixtureBox,
    routed_shape_type: str,
) -> VectorResult:
    reasons: list[str] = []
    scores: dict[str, float] = {}

    if not result.polylines:
        result.score = -1000.0
        result.reject_reasons = ["no_polylines"]
        result.geometry_scores = {"total": -1000.0}
        return result

    samples = _sample_polyline_pixels(result.polylines, box)
    support_set = set(support.support_pixels)
    core_set = set(support.high_core_pixels)

    stroke_pts = support.support_pixels or support.high_core_pixels
    covered = sum(1 for px in stroke_pts if _near_sample(px[0], px[1], samples, 3.5))
    stroke_cov = covered / max(1, len(stroke_pts))
    scores["stroke_coverage_score"] = stroke_cov

    if samples:
        precise = sum(
            1
            for sx, sy in samples
            if any((int(sx + dx), int(sy + dy)) in support_set for dx in range(-2, 3) for dy in range(-2, 3))
        )
        geom_prec = precise / len(samples)
    else:
        geom_prec = 0.0
    scores["geometry_precision_score"] = geom_prec

    color_components = _active_color_components(maps, support)
    if color_components:
        color_hits = 0
        for _name, pts in color_components:
            if any(_near_sample(x, y, samples, 5.0) for x, y in pts[:: max(1, len(pts) // 8)]):
                color_hits += 1
        color_span = color_hits / len(color_components)
    else:
        color_span = 1.0 if stroke_cov > 0.4 else 0.0
    scores["color_span_score"] = color_span

    dot_expected = len([c for c in support.support_components if len(c) <= 160])
    if result.shape_type in ("dotted_pattern", "dot_cluster"):
        dot_score = min(1.0, len(result.polylines) / max(1, dot_expected))
    else:
        dot_score = 1.0
    scores["dot_preservation_score"] = dot_score

    if result.shape_type == "continuous_stroke":
        main_path = longest_geodesic_path(build_skeleton_graph(skeletonize_support_mask(support.support_mask)))
        support_len = path_length_px(main_path)
        poly_lens = []
        for poly in result.polylines:
            pix_path = []
            for p in poly.get("points") or []:
                if len(p) >= 2:
                    px, py = _wall_to_crop_px(p[0], p[1], box)
                    pix_path.append((int(round(px)), int(round(py))))
            if len(pix_path) >= 2:
                poly_lens.append(path_length_px(pix_path))
        main_len = max(poly_lens) if poly_lens else 0.0
        continuity = min(1.0, main_len / max(1.0, support_len * 0.5)) if support_len > 0 else stroke_cov
    else:
        continuity = 1.0 if result.polylines else 0.0
    scores["continuity_score"] = continuity

    topology_match = 1.0 if result.shape_type == routed_shape_type else 0.45
    scores["topology_match_score"] = topology_match

    halo = 0.0
    if samples and stroke_pts:
        boundary = [p for p in stroke_pts if _neighbor_boundary(support.support_mask, p[0], p[1])]
        if boundary:
            halo = sum(1 for x, y in boundary if _near_sample(x, y, samples, 2.0)) / len(boundary)
    scores["halo_leakage_score"] = 1.0 - halo

    fragment = 0.0
    if stroke_cov < 0.22:
        fragment = 1.0
        reasons.append("fragment_only")
    elif stroke_cov < 0.38:
        fragment = 0.5
        reasons.append("partial_fragment")
    if color_span < 0.34 and len(color_components) >= 2:
        reasons.append("missing_color_span")
    if geom_prec < 0.35:
        reasons.append("geometry_off_support")
    if result.vectorizer == "closed_loop_contour" and routed_shape_type != "closed_loop":
        reasons.append("contour_not_applicable")
    scores["fragment_score"] = 1.0 - fragment

    total = (
        stroke_cov * 30.0
        + geom_prec * 25.0
        + color_span * 18.0
        + dot_score * 10.0
        + continuity * 12.0
        + topology_match * 8.0
        + scores["halo_leakage_score"] * 7.0
        + scores["fragment_score"] * 10.0
    )
    if "fragment_only" in reasons:
        total -= 40
    if "missing_color_span" in reasons:
        total -= 20

    scores["total"] = total
    result.geometry_scores = scores
    result.reject_reasons = reasons
    result.score = total
    return result


def _neighbor_boundary(mask: list[list[bool]], x: int, y: int) -> bool:
    h = len(mask)
    w = len(mask[0]) if h else 0
    if not mask[y][x]:
        return False
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < w and 0 <= ny < h) or not mask[ny][nx]:
            return True
    return False


def run_typed_vectorization(
    maps: LaserMaps,
    support: SupportMasks,
    box: FixtureBox,
    shape_type: str,
) -> tuple[VectorResult, dict[str, Any]]:
    eligible = VECTORIZER_ELIGIBILITY.get(shape_type, VECTORIZER_ELIGIBILITY["unknown"])
    tried: list[str] = []
    results: list[VectorResult] = []
    for name in VECTORIZER_NAMES:
        if name not in eligible:
            continue
        tried.append(name)
        fn = VECTORIZER_FUNCS[name]
        raw = fn(support, box, maps)
        raw.shape_type = shape_type if name == eligible[0] else raw.shape_type
        scored = score_geometry_fit(raw, support, maps, box, shape_type)
        results.append(scored)

    if not results:
        empty = VectorResult(vectorizer="none", shape_type=shape_type)
        meta = {
            "extraction_candidates_tried": tried,
            "selected_extractor": "none",
            "selected_vectorizer": "none",
            "selected_extractor_reason": "no eligible vectorizer produced polylines",
            "shape_type": shape_type,
            "candidate_scores": {},
            "geometry_scores": {},
            "rejected_candidate_reasons": {},
        }
        return empty, meta

    viable = [r for r in results if r.polylines]
    best = max(viable or results, key=lambda r: r.score)
    meta = {
        "extraction_candidates_tried": tried,
        "selected_extractor": best.vectorizer,
        "selected_vectorizer": best.vectorizer,
        "selected_extractor_reason": (
            f"pixel-fit score {best.score:.1f}; "
            f"stroke_coverage={best.geometry_scores.get('stroke_coverage_score', 0):.2f}; "
            f"geometry_precision={best.geometry_scores.get('geometry_precision_score', 0):.2f}"
        ),
        "shape_type": shape_type,
        "candidate_scores": {r.vectorizer: round(r.score, 2) for r in results},
        "geometry_scores": best.geometry_scores,
        "rejected_candidate_reasons": {
            r.vectorizer: r.reject_reasons for r in results if r.vectorizer != best.vectorizer or r.reject_reasons
        },
    }
    return best, meta


def classify_visual_status(shape: dict[str, Any]) -> tuple[str, bool, str]:
    """pass → usable; weak/fail → not usable."""
    polys = shape.get("polylines") or []
    geom = shape.get("geometry_scores") or shape.get("extraction_params", {}).get("geometry_scores") or {}

    if shape.get("shape_point_count", 0) <= 0 or not polys:
        return "fail", False, "empty extraction or no polylines"

    stroke_cov = float(geom.get("stroke_coverage_score", 0.0))
    geom_prec = float(geom.get("geometry_precision_score", 0.0))
    color_span = float(geom.get("color_span_score", 1.0))
    fragment = float(geom.get("fragment_score", 0.0))
    total = float(geom.get("total", shape.get("candidate_scores", {}).get(shape.get("selected_extractor", ""), 0)))

    flags = set(shape.get("quality_flags") or [])
    if "internal_strokes_missing" in flags:
        return "fail", False, "internal strokes missing from complex shape"
    if "broad_glow_rejected" in flags and stroke_cov < 0.3:
        return "fail", False, "broad glow band detected"

    if (
        stroke_cov >= 0.52
        and geom_prec >= 0.55
        and fragment >= 0.55
        and color_span >= 0.5
        and total >= 55.0
    ):
        return "pass", True, "automated pixel-fit pass; geometry aligns with support mask"

    if stroke_cov < 0.18 or fragment < 0.25:
        return "fail", False, "fragment-only or insufficient stroke coverage"

    if "missing_color_span" in (shape.get("rejected_candidate_reasons", {}).get(shape.get("selected_extractor", ""), [])):
        return "weak", False, "multicolor span not fully covered"

    return "weak", False, "pending Brandon visual review; automated pixel-fit below pass threshold"
