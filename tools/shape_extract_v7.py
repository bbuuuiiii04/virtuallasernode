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
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics
    from tools.shape_vectorize_v7 import vectorize_component

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

    # Process components
    source_core_components: list[dict[str, Any]] = []
    included_component_ids: list[str] = []
    sibling_aperture_component_ids: list[str] = []
    unaccounted_component_ids: list[str] = []
    
    components: list[dict[str, Any]] = []
    polylines: list[dict[str, Any]] = []
    quality_flags: list[str] = []
    target_core_mask = np.zeros((H, W), dtype=bool)

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

        if a_label == target_box_label:
            included_component_ids.append(comp_id)
            target_core_mask |= comp_mask

            if a_type == "ambiguous":
                quality_flags.append("fixture_assignment_ambiguous")

            comp_class = classify_component(comp_mask)

            wnorm = bbox_wall_norm(
                float(bbox_px[0]), float(bbox_px[1]),
                float(bbox_px[2]), float(bbox_px[3]),
                target_box,
            ) if target_box else [0.0, 0.0, 0.0, 0.0]

            if out_of_box:
                quality_flags.append("out_of_box_geometry")

            components.append({
                "component_id": comp_id,
                "class": comp_class,
                "area_px": area,
                "bbox_px": bbox_px,
                "bbox_wall_norm": wnorm,
                "out_of_box_geometry": out_of_box,
                "fixture_assignment": a_type,
            })

            comp_polys = vectorize_component(comp_mask, comp_class, score_map, comp_id)
            polylines.extend(comp_polys)
        elif a_label is not None:
            sibling_aperture_component_ids.append(comp_id)
        else:
            unaccounted_component_ids.append(comp_id)

    fixture_output_accounting_complete = (len(sibling_aperture_component_ids) == 0 and len(unaccounted_component_ids) == 0)
    source_frame_accounting_complete = fixture_output_accounting_complete

    n_detected = len(components)
    n_vectorized = len(set(pl["component_id"] for pl in polylines))

    if n_detected == 0:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return _empty_record(
            shape_ref, entry, geom, geom_path, params,
            bg_median, bg_mad, elapsed_ms,
            status="quarantined",
            reasons=["low_contrast"],
            target_box_label=target_box_label,
            fixture_boxes=fixture_boxes,
        )

    # Add wall_norm coords to polylines
    for pl in polylines:
        wpts = []
        if target_box:
            for xy in pl["points_px"]:
                wx, wy = pixel_to_wall_norm(xy[0], xy[1], target_box)
                wpts.append([round(wx, 4), round(wy, 4)])
        pl["points_wall_norm"] = wpts
        pl["point_count"] = len(pl["points_px"])

    # Assign polyline_id
    for i, pl in enumerate(polylines):
        pl["polyline_id"] = f"p{i}"

    # Topology summary
    dots = sum(1 for c in components if c["class"] == "dot")
    closed = sum(1 for c in components if c["class"] == "closed_stroke")
    opened = sum(1 for c in components if c["class"] == "open_stroke")
    topo = {"dots": dots, "closed_strokes": closed, "open_strokes": opened}

    # Core mask stats restricted to target box
    # Instead of clipping to the calibration box, we use the union of all components
    # assigned to this box, which preserves out-of-box geometry.
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
    rle_path_rel = f"masks/{shape_ref}.rle.json"

    metrics = compute_metrics(polylines, core_in_box, glow_mask, components)
    metrics["components_detected"] = n_detected
    metrics["components_vectorized"] = n_vectorized

    auth_eligible, status, reasons = compute_authority_gate(
        metrics, n_detected, n_vectorized, quality_flags, fixture_output_accounting_complete
    )

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
            "timing_ms": elapsed_ms,
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
        "topology_summary": topo,
        "metrics": metrics,
        "status": status,
        "selected_aperture_authority_eligible": auth_eligible,
        "authority_eligible": auth_eligible,
        "status_reasons": reasons,
        "quality_flags": list(set(quality_flags)),
        "geometry_layers": {
            "core_mask": "primary_evidence_authority",
            "raw_debug_vectors": "diagnostic_only",
            "render_vectors": "derived_validated" if auth_eligible else None,
            "render_fallback": "core_mask" if not auth_eligible else "none"
        },
        "human_review": {"verdict": "pending", "date": None},
        "_rle_data": rle_data,  # ephemeral; written separately, then removed
    }
    return record


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
            "timing_ms": elapsed_ms,
        },
        "core_mask": {"rle_path": None, "pixel_count": 0, "bbox_px": [], "bbox_wall_norm": [], "centroid_wall_norm": []},
        "components": [],
        "polylines": [],
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
) -> None:
    """Render side-by-side contact sheet with binding palette (§16)."""
    from PIL import Image, ImageDraw, ImageFont

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

    # Choose geometry color by status (§16)
    if status == "authority":
        geom_color = (255, 255, 0)  # yellow — authority only
    elif status == "provisional":
        geom_color = (255, 165, 0)  # orange
    else:
        geom_color = (255, 0, 255)  # magenta — rejected/quarantined

    # Red: component bboxes
    for comp in record.get("components", []):
        bbox = comp.get("bbox_px", [])
        if len(bbox) == 4:
            draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], outline=(255, 50, 50), width=1)

    # Draw geometry (color based on status)
    for pl in record.get("polylines", []):
        pts = pl.get("points_px", [])
        if len(pts) == 1:
            x, y = int(pts[0][0]), int(pts[0][1])
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=geom_color)
        elif len(pts) >= 2:
            flat = [(int(p[0]), int(p[1])) for p in pts]
            draw.line(flat, fill=geom_color, width=2)

    # Status label at top of fixture box
    label_text = f"{record['shape_ref']} | {status}"
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
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
                render_contact_sheet(record, still_path, cs_path, fixture_boxes, geom["analysis_roi"])
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
