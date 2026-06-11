"""V7 CLI: selection-entry → record + RLE mask + contact sheet.

Usage:
    python3 tools/shape_extract_v7.py \\
        --selection artifacts/renderer/pr-g1-shape-authority/shape_selection.json \\
        --refs sh1_21b9e82ef84b930b sh1_41c84ad2ac1f458e sh1_adb58093da473f3e \\
        --out artifacts/renderer/shape_authority_v2/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np

# Guard: AI imports forbidden in this module
_FORBIDDEN = ["ai_shape", "gemini", "google.generativeai"]


def _check_no_ai() -> None:
    for name in list(sys.modules.keys()):
        for bad in _FORBIDDEN:
            if bad in name:
                raise RuntimeError(f"Forbidden AI module imported: {name}")


EXTRACTION_POLICY_VERSION = "v7"
RECORD_VERSION = "shape-authority-v2"
ARTIFACT_VERSION = "shape-library-v1"  # keep sh1_ refs for backward compat

GEOMETRY_FILE = "captures/fixture_model/analysis_geometry.json"


def compute_shape_ref(vector_key: str, capture_path: str, fixture_box_label: str) -> str:
    payload = f"{ARTIFACT_VERSION}|{vector_key}|{capture_path}|{fixture_box_label}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"sh1_{digest}"


def load_selection(path: str | Path) -> list[dict[str, Any]]:
    with open(path) as f:
        data = json.load(f)
    return data.get("entries", [])


def find_entry_by_ref(entries: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
    for e in entries:
        vk = e.get("vector_key", "")
        cp = e.get("capture_path", "")
        box = e.get("selected_fixture_box", "image_left")
        if compute_shape_ref(vk, cp, box) == ref:
            return e
    return None


def extract_record(
    entry: dict[str, Any],
    shape_ref: str,
    capture_root: Path,
    geom: dict[str, Any],
    geom_path: Path,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Run full v7 extraction pipeline for one selection entry."""
    from PIL import Image

    from tools.shape_core_mask import (
        FixtureBox,
        assign_fixture,
        bbox_wall_norm,
        classify_component,
        compute_bg_model,
        compute_combined_score,
        geometry_source_sha,
        label_components,
        load_fixture_boxes,
        make_core_mask,
        make_glow_mask,
        make_roi_mask,
        pixel_to_wall_norm,
        rle_encode,
    )
    from tools.shape_validation_v2 import (
        compute_authority_gate,
        compute_metrics,
        component_structure_coverage,
    )
    from tools.shape_vectorize_v7 import (
        extract_structure_submask,
        group_chain_rejection_reasons,
        sample_geometry_points,
        vectorize_component,
        vectorize_group,
    )

    t0 = time.perf_counter()

    still_path = capture_root / entry["still_path"]
    if not still_path.exists():
        # Try still_color.jpg fallback
        still_color = still_path.parent / "still_color.jpg"
        if still_color.exists():
            still_path = still_color

    img_pil = Image.open(still_path).convert("RGB")
    img_rgb = np.array(img_pil, dtype=np.uint8)
    H, W = img_rgb.shape[:2]

    roi = geom["analysis_roi"]  # [x0, y0, x1, y1]
    roi_mask = make_roi_mask((H, W), roi)
    fixture_boxes = load_fixture_boxes(geom)

    target_box_label = entry.get("selected_fixture_box", "image_left")
    target_box = fixture_boxes.get(target_box_label)

    # Compute score map + background model
    score_map = compute_combined_score(img_rgb)
    bg_median, bg_mad = compute_bg_model(score_map, roi_mask)

    k_core = params.get("k_core", 8.0)
    k_glow = params.get("k_glow", 3.5)
    sat_floor = params.get("sat_floor", 200)
    min_core_area = params.get("min_core_area_px", 4)

    core_mask = make_core_mask(
        score_map, roi_mask, img_rgb, bg_median, bg_mad,
        k_core=k_core, sat_floor=sat_floor, min_core_area=min_core_area,
    )
    glow_mask = make_glow_mask(score_map, roi_mask, bg_median, bg_mad, k_glow=k_glow)

    labeled, n_components = label_components(core_mask)

    if n_components == 0:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return _empty_record(
            shape_ref, entry, geom, geom_path, params,
            bg_median, bg_mad, elapsed_ms,
            status="quarantined",
            reasons=["blank_still"],
            target_box_label=target_box_label,
            fixture_boxes=fixture_boxes,
        )

    # Component pass: preserve source component IDs/order, but defer authority
    # accounting until grouped vectorization and artifact rejection are known.
    source_core_components: list[dict[str, Any]] = []
    included_component_ids: list[str] = []
    sibling_aperture_component_ids: list[str] = []
    unaccounted_component_ids: list[str] = []

    comp_infos: list[dict[str, Any]] = []
    polylines: list[dict[str, Any]] = []
    sibling_polylines: list[dict[str, Any]] = []
    quality_flags: list[str] = []
    full_core_mask = np.zeros((H, W), dtype=bool)
    structure_by_comp: dict[str, np.ndarray] = {}
    comp_class_by_id: dict[str, str] = {}

    for cid in range(1, n_components + 1):
        comp_mask = labeled == cid
        ys, xs = np.where(comp_mask)
        area = int(len(ys))
        bbox_px = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]

        a_type, a_label, out_of_box = assign_fixture(comp_mask, fixture_boxes)

        comp_id = f"s{len(source_core_components)}"
        source_core_components.append({
            "source_component_id": comp_id,
            "aperture_assignment": a_label,
            "significant": True,
            "bbox_px": bbox_px,
            "area_px": area,
            "out_of_box_geometry": out_of_box
        })

        full_core_mask |= comp_mask

        comp_class = classify_component(comp_mask)
        comp_structure = extract_structure_submask(comp_mask, img_rgb)
        structure_by_comp[comp_id] = comp_structure
        comp_class_by_id[comp_id] = comp_class
        comp_infos.append({
            "index": len(comp_infos),
            "component_id": comp_id,
            "mask": comp_mask,
            "structure": comp_structure,
            "class": comp_class,
            "area_px": area,
            "bbox_px": bbox_px,
            "aperture_assignment": a_type,
            "aperture_label": a_label,
            "out_of_box_geometry": out_of_box,
            "centroid_px": [float(xs.mean()), float(ys.mean())],
            "peak_score": float(score_map[comp_mask].max()) if area else 0.0,
        })

        if a_label == target_box_label:
            included_component_ids.append(comp_id)

            if a_type == "ambiguous":
                quality_flags.append("fixture_assignment_ambiguous")

            if out_of_box:
                quality_flags.append("out_of_box_geometry")
        elif a_label is not None:
            sibling_aperture_component_ids.append(comp_id)
        else:
            unaccounted_component_ids.append(comp_id)

    if not included_component_ids:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return _empty_record(
            shape_ref, entry, geom, geom_path, params,
            bg_median, bg_mad, elapsed_ms,
            status="quarantined",
            reasons=["low_contrast"],
            target_box_label=target_box_label,
            fixture_boxes=fixture_boxes,
        )

    from skimage.measure import label as _label

    glow_labeled = _label(glow_mask, connectivity=2)
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    solo_groups: list[list[dict[str, Any]]] = []
    for info in comp_infos:
        aperture = info["aperture_label"]
        if aperture is None:
            continue
        if info["class"] == "closed_stroke":
            solo_groups.append([info])
            continue
        labels = glow_labeled[info["mask"]]
        labels = labels[labels > 0]
        if labels.size == 0:
            solo_groups.append([info])
            continue
        vals, counts = np.unique(labels, return_counts=True)
        glow_id = int(vals[int(np.argmax(counts))])
        grouped.setdefault((str(aperture), glow_id), []).append(info)

    groups = solo_groups + list(grouped.values())
    groups.sort(key=lambda g: min(int(info["index"]) for info in g))
    for group in groups:
        group.sort(key=lambda info: int(info["index"]))
        aperture = group[0]["aperture_label"]
        if len(group) == 1:
            info = group[0]
            group_polys = vectorize_component(
                info["mask"], info["class"], score_map, info["component_id"],
                img_rgb=img_rgb, structure_mask=info["structure"],
            )
        else:
            group_polys = vectorize_group(
                [info["mask"] for info in group],
                [info["structure"] for info in group],
                [info["class"] for info in group],
                [info["component_id"] for info in group],
                score_map,
                glow_mask,
                img_rgb,
            )
            if group_polys is None:
                group_polys = []
                rejection_reasons = group_chain_rejection_reasons(
                    [info["structure"] for info in group],
                    glow_mask,
                )
                turn_rejected = any(
                    r in {"chain_sharp_turns_above_threshold", "chain_mean_turn_above_threshold"}
                    for r in rejection_reasons
                )
                for info in group:
                    # A turn-rejected constellation of genuinely compact dots
                    # stays as explicit diagnostic anchors. Members with real
                    # internal structure (multi-fragment or elongated) keep
                    # full per-component vectorization, which has its own
                    # ordering/coverage gates.
                    if turn_rejected and _is_compact_dot_member(info):
                        group_polys.append(_diagnostic_anchor_polyline(
                            info["mask"], score_map, info["component_id"], "group_chain_rejected"
                        ))
                        continue
                    fallback_polys = vectorize_component(
                        info["mask"], info["class"], score_map, info["component_id"],
                        img_rgb=img_rgb, structure_mask=info["structure"],
                    )
                    for pl in fallback_polys:
                        if rejection_reasons:
                            pl["group_rejection_reasons"] = rejection_reasons
                    group_polys.extend(fallback_polys)

        represented = {
            member
            for pl in group_polys
            for member in _polyline_member_ids(pl)
        }
        for info in group:
            if info["component_id"] not in represented:
                group_polys.append(_diagnostic_anchor_polyline(
                    info["mask"], score_map, info["component_id"], "empty_trace_fallback"
                ))

        for pl in group_polys:
            pl["aperture"] = aperture
            if aperture == target_box_label:
                polylines.append(pl)
            else:
                sibling_polylines.append(pl)

    for pl in polylines + sibling_polylines:
        box = fixture_boxes.get(pl.get("aperture"))
        wpts = []
        if box:
            for xy in pl.get("points_px", []):
                wx, wy = pixel_to_wall_norm(xy[0], xy[1], box)
                wpts.append([round(wx, 4), round(wy, 4)])
        pl["points_wall_norm"] = wpts
        pl["point_count"] = len(pl.get("points_px", []))

    for i, pl in enumerate(polylines):
        pl["polyline_id"] = f"p{i}"
    for i, pl in enumerate(sibling_polylines):
        pl["polyline_id"] = f"sp{i}"

    coverage_by_comp: dict[str, float] = {}
    render_represented_by_comp: set[str] = set()
    _assign_render_roles(
        polylines + sibling_polylines,
        structure_by_comp,
        comp_class_by_id,
        component_structure_coverage,
        coverage_by_comp,
        render_represented_by_comp,
    )

    artifact_reasons = _find_artifact_rejections(
        comp_infos,
        polylines + sibling_polylines,
        render_represented_by_comp,
        sample_geometry_points,
    )
    rejected_component_ids = sorted(
        artifact_reasons.keys(),
        key=lambda cid: int(cid[1:]) if cid.startswith("s") and cid[1:].isdigit() else cid,
    )
    rejected_set = set(rejected_component_ids)
    for sc in source_core_components:
        cid = sc.get("source_component_id")
        if cid in artifact_reasons:
            sc["significant"] = False
            sc["artifact_reason"] = artifact_reasons[cid]

    significant_included_ids = [
        cid for cid in included_component_ids if cid not in rejected_set
    ]
    significant_sibling_ids = [
        cid for cid in sibling_aperture_component_ids if cid not in rejected_set
    ]

    comp_polys_by_id: dict[str, list[dict[str, Any]]] = {}
    for pl in polylines:
        for member in _polyline_member_ids(pl):
            comp_polys_by_id.setdefault(member, []).append(pl)

    components: list[dict[str, Any]] = []
    target_core_mask = np.zeros((H, W), dtype=bool)
    target_structure_mask = np.zeros((H, W), dtype=bool)
    for info in comp_infos:
        cid = info["component_id"]
        if cid not in significant_included_ids:
            continue
        target_core_mask |= info["mask"]
        target_structure_mask |= info["structure"]
        bbox_px = info["bbox_px"]
        wnorm = bbox_wall_norm(
            float(bbox_px[0]), float(bbox_px[1]),
            float(bbox_px[2]), float(bbox_px[3]),
            target_box,
        ) if target_box else [0.0, 0.0, 0.0, 0.0]
        components.append({
            "component_id": cid,
            "class": _refined_component_class(
                info["class"], comp_polys_by_id.get(cid, [])
            ),
            "area_px": info["area_px"],
            "bbox_px": bbox_px,
            "bbox_wall_norm": wnorm,
            "out_of_box_geometry": info["out_of_box_geometry"],
            "fixture_assignment": info["aperture_assignment"],
        })

    n_detected = len(components)
    vectorized_ids = {
        member
        for pl in polylines
        for member in _polyline_member_ids(pl)
        if member in significant_included_ids
    }
    n_vectorized = len(vectorized_ids)

    dots = sum(1 for c in components if c["class"] == "dot")
    closed = sum(1 for c in components if c["class"] == "closed_stroke")
    opened = sum(1 for c in components if c["class"] == "open_stroke")
    topo = {"dots": dots, "closed_strokes": closed, "open_strokes": opened}

    core_in_box = target_core_mask
    core_ys, core_xs = np.where(core_in_box)
    if len(core_ys):
        core_bbox_px = [int(core_xs.min()), int(core_ys.min()), int(core_xs.max()), int(core_ys.max())]
        ccx = float(core_xs.mean())
        ccy = float(core_ys.mean())
        core_centroid_wn = list(pixel_to_wall_norm(ccx, ccy, target_box)) if target_box else [0.0, 0.0]
        core_bbox_wn = bbox_wall_norm(
            float(core_bbox_px[0]), float(core_bbox_px[1]),
            float(core_bbox_px[2]), float(core_bbox_px[3]),
            target_box,
        ) if target_box else [0.0, 0.0, 0.0, 0.0]
    else:
        core_bbox_px = [0, 0, 0, 0]
        core_centroid_wn = [0.0, 0.0]
        core_bbox_wn = [0.0, 0.0, 0.0, 0.0]

    rle_data = rle_encode(core_in_box)
    full_core_rle = rle_encode(full_core_mask)
    rle_path_rel = f"masks/{shape_ref}.rle.json"

    has_vector_authority = (
        n_detected > 0
        and all(cid in render_represented_by_comp for cid in significant_included_ids)
    )
    render_authority = "vector" if has_vector_authority else "core_mask"

    sibling_accounted = all(
        cid in render_represented_by_comp
        for cid in significant_sibling_ids
    )
    sibling_missing_reasons = {
        cid: f"no_render_geometry:structure_coverage={coverage_by_comp.get(cid, 0.0):.2f}"
        for cid in significant_sibling_ids
        if cid not in render_represented_by_comp
    }
    fixture_output_accounting_complete = (
        len(unaccounted_component_ids) == 0 and sibling_accounted
    )
    source_frame_accounting_complete = fixture_output_accounting_complete

    render_polys = [p for p in polylines if p.get("render_role") == "render"]
    metrics = compute_metrics(
        render_polys, core_in_box, glow_mask, components,
        structure_mask=target_structure_mask,
    )
    metrics["components_detected"] = n_detected
    metrics["components_vectorized"] = n_vectorized

    auth_eligible, status, reasons = compute_authority_gate(
        metrics, n_detected, n_vectorized, quality_flags, fixture_output_accounting_complete
    )
    status, reasons = _cap_status_for_render_authority(status, reasons, render_authority)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    record: dict[str, Any] = {
        "record_version": RECORD_VERSION,
        "shape_ref": shape_ref,
        "vector_key": entry.get("vector_key", ""),
        "ch1_19": entry.get("ch1_19", {}),
        "capture_path": entry.get("capture_path", ""),
        "source_still": str(entry.get("still_path", "")),
        "test_id": entry.get("family_or_checkpoint", ""),
        "phase": entry.get("phase", ""),
        "exposure_track": entry.get("exposure_track", ""),
        "fixture_box_label": target_box_label,
        "detection_domain_px": roi,
        "authority_scope": "aperture",
        "selected_aperture": target_box_label,
        "aperture_boxes": {k: [v.x0, v.y0, v.x1, v.y1] for k, v in fixture_boxes.items() if v},
        "source_core_components": source_core_components,
        "included_component_ids": included_component_ids,
        "sibling_aperture_component_ids": sibling_aperture_component_ids,
        "unaccounted_component_ids": unaccounted_component_ids,
        "rejected_component_ids": rejected_component_ids,
        "sibling_missing_reasons": sibling_missing_reasons,
        "component_structure_coverage": coverage_by_comp,
        "source_frame_accounting_complete": source_frame_accounting_complete,
        "fixture_output_accounting_complete": fixture_output_accounting_complete,
        "geometry_source": {
            "path": GEOMETRY_FILE,
            "sha256": geometry_source_sha(geom_path),
        },
        "extraction": {
            "policy_version": EXTRACTION_POLICY_VERSION,
            "params": {
                "k_core": k_core,
                "k_glow": k_glow,
                "sat_floor": sat_floor,
                "min_core_area_px": min_core_area,
            },
            "background": {
                "median_score": round(bg_median, 2),
                "mad_score": round(bg_mad, 2),
            },
            "timing_ms": 0,
        },
        "core_mask": {
            "rle_path": rle_path_rel,
            "pixel_count": int(np.sum(core_in_box)),
            "bbox_px": core_bbox_px,
            "bbox_wall_norm": [round(v, 4) for v in core_bbox_wn],
            "centroid_wall_norm": [round(v, 4) for v in core_centroid_wn],
        },
        "components": components,
        "polylines": polylines,
        "sibling_polylines": sibling_polylines,
        "topology_summary": topo,
        "metrics": metrics,
        "status": status,
        "selected_aperture_authority_eligible": auth_eligible,
        "authority_eligible": auth_eligible,
        "status_reasons": reasons,
        "quality_flags": sorted(set(quality_flags)),
        "render_authority": render_authority,
        "geometry_layers": {
            "core_mask": "primary_evidence_authority",
            "raw_debug_vectors": "diagnostic_only",
            "render_vectors": "derived_validated" if (auth_eligible and render_authority == "vector") else None,
            "render_fallback": "core_mask" if render_authority == "core_mask" else "none"
        },
        "human_review": {"verdict": "pending", "date": None},
        "_rle_data": rle_data,  # ephemeral; written separately, then removed
        "_full_core_rle": full_core_rle,  # ephemeral; used by contact sheet, then removed
    }
    return record


