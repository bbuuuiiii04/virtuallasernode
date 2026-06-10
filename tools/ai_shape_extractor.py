#!/usr/bin/env python3
"""Optional offline Gemini shape extraction prototype for PR-G1 targets."""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ai_shape_extractor_adapter import (  # noqa: E402
    AIShapeExtractorError,
    ExtractionRequest,
    GeminiShapeExtractorAdapter,
    get_adapter,
)
from tools.ai_shape_cv_refinement import (  # noqa: E402
    apply_cv_refinement_to_result,
    collect_strict_core_pixels,
    extract_raw_gemini_geometry,
)
from tools.ai_shape_geometry_convert import explain_authority_ineligibility  # noqa: E402
from tools.ai_shape_spatial_gate import LaserSpatialMasks, build_laser_spatial_masks  # noqa: E402
from tools.shape_extraction import (  # noqa: E402
    compute_shape_ref,
    load_fixture_boxes,
    make_contact_sheet,
)

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit("AI shape extractor requires Pillow: pip install Pillow") from exc

ARTIFACT_ROOT = ROOT / "artifacts" / "renderer" / "pr-g1-ai-extraction"
DEFAULT_SELECTION = ROOT / "artifacts" / "renderer" / "pr-g1-shape-authority" / "shape_selection.json"
DEFAULT_GEOMETRY = ROOT / "captures" / "fixture_model" / "analysis_geometry.json"
DEFAULT_PROMPT = ARTIFACT_ROOT / "ai_extraction_prompt.md"
GENERATED_DIR = ARTIFACT_ROOT / "generated"
CONTACT_DIR = ARTIFACT_ROOT / "contact_sheets"
MASKS_DIR = ARTIFACT_ROOT / "masks"
DEFAULT_OUTPUT = GENERATED_DIR / "ai_extractions.json"
DEFAULT_FIXTURE_BOX = "image_left"
AUTHORITY_OVERLAY_YELLOW = (255, 255, 0)
REJECTED_DEBUG_OVERLAY_COLOR = (0, 180, 255)
PATH_LINE_WIDTH = 1
DOT_RADIUS = 3
SEGMENT_LINE_WIDTH = 1
REJECTED_PATH_LINE_WIDTH = 1
REJECTED_DOT_RADIUS = 2
DEBUG_CONTEXT_CROP_OUTLINE = (0, 255, 255)
DEBUG_CONTEXT_STRICT_CORE_PIXEL = (160, 32, 160)
DEBUG_CONTEXT_PARENT_BBOX = (255, 0, 255)
DEBUG_CONTEXT_CHILD_BBOX = (255, 200, 0)
DEBUG_CONTEXT_COMPONENT_BBOX = (255, 128, 0)
DEBUG_CONTEXT_MATCHED_BBOX = (0, 255, 128)
DEBUG_CONTEXT_FIXTURE_LABEL = (200, 200, 200)
DEBUG_CONTEXT_REJECTED_MASK = (255, 0, 255)
DEBUG_CONTEXT_REJECTED_LABEL = (255, 120, 255)


def _encode_crop_png(crop: Image.Image) -> tuple[bytes, str]:
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_selection_entries(selection_path: Path, limit: int | None) -> list[dict[str, Any]]:
    doc = _load_json(selection_path)
    entries = [
        e
        for e in doc.get("entries") or []
        if e.get("local_media_exists") and e.get("still_path") and not e.get("excluded_reason")
    ]
    if limit is not None:
        entries = entries[:limit]
    return entries


def _crop_to_fixture_box(image: Image.Image, box: Any) -> Image.Image:
    return image.crop((box.x0, box.y0, box.x1, box.y1)).convert("RGB")


def _has_drawable_geometry(result: dict[str, Any]) -> bool:
    return bool(result.get("paths_px") or result.get("dot_anchors_px") or result.get("segment_anchors_px"))


def _draw_ai_geometry(
    draw: ImageDraw.ImageDraw,
    result: dict[str, Any],
    *,
    color: tuple[int, int, int],
    path_line_width: int,
    dot_radius: int,
    segment_line_width: int,
) -> None:
    for path in result.get("paths_px") or []:
        if len(path) >= 2:
            draw.line([(x, y) for x, y in path], fill=color, width=path_line_width)
        elif len(path) == 1:
            x, y = path[0]
            draw.ellipse(
                (x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius),
                fill=color,
            )
    for x, y in result.get("dot_anchors_px") or []:
        draw.ellipse(
            (x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius),
            fill=color,
        )
    for seg in result.get("segment_anchors_px") or []:
        if len(seg) == 2:
            draw.line(
                [(seg[0][0], seg[0][1]), (seg[1][0], seg[1][1])],
                fill=color,
                width=segment_line_width,
            )


