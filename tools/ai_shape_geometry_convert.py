"""Validate and convert AI pixel-space extraction results to wall-normal shape geometry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.shape_extraction import (
    ARTIFACT_VERSION,
    FixtureBox,
    bbox_wall_norm_from_pixel_bbox,
    compute_shape_ref,
    pixel_to_wall_norm,
)

from tools.ai_shape_spatial_gate import LaserSpatialMasks, explain_spatial_authority_mismatch

AI_EXTRACTION_STATUSES = frozenset({"extracted", "uncertain", "failed"})
AI_GEOMETRY_KINDS = frozenset(
    {
        "centerline_polyline",
        "branch_polyline",
        "dot_anchor_points",
        "segment_anchor_points",
        "closed_loop_contour",
        "unknown",
    }
)
AI_FAILURE_MODES = frozenset(
    {
        "halo_or_glow",
        "fragment_only",
        "uncertain_dots",
        "missed_color_span",
        "wrong_fixture",
        "low_confidence",
        "ambiguous_shape",
    }
)
AI_COLOR_COVERAGE = frozenset(
    {"red", "green", "blue", "cyan", "magenta", "yellow", "white"}
)
AI_COLOR_ALIASES = {
    "purple": "magenta",
    "violet": "magenta",
}

DEFAULT_MIN_AUTHORITY_CONFIDENCE = 0.75


class AIExtractionValidationError(ValueError):
    """Raised when an AI extraction payload is structurally or geometrically invalid."""


def _is_point_pair(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    )


def _validate_point_list(name: str, points: Any, *, image_width: int, image_height: int) -> list[list[float]]:
    if not isinstance(points, list):
        raise AIExtractionValidationError(f"{name} must be an array")
    out: list[list[float]] = []
    for idx, pt in enumerate(points):
        if not _is_point_pair(pt):
            raise AIExtractionValidationError(f"{name}[{idx}] must be [x, y]")
        x, y = float(pt[0]), float(pt[1])
        if x < 0 or y < 0 or x >= image_width or y >= image_height:
            raise AIExtractionValidationError(
                f"{name}[{idx}] out of image bounds: ({x}, {y}) not in "
                f"[0, {image_width}) x [0, {image_height})"
            )
        out.append([x, y])
    return out


def _validate_paths(name: str, paths: Any, *, image_width: int, image_height: int) -> list[list[list[float]]]:
    if not isinstance(paths, list):
        raise AIExtractionValidationError(f"{name} must be an array")
    validated: list[list[list[float]]] = []
    for pidx, path in enumerate(paths):
        validated.append(
            _validate_point_list(f"{name}[{pidx}]", path, image_width=image_width, image_height=image_height)
        )
    return validated


def normalize_ai_color_coverage(colors: Any) -> list[str]:
    """Map AI color aliases to canonical coverage tokens; reject unknown colors."""
    if not isinstance(colors, list):
        raise AIExtractionValidationError("color_coverage must be an array")
    normalized: list[str] = []
    seen: set[str] = set()
    for color in colors:
        if not isinstance(color, str):
            raise AIExtractionValidationError(f"unsupported color_coverage value: {color!r}")
        token = color.strip().lower()
        canonical = AI_COLOR_ALIASES.get(token, token)
        if canonical not in AI_COLOR_COVERAGE:
            raise AIExtractionValidationError(f"unsupported color_coverage value: {color!r}")
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return normalized


def validate_ai_extraction_result(result: dict[str, Any]) -> dict[str, Any]:
    """Structural validation; raises AIExtractionValidationError on invalid payloads."""
    if not isinstance(result, dict):
        raise AIExtractionValidationError("AI extraction result must be an object")

    shape_ref = result.get("shape_ref")
    if not isinstance(shape_ref, str) or not shape_ref.strip():
        raise AIExtractionValidationError("shape_ref must be a non-empty string")

    status = result.get("status")
    if status not in AI_EXTRACTION_STATUSES:
        raise AIExtractionValidationError(f"status must be one of {sorted(AI_EXTRACTION_STATUSES)}")

    geometry_kind = result.get("geometry_kind")
    if geometry_kind not in AI_GEOMETRY_KINDS:
        raise AIExtractionValidationError(f"geometry_kind must be one of {sorted(AI_GEOMETRY_KINDS)}")

    confidence = result.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
        raise AIExtractionValidationError("confidence must be a number in [0, 1]")

    image_width = result.get("image_width")
    image_height = result.get("image_height")
    if not isinstance(image_width, int) or image_width <= 0:
        raise AIExtractionValidationError("image_width must be a positive integer")
    if not isinstance(image_height, int) or image_height <= 0:
        raise AIExtractionValidationError("image_height must be a positive integer")

    paths_px = _validate_paths(
        "paths_px", result.get("paths_px", []), image_width=image_width, image_height=image_height
    )
    dot_anchors_px = _validate_point_list(
        "dot_anchors_px",
        result.get("dot_anchors_px", []),
        image_width=image_width,
        image_height=image_height,
    )

    segment_anchors_px: list[list[list[float]]] = []
    raw_segments = result.get("segment_anchors_px", [])
    if not isinstance(raw_segments, list):
        raise AIExtractionValidationError("segment_anchors_px must be an array")
    for sidx, segment in enumerate(raw_segments):
        if not isinstance(segment, list) or len(segment) != 2:
            raise AIExtractionValidationError(f"segment_anchors_px[{sidx}] must be [[x0,y0],[x1,y1]]")
        segment_anchors_px.append(
            _validate_point_list(
                f"segment_anchors_px[{sidx}]",
                segment,
                image_width=image_width,
                image_height=image_height,
            )
        )

    mask_path = result.get("mask_path")
    if mask_path is not None and not isinstance(mask_path, str):
        raise AIExtractionValidationError("mask_path must be a string when present")

    color_coverage = normalize_ai_color_coverage(result.get("color_coverage", []))

    failure_modes = result.get("failure_modes", [])
    if not isinstance(failure_modes, list):
        raise AIExtractionValidationError("failure_modes must be an array")
    for mode in failure_modes:
        if mode not in AI_FAILURE_MODES:
            raise AIExtractionValidationError(f"unsupported failure_modes value: {mode!r}")

    reason = result.get("reason")
    if not isinstance(reason, str):
        raise AIExtractionValidationError("reason must be a string")

    return {
        "shape_ref": shape_ref,
        "status": status,
        "geometry_kind": geometry_kind,
        "confidence": float(confidence),
        "image_width": image_width,
        "image_height": image_height,
        "paths_px": paths_px,
        "dot_anchors_px": dot_anchors_px,
        "segment_anchors_px": segment_anchors_px,
        "mask_path": mask_path,
        "color_coverage": list(color_coverage),
        "failure_modes": list(failure_modes),
        "reason": reason,
    }


def convert_ai_px_to_wall_norm(
    px: float,
    py: float,
    *,
    box: FixtureBox,
    crop_width: int,
    crop_height: int,
) -> tuple[float, float]:
    """Convert cropped-image pixel coords to wall-normal; y increases up on wall."""
    if px < 0 or py < 0 or px >= crop_width or py >= crop_height:
        raise AIExtractionValidationError(
            f"point ({px}, {py}) out of crop bounds [0, {crop_width}) x [0, {crop_height})"
        )
    full_x = box.x0 + px
    full_y = box.y0 + py
    return pixel_to_wall_norm(full_x, full_y, box)


def _convert_path(path_px: list[list[float]], *, box: FixtureBox, crop_width: int, crop_height: int) -> list[list[float]]:
    return [
        list(convert_ai_px_to_wall_norm(x, y, box=box, crop_width=crop_width, crop_height=crop_height))
        for x, y in path_px
    ]


def explain_authority_ineligibility(
    result: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_MIN_AUTHORITY_CONFIDENCE,
    require_status: str = "extracted",
    laser_mask: LaserSpatialMasks | None = None,
) -> str | None:
    """Return None when eligible for authority; otherwise a specific gate reason."""
    try:
        validated = validate_ai_extraction_result(result)
    except AIExtractionValidationError as exc:
        msg = str(exc)
        if "unsupported color_coverage value" in msg:
            token = msg.split("unsupported color_coverage value:", 1)[-1].strip()
            return f"unsupported_color_coverage={token}"
        return msg

    if validated["status"] != require_status:
        return f"status={validated['status']}"
    if validated["geometry_kind"] == "unknown":
        return "geometry_kind=unknown"
    if validated["confidence"] < min_confidence:
        return f"low_confidence={validated['confidence']:.3f}"
    if validated["failure_modes"]:
        return "failure_modes=" + ",".join(validated["failure_modes"])
    has_geometry = bool(validated["paths_px"] or validated["dot_anchors_px"] or validated["segment_anchors_px"])
    if not has_geometry:
        return "no_geometry"
    if laser_mask is not None:
        spatial_reason = explain_spatial_authority_mismatch(validated, laser_mask)
        if spatial_reason is not None:
            return spatial_reason
    return None


def ai_result_eligible_for_authority(
    result: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_MIN_AUTHORITY_CONFIDENCE,
    require_status: str = "extracted",
    laser_mask: LaserSpatialMasks | None = None,
) -> bool:
    """Opt-in authority gate for --require-ai-pass-for-authority integration."""
    return explain_authority_ineligibility(
        result,
        min_confidence=min_confidence,
        require_status=require_status,
        laser_mask=laser_mask,
    ) is None


def ai_result_to_shape_entry(
    result: dict[str, Any],
    *,
    box: FixtureBox,
    vector_key: str,
    capture_path: str,
    source_still: str,
    fixture_box_label: str,
    entry_meta: dict[str, Any] | None = None,
    laser_mask: LaserSpatialMasks | None = None,
) -> dict[str, Any]:
    """Convert a validated extracted AI result into a partial shape-library entry."""
    validated = validate_ai_extraction_result(result)
    if validated["status"] != "extracted":
        raise AIExtractionValidationError(f"cannot convert non-extracted status: {validated['status']}")
    if validated["geometry_kind"] == "unknown":
        raise AIExtractionValidationError("cannot convert unknown geometry_kind")
    if not ai_result_eligible_for_authority(validated, laser_mask=laser_mask):
        raise AIExtractionValidationError("AI result fails authority eligibility gate")

    crop_w = validated["image_width"]
    crop_h = validated["image_height"]
    if crop_w != box.width or crop_h != box.height:
        raise AIExtractionValidationError(
            f"AI image size {crop_w}x{crop_h} does not match fixture box {box.width}x{box.height}"
        )

    polylines: list[dict[str, Any]] = []
    point_count = 0
    for idx, path_px in enumerate(validated["paths_px"]):
        if len(path_px) < 2 and validated["geometry_kind"] not in ("dot_anchor_points",):
            continue
        points = _convert_path(path_px, box=box, crop_width=crop_w, crop_height=crop_h)
        point_count += len(points)
        polylines.append(
            {
                "polyline_id": f"ai_p{idx}",
                "points": points,
                "point_count": len(points),
                "source": "ai_extraction",
                "geometry_kind": validated["geometry_kind"],
            }
        )

    for idx, anchor_px in enumerate(validated["dot_anchors_px"]):
        pt = list(
            convert_ai_px_to_wall_norm(
                anchor_px[0], anchor_px[1], box=box, crop_width=crop_w, crop_height=crop_h
            )
        )
        point_count += 1
        polylines.append(
            {
                "polyline_id": f"ai_dot{idx}",
                "points": [pt],
                "point_count": 1,
                "source": "ai_extraction",
                "geometry_kind": "dot_anchor_points",
            }
        )

    for idx, segment_px in enumerate(validated["segment_anchors_px"]):
        points = _convert_path(segment_px, box=box, crop_width=crop_w, crop_height=crop_h)
        point_count += len(points)
        polylines.append(
            {
                "polyline_id": f"ai_seg{idx}",
                "points": points,
                "point_count": len(points),
                "source": "ai_extraction",
                "geometry_kind": "segment_anchor_points",
            }
        )

    if not polylines:
        raise AIExtractionValidationError("AI result has no convertible geometry")

    xs = [p[0] for pl in polylines for p in pl["points"]]
    ys = [p[1] for pl in polylines for p in pl["points"]]
    px_coords = [
        (box.x0 + x, box.y0 + y)
        for path in validated["paths_px"]
        for x, y in path
    ]
    px_coords.extend(
        (box.x0 + x, box.y0 + y) for x, y in validated["dot_anchors_px"]
    )
    px_coords.extend(
        (box.x0 + x, box.y0 + y)
        for seg in validated["segment_anchors_px"]
        for x, y in seg
    )
    px0 = min(x for x, _ in px_coords)
    py0 = min(y for _, y in px_coords)
    px1 = max(x for x, _ in px_coords)
    py1 = max(y for _, y in px_coords)

    meta = entry_meta or {}
    expected_shape_ref = compute_shape_ref(ARTIFACT_VERSION, vector_key, capture_path, fixture_box_label)
    ai_returned_shape_ref = None
    if validated["shape_ref"] != expected_shape_ref:
        ai_returned_shape_ref = validated["shape_ref"]

    ai_extraction_diag: dict[str, Any] = {
        "confidence": validated["confidence"],
        "color_coverage": validated["color_coverage"],
        "failure_modes": validated["failure_modes"],
        "provider": "gemini",
    }
    if ai_returned_shape_ref is not None:
        ai_extraction_diag["ai_returned_shape_ref"] = ai_returned_shape_ref

    return {
        "shape_ref": expected_shape_ref,
        "vector_key": vector_key,
        "capture_path": capture_path,
        "source_still": source_still,
        "test_id": meta.get("test_id") or meta.get("family_or_checkpoint") or capture_path,
        "phase": meta.get("phase") or "",
        "exposure_track": meta.get("exposure_track") or "",
        "ch1_19": meta.get("ch1_19") or {},
        "fixture_box_label": fixture_box_label,
        "source_pixel_bbox": [px0, py0, px1, py1],
        "bbox_wall_norm": bbox_wall_norm_from_pixel_bbox(px0, py0, px1, py1, box),
        "centroid_wall_norm": [sum(xs) / len(xs), sum(ys) / len(ys)],
        "topology_class": "ai_extracted",
        "shape_point_count": point_count,
        "clusters": [],
        "polylines": polylines,
        "geometry_kind": validated["geometry_kind"],
        "ordered": True,
        "quality_flags": ["ai_extraction"],
        "selected_extractor": "gemini_ai_extraction",
        "selected_extractor_reason": validated["reason"],
        "visual_status": "pass",
        "usable_as_shape_authority": True,
        "visual_review_reason": "ai_extracted_high_confidence",
        "ai_extraction": ai_extraction_diag,
    }


def load_ai_extractions(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise AIExtractionValidationError("AI extractions file must be an object")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise AIExtractionValidationError("AI extractions file must contain entries[]")
    return doc
