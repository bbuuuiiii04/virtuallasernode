"""Pixel→wall conversion, y-flip, and authority rejection for AI extraction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ai_shape_geometry_convert import (  # noqa: E402
    AIExtractionValidationError,
    ai_result_eligible_for_authority,
    ai_result_to_shape_entry,
    convert_ai_px_to_wall_norm,
    validate_ai_extraction_result,
)
from tools.shape_extraction import ARTIFACT_VERSION, FixtureBox, compute_shape_ref  # noqa: E402

IMAGE_LEFT = FixtureBox(label="image_left", x0=60, y0=156, x1=554, y1=578)
CROP_W = IMAGE_LEFT.width
CROP_H = IMAGE_LEFT.height


def _base_result(**overrides):
    payload = {
        "shape_ref": "sh1_test000000000001",
        "status": "extracted",
        "geometry_kind": "centerline_polyline",
        "confidence": 0.9,
        "image_width": CROP_W,
        "image_height": CROP_H,
        "paths_px": [[[0, CROP_H // 2], [CROP_W - 1, CROP_H // 2]]],
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["green"],
        "failure_modes": [],
        "reason": "test centerline",
    }
    payload.update(overrides)
    return payload


def test_y_axis_flip_top_vs_bottom() -> None:
    _, y_top = convert_ai_px_to_wall_norm(
        CROP_W // 2, 0, box=IMAGE_LEFT, crop_width=CROP_W, crop_height=CROP_H
    )
    _, y_bottom = convert_ai_px_to_wall_norm(
        CROP_W // 2, CROP_H - 1, box=IMAGE_LEFT, crop_width=CROP_W, crop_height=CROP_H
    )
    assert y_top > y_bottom


def test_center_point_near_zero() -> None:
    x, y = convert_ai_px_to_wall_norm(
        CROP_W / 2, CROP_H / 2, box=IMAGE_LEFT, crop_width=CROP_W, crop_height=CROP_H
    )
    assert abs(x) < 0.05
    assert abs(y) < 0.05


def test_out_of_box_point_rejected_not_clamped() -> None:
    with pytest.raises(AIExtractionValidationError):
        convert_ai_px_to_wall_norm(-1, 0, box=IMAGE_LEFT, crop_width=CROP_W, crop_height=CROP_H)
    with pytest.raises(AIExtractionValidationError):
        convert_ai_px_to_wall_norm(CROP_W, 0, box=IMAGE_LEFT, crop_width=CROP_W, crop_height=CROP_H)


def test_validate_rejects_out_of_bounds_paths() -> None:
    with pytest.raises(AIExtractionValidationError):
        validate_ai_extraction_result(_base_result(paths_px=[[[CROP_W + 5, 10], [20, 20]]]))


def test_uncertain_failed_low_confidence_not_authority() -> None:
    assert ai_result_eligible_for_authority(_base_result(status="uncertain")) is False
    assert ai_result_eligible_for_authority(_base_result(status="failed")) is False
    assert ai_result_eligible_for_authority(_base_result(confidence=0.5)) is False
    assert ai_result_eligible_for_authority(_base_result(geometry_kind="unknown")) is False
    assert ai_result_eligible_for_authority(_base_result(failure_modes=["low_confidence"])) is False


def test_high_confidence_extracted_is_authority_eligible() -> None:
    assert ai_result_eligible_for_authority(_base_result()) is True


def test_ai_result_to_shape_entry_produces_wall_norm_polylines() -> None:
    entry = ai_result_to_shape_entry(
        _base_result(),
        box=IMAGE_LEFT,
        vector_key="v1:0",
        capture_path="phase1/test",
        source_still="captures/fixture_model/phase1/test/still.jpg",
        fixture_box_label="image_left",
    )
    pts = entry["polylines"][0]["points"]
    assert all(len(p) == 2 for p in pts)
    assert entry["usable_as_shape_authority"] is True
    assert len(pts) >= 2


def test_ai_result_to_shape_entry_uses_repo_shape_ref_not_ai_value() -> None:
    wrong_ref = "sh1_ai_hallucinated0001"
    vector_key = "v1:0,0,32,0,90,128,128,0,0,0,0,0,0,0,0,0,0,0,0"
    capture_path = "phase1/test"
    fixture_box_label = "image_left"
    expected = compute_shape_ref(ARTIFACT_VERSION, vector_key, capture_path, fixture_box_label)
    entry = ai_result_to_shape_entry(
        _base_result(shape_ref=wrong_ref),
        box=IMAGE_LEFT,
        vector_key=vector_key,
        capture_path=capture_path,
        source_still="captures/fixture_model/phase1/test/still.jpg",
        fixture_box_label=fixture_box_label,
    )
    assert entry["shape_ref"] == expected
    assert entry["shape_ref"] != wrong_ref
    assert entry["ai_extraction"]["ai_returned_shape_ref"] == wrong_ref