def _draw_debug_context_overlay(
    draw: ImageDraw.ImageDraw,
    crop: Image.Image,
    *,
    debug_context: dict[str, Any],
) -> None:
    width, height = crop.size
    draw.rectangle([0, 0, width - 1, height - 1], outline=DEBUG_CONTEXT_CROP_OUTLINE, width=1)
    label = debug_context.get("selected_fixture_box")
    if isinstance(label, str) and label:
        draw.text((2, 2), f"fixture={label}", fill=DEBUG_CONTEXT_FIXTURE_LABEL)
    matched_ids = set(debug_context.get("matched_component_ids") or [])
    classes = debug_context.get("core_component_classes") or []
    parent_bbox = debug_context.get("parent_component_bbox")
    if isinstance(parent_bbox, (list, tuple)) and len(parent_bbox) == 4:
        x0, y0, x1, y1 = [int(v) for v in parent_bbox]
        draw.rectangle([x0, y0, x1, y1], outline=DEBUG_CONTEXT_PARENT_BBOX, width=2)
        draw.text((x0 + 1, max(0, y0 - 22)), "parent:merged", fill=DEBUG_CONTEXT_PARENT_BBOX)
    split_child_bboxes = debug_context.get("split_child_bboxes") or []
    split_child_match_ids = debug_context.get("split_child_match_ids") or []
    for child_idx, bbox in enumerate(split_child_bboxes):
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = [int(v) for v in bbox]
        match_id = (
            split_child_match_ids[child_idx]
            if child_idx < len(split_child_match_ids)
            else child_idx
        )
        color = DEBUG_CONTEXT_MATCHED_BBOX if match_id in matched_ids else DEBUG_CONTEXT_CHILD_BBOX
        draw.rectangle([x0, y0, x1, y1], outline=color, width=1)
        draw.text((x0 + 1, max(0, y0 - 10)), f"child={match_id}", fill=color)
    for idx, bbox in enumerate(debug_context.get("core_component_bboxes") or []):
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = [int(v) for v in bbox]
        color = DEBUG_CONTEXT_MATCHED_BBOX if idx in matched_ids else DEBUG_CONTEXT_COMPONENT_BBOX
        draw.rectangle([x0, y0, x1, y1], outline=color, width=1)
        class_label = classes[idx] if idx < len(classes) else "unknown"
        draw.text((x0 + 1, max(0, y0 - 10)), f"{idx}:{class_label}", fill=color)
    for pt in debug_context.get("strict_core_pixels") or []:
        if isinstance(pt, (list, tuple)) and len(pt) == 2:
            x, y = int(pt[0]), int(pt[1])
            if 0 <= x < width and 0 <= y < height:
                draw.point((x, y), fill=DEBUG_CONTEXT_STRICT_CORE_PIXEL)
    rejected_pixels = debug_context.get("rejected_debug_pixels") or []
    for pt in rejected_pixels:
        if isinstance(pt, (list, tuple)) and len(pt) == 2:
            x, y = int(pt[0]), int(pt[1])
            if 0 <= x < width and 0 <= y < height:
                draw.point((x, y), fill=DEBUG_CONTEXT_REJECTED_MASK)
    reject_reason = debug_context.get("rejection_reason")
    if isinstance(reject_reason, str) and reject_reason:
        draw.text((2, 14), f"reject={reject_reason[:48]}", fill=DEBUG_CONTEXT_REJECTED_LABEL)


def _render_ai_overlay(
    crop: Image.Image,
    *,
    authority_geometry: dict[str, Any] | None,
    raw_geometry: dict[str, Any] | None,
    authority_eligible: bool,
    debug_draw_rejected: bool = False,
    debug_context: dict[str, Any] | None = None,
) -> Image.Image:
    overlay = crop.copy()
    draw = ImageDraw.Draw(overlay)
    if debug_context:
        _draw_debug_context_overlay(draw, overlay, debug_context=debug_context)
    if debug_draw_rejected and raw_geometry and _has_drawable_geometry(raw_geometry):
        _draw_ai_geometry(
            draw,
            raw_geometry,
            color=REJECTED_DEBUG_OVERLAY_COLOR,
            path_line_width=REJECTED_PATH_LINE_WIDTH,
            dot_radius=REJECTED_DOT_RADIUS,
            segment_line_width=REJECTED_PATH_LINE_WIDTH,
        )
    if authority_eligible and authority_geometry and _has_drawable_geometry(authority_geometry):
        _draw_ai_geometry(
            draw,
            authority_geometry,
            color=AUTHORITY_OVERLAY_YELLOW,
            path_line_width=PATH_LINE_WIDTH,
            dot_radius=DOT_RADIUS,
            segment_line_width=SEGMENT_LINE_WIDTH,
        )
    return overlay


