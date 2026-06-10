"""Runtime must respect bucket shape_authority=false even when shape_ref exists."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture_index_runtime import CaptureIndexRuntime, vector_key_from_ch1_19  # noqa: E402


def _index_with_bucket(extra: dict) -> tuple[dict, list[int]]:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH3"] = 32
    key = vector_key_from_ch1_19(ch1_19)
    bucket = {
        "capture_ids": [0],
        "preferred_capture_id": 0,
        "by_exposure_track": {"geometry_motion": [0]},
        "phase_counts": {"phase1": 1},
        "shape_ref": "sh1_weakshape00000001",
        "shape_point_count": 88,
        "topology_class": "line",
        "shape_evidence": "still",
        "shape_source_capture_path": "phase1/ch3_032",
    }
    bucket.update(extra)
    index = {
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
    }
    channels = [0] * 36
    channels[2] = 32
    return index, channels


def test_shape_authority_false_hides_shape_ref() -> None:
    index, channels = _index_with_bucket({"shape_authority": False})
    hit = CaptureIndexRuntime(index_data=index).lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["shape_authority"] is False
    assert hit["shape_ref"] is None
    assert hit["shape_point_count"] == 0


def test_shape_authority_true_exposes_shape_ref() -> None:
    index, channels = _index_with_bucket({"shape_authority": True})
    hit = CaptureIndexRuntime(index_data=index).lookup_exact_from_channels(channels)
    assert hit["shape_authority"] is True
    assert hit["shape_ref"] == "sh1_weakshape00000001"
    assert hit["shape_point_count"] == 88
