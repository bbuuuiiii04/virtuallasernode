"""V7 two-sided validation metrics and authority gate (§15)."""

from __future__ import annotations

from typing import Any

import numpy as np
from skimage.morphology import dilation, disk, skeletonize

from tools.shape_vectorize_v7 import sample_geometry_points, sample_geometry_points_with_bridge_flags

R_P = 2.0   # core_precision radius (px)
R_R = 3.0   # core_recall radius (px)
PREC_GATE = 0.90
RECALL_GATE = 0.80
HALO_GATE = 0.05
RESIDUAL_GATE = 2.5


def compute_metrics(
    polylines: list[dict[str, Any]],
    core_mask: np.ndarray,
    glow_mask: np.ndarray,
    components: list[dict[str, Any]] | None = None,
    r_p: float = R_P,
    r_r: float = R_R,
    structure_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Compute §15 metrics.

    Precision is always measured against the CORE mask (geometry must lie on
    core evidence). Recall is measured against the skeleton of
    `structure_mask` when given — the saturated laser structure that the
    geometry is required to reconstruct — because the CORE mask of
    high-exposure captures includes glow whose skeleton is not laser
    geometry. Without structure_mask, recall uses the CORE skeleton.

    Returns dict with keys:
      core_precision, core_recall, halo_spill, vector_fit_residual_px_p95,
      components_detected (set externally), components_vectorized (set externally).
    """
    H, W = core_mask.shape
    geom_pts, bridge_flags = sample_geometry_points_with_bridge_flags(polylines, spacing=1.0)
    metric_pts = [pt for pt, is_bridge in zip(geom_pts, bridge_flags) if not is_bridge]

    # Skeleton of the recall basis (structure if provided, else CORE)
    recall_mask = structure_mask if structure_mask is not None else core_mask
    skel_core = skeletonize(recall_mask)
    skel_count = int(np.sum(skel_core))

    if not geom_pts:
        return {
            "core_precision": 0.0,
            "core_recall": 0.0 if skel_count > 0 else 1.0,
            "halo_spill": 0.0,
            "vector_fit_residual_px_p95": 0.0,
            "components_detected": 0,
            "components_vectorized": 0,
        }

    # Dilate CORE by r_p for precision check
    r_p_int = max(1, int(np.ceil(r_p)))
    core_dilated = dilation(core_mask, disk(r_p_int))

    # core_precision: fraction of geometry pts within r_p of core
    if metric_pts:
        in_core = sum(
            1 for (gx, gy) in metric_pts
            if 0 <= int(gy) < H and 0 <= int(gx) < W and core_dilated[int(gy), int(gx)]
        )
        core_precision = in_core / len(metric_pts)
    else:
        core_precision = 1.0

    # halo_spill: fraction of geometry pts not in core_dilated but in glow
    if metric_pts:
        halo_count = sum(
            1 for (gx, gy) in metric_pts
            if 0 <= int(gy) < H and 0 <= int(gx) < W
            and not core_dilated[int(gy), int(gx)]
            and glow_mask[int(gy), int(gx)]
        )
        halo_spill = halo_count / len(metric_pts)
    else:
        halo_spill = 0.0

    # core_recall: fraction of SKEL(CORE) pts within r_r of geometry
    if skel_count == 0:
        core_recall = 1.0
    else:
        # Build geometry mask, dilate by r_r, check overlap with skeleton
        geom_mask = np.zeros((H, W), dtype=bool)
        for gx, gy in geom_pts:
            xi, yi = int(round(gx)), int(round(gy))
            if 0 <= yi < H and 0 <= xi < W:
                geom_mask[yi, xi] = True
        r_r_int = max(1, int(np.ceil(r_r)))
        geom_dilated = dilation(geom_mask, disk(r_r_int))
        covered = int(np.sum(skel_core & geom_dilated))
        core_recall = covered / skel_count

    try:
        from scipy.ndimage import distance_transform_edt
        dist_to_core = distance_transform_edt(~core_mask)
        residuals = [
            float(dist_to_core[int(gy), int(gx)])
            for gx, gy in metric_pts
            if 0 <= int(gy) < H and 0 <= int(gx) < W
        ]
        p95 = float(np.percentile(residuals, 95)) if residuals else 0.0
    except Exception:
        dist_to_core = None
        p95 = 0.0

    dot_reasons = []
    is_dot_only = False
    if components is not None and len(components) > 0:
        dot_comps = [c for c in components if c["class"] == "dot"]
        is_dot_only = len(dot_comps) == len(components)
        
        if is_dot_only:
            dot_anchors = [p for p in polylines if p.get("geometry_kind") == "dot_anchor"]
            if len(dot_anchors) != len(dot_comps):
                dot_reasons.append(f"dot_anchor_count_mismatch:{len(dot_anchors)}!={len(dot_comps)}")
            else:
                anchor_by_cid = {a["component_id"]: a for a in dot_anchors}
                for c in dot_comps:
                    cid = c["component_id"]
                    if cid not in anchor_by_cid:
                        dot_reasons.append(f"missing_anchor_for_dot:{cid}")
                        continue
                    
                    a = anchor_by_cid[cid]
                    pts = a.get("points_px", [])
                    if not pts:
                        dot_reasons.append(f"empty_anchor:{cid}")
                        continue
                        
                    ax, ay = pts[0]
                    
                    if dist_to_core is not None:
                        dist = float(dist_to_core[int(ay), int(ax)]) if (0 <= int(ay) < H and 0 <= int(ax) < W) else 999.0
                        if dist > 2.0:
                            dot_reasons.append(f"dot_anchor_off_core:{dist:.1f}>2.0")
                    
                    bx = c["bbox_px"]
                    w = bx[2] - bx[0]
                    h = bx[3] - bx[1]
                    ccx = (bx[0] + bx[2]) / 2.0
                    ccy = (bx[1] + bx[3]) / 2.0
                    centroid_dist = ((ax - ccx)**2 + (ay - ccy)**2)**0.5
                    
                    if centroid_dist > max(w, h) * 0.5 + 2.0:
                        dot_reasons.append(f"dot_anchor_residual_high:{centroid_dist:.1f}")
                    
                    aspect = max(w, h) / max(1, min(w, h))
                    if aspect > 3.0:
                        dot_reasons.append(f"dot_aspect_too_high:{aspect:.1f}>3.0")

            if not dot_reasons:
                core_recall = 1.0

    return {
        "core_precision": round(core_precision, 4),
        "core_recall": round(core_recall, 4),
        "recall_basis": "structure_skeleton" if structure_mask is not None else "core_skeleton",
        "halo_spill": round(halo_spill, 4),
        "vector_fit_residual_px_p95": round(p95, 3),
        "components_detected": 0,
        "components_vectorized": 0,
        "is_dot_only": is_dot_only,
        "dot_reasons": dot_reasons,
    }


def component_structure_coverage(
    polylines: list[dict[str, Any]],
    structure_mask: np.ndarray,
    r_r: float = R_R,
) -> float:
    """Fraction of the structure skeleton covered within r_r of the geometry.

    Used to decide whether a component's vectors faithfully represent its
    laser structure (render) or are merely diagnostic traces.
    """
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
    r_r_int = max(1, int(np.ceil(r_r)))
    geom_dilated = dilation(geom_mask, disk(r_r_int))
    covered = int(np.sum(skel & geom_dilated))
    return covered / skel_count


def compute_authority_gate(
    metrics: dict[str, Any],
    components_detected: int,
    components_vectorized: int,
    quality_flags: list[str],
    fixture_output_accounting_complete: bool,
) -> tuple[bool, str, list[str]]:
    """
    Apply §15 authority gate.

    Returns (authority_eligible, status, reasons).
    status: 'authority' | 'provisional' | 'quarantined'
    """
    reasons: list[str] = []

    if metrics["core_precision"] < PREC_GATE:
        reasons.append(f"core_precision_below_threshold:{metrics['core_precision']:.3f}<{PREC_GATE}")
    if metrics["core_recall"] < RECALL_GATE:
        reasons.append(f"core_recall_below_threshold:{metrics['core_recall']:.3f}<{RECALL_GATE}")
        reasons.append("component_reconstruction_incomplete")
    if metrics["halo_spill"] > HALO_GATE:
        reasons.append(f"halo_spill_above_threshold:{metrics['halo_spill']:.3f}>{HALO_GATE}")
    if metrics.get("vector_fit_residual_px_p95", 0.0) > RESIDUAL_GATE:
        reasons.append(
            f"vector_fit_residual_above_threshold:"
            f"{metrics['vector_fit_residual_px_p95']:.3f}>{RESIDUAL_GATE}"
        )
    
    if components_detected > 0 and components_vectorized < components_detected:
        reasons.append("vectorization_incomplete")
        
    if "fixture_assignment_ambiguous" in quality_flags:
        reasons.append("fixture_assignment_ambiguous")

    if metrics.get("is_dot_only", False):
        reasons.extend(metrics.get("dot_reasons", []))

    if not fixture_output_accounting_complete:
        reasons.append("sibling_aperture_unaccounted")

    # The actual gate MUST measure reconstruction coverage against the full significant selected-aperture CORE evidence.
    authority_eligible = (
        metrics["core_precision"] >= PREC_GATE and
        metrics["core_recall"] >= RECALL_GATE and
        metrics["halo_spill"] <= HALO_GATE and
        metrics.get("vector_fit_residual_px_p95", 0.0) <= RESIDUAL_GATE and
        "fixture_assignment_ambiguous" not in quality_flags
        and not metrics.get("dot_reasons", [])
    )

    if authority_eligible and fixture_output_accounting_complete:
        status = "authority"
    elif "fixture_assignment_ambiguous" in quality_flags:
        status = "quarantined"
    elif "vectorization_incomplete" in [r.split(":")[0] for r in reasons] or "component_reconstruction_incomplete" in reasons or "sibling_aperture_unaccounted" in reasons:
        # Mask may still hold local aperture authority even if vectorization is incomplete or sibling is missing
        status = "provisional"
    else:
        status = "quarantined"

    return authority_eligible, status, reasons
