from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture_index_runtime import (  # noqa: E402
    CaptureIndexRuntime,
    normalize_ch1_19_from_channels,
    vector_key_from_ch1_19,
)


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_normalize_ch1_19_from_channels_bounds_and_length() -> None:
    vec = normalize_ch1_19_from_channels([300, -1, "x", 4])  # type: ignore[list-item]
    assert vec["CH1"] == 255
    assert vec["CH2"] == 0
    assert vec["CH3"] == 0
    assert vec["CH4"] == 4
    assert len(vec) == 19
    assert all(k.startswith("CH") for k in vec)


def test_lookup_exact_hit_and_cue_matches(tmp_path: Path) -> None:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH1"] = 77
    key = vector_key_from_ch1_19(ch1_19)

    index = {
        "captures": [
            {
                "capture_id": 0,
                "test_id": "phase6_cue_validation__cue_relevant__cue_077_test",
                "phase": "phase6_cue_validation",
                "folder": "phase6_cue_validation/cue_relevant/cue_077_test",
                "exposure_track": "geometry_motion",
                "quality": {"usable_evidence": True},
                "metrics": {"motion_type": "static"},
            }
        ],
        "vector_index": {
            key: {
                "capture_ids": [0],
                "preferred_capture_id": 0,
                "by_exposure_track": {"geometry_motion": [0]},
                "phase_counts": {"phase6_cue_validation": 1},
            }
        },
    }

    cues = [{"cue_id": "abc", "cue_name": "Cue 77", "dmx": ch1_19}]
    runtime = CaptureIndexRuntime(index_data=index, cues_data=cues, fixture_model_data={"validation": {"buckets": {"pass": 0}}})
    channels = [0] * 36
    channels[0] = 77

    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["provenance_label"] == "EXACT_VECTOR_MATCH"
    assert hit["vector_match"] is True
    assert hit["validation_backed"] is False
    assert hit["capture_id"] == 0
    assert hit["cue_matches"][0]["cue_name"] == "Cue 77"


def test_lookup_exact_miss_returns_fallback_label() -> None:
    runtime = CaptureIndexRuntime(index_data={"captures": [], "vector_index": {}}, cues_data=[])
    miss = runtime.lookup_exact_from_channels([0] * 36)
    assert miss["hit"] is False
    assert miss["provenance_label"] == "NO_VECTOR_MATCH"
    assert miss["fallback_reason"] == "no_exact_capture_vector_match"


def test_runtime_loader_from_paths(tmp_path: Path) -> None:
    index_path = tmp_path / "capture_index.json"
    cues_path = tmp_path / "cues.json"
    _write_json(index_path, {"captures": [], "vector_index": {}})
    _write_json(cues_path, [{"cue_id": "1", "cue_name": "x", "dmx": {f"CH{i}": 0 for i in range(1, 20)}}])
    model_path = tmp_path / "fixture_model.json"
    _write_json(model_path, {"validation": {"buckets": {"pass": 0}}})
    runtime = CaptureIndexRuntime.from_paths(index_path=index_path, cues_path=cues_path, fixture_model_path=model_path)
    miss = runtime.lookup_exact_from_channels([0] * 36)
    assert miss["hit"] is False
    assert "cue_matches" in miss


def test_multi_name_vector_reports_aliases_and_unresolved_identity() -> None:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH1"] = 31
    ch1_19["CH3"] = 28
    ch1_19["CH7"] = 141
    key = vector_key_from_ch1_19(ch1_19)
    index = {
        "captures": [
            {
                "capture_id": 0,
                "test_id": "phase6_cue_validation__cue_relevant__cue_alias_case",
                "phase": "phase6_cue_validation",
                "folder": "phase6_cue_validation/cue_relevant/cue_alias_case",
                "exposure_track": "geometry_motion",
                "quality": {"usable_evidence": True},
                "metrics": {"motion_type": "static"},
            }
        ],
        "vector_index": {
            key: {
                "capture_ids": [0],
                "preferred_capture_id": 0,
                "by_exposure_track": {"geometry_motion": [0]},
                "phase_counts": {"phase6_cue_validation": 1},
            }
        },
    }
    cues = [
        {"cue_id": "a", "cue_name": "BASS HOUSE DROP 139bpm", "dmx": ch1_19},
        {"cue_id": "b", "cue_name": "white wave gradient 140 bpm", "dmx": ch1_19},
    ]
    runtime = CaptureIndexRuntime(index_data=index, cues_data=cues, fixture_model_data={"validation": {"buckets": {"pass": 0}}})
    channels = [0] * 36
    channels[0] = 31
    channels[2] = 28
    channels[6] = 141
    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["cue_identity_resolved"] is False
    assert hit["cue_alias_count"] > 1
    assert len(hit["cue_aliases"]) > 1


def test_validation_backed_false_for_normal_hit() -> None:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH1"] = 77
    key = vector_key_from_ch1_19(ch1_19)
    index = {
        "captures": [
            {
                "capture_id": 0,
                "test_id": "phase6_cue_validation__cue_relevant__cue_077_test",
                "phase": "phase6_cue_validation",
                "folder": "phase6_cue_validation/cue_relevant/cue_077_test",
                "exposure_track": "geometry_motion",
                "quality": {"usable_evidence": True},
                "metrics": {"motion_type": "static"},
            }
        ],
        "vector_index": {
            key: {
                "capture_ids": [0],
                "preferred_capture_id": 0,
                "by_exposure_track": {"geometry_motion": [0]},
                "phase_counts": {"phase6_cue_validation": 1},
            }
        },
    }
    runtime = CaptureIndexRuntime(index_data=index, cues_data=[], fixture_model_data={"validation": {"buckets": {"pass": 0}}})
    channels = [0] * 36
    channels[0] = 77
    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["validation_backed"] is False


def test_validation_backed_true_when_vector_in_pass_bucket() -> None:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH1"] = 99
    key = vector_key_from_ch1_19(ch1_19)
    index = {
        "captures": [
            {
                "capture_id": 0,
                "test_id": "phase6_cue_validation__cue_relevant__cue_099",
                "phase": "phase6_cue_validation",
                "folder": "phase6_cue_validation/cue_relevant/cue_099",
                "exposure_track": "geometry_motion",
                "quality": {"usable_evidence": True},
                "metrics": {"motion_type": "static"},
            }
        ],
        "vector_index": {
            key: {
                "capture_ids": [0],
                "preferred_capture_id": 0,
                "by_exposure_track": {"geometry_motion": [0]},
                "phase_counts": {"phase6_cue_validation": 1},
            }
        },
    }
    fixture_model_data = {
        "validation": {
            "buckets": {
                "pass": [{"vector_key": key}],
            }
        }
    }
    runtime = CaptureIndexRuntime(index_data=index, cues_data=[], fixture_model_data=fixture_model_data)
    channels = [0] * 36
    channels[0] = 99
    hit = runtime.lookup_exact_from_channels(channels)
    assert hit["hit"] is True
    assert hit["validation_backed"] is True

