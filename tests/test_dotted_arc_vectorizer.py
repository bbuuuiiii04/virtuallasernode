"""Dotted arc must preserve dot anchors, not smear into one blob."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (16, 16, 20)


def _dot(px, cx: int, cy: int, color: tuple[int, int, int] = (255, 200, 80), glow: int = 5) -> None:
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = cx + dx, cy + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                if d <= 1.2:
                    px[xx, yy] = color
                else:
                    fade = max(0, int(60 * (1.0 - d / glow)))
                    px[xx, yy] = tuple(min(255, BG[i] + fade) for i in range(3))


def test_dotted_arc_preserves_dot_anchors() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    dots = [(50, 120), (70, 105), (95, 95), (120, 100), (145, 115), (165, 135)]
    for cx, cy in dots:
        _dot(px, cx, cy)

    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert out["shape_type"] in ("dotted_pattern", "dot_cluster")
    assert out["selected_extractor"] in ("dotted_component_vectorizer", "dot_cluster_vectorizer")
    assert len(out["polylines"]) >= 4
    for poly in out["polylines"]:
        assert len(poly.get("points") or []) >= 1
        assert not poly.get("closed")
        assert poly.get("geometry_kind") in ("dot_anchor_points", "segment_anchor_points")
    assert out.get("geometry_kind") in ("dot_anchor_points", "segment_anchor_points")