def _polyline_member_ids(pl: dict[str, Any]) -> list[str]:
    members = pl.get("member_component_ids")
    if isinstance(members, list) and members:
        return [str(m) for m in members]
    cid = pl.get("component_id")
    return [str(cid)] if cid else []


def _component_sort_key(cid: str) -> int:
    return int(cid[1:]) if cid.startswith("s") and cid[1:].isdigit() else 10**9


def _refined_component_class(original_cls: str, comp_polys: list[dict[str, Any]]) -> str:
    """Component class refined by the geometry the structure actually earned.

    CORE-blob classification can mislabel glow-merged shapes (a glow ring
    around a dot reads as closed_stroke; a sparse crescent reads as dot).
    The emitted, structure-validated geometry is the truthful class basis.
    Components with only diagnostic fallbacks keep their original class.
    """
    kinds: list[str] = []
    closed_any = False
    for pl in comp_polys:
        if pl.get("diagnostic_fallback_reason"):
            continue
        kinds.append(str(pl.get("geometry_kind")))
        if pl.get("closed"):
            closed_any = True
    if not kinds:
        return original_cls
    if all(k == "dot_anchor" for k in kinds):
        return "dot"
    if closed_any or any(
        k in ("rect_centerline", "quad_centerline", "closed_centerline") for k in kinds
    ):
        return "closed_stroke"
    return "open_stroke"


