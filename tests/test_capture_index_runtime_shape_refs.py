"""PR-G1 capture index runtime shape_ref exposure."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture_index_runtime import CaptureIndexRuntime, vector_key_from_ch1_19  # noqa: E402


def _base_index_with_bucket(extra_bucket: dict) -> dict:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH3"] = 32
    key = vector_key_from_ch1_19(ch1_19)
    bucket = {
        "capture_ids": [0],
        "preferred_capture_id": 0,
        "by_exposure_track": {"geometry_motion": [0]},
        "phase_counts": {"phase1": 1},
    }
    bucket.update(extra_bucket)
    return {
        "captures": [
            {
                "capture_id": 0,
                "test_id": "ch3_032_line",
                "phase": "phase1",
                "folder": "phase1/ch3_032",
                "exposure_track": "geometry_motion",
            }
        ],
        "vector_index": {key: bucket},
    }, ch1_19


def test_exact_lookup_exposes_shape_ref_when_index_has_it() -> None:
    index, ch1_19 = _base_index_with_bucket(
        {
            "shape_ref": "sh1_abc123def4567890",
            "shape_point_count": 120,
            "topology_class": "line",
            "shape_evidence": "still",
            "shape_quality_flags": [],
            "shape_source_capture_path": "phase1/ch3_032",
        }
    )
    runtime = CaptureIndexRuntime(index_data=index)
    channels = [0] * 36
    channels[2] = 32
    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["vector_match"] is True
    assert hit["shape_authority"] is True
    assert hit["shape_ref"] == "sh1_abc123def4567890"
    assert hit["shape_point_count"] == 120
    assert hit["topology_class"] == "line"
    assert hit["shape_evidence"] == "still"
    assert hit["shape_source_capture_path"] == "phase1/ch3_032"


def test_vector_match_without_shape_ref_is_not_shape_authority() -> None:
    index, _ = _base_index_with_bucket({})
    runtime = CaptureIndexRuntime(index_data=index)
    channels = [0] * 36
    channels[2] = 32
    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["vector_match"] is True
    assert hit["shape_authority"] is False
    assert hit["shape_ref"] is None
    assert hit["shape_fallback_reason"] == "no_static_shape_for_vector"


def test_empty_shape_ref_not_authority() -> None:
    index, _ = _base_index_with_bucket(
        {
            "shape_ref": "",
            "shape_point_count": 0,
        }
    )
    runtime = CaptureIndexRuntime(index_data=index)
    channels = [0] * 36
    channels[2] = 32
    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["shape_authority"] is False
    assert hit["shape_ref"] is None
