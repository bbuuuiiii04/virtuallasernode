"""PR-G1 schema must require all shape fields; jsonschema is mandatory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LIBRARY_PATH = ROOT / "artifacts" / "renderer" / "shape_library_v1.json"
SCHEMA_PATH = ROOT / "artifacts" / "renderer" / "shape_library_v1.schema.json"

SHAPE_REQUIRED = [
    "shape_ref",
    "vector_key",
    "capture_path",
    "source_still",
    "test_id",
    "phase",
    "exposure_track",
    "ch1_19",
    "fixture_box_label",
    "source_pixel_bbox",
    "bbox_wall_norm",
    "centroid_wall_norm",
    "topology_class",
    "shape_point_count",
    "clusters",
    "polylines",
    "extraction_params",
    "quality_flags",
    "fallback_reason",
    "extraction_candidates_tried",
    "selected_extractor",
    "selected_extractor_reason",
    "candidate_scores",
    "rejected_candidate_reasons",
    "visual_status",
    "usable_as_shape_authority",
    "visual_review_reason",
]


def _require_jsonschema():
    try:
        import jsonschema  # type: ignore
    except ImportError:
        pytest.fail(
            "jsonschema missing — install test requirements: pip install -r test-requirements.txt"
        )
    return jsonschema


@pytest.mark.skipif(not SCHEMA_PATH.is_file(), reason="shape library schema missing")
def test_schema_lists_all_required_shape_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = schema["properties"]["shapes"]["items"]["required"]
    for field in SHAPE_REQUIRED:
        assert field in required, f"schema missing required shape field {field}"


@pytest.mark.skipif(not LIBRARY_PATH.is_file(), reason="shape library not built yet")
@pytest.mark.skipif(not SCHEMA_PATH.is_file(), reason="shape library schema missing")
def test_library_shapes_include_all_required_fields() -> None:
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    for shape in library.get("shapes") or []:
        for field in SHAPE_REQUIRED:
            assert field in shape, f"library shape missing {field}"


@pytest.mark.skipif(not LIBRARY_PATH.is_file(), reason="shape library not built yet")
@pytest.mark.skipif(not SCHEMA_PATH.is_file(), reason="shape library schema missing")
def test_library_validates_with_jsonschema() -> None:
    jsonschema = _require_jsonschema()
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=library, schema=schema)