def _is_compact_dot_member(info: dict[str, Any]) -> bool:
    """True when a group member is a genuine compact dot: dot-classed CORE
    component whose saturated structure is a single compact fragment."""
    from tools.shape_vectorize_v7 import _classify_substructure, _structure_subcomponents
    if info.get("class") != "dot":
        return False
    subs = _structure_subcomponents(info["structure"], info["mask"])
    return len(subs) == 1 and _classify_substructure(subs[0]) == "dash"


def _diagnostic_anchor_polyline(
    comp_mask: np.ndarray,
    score_map: np.ndarray,
    comp_id: str,
    reason: str,
) -> dict[str, Any]:
    ys, xs = np.where(comp_mask)
    if len(ys) == 0:
        cx = cy = 0.0
    else:
        weights = score_map[ys, xs].astype(np.float64)
        if weights.sum() < 1e-9:
            weights = np.ones(len(ys), dtype=np.float64)
        cx = float(np.average(xs, weights=weights))
        cy = float(np.average(ys, weights=weights))
    return {
        "component_id": comp_id,
        "geometry_kind": "dot_anchor",
        "closed": False,
        "ordered": True,
        "diagnostic_fallback_reason": reason,
        "points_px": [[round(cx, 2), round(cy, 2)]],
    }


def _assign_render_roles(
    polylines: list[dict[str, Any]],
    structure_by_comp: dict[str, np.ndarray],
    comp_class_by_id: dict[str, str],
    component_structure_coverage_fn: Any,
    coverage_by_comp: dict[str, float],
    render_represented_by_comp: set[str],
) -> None:
    MIN_COMPONENT_COVERAGE = 0.6
    MIN_MEMBER_RENDER_COVERAGE = 0.4
    from skimage.morphology import dilation as _dilation, disk as _disk

    clusters: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for pl in polylines:
        key = tuple(sorted(_polyline_member_ids(pl), key=_component_sort_key))
        if key:
            clusters.setdefault(key, []).append(pl)

    for members, pls in clusters.items():
        union_structure = None
        for cid in members:
            struct = structure_by_comp.get(cid)
            if struct is None:
                continue
            union_structure = struct.copy() if union_structure is None else (union_structure | struct)

        cluster_cov = (
            component_structure_coverage_fn(pls, union_structure)
            if union_structure is not None else 0.0
        )
        single_dot_anchor = (
            len(members) == 1
            and comp_class_by_id.get(members[0]) == "dot"
            and all(pl.get("geometry_kind") == "dot_anchor" for pl in pls)
        )
        on_structure = False
        if single_dot_anchor:
            struct = structure_by_comp.get(members[0])
            struct_near = _dilation(struct, _disk(2)) if struct is not None else None
            for pl in pls:
                for ax, ay in pl.get("points_px", []):
                    xi, yi = int(round(ax)), int(round(ay))
                    if (
                        struct_near is not None
                        and 0 <= yi < struct_near.shape[0]
                        and 0 <= xi < struct_near.shape[1]
                        and struct_near[yi, xi]
                    ):
                        on_structure = True
            role = "render" if on_structure else "diagnostic"
        else:
            role = "render" if cluster_cov >= MIN_COMPONENT_COVERAGE else "diagnostic"

        for cid in members:
            struct = structure_by_comp.get(cid)
            if struct is None:
                member_cov = 0.0
            elif single_dot_anchor and on_structure:
                member_cov = 1.0
            else:
                member_cov = component_structure_coverage_fn(pls, struct)
            coverage_by_comp[cid] = round(float(member_cov), 4)
            if role == "render" and member_cov >= MIN_MEMBER_RENDER_COVERAGE:
                render_represented_by_comp.add(cid)

        for pl in pls:
            pl["render_role"] = role
            pl["structure_coverage"] = round(float(cluster_cov), 4)


