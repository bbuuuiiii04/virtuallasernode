"""Colored synthetic laser extraction tests (including glow cases)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polylines_are_real_geometry  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (20, 20, 25)


def _glow_stroke(px, x: int, y: int, color: tuple[int, int, int], glow: int = 7) -> None:
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = x + dx, y + dy
            if d <= 1.2:
                px[xx, yy] = color
            else:
                fade = max(0, int(80 * (1.0 - d / glow)))
                px[xx, yy] = tuple(min(255, BG[i] + fade) for i in range(3))


def test_blue_cyan_line_with_glow() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    blue = (40, 80, 255)
    for x in range(30, 170):
        _glow_stroke(px, x, 100, blue)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    assert out["topology_class"] == "line"
    assert out["polylines"][0]["source"] == "skeleton"
    assert polylines_are_real_geometry(out["polylines"], out["source_pixel_bbox"], BOX)


def test_red_two_dots_with_glow() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    red = (255, 40, 40)
    for cx in (50, 150):
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 7:
                    continue
                xx, yy = cx + dx, 100 + dy
                if d <= 1.2:
                    px[xx, yy] = red
                else:
                    fade = max(0, int(70 * (1.0 - d / 7.0)))
                    px[xx, yy] = (BG[0] + fade, BG[1], BG[2])
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["topology_class"] == "two_clusters"
    assert len(out["polylines"]) >= 2


def test_green_ring_with_glow() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    green = (40, 255, 70)
    for x in range(60, 140):
        _glow_stroke(px, x, 60, green, glow=5)
        _glow_stroke(px, x, 139, green, glow=5)
    for y in range(60, 140):
        _glow_stroke(px, 60, y, green, glow=5)
        _glow_stroke(px, 139, y, green, glow=5)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["topology_class"] == "closed_loop"
    assert polylines_are_real_geometry(out["polylines"], out["source_pixel_bbox"], BOX)


def test_magenta_u_with_glow() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    mag = (220, 40, 220)
    for x in range(70, 131):
        _glow_stroke(px, x, 70, mag, glow=6)
    for y in range(70, 131):
        _glow_stroke(px, 130, y, mag, glow=6)
        _glow_stroke(px, 70, y, mag, glow=6)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    assert out["polylines"][0].get("closed") is False


def test_dim_colored_laser_over_background() -> None:
    img = Image.new("RGB", (200, 200), (45, 45, 50))
    px = img.load()
    dim_cyan = (50, 120, 130)
    for x in range(40, 160):
        px[x, 100] = dim_cyan
    out = extract_shape_from_image(img, BOX, min_area_px=8, threshold_k=2.5)
    assert out["shape_point_count"] > 0 or "low_contrast" in out["quality_flags"]