def _finalize_result(
    parsed: dict[str, Any] | None,
    *,
    shape_ref: str,
    crop_width: int,
    crop_height: int,
) -> dict[str, Any]:
    if parsed is None:
        return {
            "shape_ref": shape_ref,
            "status": "failed",
            "geometry_kind": "unknown",
            "confidence": 0.0,
            "image_width": crop_width,
            "image_height": crop_height,
            "paths_px": [],
            "dot_anchors_px": [],
            "segment_anchors_px": [],
            "color_coverage": [],
            "failure_modes": ["ambiguous_shape"],
            "reason": "model returned non-json payload",
        }
    parsed = dict(parsed)
    ai_returned_shape_ref = None
    returned_ref = parsed.get("shape_ref")
    if isinstance(returned_ref, str) and returned_ref.strip() and returned_ref != shape_ref:
        ai_returned_shape_ref = returned_ref
    parsed["shape_ref"] = shape_ref
    parsed.setdefault("image_width", crop_width)
    parsed.setdefault("image_height", crop_height)
    if ai_returned_shape_ref is not None:
        parsed["ai_returned_shape_ref"] = ai_returned_shape_ref
    return parsed


def _authority_gate(result: dict[str, Any], *, spatial_masks: LaserSpatialMasks) -> tuple[bool, str]:
    reason = explain_authority_ineligibility(result, laser_mask=spatial_masks)
    if reason is None:
        return True, "eligible"
    return False, reason


