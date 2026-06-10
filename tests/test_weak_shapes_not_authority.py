"""Weak/fail shapes must not be usable_as_shape_authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_stroke_vectorization import classify_visual_status  # noqa: E402

LIBRARY = ROOT / "artifacts/renderer/shape_library_v1.json"
SUMMARY = ROOT / "artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md"


def test_weak_and_fail_are_not_usable_authority() -> None:
    assert classify_visual_status({"shape_point_count": 0, "polylines": []})[1] is False
    weak_shape = {
        "shape_point_count": 10,
        "polylines": [{"points": [[0, 0], [0.5, 0.5]], "point_count": 2}],
        "geometry_scores": {"stroke_coverage_score": 0.3, "geometry_precision_score": 0.4, "fragment_score": 0.4, "total": 30},
        "quality_flags": ["visual_review_required"],
    }
    status, usable, _ = classify_visual_status(weak_shape)
    assert status == "weak"
    assert usable is False


@pytest.mark.skipif(not LIBRARY.is_file(), reason="shape library not built")
def test_library_weak_fail_not_usable() -> None:
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    for shape in library.get("shapes") or []:
        if shape.get("visual_status") in ("weak", "fail"):
            assert shape["usable_as_shape_authority"] is False
        if shape.get("visual_status") == "pass":
            assert shape["usable_as_shape_authority"] is True


@pytest.mark.skipif(not SUMMARY.is_file(), reason="visual summary not built")
def test_summary_usable_count_matches_pass_only() -> None:
    text = SUMMARY.read_text(encoding="utf-8")
    pass_count = int(text.split("pass: ")[1].split("\n")[0])
    usable_count = int(text.split("usable_as_shape_authority: ")[1].split("\n")[0])
    assert usable_count == pass_count
