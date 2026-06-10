"""Lane A selection must prefer rep_ch3 distance, not distance to zero."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_library_builder import CH3_FAMILIES, score_lane_a_candidate  # noqa: E402


def test_score_prefers_exact_rep_ch3() -> None:
    family = next(f for f in CH3_FAMILIES if f["rep_ch3"] == 32)
    rep = 32
    exact_meta = {"ch1_19": {"CH3": 32, "CH5": 90, "CH6": 128, "CH7": 128}, "exposure_track": "geometry_motion"}
    near_meta = {"ch1_19": {"CH3": 24, "CH5": 90, "CH6": 128, "CH7": 128}, "exposure_track": "geometry_motion"}
    ch0_meta = {"ch1_19": {"CH3": 0, "CH5": 90, "CH6": 128, "CH7": 128}, "exposure_track": "geometry_motion"}
    analysis = {"usable_evidence": True, "geometry_clipped_low": False, "expected_blank": False}
    exact = score_lane_a_candidate(exact_meta, analysis, rep)
    near = score_lane_a_candidate(near_meta, analysis, rep)
    zero = score_lane_a_candidate(ch0_meta, analysis, rep)
    assert exact > near
    assert near > zero


def test_score_uses_rep_distance_not_zero_distance() -> None:
    rep = 32
    ch24 = score_lane_a_candidate(
        {"ch1_19": {"CH3": 24}, "exposure_track": "geometry_motion"},
        {"usable_evidence": True, "geometry_clipped_low": False},
        rep,
    )
    ch40 = score_lane_a_candidate(
        {"ch1_19": {"CH3": 40}, "exposure_track": "geometry_motion"},
        {"usable_evidence": True, "geometry_clipped_low": False},
        rep,
    )
    assert ch24 == ch40


def test_nearest_family_selection_reason_documents_distance() -> None:
    import json

    sel_path = ROOT / "artifacts/renderer/pr-g1-shape-authority/shape_selection.json"
    if not sel_path.is_file():
        return
    data = json.loads(sel_path.read_text())
    line_entry = next(
        e for e in data["entries"]
        if e.get("family_or_checkpoint") == "horizontal line static" and e.get("selection_lane") == "ch3_family"
    )
    if line_entry.get("selection_tier") == "nearest_family":
        reason = line_entry.get("selection_reason", "")
        assert "rep CH3=32" in reason
        assert "distance=" in reason
