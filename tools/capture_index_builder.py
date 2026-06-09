#!/usr/bin/env python3
"""Build compact capture-backed index for renderer PR1.

PR1 scope:
- Build-time join of manifest + per-capture analysis + analysis geometry.
- No renderer/webserver runtime changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROVENANCE_LABELS = [
    "EXACT_CAPTURE",
    "CAPTURE_INDEX_INTERPOLATED",
    "MEASURED_FIXTURE_MODEL",
    "MEASURED_MOTION_ANALYSIS",
    "FALLBACK_MOTIONSTATE",
    "MANUAL_DECODER",
]

CH1_19_KEYS = [f"CH{i}" for i in range(1, 20)]


class ManifestJsonlError(ValueError):
    """Raised when manifest JSONL has invalid rows."""


class AnalysisGeometryError(ValueError):
    """Raised when analysis_geometry.json is missing required conversion fields."""


@dataclass(frozen=True)
class GeometryConversion:
    px_per_inch: float
    roi_x0: int
    roi_y0: int
    roi_x1: int
    roi_y1: int

    @property
    def roi_width(self) -> int:
        return max(1, self.roi_x1 - self.roi_x0)

    @property
    def roi_height(self) -> int:
        return max(1, self.roi_y1 - self.roi_y0)


def _safe_int(value: Any) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError):
        iv = 0
    return max(0, min(255, iv))


def normalize_ch1_19_vector(ch1_19: dict[str, Any]) -> dict[str, int]:
    """Normalize CH1-19 map to deterministic bounded ints."""
    return {key: _safe_int(ch1_19.get(key, 0)) for key in CH1_19_KEYS}


def vector_key_from_vector(ch1_19: dict[str, Any]) -> str:
    """Deterministic normalized CH1-19 vector key."""
    vec = normalize_ch1_19_vector(ch1_19)
    return "v1:" + ",".join(str(vec[k]) for k in CH1_19_KEYS)


def parse_manifest_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ManifestJsonlError(
                    f"Invalid JSONL at {path} line {line_no}: {exc.msg}"
                ) from exc
            row["__line_number"] = line_no
            rows.append(row)
    return rows


def _parse_timestamp(ts: str | None) -> float:
    if not ts:
        return float("-inf")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return float("-inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def dedup_latest_test_id(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep latest row per test_id by timestamp, then by manifest line number."""
    best: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for row in rows:
        test_id = row.get("test_id")
        if not test_id:
            continue
        counts[test_id] = counts.get(test_id, 0) + 1
        prev = best.get(test_id)
        if prev is None:
            best[test_id] = row
            continue
        prev_key = (_parse_timestamp(prev.get("timestamp")), int(prev.get("__line_number", 0)))
        cur_key = (_parse_timestamp(row.get("timestamp")), int(row.get("__line_number", 0)))
        if cur_key >= prev_key:
            best[test_id] = row
    deduped = sorted(best.values(), key=lambda r: (r.get("test_id", ""), int(r.get("__line_number", 0))))
    dup_counts = {k: v for k, v in counts.items() if v > 1}
    return deduped, dup_counts


