"""Runtime helpers for capture lookup + truthful provenance plumbing."""

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

    def __init__(
        self,
        index_data: dict[str, Any],
        cues_data: list[dict[str, Any]] | None = None,
        fixture_model_data: dict[str, Any] | None = None,
    ):
        self._index = index_data
        self._captures = index_data.get("captures") or []
        self._vectors = index_data.get("vector_index") or {}
        self._cues_by_vector: dict[str, list[dict[str, str]]] = {}
        self._validation_backed_vectors = self._extract_validation_backed_vectors(fixture_model_data or {})
        if cues_data:
            self._build_cue_map(cues_data)

    @classmethod
    def from_paths(
        cls,
        index_path: Path,
        cues_path: Path | None = None,
        fixture_model_path: Path | None = None,
    ) -> "CaptureIndexRuntime":
        with index_path.open("r", encoding="utf-8") as fh:
            index_data = json.load(fh)
        cues_data: list[dict[str, Any]] | None = None
        fixture_model_data: dict[str, Any] | None = None
        if cues_path and cues_path.exists():
            with cues_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                cues_data = loaded
        if fixture_model_path and fixture_model_path.exists():
            with fixture_model_path.open("r", encoding="utf-8") as fh:
                loaded_model = json.load(fh)
            if isinstance(loaded_model, dict):
                fixture_model_data = loaded_model
        return cls(index_data=index_data, cues_data=cues_data, fixture_model_data=fixture_model_data)

    def _candidate_vector_key(self, row: Any) -> str | None:
        if isinstance(row, str):
            s = row.strip()
            if not s:
                return None
            if s.startswith("v1:"):
                return s
            parts = [p.strip() for p in s.split(",")]
            if len(parts) == 19 and all(p.isdigit() for p in parts):
                return "v1:" + ",".join(parts)
            return None
        if not isinstance(row, dict):
            return None
        if isinstance(row.get("vector_key"), str):
            return self._candidate_vector_key(row.get("vector_key"))
        for key in ("ch1_19", "dmx", "vector"):
            vec = row.get(key)
            if isinstance(vec, dict):
                return vector_key_from_ch1_19(vec)
        return None

    def _collect_vector_keys(self, rows: Any) -> set[str]:
        if not isinstance(rows, list):
            return set()
        out: set[str] = set()
        for row in rows:
            key = self._candidate_vector_key(row)
            if key:
                out.add(key)
        return out

    def _extract_validation_backed_vectors(self, fixture_model_data: dict[str, Any]) -> set[str]:
        validation = fixture_model_data.get("validation")
        if not isinstance(validation, dict):
            return set()
        vectors: set[str] = set()

        # Preferred explicit containers.
        for key in ("pass_vectors", "validated_vectors", "validated", "pass"):
            vectors.update(self._collect_vector_keys(validation.get(key)))

        buckets = validation.get("buckets")
        if isinstance(buckets, dict):
            vectors.update(self._collect_vector_keys(buckets.get("pass")))
            vectors.update(self._collect_vector_keys(buckets.get("validated")))

        return vectors

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
        cue_aliases = self._cues_by_vector.get(vector_key, [])
        distinct_names = {c.get("cue_name", "") for c in cue_aliases if c.get("cue_name", "")}
        cue_identity_resolved = len(distinct_names) == 1
        validation_backed = vector_key in self._validation_backed_vectors

        if not bucket:
            return {
                "hit": False,
                "vector_match": False,
                "validation_backed": False,
                "provenance_label": "NO_VECTOR_MATCH",
                "fallback_reason": "no_exact_capture_vector_match",
                "vector_key": vector_key,
                "cue_matches": cue_aliases[:8],
                "cue_aliases": cue_aliases,
                "cue_alias_count": len(cue_aliases),
                "cue_identity_resolved": cue_identity_resolved,
                "shape_authority": False,
                "shape_ref": None,
                "shape_point_count": 0,
                "topology_class": None,
                "shape_evidence": None,
                "shape_fallback_reason": "no_exact_capture_vector_match",
                "shape_quality_flags": [],
                "shape_source_capture_path": None,
            }

        capture_id = int(bucket.get("preferred_capture_id"))
        capture = self._captures[capture_id] if 0 <= capture_id < len(self._captures) else None
        if capture is None:
            return {
                "hit": False,
                "vector_match": False,
                "validation_backed": False,
                "provenance_label": "NO_VECTOR_MATCH",
                "fallback_reason": "preferred_capture_id_missing",
                "vector_key": vector_key,
                "cue_matches": cue_aliases[:8],
                "cue_aliases": cue_aliases,
                "cue_alias_count": len(cue_aliases),
                "cue_identity_resolved": cue_identity_resolved,
                "shape_authority": False,
                "shape_ref": None,
                "shape_point_count": 0,
                "topology_class": None,
                "shape_evidence": None,
                "shape_fallback_reason": "preferred_capture_id_missing",
                "shape_quality_flags": [],
                "shape_source_capture_path": None,
            }

        shape_ref = bucket.get("shape_ref")
        shape_point_count = int(bucket.get("shape_point_count") or 0)
        shape_authority = bool(shape_ref) and shape_point_count > 0
        shape_fallback_reason = bucket.get("shape_fallback_reason")
        if not shape_authority and shape_fallback_reason is None:
            shape_fallback_reason = "no_static_shape_for_vector"

        return {
            "hit": True,
            "vector_match": True,
            "validation_backed": validation_backed,
            "provenance_label": "EXACT_VECTOR_MATCH",
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
            "cue_matches": cue_aliases[:8],
            "cue_aliases": cue_aliases,
            "cue_alias_count": len(cue_aliases),
            "cue_identity_resolved": cue_identity_resolved,
            "shape_authority": shape_authority,
            "shape_ref": shape_ref if shape_authority else None,
            "shape_point_count": shape_point_count if shape_authority else 0,
            "topology_class": bucket.get("topology_class") if shape_authority else None,
            "shape_evidence": bucket.get("shape_evidence") if shape_authority else None,
            "shape_fallback_reason": shape_fallback_reason if not shape_authority else None,
            "shape_quality_flags": list(bucket.get("shape_quality_flags") or []) if shape_authority else [],
            "shape_source_capture_path": bucket.get("shape_source_capture_path") if shape_authority else None,
        }

