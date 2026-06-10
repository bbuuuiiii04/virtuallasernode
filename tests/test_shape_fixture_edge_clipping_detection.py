"""Geometry stuck on fixture boundary when laser is interior should score poorly."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402

INNER = FixtureBox(label="image_left", x0=40, y0=40, x1=160, y1=160)
BG = (14, 14, 18)
CORE = (255, 255, 255)


def test_interior_shape_not_fixture_edge_clipped() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for x in range(70, 130):
        for dy in range(-1, 2):
            px[x, 100 + dy] = CORE
    out = extract_shape_from_image(img, INNER, min_area_px=8)
    assert out["shape_point_count"] > 0
    rejected = out.get("rejected_candidate_reasons") or {}
    selected = out.get("selected_extractor") or ""
    assert "fixture_edge_clipped" not in (rejected.get(selected) or [])
    pts = [p for poly in out["polylines"] for p in poly.get("points") or []]
    xs = [p[0] for p in pts if len(p) >= 2]
    assert max(xs) - min(xs) > 0.1
    assert all(abs(x) < 0.85 for x in xs)
