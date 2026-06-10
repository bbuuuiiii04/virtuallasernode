"""Straight lines with glow must extract thin centerlines, not fat bands."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import (  # noqa: E402
    polyline_is_fat_closed_band,
    polyline_is_thin_centerline,
)

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (14, 14, 18)
BLUE = (40, 90, 255)


def _draw_blue_line_with_glow(img: Image.Image, y: int = 100) -> None:
    px = img.load()
    for x in range(30, 170):
        for dy in range(-12, 13):
            for dx in range(-12, 13):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 12:
                    continue
                xx, yy = x + dx, y + dy
                if d <= 1.2:
                    px[xx, yy] = BLUE
                else:
                    fade = max(0, int(100 * (1.0 - d / 12.0)))
                    px[xx, yy] = (BG[0] + fade, BG[1] + fade, min(255, BG[2] + fade))


def test_straight_blue_line_core_centerline_not_glow_band() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_blue_line_with_glow(img)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    assert out["topology_class"] == "line"
    assert "core_mask_used" in out["quality_flags"]
    poly = out["polylines"][0]
    assert poly.get("closed") is False
    assert not polyline_is_fat_closed_band(poly)
    assert polyline_is_thin_centerline(poly)
    ys = [p[1] for p in poly["points"]]
    assert max(ys) - min(ys) < 0.25
