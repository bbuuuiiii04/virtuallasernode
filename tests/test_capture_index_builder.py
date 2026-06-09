from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from capture_index_builder import (  # noqa: E402
    AnalysisGeometryError,
    ManifestJsonlError,
    build_capture_index,
    lookup_exact,
    normalize_ch1_19_vector,
    parse_manifest_jsonl,
    vector_key_from_vector,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _base_row(test_id: str, folder: str, timestamp: str, ch1: int = 1) -> dict:
    return {
        "folder": folder,
        "capture_path": folder,
        "phase": "phase1_single_channel",
        "test_id": test_id,
        "intent": "",
        "baseline": "base_CH3_032_CH4_010",
        "ch1_19": {
            "CH1": ch1,
            "CH2": 0,
            "CH3": 32,
            "CH4": 10,
            "CH5": 90,
            "CH6": 128,
            "CH7": 128,
            "CH8": 20,
            "CH9": 0,
            "CH10": 0,
            "CH11": 0,
            "CH12": 0,
            "CH13": 0,
            "CH14": 0,
            "CH15": 0,
            "CH16": 0,
            "CH17": 0,
            "CH18": 0,
            "CH19": 0,
        },
        "changed_channels": {"CH1": ch1},
        "ch3_bank": 32,
        "ch4_program": 10,
        "exposure_track": "geometry_motion",
        "timestamp": timestamp,
        "analysis": {
            "expected_blank": None,
            "blank_zone_observed": None,
            "recapture_pending": False,
            "motion_type": "manifest_should_not_be_authority",
            "loop_confidence": 0.11,
        },
    }


def _analysis_payload(motion: str, usable: bool, clipped: bool, loop_conf: float, x_px: float) -> dict:
    return {
        "valid": True,
        "blank": False,
        "clipped": False,
        "clipped_roi_bottom_any": clipped,
        "geometry_clipped_low": clipped,
        "analysis_fps": 60,
        "analysis_frame_count": 100,
        "analysis_nonblank_frames": 100,
        "x_range": x_px,
        "y_range": 20.0,
        "angle_range_deg": 10.0,
        "area_range_frac": 0.1,
        "brightness_cv": 0.05,
        "dominant_colors": ["cyan"],
        "strobe_frequency_hz": 8.5,
        "duty_cycle": 0.5,
        "strobe_crossings": 12,
        "motion_type": motion,
        "motion_direction": "rightward",
        "motion_direction_source": "numeric_regression_slope",
        "motion_direction_confidence": 0.7,
        "motion_signed_slope_per_second": 1.2,
        "loop_duration_estimate": 0.25,
        "loop_confidence": loop_conf,
        "full_loop_captured": True,
        "periodic_motion": True,
        "motion_characterized": True,
        "fast_motion_timing_inferred": False,
        "usable_evidence": usable,
        "analysis_notes": "ok",
    }


def test_parse_manifest_jsonl_rejects_invalid_line(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"ok":1}\n{bad json}\n', encoding="utf-8")
    try:
        parse_manifest_jsonl(manifest)
        assert False, "expected ManifestJsonlError"
    except ManifestJsonlError:
        assert True


def test_ch1_19_normalization_and_key_are_deterministic() -> None:
    vec = {"CH1": "999", "CH2": -4, "CH3": "x"}
    normalized = normalize_ch1_19_vector(vec)
    assert normalized["CH1"] == 255
    assert normalized["CH2"] == 0
    assert normalized["CH3"] == 0
    key = vector_key_from_vector(vec)
    assert key.startswith("v1:")
    assert len(key.split(",")) == 19


def test_build_index_dedups_latest_test_id_and_prefers_quality(tmp_path: Path) -> None:
    capture_root = tmp_path / "captures" / "fixture_model"
    manifest = capture_root / "manifest.jsonl"
    analysis_geometry = capture_root / "analysis_geometry.json"

    _write_json(
        analysis_geometry,
        {
            "analysis_roi": [0, 100, 1280, 600],
            "scale": {"px_per_inch": 10.5185},
        },
    )

    row_old = _base_row("dup_test", "phase1_single_channel/CH01/old", "2026-06-08T12:00:00")
    row_new = _base_row("dup_test", "phase1_single_channel/CH01/new", "2026-06-08T13:00:00")
    row_pair_geo = _base_row("pair_geo", "phase1_single_channel/PAIR/geo", "2026-06-08T14:00:00", ch1=9)
    row_pair_color = _base_row("pair_color", "phase1_single_channel/PAIR/color", "2026-06-08T14:01:00", ch1=9)
    row_pair_color["exposure_track"] = "color"

    manifest_rows = [row_old, row_new, row_pair_geo, row_pair_color]
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("".join(json.dumps(r) + "\n" for r in manifest_rows), encoding="utf-8")

    _write_json(capture_root / row_old["folder"] / "analysis.json", _analysis_payload("old_motion", True, False, 0.4, 100.0))
    _write_json(capture_root / row_new["folder"] / "analysis.json", _analysis_payload("new_motion", True, False, 0.9, 200.0))
    _write_json(capture_root / row_pair_geo["folder"] / "analysis.json", _analysis_payload("pair_motion_geo", True, False, 0.6, 110.0))
    _write_json(capture_root / row_pair_color["folder"] / "analysis.json", _analysis_payload("pair_motion_color", False, True, 0.2, 120.0))

    index, report = build_capture_index(
        manifest_path=manifest,
        capture_root=capture_root,
        analysis_geometry_path=analysis_geometry,
    )

    assert report["manifest_row_count"] == 4
    assert report["deduped_test_id_row_count"] == 3
    assert report["duplicate_test_id_count"] == 1
    assert report["analysis_files_joined"] == 3
    assert report["authority_notes"]["manifest_inline_analysis_used_as_analysis_authority"] is False
    assert report["authority_notes"]["manifest_inline_fields_usage"] == "quality/context flags only"

    dup_capture = next(c for c in index["captures"] if c["test_id"] == "dup_test")
    assert dup_capture["folder"].endswith("/new")
    assert dup_capture["metrics"]["motion_type"] == "new_motion"
    assert dup_capture["metrics"]["x_range_in"] == round(200.0 / 10.5185, 6)
    assert dup_capture["metrics"]["x_range_norm_roi"] == round(200.0 / 1280.0, 6)
    assert dup_capture["quality"]["recapture_pending_manifest"] is False
    assert dup_capture["quality_field_sources"]["recapture_pending_manifest"] == "manifest_inline_analysis"

    pair_vec_key = vector_key_from_vector(row_pair_geo["ch1_19"])
    assert pair_vec_key in index["vector_index"]
    pair_bucket = index["vector_index"][pair_vec_key]
    assert len(pair_bucket["capture_ids"]) == 2
    assert set(pair_bucket["by_exposure_track"].keys()) == {"color", "geometry_motion"}

    preferred_id = pair_bucket["preferred_capture_id"]
    preferred_capture = next(c for c in index["captures"] if c["capture_id"] == preferred_id)
    assert preferred_capture["exposure_track"] == "geometry_motion"
    assert preferred_capture["quality"]["usable_evidence"] is True


def test_lookup_exact_returns_bucket(tmp_path: Path) -> None:
    capture_root = tmp_path / "captures" / "fixture_model"
    manifest = capture_root / "manifest.jsonl"
    analysis_geometry = capture_root / "analysis_geometry.json"
    _write_json(analysis_geometry, {"analysis_roi": [0, 0, 100, 100], "scale": {"px_per_inch": 10.5185}})

    row = _base_row("one", "phase1_single_channel/CH01/one", "2026-06-08T10:00:00", ch1=77)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    _write_json(capture_root / row["folder"] / "analysis.json", _analysis_payload("exact_motion", True, False, 0.7, 50.0))

    index, _ = build_capture_index(
        manifest_path=manifest,
        capture_root=capture_root,
        analysis_geometry_path=analysis_geometry,
    )
    bucket = lookup_exact(index, row["ch1_19"])
    assert bucket is not None
    assert len(bucket["capture_ids"]) == 1


def test_load_analysis_geometry_requires_px_per_inch(tmp_path: Path) -> None:
    capture_root = tmp_path / "captures" / "fixture_model"
    manifest = capture_root / "manifest.jsonl"
    analysis_geometry = capture_root / "analysis_geometry.json"

    row = _base_row("geom_fail", "phase1_single_channel/CH01/geom_fail", "2026-06-08T10:00:00", ch1=11)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    _write_json(capture_root / row["folder"] / "analysis.json", _analysis_payload("exact_motion", True, False, 0.7, 50.0))

    # Missing scale.px_per_inch should fail fast (no silent fallback).
    _write_json(analysis_geometry, {"analysis_roi": [0, 0, 100, 100], "scale": {}})
    try:
        build_capture_index(
            manifest_path=manifest,
            capture_root=capture_root,
            analysis_geometry_path=analysis_geometry,
        )
        assert False, "expected AnalysisGeometryError"
    except AnalysisGeometryError:
        assert True

