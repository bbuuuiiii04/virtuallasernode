"""Spatial authority sanity gate for AI extraction geometry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ai_shape_geometry_convert import (  # noqa: E402
    ai_result_eligible_for_authority,
    explain_authority_ineligibility,
    validate_ai_extraction_result,
)
from tools.ai_shape_spatial_gate import build_laser_spatial_masks  # noqa: E402
from tools.ai_shape_extractor import (  # noqa: E402
    AUTHORITY_OVERLAY_YELLOW,
    REJECTED_DEBUG_OVERLAY_COLOR,
    _render_ai_overlay,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

CROP_W = 120
CROP_H = 160
LASER_Y = 42

REGRESSION_W = 200
REGRESSION_H = 400
CORE_Y0 = 178
CORE_Y1 = 216
GEO_Y0 = 230
GEO_Y1 = 250


def _laser_line_crop(y_line: int = LASER_Y) -> Image.Image:
    crop = Image.new("RGB", (CROP_W, CROP_H), (15, 15, 18))
    px = crop.load()
    for x in range(24, 96):
        px[x, y_line] = (255, 0, 255)
        if y_line > 0:
            px[x, y_line - 1] = (210, 50, 230)
    return crop


def _extracted_result_at_y(y: int, *, width: int = CROP_W, height: int = CROP_H, **overrides) -> dict:
    payload = {
        "shape_ref": "sh1_spatial00000001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.92,
        "image_width": width,
        "image_height": height,
        "paths_px": [[[30, y], [90, y], [90, y + 4], [30, y + 4], [30, y]]],
        "dot_anchors_px": [[50, y + 2]],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "test spatial geometry",
    }
    payload.update(overrides)
    return validate_ai_extraction_result(payload)


def _regression_crop_with_core_and_glow() -> Image.Image:
    """Laser core around y=178..216 with softer glow below; geometry placed too low."""
    crop = Image.new("RGB", (REGRESSION_W, REGRESSION_H), (15, 15, 18))
    px = crop.load()
    for y in range(CORE_Y0, CORE_Y1 + 1):
        for x in range(60, 141):
            on_edge = y in (CORE_Y0, CORE_Y1) or x in (60, 140)
            if on_edge:
                px[x, y] = (255, 0, 255)
    return crop


def _regression_geometry_too_low() -> dict:
    return validate_ai_extraction_result(
        {
            "shape_ref": "sh1_gemini_low_placement01",
            "status": "extracted",
            "geometry_kind": "closed_loop_contour",
            "confidence": 0.93,
            "image_width": REGRESSION_W,
            "image_height": REGRESSION_H,
            "paths_px": [
                [
                    [60, GEO_Y0],
                    [140, GEO_Y0],
                    [140, GEO_Y1],
                    [60, GEO_Y1],
                    [60, GEO_Y0],
                ]
            ],
            "dot_anchors_px": [[52, GEO_Y0 - 4]],
            "segment_anchors_px": [],
            "color_coverage": ["magenta"],
            "failure_modes": [],
            "reason": "semantic shape placed too low",
        }
    )


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_gemini_low_placement_regression_core_178_geometry_230() -> None:
    crop = _regression_crop_with_core_and_glow()
    masks = build_laser_spatial_masks(crop)
    result = _regression_geometry_too_low()
    assert result["status"] == "extracted"
    reason = explain_authority_ineligibility(result, laser_mask=masks)
    assert reason == "spatial_mismatch_bbox_y_disjoint"
    assert ai_result_eligible_for_authority(result, laser_mask=masks) is False


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_geometry_far_below_laser_is_authority_ineligible() -> None:
    crop = _laser_line_crop()
    masks = build_laser_spatial_masks(crop)
    result = _extracted_result_at_y(130)
    assert result["status"] == "extracted"
    reason = explain_authority_ineligibility(result, laser_mask=masks)
    assert reason is not None
    assert reason.startswith("spatial_mismatch_")
    assert ai_result_eligible_for_authority(result, laser_mask=masks) is False


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_geometry_overlapping_laser_can_remain_eligible() -> None:
    crop = _laser_line_crop()
    masks = build_laser_spatial_masks(crop)
    result = _extracted_result_at_y(LASER_Y)
    assert explain_authority_ineligibility(result, laser_mask=masks) is None
    assert ai_result_eligible_for_authority(result, laser_mask=masks) is True


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_spatial_mismatch_reports_exact_gate_reason() -> None:
    crop = _laser_line_crop()
    masks = build_laser_spatial_masks(crop)
    result = _extracted_result_at_y(130)
    reason = explain_authority_ineligibility(result, laser_mask=masks)
    assert reason in {
        "spatial_mismatch_no_laser_overlap",
        "spatial_mismatch_bbox_y_disjoint",
        "spatial_mismatch_bbox_far_from_laser",
    } or reason.startswith(
        (
            "spatial_mismatch_low_overlap_ratio=",
            "spatial_mismatch_core_overlap_low=",
            "spatial_mismatch_y_offset_px=",
        )
    )


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_spatial_mismatch_keeps_extracted_status() -> None:
    crop = _regression_crop_with_core_and_glow()
    masks = build_laser_spatial_masks(crop)
    raw = _regression_geometry_too_low()
    assert raw["status"] == "extracted"
    assert explain_authority_ineligibility(raw, laser_mask=masks) is not None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_spatial_mismatch_rejected_overlay_not_yellow_by_default() -> None:
    crop = _regression_crop_with_core_and_glow()
    masks = build_laser_spatial_masks(crop)
    result = _regression_geometry_too_low()
    eligible = explain_authority_ineligibility(result, laser_mask=masks) is None
    assert eligible is False
    raw_geometry = {
        "paths_px": result["paths_px"],
        "dot_anchors_px": result["dot_anchors_px"],
        "segment_anchors_px": result["segment_anchors_px"],
    }
    overlay = _render_ai_overlay(
        crop,
        authority_geometry=None,
        raw_geometry=raw_geometry,
        authority_eligible=False,
        debug_draw_rejected=False,
    )
    assert overlay.getpixel((100, GEO_Y0)) == crop.getpixel((100, GEO_Y0))


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_debug_rejected_spatial_mismatch_draws_non_yellow() -> None:
    crop = _regression_crop_with_core_and_glow()
    masks = build_laser_spatial_masks(crop)
    result = _regression_geometry_too_low()
    assert explain_authority_ineligibility(result, laser_mask=masks) is not None
    raw_geometry = {
        "paths_px": result["paths_px"],
        "dot_anchors_px": result["dot_anchors_px"],
        "segment_anchors_px": result["segment_anchors_px"],
    }
    overlay = _render_ai_overlay(
        crop,
        authority_geometry=None,
        raw_geometry=raw_geometry,
        authority_eligible=False,
        debug_draw_rejected=True,
    )
    sample = overlay.getpixel((100, GEO_Y0))
    assert sample == REJECTED_DEBUG_OVERLAY_COLOR
    assert sample != AUTHORITY_OVERLAY_YELLOW
