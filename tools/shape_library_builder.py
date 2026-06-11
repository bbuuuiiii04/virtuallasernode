#!/usr/bin/env python3
"""PR-G1: build shape_selection.json + shape_library_v1.json from local corpus stills."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capture_index_runtime import vector_key_from_ch1_19  # noqa: E402
from tools.shape_candidate_extraction import classify_visual_status  # noqa: E402
from tools.shape_extraction import (  # noqa: E402
    ARTIFACT_VERSION,
    COORDINATE_SPACE,
    EXTRACTION_POLICY_VERSION,
    compute_shape_ref,
    extract_shape_from_image,
    load_fixture_boxes,
    make_contact_sheet,
    render_overlay_image,
)

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PR-G1 requires Pillow: pip install Pillow") from exc


CAPTURE_ROOT_REL = "captures/fixture_model"
PLAN_REVISION = "RENDERER_WALL_TO_AERIAL_PLAN_V1 rev 4"
SELECTION_POLICY_VERSION = "v1"
DEFAULT_FIXTURE_BOX = "image_left"
V7_AUTHORITY_ROOT_REL = "artifacts/renderer/shape_authority_v2"
V7_POLICY_VERSION = "v7"
FORBIDDEN_PATH_FRAGMENTS = (
    "calib/captures",
    "archive/pre_corpus",
    "/tmp/",
    "vln_wall_ch3_atlas",
    "wall_atlas_ch3",
    "docs/_archive",
)

CH3_FAMILIES: list[dict[str, Any]] = [
    {"family_or_checkpoint": "circle/ring static", "rep_ch3": 0, "ch3_min": 0, "ch3_max": 8},
    {"family_or_checkpoint": "horizontal line static", "rep_ch3": 32, "ch3_min": 16, "ch3_max": 40},
    {"family_or_checkpoint": "two-point / dual-dot static", "rep_ch3": 48, "ch3_min": 48, "ch3_max": 56},
    {"family_or_checkpoint": "dotted arc / compact swirl static-animation bank", "rep_ch3": 96, "ch3_min": 64, "ch3_max": 120},
    {"family_or_checkpoint": "U-wave dynamic macro", "rep_ch3": 128, "ch3_min": 128, "ch3_max": 136},
    {"family_or_checkpoint": "three-star dynamic macro", "rep_ch3": 144, "ch3_min": 144, "ch3_max": 152},
    {"family_or_checkpoint": "compact swirl dynamic macro", "rep_ch3": 160, "ch3_min": 160, "ch3_max": 168},
    {"family_or_checkpoint": "large star polygon dynamic macro", "rep_ch3": 176, "ch3_min": 176, "ch3_max": 176},
    {"family_or_checkpoint": "horizontal line dynamic variants", "rep_ch3": 216, "ch3_min": 184, "ch3_max": 255},
    {"family_or_checkpoint": "low dotted-row dynamic macro", "rep_ch3": 200, "ch3_min": 200, "ch3_max": 200},
    {"family_or_checkpoint": "compact point/dot dynamic macro", "rep_ch3": 224, "ch3_min": 224, "ch3_max": 224},
    {"family_or_checkpoint": "late ring dynamic macro", "rep_ch3": 248, "ch3_min": 248, "ch3_max": 248},
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _ch1_19_from_metadata(meta: dict[str, Any]) -> dict[str, int]:
    raw = meta.get("ch1_19") or meta.get("dmx") or {}
    return {f"CH{i}": int(raw.get(f"CH{i}", raw.get(str(i), 0)) or 0) for i in range(1, 20)}


def _resolve_still(folder: Path) -> Path | None:
    for name in ("still.jpg", "still_color.jpg"):
        p = folder / name
        if p.is_file():
            return p
    return None


def _path_forbidden(path: str) -> bool:
    lower = path.replace("\\", "/").lower()
    return any(frag in lower for frag in FORBIDDEN_PATH_FRAGMENTS)


def score_lane_a_candidate(
    meta: dict[str, Any],
    analysis: dict[str, Any],
    rep_ch3: int,
) -> tuple[Any, ...]:
    ch1_19 = _ch1_19_from_metadata(meta)
    ch3 = ch1_19.get("CH3", 0)
    ch3_dist = abs(ch3 - rep_ch3)
    exact = 1 if ch3 == rep_ch3 else 0
    neutral = abs(ch1_19.get("CH5", 90) - 90) + abs(ch1_19.get("CH6", 128) - 128) + abs(ch1_19.get("CH7", 128) - 128)
    usable = 1 if analysis.get("usable_evidence") is True else 0
    not_clipped = 1 if analysis.get("geometry_clipped_low") is False else 0
    not_blank = 1 if analysis.get("expected_blank") is not True else 0
    geom_track = 1 if meta.get("exposure_track") == "geometry_motion" else 0
    return (exact, usable, not_clipped, not_blank, geom_track, -ch3_dist, -neutral)


def _lane_a_selection_reason(
    family: dict[str, Any],
    ch3: int,
    tier: str,
    *,
    exact_available: bool,
    analysis: dict[str, Any],
) -> str:
    rep = int(family["rep_ch3"])
    ch3_min = int(family["ch3_min"])
    ch3_max = int(family["ch3_max"])
    if tier == "exact_family":
        return f"exact CH3={rep} representative in range {ch3_min}-{ch3_max}"
    parts = [f"nearest CH3={ch3} to rep CH3={rep} (distance={abs(ch3 - rep)}) in range {ch3_min}-{ch3_max}"]
    if not exact_available:
        parts.append(f"no usable local capture at exact CH3={rep}")
    if analysis.get("usable_evidence") is False:
        parts.append("exact rep candidates had usable_evidence=false")
    if analysis.get("geometry_clipped_low"):
        parts.append("exact rep candidates had geometry_clipped_low")
    return "; ".join(parts)


def _manifest_rows(manifest_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _capture_folder_rel(row: dict[str, Any]) -> str:
    folder = row.get("folder") or row.get("capture_path") or ""
    return str(folder).strip("/")


def _build_geometry_source(geometry_path: Path, root: Path) -> dict[str, Any]:
    raw = geometry_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    return {
        "path": _rel(geometry_path, root),
        "version": data.get("version", 1),
        "created_at": data.get("created_at"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _stable_v7_generated_at(v7_manifest: dict[str, Any]) -> str:
    generated_at = v7_manifest.get("generated_at")
    if isinstance(generated_at, str) and generated_at:
        return generated_at
    return "1970-01-01T00:00:00Z"


def _selection_entries_for_v7_subset(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(entry)
        for entry in entries
        if entry.get("local_media_exists") is True
        and not entry.get("excluded_reason")
        and entry.get("capture_path")
        and entry.get("vector_key")
    ]


def _load_v7_records(v7_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    records_dir = v7_root / "records"
    manifest_path = v7_root / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.is_file() else {}
    records: dict[str, dict[str, Any]] = {}
    if not records_dir.is_dir():
        return records, manifest
    for path in sorted(records_dir.glob("*.json")):
        record = _load_json(path)
        shape_ref = record.get("shape_ref")
        if isinstance(shape_ref, str) and shape_ref:
            records[shape_ref] = record
    return records, manifest


def _v7_layer_value(record: dict[str, Any], key: str) -> Any:
    if key in record:
        return record.get(key)
    layers = record.get("geometry_layers")
    if isinstance(layers, dict):
        return layers.get(key)
    return None


def _v7_render_polylines(record: dict[str, Any], field: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw_polys = record.get(field)
    if not isinstance(raw_polys, list):
        return out
    for poly in raw_polys:
        if not isinstance(poly, dict) or poly.get("render_role") != "render":
            continue
        points_wall_norm = poly.get("points_wall_norm")
        if not isinstance(points_wall_norm, list) or not points_wall_norm:
            continue
        normalized = dict(poly)
        normalized["points"] = points_wall_norm
        normalized["point_count"] = int(poly.get("point_count") or len(points_wall_norm))
        out.append(normalized)
    return out


def _v7_topology_class(record: dict[str, Any], polylines: list[dict[str, Any]]) -> str:
    topo = record.get("topology_summary") if isinstance(record.get("topology_summary"), dict) else {}
    dots = int(topo.get("dots") or 0)
    closed = int(topo.get("closed_strokes") or 0)
    opened = int(topo.get("open_strokes") or 0)
    if dots and not closed and not opened:
        return "dot_cluster"
    if opened and not closed and not dots and len(polylines) == 1:
        return "line"
    if closed == 1 and not opened and not dots and len(polylines) == 1:
        return "closed_shape"
    return "complex_shape"


def _v7_geometry_kind(polylines: list[dict[str, Any]]) -> str:
    kinds = sorted({str(poly.get("geometry_kind") or "") for poly in polylines if poly.get("geometry_kind")})
    if len(kinds) == 1:
        return kinds[0]
    return "multi_geometry"


def _v7_rejection_reason(
    *,
    expected_shape_ref: str,
    entry: dict[str, Any],
    record: dict[str, Any] | None,
    selected_polylines: list[dict[str, Any]] | None = None,
) -> str | None:
    if record is None:
        return "missing_v7_record"
    if record.get("shape_ref") != expected_shape_ref:
        return "shape_ref_mismatch"
    if record.get("vector_key") != entry.get("vector_key"):
        return "vector_key_mismatch"
    if record.get("capture_path") != entry.get("capture_path"):
        return "capture_path_mismatch"
    if record.get("status") != "authority":
        return f"v7_status_{record.get('status') or 'missing'}"
    if record.get("render_authority") != "vector":
        return f"render_authority_{record.get('render_authority') or 'missing'}"
    if _v7_layer_value(record, "render_vectors") != "derived_validated":
        return f"render_vectors_{_v7_layer_value(record, 'render_vectors') or 'missing'}"
    if _v7_layer_value(record, "render_fallback") not in ("none", None):
        return f"render_fallback_{_v7_layer_value(record, 'render_fallback')}"
    if selected_polylines is not None and not selected_polylines:
        return "empty_selected_render_geometry"
    return None


def _shape_from_v7_record(
    entry: dict[str, Any],
    record: dict[str, Any],
    selected_polylines: list[dict[str, Any]],
    sibling_polylines: list[dict[str, Any]],
) -> dict[str, Any]:
    core_mask = record.get("core_mask") if isinstance(record.get("core_mask"), dict) else {}
    point_count = sum(int(poly.get("point_count") or 0) for poly in selected_polylines)
    geometry_kind = _v7_geometry_kind(selected_polylines)
    shape_ref = str(record["shape_ref"])
    return {
        "shape_ref": shape_ref,
        "vector_key": record.get("vector_key") or entry.get("vector_key") or "",
        "capture_path": record.get("capture_path") or entry.get("capture_path") or "",
        "source_still": record.get("source_still") or entry.get("still_path") or "",
        "test_id": record.get("test_id") or entry.get("family_or_checkpoint") or "",
        "family_or_checkpoint": entry.get("family_or_checkpoint") or record.get("test_id") or "",
        "phase": record.get("phase") or entry.get("phase") or "",
        "exposure_track": record.get("exposure_track") or entry.get("exposure_track") or "",
        "ch1_19": record.get("ch1_19") or entry.get("ch1_19") or {},
        "fixture_box_label": record.get("fixture_box_label") or entry.get("selected_fixture_box") or DEFAULT_FIXTURE_BOX,
        "source_pixel_bbox": core_mask.get("bbox_px") or [0, 0, 0, 0],
        "bbox_wall_norm": core_mask.get("bbox_wall_norm") or [0.0, 0.0, 0.0, 0.0],
        "centroid_wall_norm": core_mask.get("centroid_wall_norm") or [0.0, 0.0],
        "topology_class": _v7_topology_class(record, selected_polylines),
        "shape_point_count": point_count,
        "clusters": record.get("components") or [],
        "polylines": selected_polylines,
        "sibling_polylines": sibling_polylines,
        "aperture_boxes": record.get("aperture_boxes") or {},
        "selected_aperture": record.get("selected_aperture") or record.get("fixture_box_label") or DEFAULT_FIXTURE_BOX,
        "extraction_params": {
            "extraction_policy": V7_POLICY_VERSION,
            "shape_type": geometry_kind,
            "selected_vectorizer": "v7_shape_authority_record",
            "geometry_scores": record.get("metrics") or {},
        },
        "quality_flags": sorted(set(record.get("quality_flags") or [])),
        "fallback_reason": None,
        "extraction_candidates_tried": ["v7_shape_authority_record"],
        "selected_extractor": "v7_shape_authority_record",
        "selected_extractor_reason": "status=authority; render_authority=vector; render_vectors=derived_validated",
        "candidate_scores": {},
        "rejected_candidate_reasons": {},
        "shape_type": geometry_kind,
        "selected_vectorizer": "v7_shape_authority_record",
        "geometry_scores": record.get("metrics") or {},
        "geometry_kind": geometry_kind,
        "ordered": all(bool(poly.get("ordered", True)) for poly in selected_polylines),
        "rejection_reasons": [],
        "visual_status": "pass",
        "usable_as_shape_authority": True,
        "visual_review_reason": "v7 authority record with vector render geometry",
        "v7_status": record.get("status"),
        "render_authority": record.get("render_authority"),
        "render_vectors": _v7_layer_value(record, "render_vectors"),
        "render_fallback": _v7_layer_value(record, "render_fallback"),
        "authority_source_record": f"{V7_AUTHORITY_ROOT_REL}/records/{shape_ref}.json",
    }


def _join_v7_authority_records(
    entries: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    shapes: list[dict[str, Any]] = []
    accounting: list[dict[str, Any]] = []
    counts = {"authority": 0, "provisional": 0, "quarantined": 0, "missing": 0, "conflicts": 0}

    seen_shape_refs: set[str] = set()
    for entry in entries:
        expected_ref = compute_shape_ref(
            ARTIFACT_VERSION,
            str(entry.get("vector_key") or ""),
            str(entry.get("capture_path") or ""),
            str(entry.get("selected_fixture_box") or DEFAULT_FIXTURE_BOX),
        )
        record = records.get(expected_ref)
        selected_polylines = _v7_render_polylines(record, "polylines") if record else []
        sibling_polylines = _v7_render_polylines(record, "sibling_polylines") if record else []
        reason = _v7_rejection_reason(
            expected_shape_ref=expected_ref,
            entry=entry,
            record=record,
            selected_polylines=selected_polylines,
        )
        status = "authority" if reason is None else "missing"
        if record is not None and reason is not None:
            raw_status = record.get("status")
            if raw_status == "provisional":
                status = "provisional"
            elif raw_status == "quarantined":
                status = "quarantined"
            else:
                status = "conflicts"
        if status not in counts:
            status = "conflicts"
        counts[status] += 1

        row = {
            "shape_ref": expected_ref,
            "vector_key": entry.get("vector_key") or "",
            "capture_path": entry.get("capture_path") or "",
            "family_or_checkpoint": entry.get("family_or_checkpoint") or "",
            "v7_status": status,
            "shape_authority": reason is None,
            "reason": None if reason is None else reason,
            "record_path": f"{V7_AUTHORITY_ROOT_REL}/records/{expected_ref}.json" if record else None,
            "selected_render_polyline_count": len(selected_polylines),
            "sibling_render_polyline_count": len(sibling_polylines),
        }
        accounting.append(row)

        if reason is None and record is not None:
            seen_shape_refs.add(expected_ref)
            shapes.append(_shape_from_v7_record(entry, record, selected_polylines, sibling_polylines))

    for shape_ref, record in records.items():
        if shape_ref not in seen_shape_refs and record.get("capture_path"):
            # Records outside the current selected subset are deliberately not
            # promoted by exact vector match alone.
            continue

    return shapes, accounting, counts


def _select_lane_a(
    rows: list[dict[str, Any]],
    capture_root: Path,
    root: Path,
    phase6_paths: set[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    used_paths: set[str] = set()

    for family in CH3_FAMILIES:
        ch3_min = int(family["ch3_min"])
        ch3_max = int(family["ch3_max"])
        rep = int(family["rep_ch3"])
        candidates: list[tuple[tuple[Any, ...], dict[str, Any], Path, Path, dict[str, Any], dict[str, Any]]] = []

        for row in rows:
            folder_rel = _capture_folder_rel(row)
            if not folder_rel or folder_rel.startswith("phase6_cue_validation/"):
                continue
            folder = capture_root / folder_rel
            still = _resolve_still(folder)
            meta_path = folder / "metadata.json"
            analysis_path = folder / "analysis.json"
            if still is None or not meta_path.is_file() or not analysis_path.is_file():
                continue
            meta = _load_json(meta_path)
            analysis = _load_json(analysis_path)
            ch1_19 = _ch1_19_from_metadata(meta)
            ch3 = ch1_19.get("CH3", 0)
            if ch3 < ch3_min or ch3 > ch3_max:
                continue
            candidates.append((score_lane_a_candidate(meta, analysis, rep), row, folder, still, meta, analysis))

        entry: dict[str, Any] | None = None
        if candidates:
            exact_available = any(
                _ch1_19_from_metadata(c[4]).get("CH3") == rep for c in candidates
            )
            candidates.sort(key=lambda c: c[0], reverse=True)
            _, row, folder, still, meta, analysis = candidates[0]
            folder_rel = _capture_folder_rel(row)
            ch1_19 = _ch1_19_from_metadata(meta)
            ch3 = ch1_19.get("CH3", 0)
            tier = "exact_family" if ch3 == rep else "nearest_family"
            entry = {
                "selection_lane": "ch3_family",
                "family_or_checkpoint": family["family_or_checkpoint"],
                "capture_path": folder_rel,
                "still_path": _rel(still, root),
                "metadata_path": _rel(folder / "metadata.json", root),
                "analysis_path": _rel(folder / "analysis.json", root),
                "vector_key": vector_key_from_ch1_19(ch1_19),
                "ch1_19": ch1_19,
                "phase": str(meta.get("phase") or row.get("phase") or ""),
                "exposure_track": str(meta.get("exposure_track") or row.get("exposure_track") or ""),
                "quality_flags": [],
                "selected_fixture_box": DEFAULT_FIXTURE_BOX,
                "selection_reason": _lane_a_selection_reason(
                    family, ch3, tier, exact_available=exact_available, analysis=analysis
                ),
                "selection_tier": tier,
                "local_media_exists": True,
            }
            if analysis.get("geometry_clipped_low"):
                entry["quality_flags"].append("geometry_clipped_low")
            if analysis.get("usable_evidence") is False:
                entry["quality_flags"].append("usable_evidence_false")
            used_paths.add(folder_rel)

        if entry is None:
            # phase6 substitute for GAP families only
            for p6 in sorted(phase6_paths):
                folder = capture_root / p6
                still = _resolve_still(folder)
                meta_path = folder / "metadata.json"
                analysis_path = folder / "analysis.json"
                if still is None or not meta_path.is_file():
                    continue
                meta = _load_json(meta_path)
                ch1_19 = _ch1_19_from_metadata(meta)
                ch3 = ch1_19.get("CH3", 0)
                if ch3 < ch3_min or ch3_max < ch3:
                    continue
                entry = {
                    "selection_lane": "ch3_family",
                    "family_or_checkpoint": family["family_or_checkpoint"],
                    "capture_path": p6,
                    "still_path": _rel(still, root),
                    "metadata_path": _rel(meta_path, root),
                    "analysis_path": _rel(analysis_path, root) if analysis_path.is_file() else "",
                    "vector_key": vector_key_from_ch1_19(ch1_19),
                    "ch1_19": ch1_19,
                    "phase": str(meta.get("phase") or "phase6_cue_validation"),
                    "exposure_track": str(meta.get("exposure_track") or "geometry_motion"),
                    "quality_flags": ["phase6_derived_substitute"],
                    "selected_fixture_box": DEFAULT_FIXTURE_BOX,
                    "selection_reason": "phase6-derived local substitute for missing isolated atlas family",
                    "selection_tier": "fallback_candidate",
                    "local_media_exists": True,
                }
                break

        if entry is None:
            entry = {
                "selection_lane": "ch3_family",
                "family_or_checkpoint": family["family_or_checkpoint"],
                "capture_path": "",
                "still_path": "",
                "metadata_path": "",
                "analysis_path": "",
                "vector_key": "",
                "ch1_19": {},
                "phase": "",
                "exposure_track": "",
                "quality_flags": ["no_local_candidate"],
                "selected_fixture_box": DEFAULT_FIXTURE_BOX,
                "selection_reason": f"no local capture found for CH3 {ch3_min}-{ch3_max}",
                "selection_tier": "fallback_candidate",
                "local_media_exists": False,
                "excluded_reason": "no_ch3_family_representative",
            }
        entries.append(entry)
    return entries


def _select_lane_b(capture_root: Path, root: Path, limit: int | None = None) -> list[dict[str, Any]]:
    cue_root = capture_root / "phase6_cue_validation" / "cue_relevant"
    if not cue_root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    folders = sorted(p for p in cue_root.iterdir() if p.is_dir())
    if limit is not None:
        folders = folders[:limit]
    for folder in folders:
        still = _resolve_still(folder)
        meta_path = folder / "metadata.json"
        analysis_path = folder / "analysis.json"
        rel_folder = _rel(folder, capture_root)
        if still is None or not meta_path.is_file():
            entries.append(
                {
                    "selection_lane": "phase6_cue",
                    "family_or_checkpoint": folder.name,
                    "capture_path": rel_folder,
                    "still_path": "",
                    "metadata_path": _rel(meta_path, root) if meta_path.is_file() else "",
                    "analysis_path": _rel(analysis_path, root) if analysis_path.is_file() else "",
                    "vector_key": "",
                    "ch1_19": {},
                    "phase": "phase6_cue_validation",
                    "exposure_track": "",
                    "quality_flags": [],
                    "selected_fixture_box": DEFAULT_FIXTURE_BOX,
                    "selection_reason": "phase6 cue folder missing still media",
                    "selection_tier": "phase6_cue",
                    "local_media_exists": False,
                    "excluded_reason": "missing_still",
                }
            )
            continue
        meta = _load_json(meta_path)
        ch1_19 = _ch1_19_from_metadata(meta)
        analysis = _load_json(analysis_path) if analysis_path.is_file() else {}
        entry = {
            "selection_lane": "phase6_cue",
            "family_or_checkpoint": folder.name,
            "capture_path": rel_folder,
            "still_path": _rel(still, root),
            "metadata_path": _rel(meta_path, root),
            "analysis_path": _rel(analysis_path, root) if analysis_path.is_file() else "",
            "vector_key": vector_key_from_ch1_19(ch1_19),
            "ch1_19": ch1_19,
            "phase": str(meta.get("phase") or "phase6_cue_validation"),
            "exposure_track": str(meta.get("exposure_track") or "geometry_motion"),
            "quality_flags": [],
            "selected_fixture_box": DEFAULT_FIXTURE_BOX,
            "selection_reason": "phase6 cue_relevant local capture (CH1-19 authority)",
            "selection_tier": "phase6_cue",
            "local_media_exists": True,
        }
        if analysis.get("geometry_clipped_low"):
            entry["quality_flags"].append("geometry_clipped_low")
        entries.append(entry)
    return entries


def _extract_shapes(
    entries: list[dict[str, Any]],
    capture_root: Path,
    root: Path,
    boxes: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    shapes: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    updated_entries = []

    for entry in entries:
        entry = dict(entry)
        if not entry.get("local_media_exists") or not entry.get("still_path"):
            updated_entries.append(entry)
            continue
        if _path_forbidden(entry["still_path"]) or _path_forbidden(entry.get("capture_path", "")):
            entry["excluded_reason"] = "forbidden_historical_path"
            updated_entries.append(entry)
            continue

        still_path = root / entry["still_path"]
        box_label = entry.get("selected_fixture_box") or DEFAULT_FIXTURE_BOX
        box = boxes.get(box_label)
        if box is None:
            entry["excluded_reason"] = "fixture_box_missing"
            updated_entries.append(entry)
            continue

        image = Image.open(still_path)
        other_boxes = {k: v for k, v in boxes.items() if k != box_label}
        extraction = extract_shape_from_image(image, box, other_boxes=other_boxes)
        if extraction["shape_point_count"] <= 0:
            entry["excluded_reason"] = extraction["quality_flags"][0] if extraction["quality_flags"] else "extraction_empty"
            entry["fallback_reason"] = entry["excluded_reason"]
            updated_entries.append(entry)
            continue
        if not extraction.get("polylines"):
            entry["excluded_reason"] = "no_extracted_polylines"
            entry["fallback_reason"] = "no_extracted_polylines"
            updated_entries.append(entry)
            continue

        capture_path = entry["capture_path"]
        vector_key = entry["vector_key"]
        shape_ref = compute_shape_ref(ARTIFACT_VERSION, vector_key, capture_path, box_label)
        meta_path = root / entry["metadata_path"]
        meta = _load_json(meta_path) if meta_path.is_file() else {}
        shape = {
            "shape_ref": shape_ref,
            "vector_key": vector_key,
            "capture_path": capture_path,
            "source_still": entry["still_path"],
            "test_id": meta.get("test_id") or entry.get("family_or_checkpoint"),
            "family_or_checkpoint": entry.get("family_or_checkpoint") or "",
            "phase": entry.get("phase") or "",
            "exposure_track": entry.get("exposure_track") or "",
            "ch1_19": entry.get("ch1_19") or {},
            "fixture_box_label": box_label,
            "source_pixel_bbox": extraction["source_pixel_bbox"],
            "bbox_wall_norm": extraction["bbox_wall_norm"],
            "centroid_wall_norm": extraction["centroid_wall_norm"],
            "topology_class": extraction["topology_class"],
            "shape_point_count": extraction["shape_point_count"],
            "clusters": extraction["clusters"],
            "polylines": extraction["polylines"],
            "extraction_params": extraction["extraction_params"],
            "quality_flags": list(set((entry.get("quality_flags") or []) + extraction["quality_flags"])),
            "fallback_reason": None,
            "extraction_candidates_tried": extraction.get("extraction_candidates_tried") or [],
            "selected_extractor": extraction.get("selected_extractor"),
            "selected_extractor_reason": extraction.get("selected_extractor_reason"),
            "candidate_scores": extraction.get("candidate_scores") or {},
            "rejected_candidate_reasons": extraction.get("rejected_candidate_reasons") or {},
            "shape_type": extraction.get("shape_type") or extraction.get("extraction_params", {}).get("shape_type"),
            "selected_vectorizer": extraction.get("selected_vectorizer")
            or extraction.get("extraction_params", {}).get("selected_vectorizer")
            or extraction.get("selected_extractor"),
            "geometry_scores": extraction.get("geometry_scores")
            or extraction.get("extraction_params", {}).get("geometry_scores")
            or {},
            "geometry_kind": extraction.get("geometry_kind"),
            "ordered": extraction.get("ordered", True),
            "rejection_reasons": extraction.get("rejection_reasons") or [],
        }
        visual_status, usable, review_reason = classify_visual_status(shape)
        shape["visual_status"] = visual_status
        shape["usable_as_shape_authority"] = usable
        shape["visual_review_reason"] = review_reason
        shapes.append(shape)
        updated_entries.append(entry)

        overlay = render_overlay_image(image, extraction, box)
        sheet = make_contact_sheet(image, overlay)
        overlays.append(
            {
                "shape_ref": shape_ref,
                "lane": entry["selection_lane"],
                "family_or_checkpoint": entry["family_or_checkpoint"],
                "sheet": sheet,
                "still_path": entry["still_path"],
            }
        )
    return shapes, updated_entries, overlays


def merge_shape_refs_into_index(index_path: Path, shapes: list[dict[str, Any]]) -> dict[str, int]:
    with index_path.open("r", encoding="utf-8") as fh:
        index = json.load(fh)
    captures = index.get("captures") or []
    folder_by_id = {
        int(c.get("capture_id", i)): (c.get("folder") or c.get("capture_path") or "")
        for i, c in enumerate(captures)
    }
    shape_by_folder = {s["capture_path"]: s for s in shapes}
    shape_by_vector: dict[str, list[dict[str, Any]]] = {}
    for s in shapes:
        shape_by_vector.setdefault(s["vector_key"], []).append(s)

    merged = 0
    for vector_key, bucket in (index.get("vector_index") or {}).items():
        pref_id = int(bucket.get("preferred_capture_id", -1))
        folder = folder_by_id.get(pref_id, "")
        shape = shape_by_folder.get(folder)
        if shape is None:
            for cand in shape_by_vector.get(vector_key, []):
                shape = cand
                break
        if shape and shape.get("shape_point_count", 0) > 0:
            bucket["shape_ref"] = shape["shape_ref"]
            bucket["shape_point_count"] = shape["shape_point_count"]
            bucket["topology_class"] = shape["topology_class"]
            bucket["shape_evidence"] = "still"
            bucket["shape_fallback_reason"] = None
            bucket["shape_quality_flags"] = shape.get("quality_flags") or []
            bucket["shape_source_capture_path"] = shape["capture_path"]
            bucket["shape_authority"] = bool(shape.get("usable_as_shape_authority"))
            bucket["shape_selected_extractor"] = shape.get("selected_extractor")
            bucket["shape_visual_status"] = shape.get("visual_status")
            merged += 1
        else:
            bucket["shape_authority"] = False
            bucket.setdefault("shape_fallback_reason", "no_static_shape_for_vector")
    with index_path.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
        fh.write("\n")
    return {"vectors_with_shape_ref": merged}


def merge_v7_shape_refs_into_index(
    index_path: Path,
    shapes: list[dict[str, Any]],
    accounting: list[dict[str, Any]],
) -> dict[str, int]:
    with index_path.open("r", encoding="utf-8") as fh:
        index = json.load(fh)

    shape_by_ref = {shape["shape_ref"]: shape for shape in shapes}
    selected_vectors = 0
    authority_vectors = 0
    rejected_vectors = 0

    for row in accounting:
        vector_key = row.get("vector_key")
        if not vector_key:
            continue
        bucket = (index.get("vector_index") or {}).get(vector_key)
        if not isinstance(bucket, dict):
            continue
        selected_vectors += 1
        shape = shape_by_ref.get(row.get("shape_ref"))
        if shape is not None:
            bucket["shape_ref"] = shape["shape_ref"]
            bucket["shape_point_count"] = shape["shape_point_count"]
            bucket["topology_class"] = shape["topology_class"]
            bucket["shape_evidence"] = "v7_shape_authority_record"
            bucket["shape_fallback_reason"] = None
            bucket["shape_quality_flags"] = shape.get("quality_flags") or []
            bucket["shape_source_capture_path"] = shape["capture_path"]
            bucket["shape_authority"] = True
            bucket["shape_status"] = "authority"
            bucket["shape_selected_extractor"] = "v7_shape_authority_record"
            bucket["shape_visual_status"] = "pass"
            bucket["shape_record_path"] = row.get("record_path")
            bucket["shape_sibling_render_polyline_count"] = row.get("sibling_render_polyline_count", 0)
            authority_vectors += 1
        else:
            bucket["shape_ref"] = None
            bucket["shape_point_count"] = 0
            bucket["topology_class"] = None
            bucket["shape_evidence"] = None
            bucket["shape_authority"] = False
            bucket["shape_status"] = row.get("v7_status") or "missing"
            bucket["shape_fallback_reason"] = row.get("reason") or "missing_v7_record"
            bucket["shape_quality_flags"] = []
            bucket["shape_source_capture_path"] = row.get("capture_path") or None
            bucket["shape_selected_extractor"] = "v7_shape_authority_record"
            bucket["shape_visual_status"] = None
            bucket["shape_record_path"] = row.get("record_path")
            bucket["shape_sibling_render_polyline_count"] = row.get("sibling_render_polyline_count", 0)
            rejected_vectors += 1

    with index_path.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
        fh.write("\n")

    return {
        "selected_vectors": selected_vectors,
        "authority_vectors": authority_vectors,
        "rejected_vectors": rejected_vectors,
    }


def _visual_review_status(shape: dict[str, Any]) -> tuple[str, str, bool]:
    if shape.get("visual_status"):
        return (
            shape["visual_status"],
            shape.get("visual_review_reason") or "",
            bool(shape.get("usable_as_shape_authority")),
        )
    return classify_visual_status(shape)


def _write_visual_review_summary(
    root: Path,
    shapes: list[dict[str, Any]],
    overlay_index: list[dict[str, Any]],
    out_path: Path,
) -> None:
    by_ref = {e["shape_ref"]: e for e in overlay_index}
    lines = [
        "# PR-G1 Visual Review Summary",
        "",
        "**Brandon instruction:** Pass only if the yellow overlay roughly follows the actual bright laser drawing, not just the glow around it.",
        "",
        "v6 uses typed stroke-vectorization with hysteresis support, skeleton graph tracing, and pixel-to-geometry fit scoring.",
        "",
        "| shape_ref | lane | family/checkpoint | source path | shape_type | selected_vectorizer | visual_status | usable_as_shape_authority | reason | quality_flags | rejected_candidate_reasons | contact_sheet |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for shape in shapes:
        ref = shape["shape_ref"]
        entry = by_ref.get(ref, {})
        status, reason, usable = _visual_review_status(shape)
        sheet = entry.get("contact_sheet_path", "")
        family = shape.get("family_or_checkpoint") or entry.get("family_or_checkpoint") or ""
        source = shape.get("capture_path") or entry.get("still_path") or ""
        lane = entry.get("lane") or ""
        qflags = ", ".join(shape.get("quality_flags") or [])
        rejected = shape.get("rejected_candidate_reasons") or {}
        if isinstance(rejected, dict):
            rej_txt = "; ".join(
                f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in rejected.items() if v
            )
        else:
            rej_txt = str(rejected)
        lines.append(
            f"| `{ref}` | {lane} | {family} | `{source}` | {shape.get('shape_type', '')} | {shape.get('selected_vectorizer', shape.get('selected_extractor', ''))} | {status} | {str(usable).lower()} | {reason} | {qflags} | {rej_txt} | `{sheet}` |"
        )
    lines.extend(["", "## Status counts", ""])
    counts: dict[str, int] = {}
    usable_count = 0
    for shape in shapes:
        st, _, usable = _visual_review_status(shape)
        counts[st] = counts.get(st, 0) + 1
        if usable:
            usable_count += 1
    for key in ("pass", "weak", "fail"):
        lines.append(f"- {key}: {counts.get(key, 0)}")
    lines.append(f"- usable_as_shape_authority: {usable_count}")
    lines.append("")
    sel_counts: dict[str, int] = {}
    for shape in shapes:
        ext = shape.get("selected_extractor") or "unknown"
        sel_counts[ext] = sel_counts.get(ext, 0) + 1
    lines.extend(["## Selected vectorizer counts", ""])
    for name, count in sorted(sel_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {name}: {count}")
    type_counts: dict[str, int] = {}
    for shape in shapes:
        st = shape.get("shape_type") or "unknown"
        type_counts[st] = type_counts.get(st, 0) + 1
    lines.extend(["", "## Shape type counts", ""])
    for name, count in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {name}: {count}")
    lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_pr_g1_artifacts(
    root: Path | None = None,
    *,
    phase6_limit: int | None = None,
    merge_index: bool = True,
    extractor: str = "v6",
) -> dict[str, Any]:
    root = root or ROOT
    capture_root = root / CAPTURE_ROOT_REL
    manifest_path = capture_root / "manifest.jsonl"
    geometry_path = capture_root / "analysis_geometry.json"
    out_dir = root / "artifacts" / "renderer" / "pr-g1-shape-authority"
    library_path = root / "artifacts" / "renderer" / "shape_library_v1.json"
    schema_path = root / "artifacts" / "renderer" / "shape_library_v1.schema.json"
    index_path = root / "artifacts" / "renderer" / "renderer-capture-index-pr1" / "capture_index_v1.json"

    if extractor == "v7":
        return build_pr_g1_v7_artifacts(root, merge_index=merge_index)
    if extractor != "v6":
        raise ValueError(f"unsupported extractor: {extractor}")

    if not capture_root.is_dir():
        raise FileNotFoundError("PR-G1 requires local capture root captures/fixture_model/")
    if not manifest_path.is_file():
        raise FileNotFoundError("PR-G1 requires captures/fixture_model/manifest.jsonl")
    if not geometry_path.is_file():
        raise FileNotFoundError("PR-G1 requires captures/fixture_model/analysis_geometry.json")

    geometry = _load_json(geometry_path)
    boxes = load_fixture_boxes(geometry)
    if DEFAULT_FIXTURE_BOX not in boxes:
        raise ValueError(f"analysis_geometry missing {DEFAULT_FIXTURE_BOX}")

    # quick media probe
    still_count = sum(1 for _ in capture_root.rglob("still.jpg"))
    still_color_count = sum(1 for _ in capture_root.rglob("still_color.jpg"))
    if still_count + still_color_count == 0:
        raise FileNotFoundError("PR-G1 local media missing: no still.jpg/still_color.jpg under capture root")

    rows = _manifest_rows(manifest_path)
    phase6_root = capture_root / "phase6_cue_validation" / "cue_relevant"
    phase6_paths = {
        _rel(p, capture_root)
        for p in phase6_root.iterdir()
        if p.is_dir()
    } if phase6_root.is_dir() else set()

    lane_a = _select_lane_a(rows, capture_root, root, phase6_paths)
    lane_b = _select_lane_b(capture_root, root, limit=phase6_limit)
    entries = lane_a + lane_b

    shapes, entries, overlays = _extract_shapes(entries, capture_root, root, boxes)

    selection_doc = {
        "artifact_version": "pr-g1-shape-selection-v1",
        "generated_at": _iso_now(),
        "capture_root": CAPTURE_ROOT_REL,
        "plan_revision": PLAN_REVISION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "entries": entries,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    selection_path = out_dir / "shape_selection.json"
    selection_path.write_text(json.dumps(selection_doc, indent=2) + "\n", encoding="utf-8")

    library_doc = {
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": _iso_now(),
        "capture_root": CAPTURE_ROOT_REL,
        "coordinate_space": COORDINATE_SPACE,
        "geometry_source": _build_geometry_source(geometry_path, root),
        "selection_artifact": _rel(selection_path, root),
        "extraction_policy_version": EXTRACTION_POLICY_VERSION,
        "shapes": shapes,
    }
    library_path.parent.mkdir(parents=True, exist_ok=True)
    library_path.write_text(json.dumps(library_doc, indent=2) + "\n", encoding="utf-8")

    schema_path.write_text(_default_schema(), encoding="utf-8")

    contact_dir = out_dir / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)
    overlay_index: list[dict[str, Any]] = []
    for item in overlays:
        fname = f"{item['shape_ref']}.png"
        fpath = contact_dir / fname
        item["sheet"].save(fpath)
        overlay_index.append(
            {
                "shape_ref": item["shape_ref"],
                "lane": item["lane"],
                "family_or_checkpoint": item["family_or_checkpoint"],
                "still_path": item["still_path"],
                "contact_sheet_path": _rel(fpath, root),
                "brandon_verdict": "pending",
            }
        )
    overlay_path = out_dir / "overlay_review_index.json"
    overlay_path.write_text(json.dumps({"entries": overlay_index}, indent=2) + "\n", encoding="utf-8")

    visual_summary_path = out_dir / "visual_review_summary.md"
    _write_visual_review_summary(root, shapes, overlay_index, visual_summary_path)

    merge_stats = {}
    if merge_index and index_path.is_file():
        merge_stats = merge_shape_refs_into_index(index_path, shapes)

    return {
        "selection_path": str(selection_path),
        "library_path": str(library_path),
        "schema_path": str(schema_path),
        "overlay_index_path": str(overlay_path),
        "visual_summary_path": str(visual_summary_path),
        "lane_a_count": len(lane_a),
        "lane_b_count": len(lane_b),
        "shape_count": len(shapes),
        "skipped_count": sum(1 for e in entries if e.get("excluded_reason")),
        "still_count": still_count,
        "still_color_count": still_color_count,
        "merge_stats": merge_stats,
    }


def build_pr_g1_v7_artifacts(
    root: Path | None = None,
    *,
    merge_index: bool = True,
) -> dict[str, Any]:
    root = root or ROOT
    capture_root = root / CAPTURE_ROOT_REL
    geometry_path = capture_root / "analysis_geometry.json"
    out_dir = root / "artifacts" / "renderer" / "pr-g1-shape-authority"
    selection_path = out_dir / "shape_selection.json"
    library_path = root / "artifacts" / "renderer" / "shape_library_v1.json"
    schema_path = root / "artifacts" / "renderer" / "shape_library_v1.schema.json"
    index_path = root / "artifacts" / "renderer" / "renderer-capture-index-pr1" / "capture_index_v1.json"
    v7_root = root / V7_AUTHORITY_ROOT_REL

    if not selection_path.is_file():
        raise FileNotFoundError("PR-G1 v7 requires existing shape_selection.json")
    if not geometry_path.is_file():
        raise FileNotFoundError("PR-G1 v7 requires captures/fixture_model/analysis_geometry.json")

    selection_doc = _load_json(selection_path)
    source_entries = selection_doc.get("entries")
    if not isinstance(source_entries, list):
        raise ValueError("shape_selection.json entries must be a list")

    entries = _selection_entries_for_v7_subset(source_entries)
    records, v7_manifest = _load_v7_records(v7_root)
    shapes, accounting, counts = _join_v7_authority_records(entries, records)
    generated_at = _stable_v7_generated_at(v7_manifest)

    accounting_by_ref = {row["shape_ref"]: row for row in accounting}
    updated_entries: list[dict[str, Any]] = []
    selected_refs = set(accounting_by_ref)
    for entry in source_entries:
        updated = dict(entry)
        if entry.get("vector_key") and entry.get("capture_path"):
            expected_ref = compute_shape_ref(
                ARTIFACT_VERSION,
                str(entry.get("vector_key") or ""),
                str(entry.get("capture_path") or ""),
                str(entry.get("selected_fixture_box") or DEFAULT_FIXTURE_BOX),
            )
            row = accounting_by_ref.get(expected_ref)
            if row:
                updated["v7_shape_ref"] = expected_ref
                updated["v7_authority_status"] = row["v7_status"]
                updated["v7_shape_authority"] = row["shape_authority"]
                updated["v7_fallback_reason"] = row["reason"]
                updated["v7_record_path"] = row["record_path"]
                updated["v7_selected_render_polyline_count"] = row["selected_render_polyline_count"]
                updated["v7_sibling_render_polyline_count"] = row["sibling_render_polyline_count"]
            elif expected_ref not in selected_refs:
                updated.setdefault("v7_shape_authority", False)
        updated_entries.append(updated)

    v7_selection_doc = dict(selection_doc)
    v7_selection_doc["generated_at"] = generated_at
    v7_selection_doc["extractor"] = "v7"
    v7_selection_doc["v7_authority_root"] = V7_AUTHORITY_ROOT_REL
    v7_selection_doc["v7_subset_count"] = len(entries)
    v7_selection_doc["v7_authority_accounting"] = accounting
    v7_selection_doc["v7_authority_counts"] = counts
    v7_selection_doc["entries"] = updated_entries

    out_dir.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps(v7_selection_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    library_doc = {
        "artifact_version": ARTIFACT_VERSION,
        "generated_at": generated_at,
        "capture_root": CAPTURE_ROOT_REL,
        "coordinate_space": COORDINATE_SPACE,
        "geometry_source": _build_geometry_source(geometry_path, root),
        "selection_artifact": _rel(selection_path, root),
        "extraction_policy_version": V7_POLICY_VERSION,
        "extractor": "v7",
        "v7_authority_root": V7_AUTHORITY_ROOT_REL,
        "v7_authority_manifest": _rel(v7_root / "manifest.json", root),
        "v7_authority_accounting": accounting,
        "v7_authority_counts": counts,
        "shapes": shapes,
    }
    library_path.parent.mkdir(parents=True, exist_ok=True)
    library_path.write_text(json.dumps(library_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema_path.write_text(_default_schema(), encoding="utf-8")

    overlay_entries = []
    for shape in shapes:
        sheet_path = v7_root / "contact_sheets" / f"{shape['shape_ref']}.png"
        overlay_entries.append(
            {
                "shape_ref": shape["shape_ref"],
                "lane": "v7_authority_record",
                "family_or_checkpoint": shape.get("family_or_checkpoint") or "",
                "still_path": shape.get("source_still") or "",
                "contact_sheet_path": _rel(sheet_path, root) if sheet_path.is_file() else "",
                "brandon_verdict": "pending",
            }
        )
    overlay_path = out_dir / "overlay_review_index.json"
    overlay_path.write_text(json.dumps({"entries": overlay_entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    visual_summary_path = out_dir / "visual_review_summary.md"
    _write_visual_review_summary(root, shapes, overlay_entries, visual_summary_path)

    merge_stats = {}
    if merge_index and index_path.is_file():
        merge_stats = merge_v7_shape_refs_into_index(index_path, shapes, accounting)

    return {
        "selection_path": str(selection_path),
        "library_path": str(library_path),
        "schema_path": str(schema_path),
        "overlay_index_path": str(overlay_path),
        "visual_summary_path": str(visual_summary_path),
        "extractor": "v7",
        "v7_record_count": len(records),
        "v7_subset_count": len(entries),
        "shape_count": len(shapes),
        "authority_counts": counts,
        "merge_stats": merge_stats,
    }


def _default_schema() -> str:
    shape_required = [
        "shape_ref",
        "vector_key",
        "capture_path",
        "source_still",
        "test_id",
        "phase",
        "exposure_track",
        "ch1_19",
        "fixture_box_label",
        "source_pixel_bbox",
        "bbox_wall_norm",
        "centroid_wall_norm",
        "topology_class",
        "shape_point_count",
        "clusters",
        "polylines",
        "extraction_params",
        "quality_flags",
        "fallback_reason",
        "extraction_candidates_tried",
        "selected_extractor",
        "selected_extractor_reason",
        "candidate_scores",
        "rejected_candidate_reasons",
        "visual_status",
        "usable_as_shape_authority",
        "visual_review_reason",
        "geometry_kind",
        "ordered",
        "rejection_reasons",
    ]
    return json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "shape_library_v1",
            "type": "object",
            "required": [
                "artifact_version",
                "generated_at",
                "capture_root",
                "coordinate_space",
                "geometry_source",
                "selection_artifact",
                "extraction_policy_version",
                "shapes",
            ],
            "properties": {
                "artifact_version": {"type": "string"},
                "generated_at": {"type": "string"},
                "capture_root": {"type": "string"},
                "coordinate_space": {"const": COORDINATE_SPACE},
                "geometry_source": {
                    "type": "object",
                    "required": ["path", "version", "sha256"],
                    "properties": {
                        "path": {"type": "string"},
                        "version": {},
                        "created_at": {"type": ["string", "null"]},
                        "sha256": {"type": "string"},
                    },
                },
                "selection_artifact": {"type": "string"},
                "extraction_policy_version": {"type": "string"},
                "shapes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": shape_required,
                        "properties": {
                            "shape_ref": {"type": "string"},
                            "vector_key": {"type": "string"},
                            "capture_path": {"type": "string"},
                            "source_still": {"type": "string"},
                            "test_id": {"type": "string"},
                            "phase": {"type": "string"},
                            "exposure_track": {"type": "string"},
                            "ch1_19": {"type": "object"},
                            "fixture_box_label": {"type": "string"},
                            "source_pixel_bbox": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 4,
                                "maxItems": 4,
                            },
                            "bbox_wall_norm": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 4,
                                "maxItems": 4,
                            },
                            "centroid_wall_norm": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "topology_class": {"type": "string"},
                            "shape_point_count": {"type": "integer", "minimum": 1},
                            "clusters": {"type": "array"},
                            "polylines": {
                                "type": "array",
                                "minItems": 1,
                            },
                            "extraction_params": {"type": "object"},
                            "quality_flags": {"type": "array", "items": {"type": "string"}},
                            "fallback_reason": {"type": ["string", "null"]},
                            "extraction_candidates_tried": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "selected_extractor": {"type": "string"},
                            "selected_extractor_reason": {"type": "string"},
                            "candidate_scores": {"type": "object"},
                            "rejected_candidate_reasons": {"type": "object"},
                            "visual_status": {"type": "string", "enum": ["pass", "weak", "fail"]},
                            "usable_as_shape_authority": {"type": "boolean"},
                            "visual_review_reason": {"type": "string"},
                            "geometry_kind": {"type": "string"},
                            "ordered": {"type": "boolean"},
                            "rejection_reasons": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        indent=2,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PR-G1 shape library from local corpus stills")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--phase6-limit", type=int, default=None, help="Limit phase6 cue selections (subset smoke)")
    parser.add_argument("--no-merge-index", action="store_true")
    parser.add_argument("--extractor", choices=("v6", "v7"), default="v6")
    args = parser.parse_args()
    try:
        stats = build_pr_g1_artifacts(
            args.root,
            phase6_limit=args.phase6_limit,
            merge_index=not args.no_merge_index,
            extractor=args.extractor,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
