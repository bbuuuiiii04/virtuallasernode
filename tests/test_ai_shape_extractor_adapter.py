"""Mock AI adapter works offline without GEMINI_API_KEY."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ai_shape_extractor_adapter import (  # noqa: E402
    AIShapeExtractorError,
    ExtractionRequest,
    GeminiShapeExtractorAdapter,
    MockShapeExtractorAdapter,
    get_adapter,
)


def test_mock_adapter_without_api_key() -> None:
    request = ExtractionRequest(
        shape_ref="sh1_mocktest00000001",
        image_bytes=b"\xff\xd8\xff",
        mime_type="image/jpeg",
        prompt="extract json",
        image_width=100,
        image_height=80,
    )
    with patch.dict(os.environ, {}, clear=True):
        adapter = MockShapeExtractorAdapter()
        response = adapter.extract(request)
    assert response.provider == "mock"
    assert response.parsed is not None
    assert response.parsed["status"] == "extracted"
    assert response.parsed["paths_px"]


def test_gemini_adapter_requires_api_key() -> None:
    adapter = GeminiShapeExtractorAdapter()
    request = ExtractionRequest(
        shape_ref="sh1_gemini000000001",
        image_bytes=b"\xff\xd8\xff",
        mime_type="image/jpeg",
        prompt="extract json",
        image_width=10,
        image_height=10,
    )
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(AIShapeExtractorError, match="GEMINI_API_KEY"):
            adapter.extract(request)


def test_get_adapter_defaults_to_mock() -> None:
    adapter = get_adapter("mock")
    assert adapter.provider == "mock"


def test_no_live_api_during_mock_extract() -> None:
    """Ensure mock path never imports or calls google.genai."""
    request = ExtractionRequest(
        shape_ref="sh1_noapi000000001",
        image_bytes=b"abc",
        mime_type="image/jpeg",
        prompt="x",
        image_width=4,
        image_height=4,
    )
    with patch("tools.ai_shape_extractor_adapter.genai", create=True) as fake_genai:
        fake_genai.Client.side_effect = AssertionError("live API must not be called")
        MockShapeExtractorAdapter().extract(request)
