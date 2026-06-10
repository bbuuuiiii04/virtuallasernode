"""PR-G1 multi-candidate shape extraction and scoring."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from tools.shape_extraction import (
    DEFAULT_CONTOUR_SAMPLE_STEP,
    DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
    DEFAULT_GLOW_CONNECT_DILATE,
    DEFAULT_HOLE_MIN_AREA_PX,
    DEFAULT_MIN_CORE_AREA_PX,
    FixtureBox,
    _brightest_ridge_core,
    _component_aspect,
    _component_span,
    _component_stats,
    _connected_components,
    _contour_polyline,
    _detect_out_of_box_leak,
    _dilate_mask,
    _extract_core_components_from_glow,
    _forms_rectangular_frame,
    _has_interior_hole,
    _is_line_like,
    _is_thin_core_ring,
    _laser_brightness,
    _medial_ridge_points,
    _percentile,
    _pixels_to_polyline,
    _polyline_cross_span_norm,
    _split_core_mask_components,
    _trace_core_path,
    bbox_wall_norm_from_pixel_bbox,
    classify_topology,
    pixel_to_wall_norm,
)

CANDIDATE_NAMES = (
    "bright_core_centerline",
    "color_saturation_centerline",
    "adaptive_local_core",
    "segmented_components",
    "thin_stroke_skeleton_from_soft_mask",
    "contour_only_closed_loop",
)


@dataclass
class ImageContext:
    w: int
    h: int
    scores: list[list[float]]
    values: list[float]
    med: float
    mad: float
    pixels: Any
    min_area_px: int


@dataclass
class CandidateResult:
    name: str
    clusters: list[dict[str, Any]] = field(default_factory=list)
    polylines: list[dict[str, Any]] = field(default_factory=list)
    major: list[list[tuple[int, int]]] = field(default_factory=list)
    glow_major: list[list[tuple[int, int]]] = field(default_factory=list)
    topology: str = "unknown"
    quality_flags: list[str] = field(default_factory=list)
    score: float = -9999.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    reject_reasons: list[str] = field(default_factory=list)


def _mask_from_threshold(scores: list[list[float]], thr: float) -> list[list[bool]]:
    h = len(scores)
    w = len(scores[0]) if h else 0
    return [[scores[y][x] >= thr for x in range(w)] for y in range(h)]


def _erode_mask(mask: list[list[bool]], iterations: int = 1) -> list[list[bool]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    cur = mask
    for _ in range(max(0, iterations)):
        nxt = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if not cur[y][x]:
                    continue
                if all(
                    0 <= y + dy < h and 0 <= x + dx < w and cur[y + dy][x + dx]
                    for dy, dx in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
                ):
                    nxt[y][x] = True
        cur = nxt
    return cur


def _glow_major_from_mask(mask: list[list[bool]], min_area: int) -> list[list[tuple[int, int]]]:
    comps = _connected_components(mask)
    major = [c for c in comps if len(c) >= max(4, min_area // 2)]
    if major:
        return major
    return [c for c in comps if len(c) >= DEFAULT_MIN_CORE_AREA_PX]


def _polyline_path_length(points: list[list[float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(points, points[1:]):
        if len(a) >= 2 and len(b) >= 2:
            total += math.hypot(b[0] - a[0], b[1] - a[1])
    return total


def _looks_like_ordered_path(comp: list[tuple[int, int]]) -> bool:
    if len(comp) < 8:
        return False
    w, h = _component_span(comp)
    area = max(1.0, w * h)
    density = len(comp) / area
    return density <= 0.55 or (len(comp) >= 12 and min(w, h) <= 8)


def _components_to_polylines(
    major: list[list[tuple[int, int]]],
    box: FixtureBox,
    scores: list[list[float]],
    topology: str,
    *,
    per_component: bool,
    simplify_epsilon: float,
    sample_step: int,
) -> list[dict[str, Any]]:
    polylines: list[dict[str, Any]] = []
    for i, comp in enumerate(sorted(major, key=len, reverse=True)):
        if _looks_like_ordered_path(comp) and not (
            topology == "closed_loop" and (_has_interior_hole(comp) or _is_thin_core_ring(comp))
        ):
            points = _pixels_to_polyline(comp, box, epsilon=simplify_epsilon)
            source = "skeleton"
            closed = False
        elif (_is_thin_core_ring(comp) or _has_interior_hole(comp)) and topology == "closed_loop":
            points = _contour_polyline(
                comp, box, closed=True, simplify_epsilon=simplify_epsilon, sample_step=sample_step
            )
            source = "contour"
            closed = True
        elif per_component or len(major) > 1:
            if _is_line_like(comp) and len(comp) >= 6:
                pix = _brightest_ridge_core(comp, scores)
            else:
                path = _trace_core_path(comp, scores)
                pix = path if len(path) >= 3 else _medial_ridge_points(comp)
            if len(pix) < 2:
                pix = comp[:: max(1, sample_step)]
            points = _pixels_to_polyline(pix, box, epsilon=simplify_epsilon)
            source = "skeleton"
            closed = False
        else:
            ridge = _brightest_ridge_core(comp, scores)
            path = _trace_core_path(comp, scores)
            if _is_line_like(comp) and len(ridge) >= 3:
                pix = ridge
            elif len(path) >= 3:
                pix = path
            else:
                pix = _medial_ridge_points(comp)
                if len(pix) < 2:
                    pix = comp[:: max(1, sample_step)]
            points = _pixels_to_polyline(pix, box, epsilon=simplify_epsilon)
            source = "skeleton"
            closed = False
        if len(points) < 2:
            continue
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


def _build_result_from_components(
    name: str,
    major: list[list[tuple[int, int]]],
    glow_major: list[list[tuple[int, int]]],
    box: FixtureBox,
    ctx: ImageContext,
    *,
    per_component: bool = False,
    extra_flags: list[str] | None = None,
    simplify_epsilon: float = DEFAULT_CONTOUR_SIMPLIFY_EPSILON_PX,
    sample_step: int = DEFAULT_CONTOUR_SAMPLE_STEP,
) -> CandidateResult:
    flags = list(extra_flags or [])
    flags.append("core_mask_used")
    topology = classify_topology(major, DEFAULT_MIN_CORE_AREA_PX)
    if _forms_rectangular_frame(major):
        topology = "closed_loop"
    polylines = _components_to_polylines(
        major,
        box,
        ctx.scores,
        topology,
        per_component=per_component,
        simplify_epsilon=simplify_epsilon,
        sample_step=sample_step,
    )
    clusters = []
    for i, comp in enumerate(sorted(major, key=len, reverse=True)):
        clusters.append({"cluster_id": f"c{i}", **_component_stats(comp, box)})
    if not polylines:
        flags.append("low_shape_confidence")
        flags.append("visual_review_required")
    return CandidateResult(
        name=name,
        clusters=clusters,
        polylines=polylines,
        major=major,
        glow_major=glow_major,
        topology=topology,
        quality_flags=flags,
    )


def _extract_with_core_threshold(
    ctx: ImageContext,
    box: FixtureBox,
    core_k: float,
    core_pct: float,
    glow_k: float,
) -> tuple[list[list[tuple[int, int]]], list[list[tuple[int, int]]], list[list[bool]]]:
    glow_thr = ctx.med + glow_k * ctx.mad
    core_thr = max(ctx.med + core_k * ctx.mad, _percentile(ctx.values, core_pct))
    glow_mask = _mask_from_threshold(ctx.scores, glow_thr)
    core_mask = _mask_from_threshold(ctx.scores, core_thr)
    glow_major = _glow_major_from_mask(glow_mask, ctx.min_area_px)
    connect = _dilate_mask(glow_mask, DEFAULT_GLOW_CONNECT_DILATE)
    connect_major = _glow_major_from_mask(connect, ctx.min_area_px)
    sources = connect_major if connect_major else glow_major
    major: list[list[tuple[int, int]]] = []
    for glow_comp in sources:
        glow_px = [(x, y) for x, y in glow_comp if glow_mask[y][x]] or glow_comp
        for part in _extract_core_components_from_glow(
            glow_px, core_mask, ctx.scores, ctx.w, ctx.h, global_core_thr=core_thr
        ):
            major.append(part)
    if not major and glow_major:
        for glow_comp in glow_major:
            for part in _extract_core_components_from_glow(
                glow_comp,
                core_mask,
                ctx.scores,
                ctx.w,
                ctx.h,
                global_core_thr=max(core_thr, _percentile(ctx.values, core_pct - 6.0)),
            ):
                major.append(part)
    major = [c for c in major if len(c) >= DEFAULT_MIN_CORE_AREA_PX]
    return major, glow_major, [core_mask, glow_mask]


def _candidate_bright_core_centerline(ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    major, glow_major, _ = _extract_with_core_threshold(ctx, box, 6.2, 96.0, 3.5)
    return _build_result_from_components(
        "bright_core_centerline",
        major,
        glow_major,
        box,
        ctx,
        extra_flags=["skeleton_centerline_used"],
    )


def _candidate_color_saturation_centerline(ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    major, glow_major, _ = _extract_with_core_threshold(ctx, box, 4.2, 88.0, 2.6)
    if not major:
        glow_thr = ctx.med + 2.6 * ctx.mad
        glow_mask = _mask_from_threshold(ctx.scores, glow_thr)
        glow_major = _glow_major_from_mask(glow_mask, ctx.min_area_px)
        for glow_comp in glow_major:
            vals = [ctx.scores[y][x] for x, y in glow_comp]
            thr = _percentile(vals, 82.0)
            core_px = [(x, y) for x, y in glow_comp if ctx.scores[y][x] >= thr]
            for part in _split_core_mask_components(core_px, ctx.w, ctx.h):
                if len(part) >= DEFAULT_MIN_CORE_AREA_PX:
                    major.append(part)
    return _build_result_from_components(
        "color_saturation_centerline",
        major,
        glow_major,
        box,
        ctx,
        extra_flags=["colored_core_recovered", "skeleton_centerline_used"],
    )


def _candidate_adaptive_local_core(ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    glow_thr = ctx.med + 3.0 * ctx.mad
    glow_mask = _mask_from_threshold(ctx.scores, glow_thr)
    glow_major = _glow_major_from_mask(glow_mask, ctx.min_area_px)
    major: list[list[tuple[int, int]]] = []
    for glow_comp in glow_major:
        vals = [ctx.scores[y][x] for x, y in glow_comp]
        if not vals:
            continue
        thr = _percentile(vals, 76.0)
        core_px = [(x, y) for x, y in glow_comp if ctx.scores[y][x] >= thr]
        for part in _split_core_mask_components(core_px, ctx.w, ctx.h):
            if len(part) >= DEFAULT_MIN_CORE_AREA_PX:
                major.append(part)
    return _build_result_from_components(
        "adaptive_local_core",
        major,
        glow_major,
        box,
        ctx,
        extra_flags=["skeleton_centerline_used"],
    )


def _candidate_segmented_components(ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    glow_thr = ctx.med + 3.2 * ctx.mad
    glow_mask = _mask_from_threshold(ctx.scores, glow_thr)
    glow_major = _glow_major_from_mask(glow_mask, ctx.min_area_px)
    major: list[list[tuple[int, int]]] = []
    for glow_comp in glow_major:
        vals = [ctx.scores[y][x] for x, y in glow_comp]
        thr = _percentile(vals, 80.0) if vals else ctx.med
        core_px = [(x, y) for x, y in glow_comp if ctx.scores[y][x] >= thr]
        for part in _split_core_mask_components(core_px, ctx.w, ctx.h):
            if len(part) >= DEFAULT_MIN_CORE_AREA_PX:
                major.append(part)
    return _build_result_from_components(
        "segmented_components",
        major,
        glow_major,
        box,
        ctx,
        per_component=True,
        extra_flags=["colored_core_recovered"],
    )


def _candidate_thin_stroke_skeleton(ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    glow_thr = ctx.med + 2.9 * ctx.mad
    glow_mask = _mask_from_threshold(ctx.scores, glow_thr)
    connect = _dilate_mask(glow_mask, DEFAULT_GLOW_CONNECT_DILATE)
    glow_major = _glow_major_from_mask(connect, ctx.min_area_px)
    major: list[list[tuple[int, int]]] = []
    for comp in sorted(glow_major, key=len, reverse=True):
        if len(comp) < DEFAULT_MIN_CORE_AREA_PX:
            continue
        w, h = _component_span(comp)
        if len(comp) >= 120 or w * h >= 400:
            path = _medial_ridge_points(comp)
            if len(path) < 5:
                path = _trace_core_path(comp, ctx.scores)
        else:
            path = _trace_core_path(comp, ctx.scores)
            if len(path) < 5:
                path = _medial_ridge_points(comp)
        if len(path) >= 2:
            major.append(path)
    return _build_result_from_components(
        "thin_stroke_skeleton_from_soft_mask",
        major,
        _glow_major_from_mask(glow_mask, ctx.min_area_px),
        box,
        ctx,
        per_component=len(major) > 1,
        extra_flags=["skeleton_centerline_used"],
    )


def _candidate_contour_closed_loop(ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    glow_thr = ctx.med + 3.0 * ctx.mad
    glow_mask = _mask_from_threshold(ctx.scores, glow_thr)
    connect = _dilate_mask(glow_mask, DEFAULT_GLOW_CONNECT_DILATE)
    glow_major = _glow_major_from_mask(connect, ctx.min_area_px)
    major: list[list[tuple[int, int]]] = []
    for comp in glow_major:
        if _has_interior_hole(comp):
            core_thr = ctx.med + 4.5 * ctx.mad
            core_px = [(x, y) for x, y in comp if ctx.scores[y][x] >= core_thr]
            if len(core_px) >= DEFAULT_MIN_CORE_AREA_PX:
                for part in _split_core_mask_components(core_px, ctx.w, ctx.h):
                    if _has_interior_hole(part) or _is_thin_core_ring(part):
                        major.append(part)
            if not major:
                major.append(comp)
    if not major:
        for comp in glow_major:
            if _is_thin_core_ring(comp) or _has_interior_hole(comp):
                major.append(comp)
    return _build_result_from_components(
        "contour_only_closed_loop",
        major,
        glow_major,
        box,
        ctx,
        extra_flags=["contour_ring_only"],
    )


def _glow_reference_span(glow_major: list[list[tuple[int, int]]]) -> tuple[float, float, float]:
    if not glow_major:
        return 0.0, 0.0, 0.0
    all_pts = [p for c in glow_major for p in c]
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    w = float(max(xs) - min(xs) + 1)
    h = float(max(ys) - min(ys) + 1)
    diag = math.hypot(w, h)
    return w, h, diag


def _polyline_pixel_spans(polylines: list[dict[str, Any]], box: FixtureBox) -> tuple[float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    pix_pts: list[tuple[float, float]] = []
    for poly in polylines:
        pts = poly.get("points") or []
        for p in pts:
            if len(p) >= 2:
                px = box.x0 + ((p[0] + 1.0) / 2.0) * box.width
                py = box.y0 + ((1.0 - p[1]) / 2.0) * box.height
                xs.append(px)
                ys.append(py)
                pix_pts.append((px, py))
    path_len = 0.0
    for a, b in zip(pix_pts, pix_pts[1:]):
        path_len += math.hypot(b[0] - a[0], b[1] - a[1])
    if not xs:
        return 0.0, 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys), path_len


def _major_pixel_spans(major: list[list[tuple[int, int]]], box: FixtureBox) -> tuple[float, float]:
    if not major:
        return 0.0, 0.0
    xs: list[float] = []
    ys: list[float] = []
    for comp in major:
        for x, y in comp:
            xs.append(x + box.x0)
            ys.append(y + box.y0)
    return max(xs) - min(xs), max(ys) - min(ys)


def _edge_clipped_fraction(polylines: list[dict[str, Any]], margin: float = 0.92) -> float:
    pts = [p for poly in polylines for p in poly.get("points") or [] if len(p) >= 2]
    if not pts:
        return 0.0
    edge = 0
    for x, y in pts:
        if abs(x) >= margin or abs(y) >= margin:
            edge += 1
    return edge / len(pts)


def score_candidate(cand: CandidateResult, ctx: ImageContext, box: FixtureBox) -> CandidateResult:
    reasons: list[str] = []
    breakdown: dict[str, float] = {}
    score = 0.0

    if not cand.polylines:
        cand.score = -1000.0
        cand.reject_reasons = ["no_polylines"]
        cand.score_breakdown = {"total": -1000.0}
        return cand

    glow_w, glow_h, glow_diag = _glow_reference_span(cand.glow_major)
    poly_w, poly_h, path_len = _polyline_pixel_spans(cand.polylines, box)
    major_w, major_h = _major_pixel_spans(cand.major, box)
    box_diag = math.hypot(box.width, box.height)
    norm_glow_diag = glow_diag / max(1.0, box_diag) if glow_diag else 0.0
    norm_path = path_len / max(1e-9, glow_diag * 0.55) if glow_diag else path_len / box_diag

    breakdown["path_coverage"] = norm_path
    if norm_path < 0.18:
        score -= 55
        reasons.append("fragment_only")
    elif norm_path < 0.32:
        score -= 15
        reasons.append("partial_fragment")
    else:
        score += min(40.0, norm_path * 30.0)

    if glow_w > 8 and poly_w > 0:
        x_cov = poly_w / max(1e-9, glow_w)
        breakdown["x_span_coverage"] = x_cov
        if x_cov < 0.22:
            score -= 40
            reasons.append("missing_color_span")
        elif x_cov > 0.45:
            score += 15

    if glow_h > 8 and poly_h > 0:
        y_cov = poly_h / max(1e-9, glow_h)
        breakdown["y_span_coverage"] = y_cov
        if glow_h > box.height * 0.12 and y_cov < 0.22:
            score -= 35
            reasons.append("missing_vertical_stroke_span")
        elif y_cov > 0.35:
            score += 10

    glow_area = sum(len(c) for c in cand.glow_major) or 1
    core_area = sum(len(c) for c in cand.major) or sum(
        len(p.get("points") or []) for p in cand.polylines
    )
    area_ratio = glow_area / max(1, core_area)
    breakdown["glow_core_ratio"] = area_ratio
    if area_ratio > 12.0 and cand.name != "thin_stroke_skeleton_from_soft_mask":
        score -= 35
        reasons.append("broad_glow_blob")
    elif area_ratio > 8.0 and cand.name not in (
        "thin_stroke_skeleton_from_soft_mask",
        "color_saturation_centerline",
    ):
        score -= 15
        reasons.append("wide_glow_mask")
    elif 1.5 <= area_ratio <= 8.0:
        score += 8

    for poly in cand.polylines:
        cross = _polyline_cross_span_norm(poly.get("points") or [])
        if poly.get("closed") and cand.topology != "closed_loop":
            score -= 45
            reasons.append("closed_blob_for_open_shape")
            break
        if cross > 0.38 and cand.topology in ("line", "unknown"):
            score -= 30
            reasons.append("fat_band_not_centerline")
            break
        if cross <= 0.22 and cand.topology == "line":
            score += 12

    edge_frac = _edge_clipped_fraction(cand.polylines)
    breakdown["edge_clipped_fraction"] = edge_frac
    if edge_frac > 0.65:
        score -= 35
        reasons.append("fixture_edge_clipped")
    elif edge_frac > 0.45:
        score -= 12

    if cand.topology in ("multi_cluster", "two_clusters") and len(cand.polylines) >= 2:
        score += 18
    if (
        cand.topology in ("complex_shape", "multi_cluster")
        and len(cand.polylines) <= 1
        and len(cand.glow_major) >= 2
        and norm_path < 0.35
    ):
        score -= 25
        reasons.append("internal_strokes_missing")

    if cand.name == "contour_only_closed_loop" and cand.topology != "closed_loop":
        score -= 50
        reasons.append("contour_not_applicable")

    if cand.name == "bright_core_centerline" and "fragment_only" in reasons:
        score -= 10

    if len(cand.glow_major) <= 2 and len(cand.polylines) >= 5:
        score -= 35
        reasons.append("over_segmented_fragments")

    if len(cand.polylines) == 1 and norm_path > 0.35:
        score += 15

    if (
        cand.name == "segmented_components"
        and len(cand.polylines) >= 3
        and len(cand.glow_major) >= 3
        and all(len(c) <= 120 for c in cand.major)
    ):
        score += 15

    if cand.name == "segmented_components" and "over_segmented_fragments" in reasons:
        score -= 15

    if cand.name == "color_saturation_centerline" and norm_path > 0.45:
        score += 18

    if cand.name == "thin_stroke_skeleton_from_soft_mask" and norm_path > 0.25:
        score += 25

    if cand.name == "contour_only_closed_loop" and cand.topology == "closed_loop" and cand.polylines:
        score += 25

    if cand.name == "segmented_components" and len(cand.polylines) >= 3:
        score += 10

    breakdown["total"] = score
    cand.score = score
    cand.score_breakdown = breakdown
    cand.reject_reasons = reasons
    return cand


def run_all_candidates(
    ctx: ImageContext,
    box: FixtureBox,
) -> list[CandidateResult]:
    builders = (
        _candidate_bright_core_centerline,
        _candidate_color_saturation_centerline,
        _candidate_adaptive_local_core,
        _candidate_segmented_components,
        _candidate_thin_stroke_skeleton,
        _candidate_contour_closed_loop,
    )
    results: list[CandidateResult] = []
    for fn in builders:
        cand = fn(ctx, box)
        results.append(score_candidate(cand, ctx, box))
    return results


def select_best_candidate(candidates: list[CandidateResult]) -> tuple[CandidateResult, dict[str, Any]]:
    viable = [c for c in candidates if c.polylines]
    if not viable:
        empty = candidates[0] if candidates else CandidateResult(name="none")
        meta = {
            "extraction_candidates_tried": [c.name for c in candidates],
            "selected_extractor": empty.name,
            "selected_extractor_reason": "no viable candidate produced polylines",
            "candidate_scores": {c.name: c.score for c in candidates},
            "rejected_candidate_reasons": {c.name: c.reject_reasons for c in candidates},
        }
        return empty, meta

    best = max(viable, key=lambda c: c.score)
    reason_parts = [f"highest score {best.score:.1f}"]
    if best.score_breakdown.get("path_coverage", 0) >= 0.22:
        reason_parts.append("adequate stroke coverage")
    if "fragment_only" not in best.reject_reasons:
        reason_parts.append("not fragment-only")
    if "broad_glow_blob" not in best.reject_reasons:
        reason_parts.append("not broad glow blob")

    meta = {
        "extraction_candidates_tried": [c.name for c in candidates],
        "selected_extractor": best.name,
        "selected_extractor_reason": "; ".join(reason_parts),
        "candidate_scores": {c.name: round(c.score, 2) for c in candidates},
        "rejected_candidate_reasons": {
            c.name: c.reject_reasons for c in candidates if c.name != best.name or c.reject_reasons
        },
    }
    return best, meta


def classify_visual_status(shape: dict[str, Any]) -> tuple[str, bool, str]:
    flags = set(shape.get("quality_flags") or [])
    polys = shape.get("polylines") or []
    reject = shape.get("rejected_candidate_reasons") or {}
    selected = shape.get("selected_extractor") or ""
    selected_reasons = reject.get(selected, []) if isinstance(reject, dict) else []
    family = (shape.get("family_or_checkpoint") or "").lower()
    topology = shape.get("topology_class") or ""

    if shape.get("shape_point_count", 0) <= 0 or not polys:
        return "fail", False, "empty extraction or no polylines"

    hard_fail_reasons = {
        "internal_strokes_missing",
        "fixture_edge_clipped",
        "broad_glow_blob",
        "fat_band_not_centerline",
        "missing_color_span",
    }
    if any(r in hard_fail_reasons for r in selected_reasons) or "internal_strokes_missing" in flags:
        return "fail", False, f"selected extractor flagged: {', '.join(selected_reasons[:3]) or 'internal_strokes_missing'}"

    if "fragment_only" in selected_reasons:
        return "fail", False, "selected extractor produced fragment-only stroke"

    if any(k in family for k in ("u-wave", "u wave", "swirl", "star", "three-star", "dotted arc")):
        if selected == "segmented_components" and len(polys) >= 4:
            return "weak", False, "U/arc/swirl selected segmented fragments; needs Brandon visual review"
        if "partial_fragment" in selected_reasons or "missing_vertical_stroke_span" in selected_reasons:
            return "weak", False, "curved macro may miss stroke span; Brandon visual review required"

    if "horizontal line" in family:
        from tools.shape_polyline_utils import polyline_is_thin_centerline

        if not any(polyline_is_thin_centerline(p) for p in polys):
            return "fail", False, "horizontal line lacks thin centerline overlay"
        if selected in ("color_saturation_centerline", "bright_core_centerline", "thin_stroke_skeleton_from_soft_mask"):
            return "weak", True, "thin line candidate selected; confirm visually against still"

    if topology == "line" and len(polys) == 1:
        from tools.shape_polyline_utils import polyline_is_thin_centerline

        if any(polyline_is_thin_centerline(p) for p in polys):
            return "weak", True, "thin centerline candidate; confirm visually against still"

    if topology in ("two_clusters", "multi_cluster") and len(polys) >= 2:
        if selected == "segmented_components":
            return "weak", True, "segmented dot/cluster candidate; confirm components match still"

    if topology == "closed_loop" and selected == "contour_only_closed_loop":
        return "weak", True, "ring contour candidate; confirm yellow follows laser ring not halo"

    if "visual_review_required" in flags or "low_shape_confidence" in flags:
        return "weak", True, "automated extraction uncertain; human overlay check required"

    return "weak", True, "pending Brandon visual review"