def run_extraction(
    *,
    root: Path,
    selection_path: Path,
    geometry_path: Path,
    prompt_path: Path,
    output_path: Path,
    adapter_name: str,
    enable_gemini: bool,
    limit: int | None,
    write_contact_sheets: bool,
    debug_draw_rejected: bool = False,
    debug_draw_context: bool = False,
) -> dict[str, Any]:
    if enable_gemini and adapter_name == "mock":
        adapter_name = "gemini"
    if adapter_name == "gemini" and not enable_gemini:
        raise AIShapeExtractorError("Gemini adapter requires --enable-gemini")

    if not selection_path.is_file():
        raise FileNotFoundError(f"selection artifact missing: {selection_path}")
    if not geometry_path.is_file():
        raise FileNotFoundError(f"analysis geometry missing: {geometry_path}")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"prompt missing: {prompt_path}")

    prompt = prompt_path.read_text(encoding="utf-8")
    boxes = load_fixture_boxes(_load_json(geometry_path))
    if DEFAULT_FIXTURE_BOX not in boxes:
        raise ValueError(f"fixture box missing: {DEFAULT_FIXTURE_BOX}")

    adapter = get_adapter(adapter_name)
    entries = _load_selection_entries(selection_path, limit)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if write_contact_sheets:
        CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    MASKS_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    stats = {"processed": 0, "extracted": 0, "uncertain": 0, "failed": 0, "authority_eligible": 0, "cv_refined": 0}

    for entry in entries:
        still_path = root / entry["still_path"]
        if not still_path.is_file():
            continue
        capture_path = entry["capture_path"]
        vector_key = entry["vector_key"]
        box_label = entry.get("selected_fixture_box") or DEFAULT_FIXTURE_BOX
        box = boxes.get(box_label)
        if box is None:
            continue
        shape_ref = compute_shape_ref("shape-library-v1", vector_key, capture_path, box_label)

        image = Image.open(still_path)
        crop = _crop_to_fixture_box(image, box)
        crop_width, crop_height = crop.size

        image_bytes, mime_type = _encode_crop_png(crop)
        request = ExtractionRequest(
            shape_ref=shape_ref,
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
            image_width=crop_width,
            image_height=crop_height,
        )
        response = adapter.extract(request)
        result = _finalize_result(
            response.parsed,
            shape_ref=shape_ref,
            crop_width=crop_width,
            crop_height=crop_height,
        )
        result["provider"] = response.provider
        result["model"] = response.model

        spatial_masks = build_laser_spatial_masks(crop)
        apply_cv_refinement_to_result(result, spatial_masks)
        eligible, gate_reason = _authority_gate(result, spatial_masks=spatial_masks)
        result["authority_eligible"] = eligible
        result["authority_gate_reason"] = gate_reason

        authority_geometry = {
            "paths_px": result.get("paths_px") or [],
            "dot_anchors_px": result.get("dot_anchors_px") or [],
            "segment_anchors_px": result.get("segment_anchors_px") or [],
        }
        raw_geometry = result.get("gemini_raw_geometry") or extract_raw_gemini_geometry(result)

        status = result.get("status", "failed")
        stats["processed"] += 1
        if status in stats:
            stats[status] += 1
        else:
            stats["failed"] += 1
        if eligible:
            stats["authority_eligible"] += 1
        if result.get("cv_refinement", {}).get("applied"):
            stats["cv_refined"] += 1

        if write_contact_sheets:
            debug_context = None
            if debug_draw_context:
                cv_meta = result.get("cv_refinement") or {}
                debug_context = {
                    "selected_fixture_box": box_label,
                    "strict_core_pixels": collect_strict_core_pixels(spatial_masks),
                    "core_component_bboxes": cv_meta.get("core_component_bboxes") or [],
                    "core_component_classes": cv_meta.get("core_component_classes") or [],
                    "matched_component_ids": cv_meta.get("matched_component_ids") or [],
                    "reconstruction_method": cv_meta.get("reconstruction_method"),
                    "parent_component_bbox": cv_meta.get("parent_component_bbox"),
                    "split_child_bboxes": cv_meta.get("split_child_bboxes") or [],
                    "split_child_match_ids": cv_meta.get("split_child_match_ids") or [],
                    "rejected_debug_pixels": cv_meta.get("rejected_debug_pixels") or [],
                    "rejection_reason": None if eligible else gate_reason,
                }
            overlay = _render_ai_overlay(
                crop,
                authority_geometry=authority_geometry,
                raw_geometry=raw_geometry,
                authority_eligible=eligible,
                debug_draw_rejected=debug_draw_rejected,
                debug_context=debug_context,
            )
            sheet = make_contact_sheet(crop, overlay)
            sheet_path = CONTACT_DIR / f"{shape_ref}.png"
            sheet.save(sheet_path)
            result["contact_sheet_path"] = str(sheet_path.relative_to(root))

        results.append(result)

    doc = {
        "artifact_version": "pr-g1-ai-extraction-v1",
        "generated_at": _iso_now(),
        "selection_artifact": str(selection_path.relative_to(root)),
        "prompt_artifact": str(prompt_path.relative_to(root)),
        "adapter": adapter.provider,
        "enable_gemini": enable_gemini,
        "debug_draw_rejected_ai": debug_draw_rejected,
        "debug_draw_context": debug_draw_context,
        "entries": results,
        "stats": stats,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return {"output_path": str(output_path), "stats": stats}


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional offline AI shape extraction for PR-G1 targets")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--adapter", choices=("mock", "gemini"), default="mock")
    parser.add_argument(
        "--enable-gemini",
        action="store_true",
        help="Allow live Gemini API calls (requires GEMINI_API_KEY; default is mock/offline)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Process only first N PR-G1 selection entries")
    parser.add_argument("--no-contact-sheets", action="store_true")
    parser.add_argument(
        "--debug-draw-rejected-ai",
        action="store_true",
        help="Draw rejected/uncertain/failed AI geometry on local contact sheets in non-yellow debug color",
    )
    parser.add_argument(
        "--debug-draw-context",
        action="store_true",
        help="Draw local fixture/crop/component debug boxes on contact sheets (non-authority colors)",
    )
    args = parser.parse_args()

    try:
        summary = run_extraction(
            root=args.root,
            selection_path=args.selection if args.selection.is_absolute() else args.root / args.selection,
            geometry_path=args.geometry if args.geometry.is_absolute() else args.root / args.geometry,
            prompt_path=args.prompt if args.prompt.is_absolute() else args.root / args.prompt,
            output_path=args.output if args.output.is_absolute() else args.root / args.output,
            adapter_name=args.adapter,
            enable_gemini=args.enable_gemini,
            limit=args.limit,
            write_contact_sheets=not args.no_contact_sheets,
            debug_draw_rejected=args.debug_draw_rejected_ai,
            debug_draw_context=args.debug_draw_context,
        )
    except (AIShapeExtractorError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