def load_analysis_geometry(path: Path) -> GeometryConversion:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    analysis_roi = data.get("analysis_roi")
    if not (isinstance(analysis_roi, list) and len(analysis_roi) == 4):
        raise AnalysisGeometryError(
            f"{path} missing required analysis_roi [x0,y0,x1,y1]"
        )
    scale = data.get("scale")
    if not isinstance(scale, dict) or "px_per_inch" not in scale:
        raise AnalysisGeometryError(f"{path} missing required scale.px_per_inch")
    try:
        px_per_inch = float(scale["px_per_inch"])
    except (TypeError, ValueError) as exc:
        raise AnalysisGeometryError(f"{path} has invalid scale.px_per_inch") from exc
    if px_per_inch <= 0:
        raise AnalysisGeometryError(f"{path} has non-positive scale.px_per_inch")
    return GeometryConversion(
        px_per_inch=px_per_inch,
        roi_x0=int(analysis_roi[0]),
        roi_y0=int(analysis_roi[1]),
        roi_x1=int(analysis_roi[2]),
        roi_y1=int(analysis_roi[3]),
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_round(value: float | None, places: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, places)


def _rank_capture(record: dict[str, Any]) -> tuple[Any, ...]:
    quality = record.get("quality", {})
    metrics = record.get("metrics", {})
    return (
        1 if quality.get("usable_evidence") is True else 0,
        1 if quality.get("geometry_clipped_low") is False else 0,
        1 if quality.get("recapture_pending_manifest") is False else 0,
        1 if record.get("exposure_track") == "geometry_motion" else 0,
        metrics.get("loop_confidence") if metrics.get("loop_confidence") is not None else -1.0,
        record.get("timestamp") or "",
        record.get("test_id") or "",
    )


def _record_from_joined_row(
    row: dict[str, Any],
    analysis: dict[str, Any],
    conv: GeometryConversion,
    capture_id: int,
) -> dict[str, Any]:
    vec = normalize_ch1_19_vector(row.get("ch1_19") or {})
    manifest_analysis = row.get("analysis") or {}

    x_range_px = _to_float(analysis.get("x_range"))
    y_range_px = _to_float(analysis.get("y_range"))
    x_range_in = None if x_range_px is None else x_range_px / conv.px_per_inch
    y_range_in = None if y_range_px is None else y_range_px / conv.px_per_inch
    x_norm = None if x_range_px is None else x_range_px / conv.roi_width
    y_norm = None if y_range_px is None else y_range_px / conv.roi_height

    return {
        "capture_id": capture_id,
        "test_id": row.get("test_id"),
        "vector_key": vector_key_from_vector(vec),
        "ch1_19": vec,
        "phase": row.get("phase"),
        "folder": row.get("folder"),
        "capture_path": row.get("capture_path"),
        "baseline": row.get("baseline"),
        "intent": row.get("intent"),
        "timestamp": row.get("timestamp"),
        "changed_channels": row.get("changed_channels") or {},
        "ch3_bank": row.get("ch3_bank"),
        "ch4_program": row.get("ch4_program"),
        "exposure_track": row.get("exposure_track"),
        "provenance_label": "EXACT_CAPTURE",
        "analysis_authority": "per_capture_analysis_json",
        "quality": {
            "usable_evidence": analysis.get("usable_evidence"),
            "geometry_clipped_low": analysis.get("geometry_clipped_low"),
            "analysis_valid": analysis.get("valid"),
            "recapture_pending_manifest": manifest_analysis.get("recapture_pending"),
            "expected_blank_manifest": manifest_analysis.get("expected_blank"),
            "blank_zone_observed_manifest": manifest_analysis.get("blank_zone_observed"),
        },
        "quality_field_sources": {
            "usable_evidence": "per_capture_analysis_json",
            "geometry_clipped_low": "per_capture_analysis_json",
            "analysis_valid": "per_capture_analysis_json",
            "recapture_pending_manifest": "manifest_inline_analysis",
            "expected_blank_manifest": "manifest_inline_analysis",
            "blank_zone_observed_manifest": "manifest_inline_analysis",
        },
        "metrics": {
            "motion_type": analysis.get("motion_type"),
            "motion_direction": analysis.get("motion_direction"),
            "motion_direction_confidence": analysis.get("motion_direction_confidence"),
            "motion_direction_source": analysis.get("motion_direction_source"),
            "motion_signed_slope_per_second": analysis.get("motion_signed_slope_per_second"),
            "loop_duration_estimate": _to_float(analysis.get("loop_duration_estimate")),
            "loop_confidence": _to_float(analysis.get("loop_confidence")),
            "full_loop_captured": analysis.get("full_loop_captured"),
            "periodic_motion": analysis.get("periodic_motion"),
            "strobe_frequency_hz": _to_float(analysis.get("strobe_frequency_hz")),
            "duty_cycle": _to_float(analysis.get("duty_cycle")),
            "x_range_px": _safe_round(x_range_px),
            "y_range_px": _safe_round(y_range_px),
            "x_range_in": _safe_round(x_range_in),
            "y_range_in": _safe_round(y_range_in),
            "x_range_norm_roi": _safe_round(x_norm),
            "y_range_norm_roi": _safe_round(y_norm),
            "area_range_frac": _to_float(analysis.get("area_range_frac")),
            "angle_range_deg": _to_float(analysis.get("angle_range_deg")),
            "dominant_colors": analysis.get("dominant_colors") or [],
        },
    }


def build_capture_index(
    manifest_path: Path,
    capture_root: Path,
    analysis_geometry_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_rows = parse_manifest_jsonl(manifest_path)
    deduped_rows, dup_test_ids = dedup_latest_test_id(raw_rows)
    conv = load_analysis_geometry(analysis_geometry_path)

    captures: list[dict[str, Any]] = []
    vector_buckets: dict[str, list[dict[str, Any]]] = {}

    phase_counts_deduped: dict[str, int] = {}
    phase_counts_indexed: dict[str, int] = {}
    excluded_reasons: dict[str, int] = {}
    missing_analysis_rows: list[str] = []
    broken_analysis_rows: list[str] = []

    quality_gate_counts = {
        "usable_evidence_true": 0,
        "usable_evidence_false": 0,
        "geometry_clipped_low_true": 0,
        "geometry_clipped_low_false": 0,
        "recapture_pending_true": 0,
        "recapture_pending_false": 0,
        "recapture_pending_null": 0,
    }

    for row in deduped_rows:
        phase = str(row.get("phase", "unknown"))
        phase_counts_deduped[phase] = phase_counts_deduped.get(phase, 0) + 1

        folder = row.get("folder")
        if not folder:
            excluded_reasons["missing_folder"] = excluded_reasons.get("missing_folder", 0) + 1
            continue
        analysis_path = capture_root / folder / "analysis.json"
        if not analysis_path.exists():
            missing_analysis_rows.append(str(folder))
            excluded_reasons["missing_analysis_json"] = excluded_reasons.get("missing_analysis_json", 0) + 1
            continue

        try:
            with analysis_path.open("r", encoding="utf-8") as fh:
                analysis = json.load(fh)
        except json.JSONDecodeError:
            broken_analysis_rows.append(str(folder))
            excluded_reasons["invalid_analysis_json"] = excluded_reasons.get("invalid_analysis_json", 0) + 1
            continue

        capture_id = len(captures)
        record = _record_from_joined_row(row, analysis, conv, capture_id)
        captures.append(record)

        phase_counts_indexed[phase] = phase_counts_indexed.get(phase, 0) + 1

        if record["quality"]["usable_evidence"] is True:
            quality_gate_counts["usable_evidence_true"] += 1
        else:
            quality_gate_counts["usable_evidence_false"] += 1

        if record["quality"]["geometry_clipped_low"] is True:
            quality_gate_counts["geometry_clipped_low_true"] += 1
        else:
            quality_gate_counts["geometry_clipped_low_false"] += 1

        recapture_pending = record["quality"]["recapture_pending_manifest"]
        if recapture_pending is True:
            quality_gate_counts["recapture_pending_true"] += 1
        elif recapture_pending is False:
            quality_gate_counts["recapture_pending_false"] += 1
        else:
            quality_gate_counts["recapture_pending_null"] += 1

        vector_key = record["vector_key"]
        vector_buckets.setdefault(vector_key, []).append(record)

    vector_index: dict[str, Any] = {}
    for vector_key in sorted(vector_buckets):
        bucket = sorted(vector_buckets[vector_key], key=_rank_capture, reverse=True)
        by_exposure_track: dict[str, list[int]] = {}
        for rec in bucket:
            track = rec.get("exposure_track") or "unknown"
            by_exposure_track.setdefault(track, []).append(int(rec["capture_id"]))
        vector_index[vector_key] = {
            "capture_ids": [int(r["capture_id"]) for r in bucket],
            "preferred_capture_id": int(bucket[0]["capture_id"]),
            "by_exposure_track": {k: v for k, v in sorted(by_exposure_track.items())},
            "phase_counts": _phase_counts_for_bucket(bucket),
        }

    index = {
        "schema_version": 1,
        "provenance_labels": PROVENANCE_LABELS,
        "source": {
            "manifest_jsonl": str(manifest_path),
            "capture_root": str(capture_root),
            "analysis_geometry_json": str(analysis_geometry_path),
        },
        "analysis_authority": "per_capture_analysis_json",
        "unit_conversion": {
            "source": "analysis_geometry.scale.px_per_inch",
            "px_per_inch": conv.px_per_inch,
            "analysis_roi": [conv.roi_x0, conv.roi_y0, conv.roi_x1, conv.roi_y1],
        },
        "captures": captures,
        "vector_index": vector_index,
    }

    report = {
        "manifest_row_count": len(raw_rows),
        "deduped_test_id_row_count": len(deduped_rows),
        "analysis_files_joined": len(captures),
        "missing_analysis_count": len(missing_analysis_rows),
        "broken_analysis_count": len(broken_analysis_rows),
        "missing_or_broken_rows": {
            "missing_analysis_folders": missing_analysis_rows[:50],
            "broken_analysis_folders": broken_analysis_rows[:50],
        },
        "duplicate_test_id_count": len(dup_test_ids),
        "duplicate_test_id_rows_total": sum(dup_test_ids.values()) if dup_test_ids else 0,
        "duplicate_vector_count": sum(1 for v in vector_index.values() if len(v["capture_ids"]) > 1),
        "exact_vector_count": len(vector_index),
        "phase_counts_deduped": phase_counts_deduped,
        "phase_counts_indexed": phase_counts_indexed,
        "quality_gate_counts": quality_gate_counts,
        "rows_excluded_by_reason": excluded_reasons,
        "unit_conversion_source": {
            "analysis_geometry_path": str(analysis_geometry_path),
            "px_per_inch": conv.px_per_inch,
        },
        "authority_notes": {
            "manifest_inline_analysis_used_as_analysis_authority": False,
            "analysis_authority": "per_capture_analysis_json",
            "manifest_inline_fields_used_for_context_flags": [
                "recapture_pending",
                "expected_blank",
                "blank_zone_observed",
            ],
            "manifest_inline_fields_usage": "quality/context flags only",
        },
    }

    return index, report


def _phase_counts_for_bucket(bucket: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for rec in bucket:
        phase = str(rec.get("phase", "unknown"))
        out[phase] = out.get(phase, 0) + 1
    return dict(sorted(out.items()))


def lookup_exact(index: dict[str, Any], ch1_19: dict[str, Any]) -> dict[str, Any] | None:
    vector_key = vector_key_from_vector(ch1_19)
    return index.get("vector_index", {}).get(vector_key)


def write_capture_index_artifacts(index: dict[str, Any], report: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "capture_index_v1.json"
    report_json_path = output_dir / "capture_index_generation_report.json"
    report_md_path = output_dir / "capture_index_generation_report.md"

    with index_path.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, sort_keys=True)
        fh.write("\n")

    with report_json_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")

    with report_md_path.open("w", encoding="utf-8") as fh:
        fh.write(_report_markdown(report))

    return {
        "index": str(index_path),
        "report_json": str(report_json_path),
        "report_md": str(report_md_path),
    }


def _report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Capture Index Generation Report",
        "",
        "## Summary",
        f"- Manifest rows: {report['manifest_row_count']}",
        f"- Deduped test_id rows: {report['deduped_test_id_row_count']}",
        f"- Analysis files joined: {report['analysis_files_joined']}",
        f"- Missing analysis rows: {report['missing_analysis_count']}",
        f"- Broken analysis rows: {report['broken_analysis_count']}",
        f"- Duplicate test_id count: {report['duplicate_test_id_count']}",
        f"- Duplicate vector count: {report['duplicate_vector_count']}",
        f"- Exact vector count: {report['exact_vector_count']}",
        "",
        "## Phase Counts (Indexed)",
    ]
    for phase, count in sorted(report["phase_counts_indexed"].items()):
        lines.append(f"- {phase}: {count}")

    lines.extend(
        [
            "",
            "## Quality Gates",
        ]
    )
    for key, count in sorted(report["quality_gate_counts"].items()):
        lines.append(f"- {key}: {count}")

    lines.extend(
        [
            "",
            "## Rows Excluded / Flagged",
        ]
    )
    if report["rows_excluded_by_reason"]:
        for key, count in sorted(report["rows_excluded_by_reason"].items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Unit Conversion",
            f"- Source: {report['unit_conversion_source']['analysis_geometry_path']}",
            f"- px_per_inch: {report['unit_conversion_source']['px_per_inch']}",
            "",
            "## Authority",
            f"- Manifest inline analysis used as analysis authority: {report['authority_notes']['manifest_inline_analysis_used_as_analysis_authority']}",
            f"- Analysis authority: {report['authority_notes']['analysis_authority']}",
            f"- Manifest inline fields used for context flags: {', '.join(report['authority_notes']['manifest_inline_fields_used_for_context_flags'])}",
            f"- Manifest inline fields usage: {report['authority_notes']['manifest_inline_fields_usage']}",
            "",
        ]
    )
    return "\n".join(lines)

