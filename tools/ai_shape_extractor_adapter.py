"""Provider-neutral AI shape extraction adapters (Gemini + mock for tests)."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"


class AIShapeExtractorError(RuntimeError):
    """Raised when adapter configuration or extraction fails."""


@dataclass(frozen=True)
class ExtractionRequest:
    shape_ref: str
    image_bytes: bytes
    mime_type: str
    prompt: str
    image_width: int
    image_height: int


@dataclass(frozen=True)
class ExtractionResponse:
    raw_text: str
    parsed: dict[str, Any] | None
    provider: str
    model: str


class AIShapeExtractorAdapter(ABC):
    """Provider-neutral interface; no network I/O unless extract() is invoked."""

    provider: str

    @abstractmethod
    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        raise NotImplementedError


def _parse_json_payload(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, flags=re.IGNORECASE)
    if fence:
        stripped = fence.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _require_gemini_api_key() -> str:
    key = os.environ.get(GEMINI_API_KEY_ENV, "").strip()
    if not key:
        raise AIShapeExtractorError(
            f"{GEMINI_API_KEY_ENV} environment variable is required for Gemini extraction"
        )
    return key


def _resolve_gemini_model(model: str | None = None) -> str:
    resolved = (model or os.environ.get(GEMINI_MODEL_ENV) or DEFAULT_GEMINI_MODEL).strip()
    if not resolved:
        return DEFAULT_GEMINI_MODEL
    return resolved


class GeminiShapeExtractorAdapter(AIShapeExtractorAdapter):
    provider = "gemini"

    def __init__(self, *, model: str | None = None) -> None:
        self.model = _resolve_gemini_model(model)

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        api_key = _require_gemini_api_key()
        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise AIShapeExtractorError(
                "google-genai is required for Gemini extraction: pip install google-genai"
            ) from exc

        client = genai.Client(api_key=api_key)
        image_part = types.Part.from_bytes(data=request.image_bytes, mime_type=request.mime_type)
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        )
        response = client.models.generate_content(
            model=self.model,
            contents=[request.prompt, image_part],
            config=config,
        )
        raw_text = getattr(response, "text", None) or ""
        if not raw_text and getattr(response, "candidates", None):
            parts = response.candidates[0].content.parts  # type: ignore[index]
            raw_text = "".join(getattr(p, "text", "") or "" for p in parts)
        parsed = _parse_json_payload(raw_text)
        return ExtractionResponse(
            raw_text=raw_text,
            parsed=parsed,
            provider=self.provider,
            model=self.model,
        )


class MockShapeExtractorAdapter(AIShapeExtractorAdapter):
    """Deterministic adapter for offline tests; never performs network I/O."""

    provider = "mock"

    def __init__(self, *, canned: dict[str, dict[str, Any]] | None = None) -> None:
        self.canned = canned or {}

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        payload = self.canned.get(request.shape_ref)
        if payload is None:
            payload = {
                "shape_ref": request.shape_ref,
                "status": "extracted",
                "geometry_kind": "centerline_polyline",
                "confidence": 0.92,
                "image_width": request.image_width,
                "image_height": request.image_height,
                "paths_px": [
                    [
                        [0, request.image_height // 2],
                        [request.image_width - 1, request.image_height // 2],
                    ]
                ],
                "dot_anchors_px": [],
                "segment_anchors_px": [],
                "color_coverage": ["green"],
                "failure_modes": [],
                "reason": "mock horizontal centerline",
            }
        raw_text = json.dumps(payload)
        return ExtractionResponse(
            raw_text=raw_text,
            parsed=dict(payload),
            provider=self.provider,
            model="mock",
        )


def get_adapter(name: str, **kwargs: Any) -> AIShapeExtractorAdapter:
    normalized = (name or "mock").strip().lower()
    if normalized in ("mock", "test"):
        return MockShapeExtractorAdapter(**kwargs)
    if normalized in ("gemini", "google", "google-genai"):
        return GeminiShapeExtractorAdapter(**kwargs)
    raise AIShapeExtractorError(f"Unknown AI shape extractor adapter: {name!r}")
