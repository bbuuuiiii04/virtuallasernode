"""Diagonal line with glow must yield thin centerline, not filled band."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polyline_is_fat_closed_band, polyline_is_thin_centerline  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (12, 12, 16)


def test_diagonal_stroke_thin_centerline_not_band() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for t in range(40):
        cx = 40 + t * 3
        cy = 140 - t * 2
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 8:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    px[xx, yy] = (240, 230, 60) if d <= 1.2 else tuple(min(255, BG[i] + int(70 * (1 - d / 8))) for i in range(3))

    out = extract_shape_from_image(img, BOX, min_area_px=6)
    assert out.get("polylines"), "expected thin centerline extraction"
    poly = out["polylines"][0]
    assert poly.get("geometry_kind") in ("centerline_polyline", "branch_polyline")
    assert poly.get("ordered") is True
    assert not polyline_is_fat_closed_band(poly)
    assert polyline_is_thin_centerline(poly) or not poly.get("closed")
