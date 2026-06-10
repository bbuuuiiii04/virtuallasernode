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
from tools.ai_shape_spatial_gate import build_laser_pixel_mask  # noqa: E402
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


def _laser_line_crop(y_line: int = LASER_Y) -> Image.Image:
    crop = Image.new("RGB", (CROP_W, CROP_H), (15, 15, 18))
    px = crop.load()
    for x in range(24, 96):
        px[x, y_line] = (255, 0, 255)
        if y_line > 0:
            px[x, y_line - 1] = (210, 50, 230)
    return crop


def _extracted_result_at_y(y: int, **overrides) -> dict:
    payload = {
        "shape_ref": "sh1_spatial00000001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.92,
        "image_width": CROP_W,
        "image_height": CROP_H,
        "paths_px": [[[30, y], [90, y], [90, y + 8], [30, y + 8], [30, y]]],
        "dot_anchors_px": [[24, y - 6]] if y == LASER_Y else [[24, y]],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "test spatial geometry",
    }
    payload.update(overrides)
    return validate_ai_extraction_result(payload)


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_geometry_far_below_laser_is_authority_ineligible() -> None:
    crop = _laser_line_crop()
    mask = build_laser_pixel_mask(crop)
    result = _extracted_result_at_y(130)
    assert result["status"] == "extracted"
    reason = explain_authority_ineligibility(result, laser_mask=mask)
    assert reason is not None
    assert reason.startswith("spatial_mismatch_")
    assert ai_result_eligible_for_authority(result, laser_mask=mask) is False


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_geometry_overlapping_laser_can_remain_eligible() -> None:
    crop = _laser_line_crop()
    mask = build_laser_pixel_mask(crop)
    result = _extracted_result_at_y(LASER_Y)
    assert explain_authority_ineligibility(result, laser_mask=mask) is None
    assert ai_result_eligible_for_authority(result, laser_mask=mask) is True


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_spatial_mismatch_reports_exact_gate_reason() -> None:
    crop = _laser_line_crop()
    mask = build_laser_pixel_mask(crop)
    result = _extracted_result_at_y(130)
    reason = explain_authority_ineligibility(result, laser_mask=mask)
    assert reason in {
        "spatial_mismatch_no_laser_overlap",
        "spatial_mismatch_bbox_far_from_laser",
    } or reason.startswith("spatial_mismatch_low_overlap_ratio=")


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_spatial_mismatch_keeps_extracted_status() -> None:
    crop = _laser_line_crop()
    mask = build_laser_pixel_mask(crop)
    raw = _extracted_result_at_y(130)
    assert raw["status"] == "extracted"
    assert explain_authority_ineligibility(raw, laser_mask=mask) is not None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_spatial_mismatch_rejected_overlay_not_yellow_by_default() -> None:
    crop = _laser_line_crop()
    mask = build_laser_pixel_mask(crop)
    result = _extracted_result_at_y(130)
    eligible = explain_authority_ineligibility(result, laser_mask=mask) is None
    assert eligible is False
    overlay = _render_ai_overlay(
        crop,
        result,
        authority_eligible=eligible,
        debug_draw_rejected=False,
    )
    assert overlay.getpixel((60, 130)) == crop.getpixel((60, 130))


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_debug_rejected_spatial_mismatch_draws_non_yellow() -> None:
    crop = _laser_line_crop()
    mask = build_laser_pixel_mask(crop)
    result = _extracted_result_at_y(130)
    eligible = explain_authority_ineligibility(result, laser_mask=mask) is None
    overlay = _render_ai_overlay(
        crop,
        result,
        authority_eligible=eligible,
        debug_draw_rejected=True,
    )
    sample = overlay.getpixel((60, 130))
    assert sample == REJECTED_DEBUG_OVERLAY_COLOR
    assert sample != AUTHORITY_OVERLAY_YELLOW