def _find_artifact_rejections(
    comp_infos: list[dict[str, Any]],
    polylines: list[dict[str, Any]],
    render_represented_by_comp: set[str],
    sample_geometry_points_fn: Any,
) -> dict[str, str]:
    render_pts_by_aperture: dict[str, list[list[float]]] = {}
    for pl in polylines:
        if pl.get("render_role") != "render":
            continue
        aperture = str(pl.get("aperture") or "")
        render_pts_by_aperture.setdefault(aperture, []).extend(
            sample_geometry_points_fn([pl], spacing=1.0)
        )

    peak_by_cid = {info["component_id"]: float(info["peak_score"]) for info in comp_infos}
    max_render_peak_by_aperture: dict[str, float] = {}
    for info in comp_infos:
        cid = info["component_id"]
        aperture = str(info.get("aperture_label") or "")
        if cid not in render_represented_by_comp or not aperture:
            continue
        max_render_peak_by_aperture[aperture] = max(
            max_render_peak_by_aperture.get(aperture, 0.0),
            peak_by_cid.get(cid, 0.0),
        )

    reasons: dict[str, str] = {}
    for info in comp_infos:
        cid = info["component_id"]
        aperture = str(info.get("aperture_label") or "")
        if not aperture:
            continue
        if int(info["area_px"]) >= 30:
            continue
        if cid in render_represented_by_comp:
            continue
        pts = render_pts_by_aperture.get(aperture) or []
        if not pts:
            continue
        centroid = info["centroid_px"]
        min_dist = min(
            ((centroid[0] - p[0]) ** 2 + (centroid[1] - p[1]) ** 2) ** 0.5
            for p in pts
        )
        if min_dist <= 15.0:
            continue
        max_peak = max_render_peak_by_aperture.get(aperture, 0.0)
        if max_peak <= 0.0:
            continue
        peak = peak_by_cid.get(cid, 0.0)
        if peak >= 0.5 * max_peak:
            continue
        reasons[cid] = (
            "tiny_dim_far_artifact:"
            f"area_px={int(info['area_px'])},"
            f"centroid_distance_px={min_dist:.1f},"
            f"peak_score={peak:.1f}<0.5*{max_peak:.1f}"
        )
    return reasons


