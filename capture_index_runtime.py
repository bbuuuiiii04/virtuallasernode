"""Runtime helpers for PR2 capture lookup + provenance plumbing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CH1_19_KEYS = [f"CH{i}" for i in range(1, 20)]


def _safe_int(value: Any) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError):
        iv = 0
    return max(0, min(255, iv))


def normalize_ch1_19_from_channels(channels_36: list[int] | tuple[int, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, key in enumerate(CH1_19_KEYS, start=1):
        value = channels_36[i - 1] if i - 1 < len(channels_36) else 0
        out[key] = _safe_int(value)
    return out


def vector_key_from_ch1_19(ch1_19: dict[str, Any]) -> str:
    vec = {k: _safe_int(ch1_19.get(k, 0)) for k in CH1_19_KEYS}
    return "v1:" + ",".join(str(vec[k]) for k in CH1_19_KEYS)


class CaptureIndexRuntime:
    """In-memory runtime lookup over generated capture index artifact."""

    def __init__(self, index_data: dict[str, Any], cues_data: list[dict[str, Any]] | None = None):
        self._index = index_data
        self._captures = index_data.get("captures") or []
        self._vectors = index_data.get("vector_index") or {}
        self._cues_by_vector: dict[str, list[dict[str, str]]] = {}
        if cues_data:
            self._build_cue_map(cues_data)

    @classmethod
    def from_paths(cls, index_path: Path, cues_path: Path | None = None) -> "CaptureIndexRuntime":
        with index_path.open("r", encoding="utf-8") as fh:
            index_data = json.load(fh)
        cues_data: list[dict[str, Any]] | None = None
        if cues_path and cues_path.exists():
            with cues_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                cues_data = loaded
        return cls(index_data=index_data, cues_data=cues_data)

    def _build_cue_map(self, cues_data: list[dict[str, Any]]) -> None:
        for row in cues_data:
            vec = row.get("dmx")
            if not isinstance(vec, dict):
                continue
            key = vector_key_from_ch1_19(vec)
            self._cues_by_vector.setdefault(key, []).append(
                {
                    "cue_id": str(row.get("cue_id", "")),
                    "cue_name": str(row.get("cue_name", "")),
                }
            )
        for k in list(self._cues_by_vector.keys()):
            self._cues_by_vector[k] = sorted(
                self._cues_by_vector[k],
                key=lambda x: (x["cue_name"], x["cue_id"]),
            )

    def lookup_exact_from_channels(self, channels_36: list[int] | tuple[int, ...]) -> dict[str, Any]:
        ch1_19 = normalize_ch1_19_from_channels(channels_36)
        vector_key = vector_key_from_ch1_19(ch1_19)
        bucket = self._vectors.get(vector_key)
        cue_matches = self._cues_by_vector.get(vector_key, [])

        if not bucket:
            return {
                "hit": False,
                "provenance_label": "MEASURED_FIXTURE_MODEL",
                "fallback_reason": "no_exact_capture_vector_match",
                "vector_key": vector_key,
                "cue_matches": cue_matches[:8],
            }

        capture_id = int(bucket.get("preferred_capture_id"))
        capture = self._captures[capture_id] if 0 <= capture_id < len(self._captures) else None
        if capture is None:
            return {
                "hit": False,
                "provenance_label": "MEASURED_FIXTURE_MODEL",
                "fallback_reason": "preferred_capture_id_missing",
                "vector_key": vector_key,
                "cue_matches": cue_matches[:8],
            }

        return {
            "hit": True,
            "provenance_label": "EXACT_CAPTURE",
            "fallback_reason": None,
            "vector_key": vector_key,
            "capture_id": capture_id,
            "test_id": capture.get("test_id"),
            "phase": capture.get("phase"),
            "folder": capture.get("folder"),
            "exposure_track": capture.get("exposure_track"),
            "quality": capture.get("quality"),
            "metrics": capture.get("metrics"),
            "bucket_summary": {
                "capture_count": len(bucket.get("capture_ids") or []),
                "by_exposure_track": bucket.get("by_exposure_track") or {},
                "phase_counts": bucket.get("phase_counts") or {},
            },
            "cue_matches": cue_matches[:8],
        }

