"""Per-color support union must cover cyan/green/yellow/purple spans."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image, pixel_to_wall_norm  # noqa: E402
from tools.shape_laser_maps import build_laser_maps  # noqa: E402
from tools.shape_hysteresis_support import build_hysteresis_support, merge_per_color_support  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (18, 18, 22)


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
                    fade = max(0, int(65 * (1.0 - d / glow)))
                    px[xx, yy] = tuple(min(255, BG[i] + fade) for i in range(3))


def test_per_color_support_union_covers_all_hues() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    colors = [(40, 220, 220), (40, 230, 80), (240, 230, 60), (190, 40, 220)]
    ranges = [range(35, 85), range(85, 120), range(120, 150), range(150, 175)]
    ys = [lambda i: 110 - i // 3, lambda i: 95 + i // 4, lambda i: 100 + i // 3, lambda i: 108 + i // 2]
    for color, xr, yfn in zip(colors, ranges, ys):
        for i, x in enumerate(xr):
            _stroke(px, x, yfn(i), color)

    maps = build_laser_maps(px, 200, 200)
    support = build_hysteresis_support(maps, min_area_px=6)
    merged = merge_per_color_support(maps, support.support_mask)
    merged_pixels = sum(sum(row) for row in merged)
    assert merged_pixels >= len(support.support_pixels)

    out = extract_shape_from_image(img, BOX, min_area_px=6)
    all_pts = [p for poly in out["polylines"] for p in poly.get("points") or []]
    xs = [p[0] for p in all_pts if len(p) >= 2]
    assert max(xs) - min(xs) > 0.45
    cyan_x, _ = pixel_to_wall_norm(50, 100, BOX)
    purple_x, _ = pixel_to_wall_norm(165, 120, BOX)
    assert any(abs(p[0] - cyan_x) < 0.45 for p in all_pts)
    assert any(abs(p[0] - purple_x) < 0.45 for p in all_pts)