def _cap_status_for_render_authority(
    status: str,
    reasons: list[str],
    render_authority: str,
) -> tuple[str, list[str]]:
    if status == "authority" and render_authority != "vector":
        capped = list(reasons)
        if "render_authority_core_mask" not in capped:
            capped.append("render_authority_core_mask")
        return "provisional", capped
    return status, reasons


def _empty_record(
    shape_ref: str,
    entry: dict[str, Any],
    geom: dict[str, Any],
    geom_path: Path,
    params: dict[str, Any],
    bg_median: float,
    bg_mad: float,
    elapsed_ms: int,
    status: str,
    reasons: list[str],
    target_box_label: str = "image_left",
    fixture_boxes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from tools.shape_core_mask import geometry_source_sha
    return {
        "record_version": RECORD_VERSION,
        "shape_ref": shape_ref,
        "vector_key": entry.get("vector_key", ""),
        "ch1_19": entry.get("ch1_19", {}),
        "capture_path": entry.get("capture_path", ""),
        "source_still": str(entry.get("still_path", "")),
        "test_id": entry.get("family_or_checkpoint", ""),
        "phase": entry.get("phase", ""),
        "exposure_track": entry.get("exposure_track", ""),
        "fixture_box_label": target_box_label,
        "detection_domain_px": geom.get("analysis_roi", []),
        "authority_scope": "aperture",
        "selected_aperture": target_box_label,
        "aperture_boxes": {k: [v.x0, v.y0, v.x1, v.y1] for k, v in fixture_boxes.items() if v} if fixture_boxes else {},
        "source_core_components": [],
        "included_component_ids": [],
        "sibling_aperture_component_ids": [],
        "unaccounted_component_ids": [],
        "rejected_component_ids": [],
        "sibling_missing_reasons": {},
        "component_structure_coverage": {},
        "source_frame_accounting_complete": False,
        "fixture_output_accounting_complete": False,
        "geometry_source": {
            "path": GEOMETRY_FILE,
            "sha256": geometry_source_sha(geom_path),
        },
        "extraction": {
            "policy_version": EXTRACTION_POLICY_VERSION,
            "params": params,
            "background": {"median_score": round(bg_median, 2), "mad_score": round(bg_mad, 2)},
            "timing_ms": 0,
        },
        "core_mask": {"rle_path": None, "pixel_count": 0, "bbox_px": [], "bbox_wall_norm": [], "centroid_wall_norm": []},
        "components": [],
        "polylines": [],
        "sibling_polylines": [],
        "topology_summary": {"dots": 0, "closed_strokes": 0, "open_strokes": 0},
        "metrics": {
            "core_precision": 0.0, "core_recall": 0.0, "halo_spill": 0.0,
            "vector_fit_residual_px_p95": 0.0,
            "components_detected": 0, "components_vectorized": 0,
        },
        "status": status,
        "selected_aperture_authority_eligible": False,
        "authority_eligible": False,
        "status_reasons": reasons,
        "quality_flags": [],
        "geometry_layers": {
            "core_mask": "primary_evidence_authority",
            "raw_debug_vectors": "diagnostic_only",
            "render_vectors": None,
            "render_fallback": "none" if status == "quarantined" else "core_mask"
        },
        "human_review": {"verdict": "pending", "date": None},
        "_rle_data": None,
    }



def render_contact_sheet(
    record: dict[str, Any],
    still_path: Path,
    out_path: Path,
    fixture_boxes: dict[str, Any],
    roi: list[int],
    full_core_rle: dict | None = None,
) -> None:
    """Render side-by-side contact sheet with binding palette (§16).

    The overlay panel shows:
    - CORE mask as semi-transparent fill (primary evidence layer)
    - Fixture box frames in cyan
    - Component bboxes in red
    - Sibling aperture bboxes + masks in teal
    - Vectors colored by render_role (bright=render, dim=diagnostic)
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    img = Image.open(still_path).convert("RGB")
    W, H = img.size

    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)

    target_label = record.get("fixture_box_label", "image_left")
    box = fixture_boxes.get(target_label)

    # Cyan: fixture box frame
    if box:
        draw.rectangle([box.x0, box.y0, box.x1, box.y1], outline=(0, 255, 255), width=2)

    status = record.get("status", "quarantined")
    render_authority = record.get("render_authority", "vector")

    # Choose geometry color by status (§16)
    if status == "authority":
        geom_color = (255, 255, 0)  # yellow — authority only
    elif status == "provisional":
        geom_color = (255, 165, 0)  # orange
    else:
        geom_color = (255, 0, 255)  # magenta — rejected/quarantined

    # ── CORE mask evidence overlay ──
    # Render the CORE mask as a semi-transparent colored fill so the
    # human reviewer can see the actual detected laser evidence.
    if full_core_rle is not None:
        try:
            from tools.shape_core_mask import rle_decode
            from skimage.measure import label as _label

            full_mask = rle_decode(full_core_rle)
            labeled_full, n_full = _label(full_mask, connectivity=2, return_num=True)

            # Map component IDs to label indices
            sibling_ids = set(record.get("sibling_aperture_component_ids", []))
            included_ids = set(record.get("included_component_ids", []))
            source_comps = record.get("source_core_components", [])

            # Create mask overlay with alpha blending
            mask_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            mask_draw = ImageDraw.Draw(mask_overlay)

            for idx, sc in enumerate(source_comps):
                label_idx = idx + 1
                if label_idx > n_full:
                    continue
                comp_pixels = np.argwhere(labeled_full == label_idx)
                if len(comp_pixels) == 0:
                    continue

                cid = sc.get("source_component_id", "")
                if cid in included_ids:
                    # Selected aperture: orange fill
                    fill = (255, 140, 0, 90)
                elif cid in sibling_ids:
                    # Sibling aperture: teal fill
                    fill = (0, 180, 180, 90)
                else:
                    # Unaccounted: dim purple
                    fill = (180, 0, 180, 60)

                for y, x in comp_pixels:
                    mask_draw.point((int(x), int(y)), fill=fill)

            # Composite mask overlay onto the overlay image
            overlay = Image.alpha_composite(overlay.convert("RGBA"), mask_overlay).convert("RGB")
            draw = ImageDraw.Draw(overlay)

            # Re-draw fixture box after compositing
            if box:
                draw.rectangle([box.x0, box.y0, box.x1, box.y1], outline=(0, 255, 255), width=2)

        except Exception:
            pass  # Non-fatal: don't block extraction

    # Red: component bboxes
    for comp in record.get("components", []):
        bbox = comp.get("bbox_px", [])
        if len(bbox) == 4:
            draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], outline=(255, 50, 50), width=1)

    # Sibling aperture components (dim cyan bbox + label)
    for s_comp in record.get("source_core_components", []):
        if s_comp.get("source_component_id") in record.get("sibling_aperture_component_ids", []):
            bbox = s_comp.get("bbox_px", [])
            if len(bbox) == 4:
                draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], outline=(0, 150, 150), width=1)
                draw.text((bbox[0], max(0, bbox[1]-10)), "sibling", fill=(0, 150, 150))

    def _draw_polyline(pl, color):
        pts = pl.get("points_px", [])
        role = pl.get("render_role", "render")
        if role == "render":
            line_color, line_width = color, 2
        else:
            # Diagnostic vectors: thin, dim
            line_color = (color[0] // 2, color[1] // 2, color[2] // 2)
            line_width = 1
        if len(pts) == 1:
            x, y = int(pts[0][0]), int(pts[0][1])
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=line_color)
        elif len(pts) >= 2:
            flat = [(int(p[0]), int(p[1])) for p in pts]
            draw.line(flat, fill=line_color, width=line_width)

    # Sibling aperture geometry — same fixture output, traced in teal
    for pl in record.get("sibling_polylines", []):
        _draw_polyline(pl, (0, 220, 220))

    # Selected-aperture geometry — color by status, weight by render_role
    for pl in record.get("polylines", []):
        _draw_polyline(pl, geom_color)

    # Status label at top of fixture box
    auth_label = f" [mask]" if render_authority == "core_mask" else ""
    label_text = f"{record['shape_ref']} | {status}{auth_label}"
    if box:
        draw.text((box.x0 + 2, box.y0 + 2), label_text, fill=(200, 200, 200))

    combined = Image.new("RGB", (W * 2, H))
    combined.paste(img, (0, 0))
    combined.paste(overlay, (W, 0))
    combined.save(out_path)


def write_manifest(out_dir: Path, records: list[dict[str, Any]], geom_path: Path) -> None:
    from tools.shape_core_mask import geometry_source_sha
    import datetime
    manifest = {
        "policy_version": EXTRACTION_POLICY_VERSION,
        "record_version": RECORD_VERSION,
        "generated_at": "2026-01-01T00:00:00Z",
        "geometry_sha": geometry_source_sha(geom_path),
        "counts": {
            "total": len(records),
            "authority": sum(1 for r in records if r.get("status") == "authority"),
            "provisional": sum(1 for r in records if r.get("status") == "provisional"),
            "quarantined": sum(1 for r in records if r.get("status") == "quarantined"),
        },
        "shape_refs": [r["shape_ref"] for r in records],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def _selection_entry_has_local_media(entry: dict[str, Any], capture_root: Path) -> bool:
    if entry.get("excluded_reason"):
        return False
    if not entry.get("local_media_exists", True):
        return False
    if not entry.get("vector_key") or not entry.get("capture_path"):
        return False
    still_rel = entry.get("still_path") or ""
    if not still_rel:
        return False
    still_path = capture_root / still_rel
    return still_path.is_file() or (still_path.parent / "still_color.jpg").is_file()


def main() -> None:
    _check_no_ai()

    parser = argparse.ArgumentParser(description="V7 deterministic shape extractor")
    parser.add_argument("--selection", required=True, help="Path to shape_selection.json")
    parser.add_argument("--refs", nargs="*", help="Shape refs to process (default: all)")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--capture-root", default=".", help="Root for capture paths")
    parser.add_argument("--k-core", type=float, default=8.0)
    parser.add_argument("--k-glow", type=float, default=3.5)
    parser.add_argument("--sat-floor", type=float, default=200.0)
    parser.add_argument("--min-core-area", type=int, default=20)
    args = parser.parse_args()

    from tools.shape_core_mask import load_analysis_geometry, load_fixture_boxes

    capture_root = Path(args.capture_root)
    selection_path = Path(args.selection)
    out_dir = Path(args.out)

    # Resolve capture root relative to selection file if needed
    if not capture_root.is_absolute():
        # Try relative to cwd, then relative to selection file
        if not (capture_root / "captures").exists():
            alt = selection_path.parent.parent.parent
            if (alt / "captures").exists():
                capture_root = alt

    geom_path = capture_root / GEOMETRY_FILE
    geom = load_analysis_geometry(geom_path)
    fixture_boxes = load_fixture_boxes(geom)

    entries = load_selection(selection_path)

    params = {
        "k_core": args.k_core,
        "k_glow": args.k_glow,
        "sat_floor": args.sat_floor,
        "min_core_area_px": args.min_core_area,
    }

    # Determine which refs to process
    if args.refs:
        target_refs = set(args.refs)
        to_process = []
        for ref in args.refs:
            e = find_entry_by_ref(entries, ref)
            if e is None:
                print(f"WARNING: ref {ref} not found in selection", file=sys.stderr)
            else:
                to_process.append((ref, e))
    else:
        to_process = []
        for e in entries:
            if not _selection_entry_has_local_media(e, capture_root):
                continue
            vk = e.get("vector_key", "")
            cp = e.get("capture_path", "")
            box = e.get("selected_fixture_box", "image_left")
            ref = compute_shape_ref(vk, cp, box)
            to_process.append((ref, e))

    (out_dir / "records").mkdir(parents=True, exist_ok=True)
    (out_dir / "masks").mkdir(parents=True, exist_ok=True)
    (out_dir / "contact_sheets").mkdir(parents=True, exist_ok=True)

    records_written: list[dict[str, Any]] = []

    for shape_ref, entry in to_process:
        print(f"Processing {shape_ref} ...", end=" ", flush=True)
        try:
            record = extract_record(entry, shape_ref, capture_root, geom, geom_path, params)

            rle_data = record.pop("_rle_data", None)
            full_core_rle = record.pop("_full_core_rle", None)

            # Write record JSON
            rec_path = out_dir / "records" / f"{shape_ref}.json"
            rec_path.write_text(json.dumps(record, indent=2))

            # Write RLE mask
            if rle_data is not None:
                mask_path = out_dir / "masks" / f"{shape_ref}.rle.json"
                mask_path.write_text(json.dumps(rle_data))

            # Write contact sheet
            still_path = capture_root / entry["still_path"]
            if not still_path.exists():
                still_path = still_path.parent / "still_color.jpg"
            cs_path = out_dir / "contact_sheets" / f"{shape_ref}.png"
            try:
                render_contact_sheet(record, still_path, cs_path, fixture_boxes, geom["analysis_roi"], full_core_rle=full_core_rle)
            except Exception as e:
                print(f"[contact sheet failed: {e}]", end=" ")

            records_written.append(record)
            print(f"-> {record['status']} | prec={record['metrics']['core_precision']:.2f} "
                  f"rec={record['metrics']['core_recall']:.2f} "
                  f"topo={record['topology_summary']}")

        except Exception as e:
            import traceback
            print(f"ERROR: {e}", file=sys.stderr)
            traceback.print_exc()

    write_manifest(out_dir, records_written, geom_path)
    print(f"\nWrote {len(records_written)} records to {out_dir}")

    # Summary
    for r in records_written:
        print(f"  {r['shape_ref']}: {r['status']} | topo={r['topology_summary']} "
              f"| prec={r['metrics']['core_precision']:.2f} "
              f"rec={r['metrics']['core_recall']:.2f}")


if __name__ == "__main__":
    main()
