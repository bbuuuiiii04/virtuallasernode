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
from tools.ai_shape_extractor import run_extraction  # noqa: E402

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
