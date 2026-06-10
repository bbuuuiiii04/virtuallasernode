"""Dot clusters must preserve separate component anchors."""

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


def _dot(px, cx: int, cy: int, color: tuple[int, int, int]) -> None:
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            d = (dx * dx + dy * dy) ** 0.5
            if d > 5:
                continue
            xx, yy = cx + dx, cy + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                px[xx, yy] = color if d <= 1.2 else tuple(min(255, BG[i] + 45) for i in range(3))


def test_dot_cluster_separate_anchors() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for cx in (45, 75, 105):
        _dot(px, cx, 90, (255, 50, 50))
    for cx in (125, 155):
        _dot(px, cx, 110, (50, 90, 255))

    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert len(out.get("polylines") or []) >= 3
    kinds = {p.get("geometry_kind") for p in out.get("polylines") or []}
    assert kinds <= {"dot_anchor_points", "segment_anchor_points"}
    assert out.get("geometry_kind") in ("dot_anchor_points", "segment_anchor_points")
