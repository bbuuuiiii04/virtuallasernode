"""Visual review summary and library shapes must expose honest review fields."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUMMARY = ROOT / "artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md"
LIBRARY = ROOT / "artifacts/renderer/shape_library_v1.json"


@pytest.mark.skipif(not SUMMARY.is_file(), reason="visual review summary not built")
def test_visual_review_summary_has_required_fields() -> None:
    text = SUMMARY.read_text(encoding="utf-8")
    assert "visual_status" in text
    assert "usable_as_shape_authority" in text
    assert "selected_vectorizer" in text or "selected_extractor" in text
    assert "pass:" in text
    assert "weak:" in text
    assert "fail:" in text


@pytest.mark.skipif(not LIBRARY.is_file(), reason="shape library not built")
def test_library_shapes_have_review_metadata() -> None:
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    for shape in library.get("shapes") or []:
        assert shape.get("visual_status") in ("pass", "weak", "fail")
        assert isinstance(shape.get("usable_as_shape_authority"), bool)
        assert shape.get("selected_extractor")
        assert shape.get("visual_review_reason")
        assert shape.get("extraction_candidates_tried")
        if shape["visual_status"] in ("fail", "weak"):
            assert shape["usable_as_shape_authority"] is False
        if shape["visual_status"] == "pass":
            assert shape["usable_as_shape_authority"] is True
