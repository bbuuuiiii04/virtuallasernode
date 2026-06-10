"""Validate shape_library_v1.json against schema (jsonschema required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_PATH = ROOT / "artifacts" / "renderer" / "shape_library_v1.json"
SCHEMA_PATH = ROOT / "artifacts" / "renderer" / "shape_library_v1.schema.json"


def _require_jsonschema():
    try:
        import jsonschema  # type: ignore
    except ImportError:
        pytest.fail(
            "jsonschema missing — install test requirements: pip install -r test-requirements.txt"
        )
    return jsonschema


@pytest.mark.skipif(not LIBRARY_PATH.is_file(), reason="shape library not built yet")
@pytest.mark.skipif(not SCHEMA_PATH.is_file(), reason="shape library schema missing")
def test_shape_library_validates_against_schema() -> None:
    jsonschema = _require_jsonschema()
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=library, schema=schema)
    assert library.get("coordinate_space") == "wall_norm_per_fixture_calibration_box"
    assert isinstance(library.get("shapes"), list)


@pytest.mark.skipif(not LIBRARY_PATH.is_file(), reason="shape library not built yet")
def test_geometry_source_is_object() -> None:
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    gs = library.get("geometry_source")
    assert isinstance(gs, dict)
    assert gs.get("path") == "captures/fixture_model/analysis_geometry.json"
    assert "sha256" in gs
