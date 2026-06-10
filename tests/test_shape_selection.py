"""PR-G1 shape_selection.json lane and field validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SELECTION_PATH = ROOT / "artifacts" / "renderer" / "pr-g1-shape-authority" / "shape_selection.json"
CAPTURE_ROOT = ROOT / "captures" / "fixture_model"

REQUIRED_TOP = (
    "artifact_version",
    "generated_at",
    "capture_root",
    "plan_revision",
    "selection_policy_version",
    "entries",
)
REQUIRED_ENTRY = (
    "selection_lane",
    "family_or_checkpoint",
    "capture_path",
    "still_path",
    "metadata_path",
    "analysis_path",
    "vector_key",
    "ch1_19",
    "phase",
    "exposure_track",
    "quality_flags",
    "selected_fixture_box",
    "selection_reason",
    "selection_tier",
    "local_media_exists",
)
ALLOWED_LANES = {"ch3_family", "phase6_cue"}
ALLOWED_TIERS = {"exact_family", "nearest_family", "phase6_cue", "fallback_candidate"}
FORBIDDEN = (
    "calib/captures",
    "archive/pre_corpus",
    "/tmp/",
    "vln_wall_ch3_atlas",
    "wall_atlas_ch3",
    "docs/_archive",
)


def local_media_available() -> bool:
    if not CAPTURE_ROOT.is_dir():
        return False
    return any(CAPTURE_ROOT.rglob("still.jpg")) or any(CAPTURE_ROOT.rglob("still_color.jpg"))


@pytest.mark.skipif(not SELECTION_PATH.is_file(), reason="shape_selection.json not built yet")
def test_selection_top_level_fields() -> None:
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    for key in REQUIRED_TOP:
        assert key in data, f"missing top-level {key}"
    assert data["capture_root"] == "captures/fixture_model"


@pytest.mark.skipif(not SELECTION_PATH.is_file(), reason="shape_selection.json not built yet")
def test_both_lanes_present() -> None:
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    lanes = {e.get("selection_lane") for e in data.get("entries") or []}
    assert "ch3_family" in lanes
    assert "phase6_cue" in lanes


@pytest.mark.skipif(not SELECTION_PATH.is_file(), reason="shape_selection.json not built yet")
def test_entry_required_fields_and_tiers() -> None:
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    for entry in data.get("entries") or []:
        for key in REQUIRED_ENTRY:
            assert key in entry, f"missing entry field {key}"
        assert entry["selection_lane"] in ALLOWED_LANES
        assert entry["selection_tier"] in ALLOWED_TIERS
        assert entry.get("selected_fixture_box") in ("image_left", "image_right")


@pytest.mark.skipif(not SELECTION_PATH.is_file(), reason="shape_selection.json not built yet")
def test_no_historical_still_paths() -> None:
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    for entry in data.get("entries") or []:
        still = str(entry.get("still_path") or "")
        if not still:
            continue
        lower = still.replace("\\", "/").lower()
        for frag in FORBIDDEN:
            assert frag not in lower, f"historical path fragment {frag!r} in still_path"


@pytest.mark.skipif(not SELECTION_PATH.is_file(), reason="shape_selection.json not built yet")
@pytest.mark.skipif(not local_media_available(), reason="local capture media absent")
def test_selected_entries_have_local_media() -> None:
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    selected = [
        e for e in data.get("entries") or []
        if e.get("local_media_exists") and not e.get("excluded_reason")
    ]
    assert selected, "expected at least one selected entry with local media"
    for entry in selected:
        still = ROOT / str(entry["still_path"])
        assert still.is_file(), f"missing still on disk: {still}"


@pytest.mark.skipif(not SELECTION_PATH.is_file(), reason="shape_selection.json not built yet")
def test_skipped_entries_have_excluded_reason() -> None:
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    for entry in data.get("entries") or []:
        if not entry.get("local_media_exists"):
            assert entry.get("excluded_reason"), "skipped entry must record excluded_reason"
