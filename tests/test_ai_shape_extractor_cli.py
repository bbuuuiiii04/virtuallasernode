"""CLI smoke with mock adapter; gitignore coverage for generated AI artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture_index_runtime import CaptureIndexRuntime, vector_key_from_ch1_19  # noqa: E402
from tools.ai_shape_extractor import (  # noqa: E402
    AUTHORITY_OVERLAY_YELLOW,
    REJECTED_DEBUG_OVERLAY_COLOR,
    _encode_crop_png,
    _render_ai_overlay,
    run_extraction,
)
from tools.ai_shape_extractor_adapter import ExtractionRequest, MockShapeExtractorAdapter  # noqa: E402
from tools.shape_extraction import load_fixture_boxes  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

SELECTION = ROOT / "artifacts/renderer/pr-g1-shape-authority/shape_selection.json"
GEOMETRY = ROOT / "captures/fixture_model/analysis_geometry.json"
PROMPT = ROOT / "artifacts/renderer/pr-g1-ai-extraction/ai_extraction_prompt.md"
GITIGNORE = ROOT / ".gitignore"


@pytest.mark.skipif(not SELECTION.is_file(), reason="shape selection not built")
@pytest.mark.skipif(not GEOMETRY.is_file(), reason="analysis geometry missing")
def test_mock_cli_smoke_limit_one(tmp_path: Path) -> None:
    out = tmp_path / "ai_extractions.json"
    with patch.dict("os.environ", {}, clear=True):
        summary = run_extraction(
            root=ROOT,
            selection_path=SELECTION,
            geometry_path=GEOMETRY,
            prompt_path=PROMPT,
            output_path=out,
            adapter_name="mock",
            enable_gemini=False,
            limit=1,
            write_contact_sheets=False,
        )
    assert summary["stats"]["processed"] == 1
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert len(doc["entries"]) == 1
    assert doc["entries"][0]["provider"] == "mock"


@pytest.mark.skipif(Image is None, reason="Pillow required")
@pytest.mark.skipif(not GEOMETRY.is_file(), reason="analysis geometry missing")
def test_run_extraction_uses_entry_fixture_box(tmp_path: Path) -> None:
    boxes = load_fixture_boxes(json.loads(GEOMETRY.read_text(encoding="utf-8")))
    image_right = boxes["image_right"]

    img = Image.new("RGB", (1280, 600), (0, 0, 0))
    img.putpixel(
        ((boxes["image_left"].x0 + boxes["image_left"].x1) // 2, (boxes["image_left"].y0 + boxes["image_left"].y1) // 2),
        (0, 255, 0),
    )
    img.putpixel(
        ((image_right.x0 + image_right.x1) // 2, (image_right.y0 + image_right.y1) // 2),
        (255, 0, 0),
    )

    work = tmp_path / "work"
    work.mkdir()
    still = work / "still.jpg"
    img.save(still)
    prompt_copy = work / "ai_extraction_prompt.md"
    prompt_copy.write_text(PROMPT.read_text(encoding="utf-8"), encoding="utf-8")
    selection = work / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "local_media_exists": True,
                        "still_path": "still.jpg",
                        "capture_path": "phase1/test_right_fixture_box",
                        "vector_key": "v1:0,0,32,0,90,128,128,0,0,0,0,0,0,0,0,0,0,0,0",
                        "selected_fixture_box": "image_right",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    captured: list[ExtractionRequest] = []

    class CaptureMock(MockShapeExtractorAdapter):
        def extract(self, request: ExtractionRequest):
            captured.append(request)
            return super().extract(request)

    out = work / "ai_extractions.json"
    with patch("tools.ai_shape_extractor.get_adapter", lambda _name: CaptureMock()):
        run_extraction(
            root=work,
            selection_path=selection,
            geometry_path=GEOMETRY,
            prompt_path=prompt_copy,
            output_path=out,
            adapter_name="mock",
            enable_gemini=False,
            limit=1,
            write_contact_sheets=False,
        )

    assert len(captured) == 1
    assert captured[0].image_width == image_right.width
    assert captured[0].image_height == image_right.height
    assert captured[0].mime_type == "image/png"
    assert captured[0].image_bytes.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_encode_crop_png_uses_png_mime_type() -> None:
    crop = Image.new("RGB", (8, 6), (10, 20, 30))
    data, mime_type = _encode_crop_png(crop)
    assert mime_type == "image/png"
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_rejected_geometry_has_no_overlay_by_default() -> None:
    crop = Image.new("RGB", (40, 20), (0, 0, 0))
    result = {
        "paths_px": [[[0, 10], [39, 10]]],
        "dot_anchors_px": [[20, 5]],
        "segment_anchors_px": [[[5, 15], [15, 15]]],
    }
    overlay = _render_ai_overlay(
        crop,
        authority_geometry=None,
        raw_geometry=result,
        authority_eligible=False,
        debug_draw_rejected=False,
    )
    assert overlay.getpixel((10, 10)) == (0, 0, 0)
    assert overlay.getpixel((20, 5)) == (0, 0, 0)
    assert overlay.getpixel((10, 15)) == (0, 0, 0)


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_render_overlay_yellow_only_when_authority_eligible() -> None:
    crop = Image.new("RGB", (40, 20), (0, 0, 0))
    result = {
        "paths_px": [[[0, 10], [39, 10]]],
        "dot_anchors_px": [[20, 5]],
        "segment_anchors_px": [[[5, 15], [15, 15]]],
    }
    rejected = _render_ai_overlay(
        crop,
        authority_geometry=None,
        raw_geometry=result,
        authority_eligible=False,
        debug_draw_rejected=False,
    )
    assert rejected.getpixel((10, 10)) == (0, 0, 0)
    assert rejected.getpixel((20, 5)) == (0, 0, 0)

    approved = _render_ai_overlay(
        crop,
        authority_geometry=result,
        raw_geometry=result,
        authority_eligible=True,
        debug_draw_rejected=False,
    )
    assert approved.getpixel((10, 10)) == AUTHORITY_OVERLAY_YELLOW
    assert approved.getpixel((20, 5)) == AUTHORITY_OVERLAY_YELLOW
    assert approved.getpixel((10, 15)) == AUTHORITY_OVERLAY_YELLOW


@pytest.mark.skipif(Image is None, reason="Pillow required")
def test_debug_draw_rejected_ai_uses_non_yellow_overlay() -> None:
    crop = Image.new("RGB", (40, 20), (0, 0, 0))
    result = {
        "paths_px": [[[0, 10], [39, 10]]],
        "dot_anchors_px": [[20, 5]],
        "segment_anchors_px": [[[5, 15], [15, 15]]],
    }
    debug = _render_ai_overlay(
        crop,
        authority_geometry=None,
        raw_geometry=result,
        authority_eligible=False,
        debug_draw_rejected=True,
    )
    assert debug.getpixel((10, 10)) == REJECTED_DEBUG_OVERLAY_COLOR
    assert debug.getpixel((20, 5)) == REJECTED_DEBUG_OVERLAY_COLOR
    assert debug.getpixel((10, 15)) == REJECTED_DEBUG_OVERLAY_COLOR
    assert REJECTED_DEBUG_OVERLAY_COLOR != AUTHORITY_OVERLAY_YELLOW


def test_generated_ai_artifact_paths_are_gitignored() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    required = [
        ".venv/",
        ".env",
        ".local/renderer/pr-g1-ai-extraction/",
        "artifacts/renderer/pr-g1-ai-extraction/generated/",
        "artifacts/renderer/pr-g1-ai-extraction/contact_sheets/",
        "artifacts/renderer/pr-g1-ai-extraction/masks/",
        "artifacts/renderer/pr-g1-ai-extraction/ai_extractions.json",
    ]
    for pattern in required:
        assert pattern in text


def test_runtime_still_respects_shape_authority_flag() -> None:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19["CH3"] = 32
    key = vector_key_from_ch1_19(ch1_19)
    index = {
        "captures": [{"capture_id": 0, "folder": "phase1/ch3_032"}],
        "vector_index": {
            key: {
                "capture_ids": [0],
                "preferred_capture_id": 0,
                "shape_ref": "sh1_aiwouldnotoverride",
                "shape_point_count": 42,
                "shape_authority": False,
            }
        },
    }
    channels = [0] * 36
    channels[2] = 32
    hit = CaptureIndexRuntime(index_data=index).lookup_exact_from_channels(channels)
    assert hit["shape_authority"] is False
    assert hit["shape_ref"] is None
