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
from tools.ai_shape_geometry_convert import explain_authority_ineligibility  # noqa: E402
from tools.ai_shape_spatial_gate import build_laser_pixel_mask  # noqa: E402
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


def _render_ai_overlay(
    crop: Image.Image,
    result: dict[str, Any],
    *,
    authority_eligible: bool,
    debug_draw_rejected: bool = False,
) -> Image.Image:
    overlay = crop.copy()
    if authority_eligible:
        draw = ImageDraw.Draw(overlay)
        _draw_ai_geometry(
            draw,
            result,
            color=AUTHORITY_OVERLAY_YELLOW,
            path_line_width=PATH_LINE_WIDTH,
            dot_radius=DOT_RADIUS,
            segment_line_width=SEGMENT_LINE_WIDTH,
        )
        return overlay
    if debug_draw_rejected and _has_drawable_geometry(result):
        draw = ImageDraw.Draw(overlay)
        _draw_ai_geometry(
            draw,
            result,
            color=REJECTED_DEBUG_OVERLAY_COLOR,
            path_line_width=REJECTED_PATH_LINE_WIDTH,
            dot_radius=REJECTED_DOT_RADIUS,
            segment_line_width=REJECTED_PATH_LINE_WIDTH,
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


def _authority_gate(result: dict[str, Any], *, laser_mask: list[list[bool]]) -> tuple[bool, str]:
    reason = explain_authority_ineligibility(result, laser_mask=laser_mask)
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
    stats = {"processed": 0, "extracted": 0, "uncertain": 0, "failed": 0, "authority_eligible": 0}

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

        laser_mask = build_laser_pixel_mask(crop)
        eligible, gate_reason = _authority_gate(result, laser_mask=laser_mask)
        result["authority_eligible"] = eligible
        result["authority_gate_reason"] = gate_reason

        status = result.get("status", "failed")
        stats["processed"] += 1
        if status in stats:
            stats[status] += 1
        else:
            stats["failed"] += 1
        if eligible:
            stats["authority_eligible"] += 1

        if write_contact_sheets:
            overlay = _render_ai_overlay(
                crop,
                result,
                authority_eligible=eligible,
                debug_draw_rejected=debug_draw_rejected,
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
        )
    except (AIShapeExtractorError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
