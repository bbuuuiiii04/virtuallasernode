"""PR-G1 v6: explicit geometry kinds separate from mask representation."""

from __future__ import annotations

import math
from typing import Any

from tools.shape_extraction import FixtureBox
from tools.shape_polyline_utils import (
    polyline_is_fat_closed_band,
    polyline_is_thin_centerline,
    polyline_point_span,
)

# Authority geometry kinds (drawn on contact sheets).
GEOMETRY_KINDS = (
    "centerline_polyline",
    "branch_polyline",
    "dot_anchor_points",
    "segment_anchor_points",
    "closed_loop_contour",
)

# Non-authority / rejected kinds (never serialized as usable geometry).
REJECTED_GEOMETRY_KINDS = (
    "rejected_mask_area",
    "mask_area",
    "unordered_pixel_cloud",
)

VECTORIZER_DEFAULT_KIND: dict[str, str] = {
    "skeleton_graph_stroke": "centerline_polyline",
    "dotted_component_vectorizer": "dot_anchor_points",
    "dot_cluster_vectorizer": "dot_anchor_points",
    "closed_loop_contour": "closed_loop_contour",
    "skeleton_branch_vectorizer": "branch_polyline",
}

SOURCE_ORDERED = frozenset(
    {
        "skeleton",
        "dot_centroid",
        "segment_anchor",
        "contour",
        "simplified_component",
        "color_span_skeleton",
    }
)


def _wall_to_crop_px(x_norm: float, y_norm: float, box: FixtureBox) -> tuple[float, float]:
    px = ((x_norm + 1.0) / 2.0) * box.width
    py = ((1.0 - y_norm) / 2.0) * box.height
    return px, py


def polyline_point_count(poly: dict[str, Any]) -> int:
    pts = poly.get("points") or []
    return len(pts)


def compute_geometry_point_count(polylines: list[dict[str, Any]]) -> int:
    total = 0
    for poly in polylines:
        kind = poly.get("geometry_kind")
        if kind in REJECTED_GEOMETRY_KINDS:
            continue
        total += poly.get("point_count") or polyline_point_count(poly)
    return total


def infer_polyline_geometry_kind(
    poly: dict[str, Any],
    *,
    vectorizer: str,
    shape_type: str,
) -> tuple[str, bool]:
    """Return (geometry_kind, ordered) for one polyline."""
    source = str(poly.get("source") or "")
    pts = poly.get("points") or []
    n = len(pts)

    if source in ("mask_pixels", "unordered_mask", "support_fill"):
        return "unordered_pixel_cloud", False

    if n == 1:
        if source == "segment_anchor" or poly.get("segment"):
            return "segment_anchor_points", True
        return "dot_anchor_points", True

    if poly.get("closed") and shape_type == "closed_loop":
        return "closed_loop_contour", True

    if vectorizer == "skeleton_branch_vectorizer" or source == "skeleton_branch":
        return "branch_polyline", True

    if source == "segment_anchor":
        return "segment_anchor_points", True

    if vectorizer in ("dotted_component_vectorizer", "dot_cluster_vectorizer"):
        if n <= 2 and source == "segment_anchor":
            return "segment_anchor_points", True
        if n == 1:
            return "dot_anchor_points", True
        if n >= 4 and source in SOURCE_ORDERED:
            return "centerline_polyline", _polyline_points_are_ordered(pts)

    if source in SOURCE_ORDERED:
        return VECTORIZER_DEFAULT_KIND.get(vectorizer, "centerline_polyline"), True
    if vectorizer in VECTORIZER_DEFAULT_KIND:
        return VECTORIZER_DEFAULT_KIND.get(vectorizer, "centerline_polyline"), True

    if n >= 2:
        return "centerline_polyline", _polyline_points_are_ordered(pts)

    return "rejected_mask_area", False


