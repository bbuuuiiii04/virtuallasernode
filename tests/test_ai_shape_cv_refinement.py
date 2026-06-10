"""CV refinement snaps Gemini topology hints to laser-core pixels."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ai_shape_cv_refinement import (  # noqa: E402
    HALO_FLOOD_COMPONENT,
    RECONSTRUCTION_BLOB_TOO_FILLED,
    RECON_HINT_GUIDED,
    RECON_MERGED_SPLIT,
    TOPOLOGY_MISMATCH_PARTIAL_LOOP,
    apply_cv_refinement_to_result,
    build_morphology_candidate_mask,
    collect_strict_core_pixels,
    component_stroke_failure,
    extract_strict_core_components,
    reconstruct_components_hint_guided,
    refine_ai_geometry_against_core,
    split_merged_loop_component,
    _component_fill_ratio,
    _estimate_global_shift,
    _validation_mask,
)
from tools.ai_shape_geometry_convert import explain_authority_ineligibility  # noqa: E402
from tools.ai_shape_spatial_gate import build_laser_spatial_masks  # noqa: E402
from tools.ai_shape_extractor import (  # noqa: E402
    AUTHORITY_OVERLAY_YELLOW,
    DEBUG_CONTEXT_CROP_OUTLINE,
    DEBUG_CONTEXT_REJECTED_MASK,
    DEBUG_CONTEXT_STRICT_CORE_PIXEL,
    REJECTED_DEBUG_OVERLAY_COLOR,
    _render_ai_overlay,
)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

REGRESSION_W = 200
REGRESSION_H = 400
CORE_Y0 = 178
CORE_Y1 = 216
GEO_Y0 = 230
GEO_Y1 = 250
Y_OFFSET = 42


def _regression_crop_with_core() -> Image.Image:
    crop = Image.new("RGB", (REGRESSION_W, REGRESSION_H), (15, 15, 18))
    px = crop.load()
    for y in range(CORE_Y0, CORE_Y1 + 1):
        for x in range(60, 141):
            if y in (CORE_Y0, CORE_Y1) or x in (60, 140):
                px[x, y] = (255, 0, 255)
    return crop


def _gemini_geometry_low_placement(*, include_dot: bool = False) -> dict:
    payload = {
        "shape_ref": "sh1_cv_refine00000001",
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
        "dot_anchors_px": [[52, GEO_Y0 - 4]] if include_dot else [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "semantic shape placed too low",
    }
    return payload


def _draw_hollow_square(
    px,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
    *,
    skip_corners: set[tuple[int, int]] | None = None,
) -> None:
    blocked = skip_corners or set()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if y in (y0, y1) or x in (x0, x1):
                if (x, y) in blocked:
                    continue
                px[x, y] = color


def _four_squares_crop(*, merged_bridges: bool = False, fragmented: bool = False) -> Image.Image:
    crop = Image.new("RGB", (320, 120), (15, 15, 18))
    px = crop.load()
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    skip: set[tuple[int, int]] = set()
    if fragmented:
        skip = {(40, 40), (60, 60), (70, 40), (150, 60)}
    for x0, y0, x1, y1 in squares:
        _draw_hollow_square(px, x0, y0, x1, y1, (255, 0, 255), skip_corners=skip)
    if merged_bridges:
        for y in range(48, 53):
            for x in range(60, 71):
                px[x, y] = (255, 0, 255)
            for x in range(90, 101):
                px[x, y] = (255, 0, 255)
            for x in range(120, 131):
                px[x, y] = (255, 0, 255)
    return crop


def _four_offset_gemini_paths(squares: list[tuple[int, int, int, int]], *, offset: int = 42) -> list[list[list[float]]]:
    paths: list[list[list[float]]] = []
    for x0, y0, x1, y1 in squares:
        gy0, gy1 = y0 + offset, y1 + offset
        paths.append([[x0, gy0], [x1, gy0], [x1, gy1], [x0, gy1], [x0, gy0]])
    return paths

def _path_on_strict_core(path: list[list[float]], strict_core: list[list[bool]]) -> bool:
    for x, y in path:
        xi, yi = int(round(x)), int(round(y))
        if not strict_core[yi][xi]:
            return False
    return True


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_raw_gemini_low_placement_fails_spatial_gate() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    reason = explain_authority_ineligibility(result, laser_mask=masks)
    assert reason is not None
    assert "spatial_mismatch" in reason


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_cv_refinement_matches_component_and_passes_authority() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    refinement = refine_ai_geometry_against_core(result, masks)
    assert refinement.applied is True
    assert refinement.reason == "core_component_matched"
    assert refinement.matched_component_ids == [0]
    assert refinement.global_shift_px is not None
    assert refinement.global_shift_px[1] < -30

    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    assert result["cv_refinement"]["matched_component_ids"] == [0]
    assert result["gemini_raw_geometry"]["paths_px"][0][0][1] == GEO_Y0
    assert explain_authority_ineligibility(result, laser_mask=masks) is None
    assert _path_on_strict_core(result["paths_px"][0], masks.strict_core)


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_refinement_preserves_raw_gemini_geometry_separately() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    apply_cv_refinement_to_result(result, masks)
    assert result["paths_px"] != result["gemini_raw_geometry"]["paths_px"]
    assert result["gemini_raw_geometry"]["paths_px"][0][0] == [60, GEO_Y0]


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_refinement_fails_without_core_components() -> None:
    crop = Image.new("RGB", (REGRESSION_W, REGRESSION_H), (15, 15, 18))
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    refinement = refine_ai_geometry_against_core(result, masks)
    assert refinement.applied is False
    assert refinement.reason == "no_core_components"


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_globally_shifted_boxes_without_component_match_cannot_become_authority() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    result["paths_px"] = [
        result["paths_px"][0],
        [[10, GEO_Y0], [20, GEO_Y0], [20, GEO_Y1], [10, GEO_Y1], [10, GEO_Y0]],
    ]
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is False
    assert result["cv_refinement"]["reason"] in {"component_match_failed", "merged_component_split_required"}
    reason = explain_authority_ineligibility(result, laser_mask=masks)
    assert reason in {"topology_mismatch_no_component_match", "merged_component_split_required"}


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_multi_loop_authority_requires_matched_component_ids() -> None:
    crop = Image.new("RGB", (220, 260), (15, 15, 18))
    px = crop.load()
    squares = [(40, 60, 80, 100), (120, 60, 160, 100), (40, 130, 80, 170), (120, 130, 160, 170)]
    for x0, y0, x1, y1 in squares:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y in (y0, y1) or x in (x0, x1):
                    px[x, y] = (255, 0, 255)
    masks = build_laser_spatial_masks(crop)
    paths = []
    for x0, y0, x1, y1 in squares:
        gy0, gy1 = y0 + Y_OFFSET, y1 + Y_OFFSET
        paths.append([[x0, gy0], [x1, gy0], [x1, gy1], [x0, gy1], [x0, gy0]])
    result = {
        "shape_ref": "sh1_four_loops000001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.9,
        "image_width": 220,
        "image_height": 260,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "four offset squares",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    matched = result["cv_refinement"]["matched_component_ids"]
    assert matched is not None
    assert len(matched) == 4
    assert explain_authority_ineligibility(result, laser_mask=masks) is None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_partial_leading_box_is_not_treated_as_true_dot_authority() -> None:
    crop = Image.new("RGB", (120, 120), (15, 15, 18))
    px = crop.load()
    for y in range(40, 61):
        for x in range(40, 61):
            if y in (40, 60) or x in (40, 60):
                px[x, y] = (255, 0, 255)
    for y in range(42, 45):
        for x in range(38, 41):
            px[x, y] = (255, 0, 255)
    masks = build_laser_spatial_masks(crop)
    result = {
        "shape_ref": "sh1_partial_dot00001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.9,
        "image_width": 120,
        "image_height": 120,
        "paths_px": [[[40, 82], [60, 82], [60, 102], [40, 102], [40, 82]]],
        "dot_anchors_px": [[39, 80]],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "dot near partial fragment",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    assert TOPOLOGY_MISMATCH_PARTIAL_LOOP in result["cv_refinement"].get("dot_topology_warnings", [])
    assert not result["dot_anchors_px"]
    assert explain_authority_ineligibility(result, laser_mask=masks) is None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_contact_sheet_yellow_refined_cyan_raw_debug_only() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    apply_cv_refinement_to_result(result, masks)
    eligible = explain_authority_ineligibility(result, laser_mask=masks) is None
    assert eligible is True

    authority_geometry = {
        "paths_px": result["paths_px"],
        "dot_anchors_px": result["dot_anchors_px"],
        "segment_anchors_px": result["segment_anchors_px"],
    }
    raw_geometry = result["gemini_raw_geometry"]

    default_overlay = _render_ai_overlay(
        crop,
        authority_geometry=authority_geometry,
        raw_geometry=raw_geometry,
        authority_eligible=True,
        debug_draw_rejected=False,
    )
    core_sample_y = CORE_Y0
    assert any(
        default_overlay.getpixel((int(x), int(y))) == AUTHORITY_OVERLAY_YELLOW
        for path in result["paths_px"]
        for x, y in path
    )
    assert default_overlay.getpixel((100, GEO_Y0)) != REJECTED_DEBUG_OVERLAY_COLOR

    debug_overlay = _render_ai_overlay(
        crop,
        authority_geometry=authority_geometry,
        raw_geometry=raw_geometry,
        authority_eligible=True,
        debug_draw_rejected=True,
    )
    assert any(
        debug_overlay.getpixel((int(x), int(y))) == AUTHORITY_OVERLAY_YELLOW
        for path in result["paths_px"]
        for x, y in path
    )
    assert debug_overlay.getpixel((100, GEO_Y0)) == REJECTED_DEBUG_OVERLAY_COLOR


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_contact_sheet_debug_context_overlays_do_not_change_authority_colors() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement())
    apply_cv_refinement_to_result(result, masks)
    authority_geometry = {
        "paths_px": result["paths_px"],
        "dot_anchors_px": result["dot_anchors_px"],
        "segment_anchors_px": result["segment_anchors_px"],
    }
    debug_context = {
        "selected_fixture_box": "image_left",
        "strict_core_pixels": collect_strict_core_pixels(masks),
        "core_component_bboxes": result["cv_refinement"]["core_component_bboxes"],
        "core_component_classes": result["cv_refinement"]["core_component_classes"],
        "matched_component_ids": result["cv_refinement"]["matched_component_ids"],
    }
    overlay = _render_ai_overlay(
        crop,
        authority_geometry=authority_geometry,
        raw_geometry=result["gemini_raw_geometry"],
        authority_eligible=True,
        debug_context=debug_context,
    )
    plain = _render_ai_overlay(
        crop,
        authority_geometry=authority_geometry,
        raw_geometry=result["gemini_raw_geometry"],
        authority_eligible=True,
    )
    assert plain.getpixel((0, 0)) != DEBUG_CONTEXT_CROP_OUTLINE
    assert overlay.getpixel((0, 0)) == DEBUG_CONTEXT_CROP_OUTLINE
    assert any(
        overlay.getpixel((int(x), int(y))) == AUTHORITY_OVERLAY_YELLOW
        for path in result["paths_px"]
        for x, y in path
    )
    assert len(collect_strict_core_pixels(masks)) > 0
    ctx_only = _render_ai_overlay(
        crop,
        authority_geometry=None,
        raw_geometry=None,
        authority_eligible=False,
        debug_context=debug_context,
    )
    assert any(
        ctx_only.getpixel((pt[0], pt[1])) == DEBUG_CONTEXT_STRICT_CORE_PIXEL
        for pt in collect_strict_core_pixels(masks)[:40]
    )


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_fragmented_hollow_square_strokes_reconstruct_into_loop_components() -> None:
    crop = _four_squares_crop(fragmented=True)
    masks = build_laser_spatial_masks(crop)
    morph = build_morphology_candidate_mask(masks)
    morph_components = extract_strict_core_components(morph)
    assert len(morph_components) >= 4
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    shift = (0.0, -42.0)
    hint_components = reconstruct_components_hint_guided(masks.strict_core, paths, shift)
    assert len(hint_components) == 4
    for comp in hint_components:
        assert comp.component_class in ("loop_like", "partial_fragment")
        assert len(comp.pixels) >= 6


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_merged_four_square_loops_match_with_hint_guided_reconstruction() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    result = {
        "shape_ref": "sh1_merged_four00001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "four merged square loops",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    assert result["cv_refinement"]["reconstruction_method"] == RECON_MERGED_SPLIT
    assert result["cv_refinement"]["matched_component_ids"] == [0, 1, 2, 3]
    assert result["cv_refinement"]["parent_component_bbox"] is not None
    assert len(result["cv_refinement"]["split_child_bboxes"]) == 4
    assert result["paths_px"] != result["gemini_raw_geometry"]["paths_px"]
    assert explain_authority_ineligibility(result, laser_mask=masks) is None
    for path in result["paths_px"]:
        assert _path_on_strict_core(path, masks.strict_core)


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_raw_gemini_offset_remains_debug_only() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    result = {
        "shape_ref": "sh1_raw_debug00001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "offset debug only",
    }
    apply_cv_refinement_to_result(result, masks)
    overlay = _render_ai_overlay(
        crop,
        authority_geometry={
            "paths_px": result["paths_px"],
            "dot_anchors_px": [],
            "segment_anchors_px": [],
        },
        raw_geometry=result["gemini_raw_geometry"],
        authority_eligible=True,
        debug_draw_rejected=True,
    )
    assert overlay.getpixel((50, 82)) == REJECTED_DEBUG_OVERLAY_COLOR
    assert overlay.getpixel((50, 40)) == AUTHORITY_OVERLAY_YELLOW


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_merged_strict_core_blob_splits_into_four_child_components() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    strict = extract_strict_core_components(_validation_mask(masks))
    assert len(strict) == 1
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    morph = extract_strict_core_components(build_morphology_candidate_mask(masks))
    hint_pts = [(float(p[0]), float(p[1])) for path in paths for p in path]
    shift = _estimate_global_shift(hint_pts, morph)
    split = split_merged_loop_component(strict[0], paths, shift, masks.strict_core)
    assert split is not None
    children, debug = split
    assert len(children) == 4
    assert debug.parent_component_bbox == [40, 40, 150, 60]
    assert len(debug.split_child_bboxes) == 4
    assert debug.split_child_match_ids == [0, 1, 2, 3]


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_four_gemini_loops_match_four_split_children() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    result = {
        "shape_ref": "sh1_split_match0001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "four split children",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    assert result["cv_refinement"]["split_child_match_ids"] == [0, 1, 2, 3]
    assert explain_authority_ineligibility(result, laser_mask=masks) is None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_no_authority_when_split_overlap_is_poor() -> None:
    crop = Image.new("RGB", (320, 120), (15, 15, 18))
    px = crop.load()
    for x0, x1 in [(40, 60), (70, 90)]:
        for y in range(40, 61):
            for x in range(x0, x1 + 1):
                if y in (40, 60) or x in (x0, x1):
                    px[x, y] = (255, 0, 255)
    masks = build_laser_spatial_masks(crop)
    paths = _four_offset_gemini_paths(
        [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    )
    result = {
        "shape_ref": "sh1_poor_split0001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "only two physical loops",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is False
    assert explain_authority_ineligibility(result, laser_mask=masks) is not None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_yellow_overlay_uses_split_child_geometry_only() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    result = {
        "shape_ref": "sh1_yellow_split0001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "yellow from split children",
    }
    apply_cv_refinement_to_result(result, masks)
    overlay = _render_ai_overlay(
        crop,
        authority_geometry={"paths_px": result["paths_px"], "dot_anchors_px": [], "segment_anchors_px": []},
        raw_geometry=result["gemini_raw_geometry"],
        authority_eligible=True,
        debug_draw_rejected=True,
    )
    assert any(
        overlay.getpixel((int(x), int(y))) == AUTHORITY_OVERLAY_YELLOW
        for path in result["paths_px"]
        for x, y in path
    )
    assert overlay.getpixel((50, 82)) == REJECTED_DEBUG_OVERLAY_COLOR
    assert overlay.getpixel((50, 40)) != REJECTED_DEBUG_OVERLAY_COLOR


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_gemini_dot_on_loop_blocks_authority() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    result = dict(_gemini_geometry_low_placement(include_dot=True))
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    assert TOPOLOGY_MISMATCH_PARTIAL_LOOP in result["cv_refinement"].get("dot_topology_warnings", [])
    assert not result["dot_anchors_px"]
    assert explain_authority_ineligibility(result, laser_mask=masks) is None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_component_derived_geometry_aligns_with_core_pixels() -> None:
    crop = _regression_crop_with_core()
    masks = build_laser_spatial_masks(crop)
    components = extract_strict_core_components(masks.strict_core)
    result = dict(_gemini_geometry_low_placement())
    refinement = refine_ai_geometry_against_core(result, masks)
    assert refinement.applied is True
    for path in refinement.paths_px:
        assert _path_on_strict_core(path, masks.strict_core)
    assert refinement.matched_component_ids == [components[0].component_id]


def _glow_flood_crop() -> Image.Image:
    crop = Image.new("RGB", (320, 120), (15, 15, 18))
    px = crop.load()
    for y in range(45, 96):
        for x in range(50, 260):
            px[x, y] = (255, 0, 255)
    return crop


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_halo_bloom_flood_blob_is_rejected() -> None:
    crop = _glow_flood_crop()
    masks = build_laser_spatial_masks(crop)
    paths = _four_offset_gemini_paths(
        [(60, 45, 90, 75), (110, 45, 140, 75), (160, 45, 190, 75), (210, 45, 240, 75)]
    )
    result = {
        "shape_ref": "sh1_halo_flood0001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "glow flood blob",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is False
    assert result["status"] == "extracted"
    assert result["authority_eligible"] is False if "authority_eligible" in result else True
    reason = result["cv_refinement"]["reason"]
    assert reason in {HALO_FLOOD_COMPONENT, RECONSTRUCTION_BLOB_TOO_FILLED, "merged_component_split_required", "component_match_failed"}
    assert explain_authority_ineligibility(result, laser_mask=masks) is not None


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_filled_parent_mask_cannot_become_authority() -> None:
    crop = _glow_flood_crop()
    masks = build_laser_spatial_masks(crop)
    parent = extract_strict_core_components(_validation_mask(masks))
    assert parent
    assert component_stroke_failure(parent[0]) in {HALO_FLOOD_COMPONENT, RECONSTRUCTION_BLOB_TOO_FILLED}


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_authority_geometry_has_low_fill_ratio() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    paths = _four_offset_gemini_paths(
        [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    )
    result = {
        "shape_ref": "sh1_stroke_fill0001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "stroke-like loops",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["applied"] is True
    components = extract_strict_core_components(_validation_mask(masks))
    split = split_merged_loop_component(components[0], paths, (0.0, -40.0), masks.strict_core)
    assert split is not None
    children, _ = split
    for child in children:
        assert _component_fill_ratio(child) <= 0.32


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_hint_guided_reconstruction_is_not_authority_path() -> None:
    crop = _four_squares_crop(merged_bridges=True)
    masks = build_laser_spatial_masks(crop)
    squares = [(40, 40, 60, 60), (70, 40, 90, 60), (100, 40, 120, 60), (130, 40, 150, 60)]
    paths = _four_offset_gemini_paths(squares)
    result = {
        "shape_ref": "sh1_no_hint_auth0001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "no hint guided authority",
    }
    apply_cv_refinement_to_result(result, masks)
    assert result["cv_refinement"]["reconstruction_method"] != RECON_HINT_GUIDED


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_rejected_debug_mask_never_counts_as_authority() -> None:
    crop = _glow_flood_crop()
    masks = build_laser_spatial_masks(crop)
    paths = _four_offset_gemini_paths(
        [(60, 45, 90, 75), (110, 45, 140, 75), (160, 45, 190, 75), (210, 45, 240, 75)]
    )
    result = {
        "shape_ref": "sh1_reject_debug001",
        "status": "extracted",
        "geometry_kind": "closed_loop_contour",
        "confidence": 0.95,
        "image_width": 320,
        "image_height": 120,
        "paths_px": paths,
        "dot_anchors_px": [],
        "segment_anchors_px": [],
        "color_coverage": ["magenta"],
        "failure_modes": [],
        "reason": "debug mask non-authority",
    }
    apply_cv_refinement_to_result(result, masks)
    rejected = result["cv_refinement"].get("rejected_debug_pixels") or []
    overlay = _render_ai_overlay(
        crop,
        authority_geometry={"paths_px": result["paths_px"], "dot_anchors_px": [], "segment_anchors_px": []},
        raw_geometry=result["gemini_raw_geometry"],
        authority_eligible=False,
        debug_draw_rejected=True,
        debug_context={
            "rejected_debug_pixels": rejected,
            "rejection_reason": result["cv_refinement"]["reason"],
            "strict_core_pixels": collect_strict_core_pixels(masks),
        },
    )
    assert not any(
        overlay.getpixel((int(x), int(y))) == AUTHORITY_OVERLAY_YELLOW
        for path in result["paths_px"]
        for x, y in path
    )
    if rejected:
        x, y = rejected[0]
        assert overlay.getpixel((int(x), int(y))) == DEBUG_CONTEXT_REJECTED_MASK
