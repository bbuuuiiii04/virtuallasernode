"""Dotted arc must output dot/segment anchors, not closed smear."""

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


def _dot(px, cx: int, cy: int) -> None:
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            d = (dx * dx + dy * dy) ** 0.5
            if d > 5:
                continue
            xx, yy = cx + dx, cy + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                px[xx, yy] = (255, 200, 80) if d <= 1.2 else tuple(min(255, BG[i] + 50) for i in range(3))


def test_dotted_arc_outputs_dot_or_segment_anchors() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for cx, cy in [(50, 120), (70, 105), (95, 95), (120, 100), (145, 115), (165, 135)]:
        _dot(px, cx, cy)

    out = extract_shape_from_image(img, BOX, min_area_px=4)
    kinds = {p.get("geometry_kind") for p in out.get("polylines") or []}
    assert kinds <= {"dot_anchor_points", "segment_anchor_points"}
    assert "closed_loop_contour" not in kinds
    assert out.get("geometry_kind") in ("dot_anchor_points", "segment_anchor_points")
    for poly in out.get("polylines") or []:
        assert not poly.get("closed")
