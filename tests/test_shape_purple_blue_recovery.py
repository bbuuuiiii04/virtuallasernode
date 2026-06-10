"""Curved blue+purple strokes must recover both color sections."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image, pixel_to_wall_norm  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (18, 18, 22)
BLUE = (35, 80, 255)
PURPLE = (180, 40, 220)


def _stroke(px, x: int, y: int, color: tuple[int, int, int], glow: int = 6) -> None:
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = x + dx, y + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                if d <= 1.2:
                    px[xx, yy] = color
                else:
                    fade = max(0, int(70 * (1.0 - d / glow)))
                    px[xx, yy] = tuple(min(255, BG[i] + fade) for i in range(3))


def test_purple_blue_curved_stroke_recovery() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for x in range(40, 110):
        _stroke(px, x, 80 + int(0.015 * (x - 40) ** 2), BLUE)
    for x in range(110, 165):
        _stroke(px, x, 80 + int(0.015 * (110 - 40) ** 2) + (x - 110) // 3, PURPLE)

    out = extract_shape_from_image(img, BOX, min_area_px=6)
    assert out["shape_point_count"] > 0
    assert "colored_core_recovered" in out["quality_flags"] or len(out["polylines"]) >= 1

    all_pts = [p for poly in out["polylines"] for p in poly.get("points") or []]
    xs = [p[0] for p in all_pts if len(p) >= 2]
    assert max(xs) - min(xs) > 0.35, "purple section should extend extracted path to the right"

    blue_x, _ = pixel_to_wall_norm(70, 90, BOX)
    purple_x, _ = pixel_to_wall_norm(140, 110, BOX)
    covered_blue = any(abs(p[0] - blue_x) < 0.35 for p in all_pts)
    covered_purple = any(abs(p[0] - purple_x) < 0.35 for p in all_pts)
    assert covered_blue, "blue section missing from extracted geometry"
    assert covered_purple, "purple section missing from extracted geometry"