def _polyline_points_are_ordered(points: list[list[float]]) -> bool:
    if len(points) < 3:
        return True
    hops = [
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
        if len(points[i]) >= 2 and len(points[i + 1]) >= 2
    ]
    if not hops:
        return False
    med = sorted(hops)[len(hops) // 2]
    big_jumps = sum(1 for h in hops if h > max(0.08, med * 4.0))
    return big_jumps <= max(2, len(hops) // 5)


def annotate_polylines(
    polylines: list[dict[str, Any]],
    *,
    vectorizer: str,
    shape_type: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for poly in polylines:
        p = dict(poly)
        kind, ordered = infer_polyline_geometry_kind(p, vectorizer=vectorizer, shape_type=shape_type)
        p["geometry_kind"] = kind
        p["ordered"] = ordered
        p["point_count"] = polyline_point_count(p)
        out.append(p)
    return out


def shape_geometry_kind(polylines: list[dict[str, Any]], vectorizer: str, shape_type: str) -> str:
    kinds = {p.get("geometry_kind") for p in polylines if p.get("geometry_kind")}
    if not kinds:
        return VECTORIZER_DEFAULT_KIND.get(vectorizer, "centerline_polyline")
    if len(kinds) == 1:
        return next(iter(kinds))
    if "branch_polyline" in kinds:
        return "branch_polyline"
    if "dot_anchor_points" in kinds and "segment_anchor_points" in kinds:
        return "segment_anchor_points"
    if kinds <= {"dot_anchor_points", "segment_anchor_points"}:
        return "dot_anchor_points"
    return VECTORIZER_DEFAULT_KIND.get(vectorizer, "centerline_polyline")


def _sample_polyline_pixels_local(
    polylines: list[dict[str, Any]], box: FixtureBox
) -> list[tuple[float, float]]:
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


def _detect_dense_branch_scribble(
    annotated: list[dict[str, Any]],
    box: FixtureBox,
) -> list[str]:
    """Reject branch paths that visually recreate a filled mask/scribble."""
    branches = [p for p in annotated if p.get("geometry_kind") == "branch_polyline"]
    if not branches:
        return []

    reasons: list[str] = []
    total_pts = sum(polyline_point_count(p) for p in branches)
    samples = _sample_polyline_pixels_local(branches, box)
    if not samples:
        return reasons

    xs = [s[0] for s in samples]
    ys = [s[1] for s in samples]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    long_side = max(span_x, span_y)
    if long_side > 0 and min(span_x, span_y) / long_side >= 0.28 and total_pts >= 24:
        reasons.append("branch_mask_fill_like")

    path_len = 0.0
    for poly in branches:
        pts = poly.get("points") or []
        pix = [_wall_to_crop_px(p[0], p[1], box) for p in pts if len(p) >= 2]
        for a, b in zip(pix, pix[1:]):
            path_len += math.hypot(b[0] - a[0], b[1] - a[1])
    density = len(samples) / max(1.0, path_len)
    if len(branches) >= 4 and total_pts >= 40 and density > 1.2:
        reasons.append("dense_branch_scribble")
    if len(branches) >= 6 and total_pts >= 55:
        reasons.append("dense_branch_scribble")

    return reasons


def _polyline_is_dense_mask_cloud(poly: dict[str, Any], box: FixtureBox) -> bool:
    pts = poly.get("points") or []
    if len(pts) < 40:
        return False
    if poly.get("source") in SOURCE_ORDERED:
        return False
    pix = [_wall_to_crop_px(p[0], p[1], box) for p in pts if len(p) >= 2]
    if len(pix) < 40:
        return False
    path_len = 0.0
    for a, b in zip(pix, pix[1:]):
        path_len += math.hypot(b[0] - a[0], b[1] - a[1])
    if path_len <= 0:
        return True
    density = len(pix) / path_len
    return density > 2.5


def validate_geometry_candidate(
    polylines: list[dict[str, Any]],
    *,
    vectorizer: str,
    shape_type: str,
    routed_shape_type: str,
    box: FixtureBox,
) -> tuple[list[str], list[str]]:
    """Return (reject_reasons, quality_flags)."""
    reasons: list[str] = []
    flags: list[str] = []

    if not polylines:
        return ["no_polylines"], flags

    annotated = annotate_polylines(polylines, vectorizer=vectorizer, shape_type=shape_type)

    for poly in annotated:
        kind = poly.get("geometry_kind")
        if kind in REJECTED_GEOMETRY_KINDS:
            reasons.append(f"rejected_geometry_kind:{kind}")
        if kind == "unordered_pixel_cloud":
            reasons.append("unordered_pixel_cloud")
        if not poly.get("ordered", True):
            reasons.append("unordered_polyline")
        if _polyline_is_dense_mask_cloud(poly, box):
            reasons.append("dense_mask_pixels_as_polyline")

        if poly.get("closed") and shape_type != "closed_loop":
            if polyline_is_fat_closed_band(poly):
                reasons.append("filled_band_geometry")
                flags.append("broad_glow_rejected")
            elif routed_shape_type != "closed_loop":
                reasons.append("closed_loop_not_applicable")

        if shape_type in ("continuous_stroke", "dotted_pattern") and polyline_is_fat_closed_band(poly):
            reasons.append("filled_band_geometry")
            flags.append("broad_glow_rejected")

    if shape_type in ("dotted_pattern", "dot_cluster"):
        anchor_count = sum(
            1
            for p in annotated
            if p.get("geometry_kind") in ("dot_anchor_points", "segment_anchor_points")
        )
        if anchor_count < 2:
            reasons.append("dot_cluster_collapsed")
        long_lines = [
            p
            for p in annotated
            if p.get("geometry_kind") == "centerline_polyline"
            and polyline_point_count(p) >= 4
            and p.get("source") != "segment_anchor"
        ]
        if long_lines and shape_type == "dotted_pattern":
            reasons.append("dotted_pattern_smear")

    if shape_type == "continuous_stroke":
        centerlines = [p for p in annotated if p.get("geometry_kind") == "centerline_polyline"]
        for poly in centerlines:
            if not polyline_is_thin_centerline(poly) and poly.get("closed"):
                reasons.append("filled_band_geometry")

    if vectorizer == "closed_loop_contour" and routed_shape_type != "closed_loop":
        reasons.append("contour_not_applicable")

    branch_reasons = _detect_dense_branch_scribble(annotated, box)
    reasons.extend(branch_reasons)

    # Deduplicate while preserving order.
    seen: set[str] = set()
    uniq_reasons: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq_reasons.append(r)
    return uniq_reasons, flags


def finalize_vector_result_metadata(
    result: Any,
    *,
    routed_shape_type: str,
    box: FixtureBox,
) -> Any:
    """Attach shape-level geometry metadata after scoring."""
    _ = routed_shape_type, box
    if not all(p.get("geometry_kind") for p in result.polylines):
        result.polylines = annotate_polylines(
            result.polylines,
            vectorizer=result.vectorizer,
            shape_type=result.shape_type,
        )

    hard_reject = {
        "unordered_pixel_cloud",
        "dense_mask_pixels_as_polyline",
        "filled_band_geometry",
        "dotted_pattern_smear",
        "dot_cluster_collapsed",
        "closed_loop_not_applicable",
        "contour_not_applicable",
        "dense_branch_scribble",
        "branch_mask_fill_like",
    }
    if any(
        r in hard_reject or r.startswith("rejected_geometry_kind:")
        for r in result.reject_reasons
    ):
        result.score = min(result.score, -500.0)
        if "mask_geometry_rejected" not in result.quality_flags:
            result.quality_flags.append("mask_geometry_rejected")

    result.geometry_kind = shape_geometry_kind(
        result.polylines, result.vectorizer, result.shape_type
    )
    result.ordered = all(p.get("ordered", True) for p in result.polylines) if result.polylines else False
    result.rejection_reasons = list(result.reject_reasons)
    return result
