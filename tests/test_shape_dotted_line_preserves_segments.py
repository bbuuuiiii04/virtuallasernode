"""Dotted/segmented lines must preserve bright segments, not one fat blob."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polyline_is_fat_closed_band  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (12, 12, 16)
CORE = (255, 255, 255)


def _draw_dotted_line_with_glow(img: Image.Image) -> None:
    px = img.load()
    for x in range(25, 175, 14):
        for dy in range(-7, 8):
            for dx in range(-7, 8):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 7:
                    continue
                xx, yy = x + dx, 100 + dy
                if d <= 1.5:
                    px[xx, yy] = CORE
                else:
                    fade = max(0, int(80 * (1.0 - d / 7.0)))
                    px[xx, yy] = (BG[0] + fade, BG[1] + fade, BG[2] + fade)


def test_dotted_line_preserves_segments() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_dotted_line_with_glow(img)
    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert out["shape_point_count"] > 0
    assert len(out["polylines"]) >= 3 or len(out["clusters"]) >= 3
    for poly in out["polylines"]:
        assert not polyline_is_fat_closed_band(poly)
        assert poly.get("closed") is False
