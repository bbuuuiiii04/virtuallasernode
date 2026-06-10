"""Contact sheet overlay must draw geometry kinds correctly."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image, render_overlay_image  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (16, 16, 20)


def _dot(px, cx: int, cy: int) -> None:
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            if dx * dx + dy * dy <= 16:
                px[cx + dx, cy + dy] = (255, 200, 80)


def test_overlay_draws_dot_anchors_and_centerlines() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for cx in (50, 80, 110, 140):
        _dot(px, cx, 100)
    for x in range(30, 170):
        px[x, 130] = (255, 255, 255)

    line_out = extract_shape_from_image(img, BOX, min_area_px=4)
    overlay = render_overlay_image(img, line_out, BOX)
    yellow = sum(1 for y in range(overlay.height) for x in range(overlay.width) if overlay.getpixel((x, y))[0] > 200 and overlay.getpixel((x, y))[1] > 200)
    assert yellow > 0

    blank = Image.new("RGB", (200, 200), BG)
    rejected = {
        "polylines": [
            {
                "geometry_kind": "rejected_mask_area",
                "points": [[-0.5, -0.5], [0.5, 0.5], [0.5, -0.5], [-0.5, 0.5]],
                "closed": True,
            }
        ],
        "source_pixel_bbox": [0, 0, 200, 200],
    }
    rej_overlay = render_overlay_image(blank, rejected, BOX)
    rej_yellow = sum(1 for y in range(rej_overlay.height) for x in range(rej_overlay.width) if rej_overlay.getpixel((x, y))[0] > 200 and rej_overlay.getpixel((x, y))[1] > 200)
    assert rej_yellow == 0
