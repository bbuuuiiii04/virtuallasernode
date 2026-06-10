"""V7 real-media smoke tests for 3 named captures (skipif no media/no numpy)."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CAPTURE_ROOT = REPO_ROOT

SMOKE_REFS = {
    "sh1_21b9e82ef84b930b": {
        "desc": "row-of-squares",
        "expect_closed_strokes_gte": 4,
        "expect_status_in": {"authority", "provisional", "quarantined"},
        "must_not_status": set(),
    },
    "sh1_41c84ad2ac1f458e": {
        "desc": "dual-dot",
        "expect_dots_exact": 2,
        "expect_status_in": {"authority", "provisional", "quarantined"},
    },
    "sh1_adb58093da473f3e": {
        "desc": "cue_002 red arcs",
        "expect_status_in": {"authority", "provisional", "quarantined"},
        "no_fragment_only": True,
    },
}

# Check prerequisites
_skimage = pytest.importorskip("skimage", reason="scikit-image required")
_numpy = pytest.importorskip("numpy", reason="numpy required")

# Check media presence
_geom_path = CAPTURE_ROOT / "captures/fixture_model/analysis_geometry.json"
_selection_path = CAPTURE_ROOT / "artifacts/renderer/pr-g1-shape-authority/shape_selection.json"

media_available = (
    _geom_path.exists()
    and _selection_path.exists()
    and (CAPTURE_ROOT / "captures/fixture_model/phase1_5_base_dependence").exists()
)

pytestmark = pytest.mark.skipif(not media_available, reason="Local media not available")


def _run_extraction(shape_ref):
    """Run v7 extraction for a single ref, return the record dict."""
    from tools.shape_core_mask import load_analysis_geometry, load_fixture_boxes
    from tools.shape_extract_v7 import extract_record, find_entry_by_ref, load_selection

    entries = load_selection(_selection_path)
    entry = find_entry_by_ref(entries, shape_ref)
    if entry is None:
        pytest.skip(f"ref {shape_ref} not found in selection")

    geom = load_analysis_geometry(_geom_path)

    params = {"k_core": 8.0, "k_glow": 3.5, "sat_floor": 200, "min_core_area_px": 20}
    record = extract_record(entry, shape_ref, CAPTURE_ROOT, geom, _geom_path, params)
    record.pop("_rle_data", None)
    return record


def test_row_of_squares_has_four_or_more_closed_strokes():
    ref = "sh1_21b9e82ef84b930b"
    r = _run_extraction(ref)
    topo = r["topology_summary"]
    assert topo["closed_strokes"] >= 4, (
        f"row-of-squares: expected >=4 closed_strokes, got {topo}"
    )


def test_row_of_squares_status_not_empty():
    ref = "sh1_21b9e82ef84b930b"
    r = _run_extraction(ref)
    assert r["status"] in {"authority", "provisional", "quarantined"}, (
        f"status must be explicit, got {r['status']}"
    )
    assert r["shape_ref"] == ref


def test_dual_dot_exactly_two_dot_anchors():
    ref = "sh1_41c84ad2ac1f458e"
    r = _run_extraction(ref)
    dot_polys = [pl for pl in r["polylines"] if pl["geometry_kind"] == "dot_anchor"]
    assert len(dot_polys) == 2, (
        f"dual-dot: expected exactly 2 dot_anchor polylines, got {len(dot_polys)}"
    )
    # Each dot_anchor has exactly 1 point
    for dp in dot_polys:
        assert len(dp["points_px"]) == 1, f"dot_anchor must have 1 point, got {dp['points_px']}"


def test_cue_002_arcs_detected_no_fragment_only():
    """cue_002: arcs detected without crop-induced fragment-only failure."""
    ref = "sh1_adb58093da473f3e"
    r = _run_extraction(ref)

    # Must have at least some polylines (arcs detected)
    assert len(r["polylines"]) > 0, "cue_002: no polylines detected (fragment-only failure)"

    # Must not have zero components (detection failure)
    assert len(r["components"]) > 0, "cue_002: no components detected"

    # Status must be explicit
    assert r["status"] in {"authority", "provisional", "quarantined"}, (
        f"status must be explicit, got {r['status']}"
    )

    # Quarantine reason must NOT be 'low_contrast' if we have components
    if r["status"] == "quarantined":
        assert "low_contrast" not in r["status_reasons"], (
            "cue_002 quarantined for low_contrast despite detecting components"
        )


def test_cue_002_out_of_box_geometry_preserved():
    """cue_002: components at box boundary preserved with out_of_box flag."""
    ref = "sh1_adb58093da473f3e"
    r = _run_extraction(ref)
    # At least one component should exist (full ROI detection)
    assert len(r["components"]) >= 1

    # If out_of_box components exist, their wall_norm coords should go beyond [-1,1]
    for comp in r["components"]:
        if comp.get("out_of_box_geometry"):
            bbox_wn = comp.get("bbox_wall_norm", [])
            if bbox_wn:
                # At least one coordinate outside [-1,1]
                outside = any(abs(v) > 1.0 for v in bbox_wn)
                assert outside, (
                    f"out_of_box_geometry component has bbox_wall_norm {bbox_wn} "
                    "fully within [-1,1] — should have values outside"
                )


def test_all_smoke_records_have_valid_schema():
    """All 3 smoke records have required fields."""
    required = ["record_version", "shape_ref", "vector_key", "fixture_box_label",
                "extraction", "core_mask", "components", "polylines",
                "topology_summary", "metrics", "status", "authority_eligible",
                "status_reasons", "quality_flags"]

    for ref in SMOKE_REFS:
        r = _run_extraction(ref)
        for field in required:
            assert field in r, f"{ref}: missing required field '{field}'"
        assert r["extraction"]["policy_version"] == "v7"
        assert r["record_version"] == "shape-authority-v2"


def test_smoke_metrics_are_in_range():
    for ref in SMOKE_REFS:
        r = _run_extraction(ref)
        m = r["metrics"]
        assert 0.0 <= m["core_precision"] <= 1.0, f"{ref}: precision out of range"
        assert 0.0 <= m["core_recall"] <= 1.0, f"{ref}: recall out of range"
        assert 0.0 <= m["halo_spill"] <= 1.0, f"{ref}: halo_spill out of range"
        assert m["vector_fit_residual_px_p95"] >= 0.0, f"{ref}: negative p95 residual"
