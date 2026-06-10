"""AI extraction schema and example JSON validity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ai_shape_geometry_convert import validate_ai_extraction_result  # noqa: E402

SCHEMA_PATH = ROOT / "artifacts/renderer/pr-g1-ai-extraction/ai_extraction.schema.json"
EXAMPLE_PATH = ROOT / "artifacts/renderer/pr-g1-ai-extraction/ai_extractions.example.json"


def _require_jsonschema():
    try:
        import jsonschema  # type: ignore
    except ImportError:
        pytest.fail("jsonschema missing — pip install -r test-requirements.txt")
    return jsonschema


def test_ai_extraction_schema_is_valid_json_schema() -> None:
    jsonschema = _require_jsonschema()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_example_json_validates_against_schema() -> None:
    jsonschema = _require_jsonschema()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    doc = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    for entry in doc["entries"]:
        jsonschema.validate(instance=entry, schema=schema)
        validate_ai_extraction_result(entry)
