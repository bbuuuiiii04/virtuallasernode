"""Colored synthetic laser extraction tests."""

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


def test_blue_line() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    blue = (40, 80, 255)
    for x in range(30, 170):
        px[x, 100] = blue
    out = extract_shape_from_image(img, BOX, min_area_px=15)
    assert out["shape_point_count"] > 0
    assert out["topology_class"] == "line"
    assert polylines_are_real_geometry(out["polylines"], out["source_pixel_bbox"], BOX)


def test_red_two_dots() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    red = (255, 40, 40)
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            px[50 + dx, 100 + dy] = red
            px[150 + dx, 100 + dy] = red
    out = extract_shape_from_image(img, BOX, min_area_px=15)
    assert out["topology_class"] == "two_clusters"
    assert len(out["polylines"]) >= 2


def test_green_ring() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    green = (40, 255, 70)
    for x in range(60, 140):
        px[x, 60] = green
        px[x, 139] = green
    for y in range(60, 140):
        px[60, y] = green
        px[139, y] = green
    out = extract_shape_from_image(img, BOX, min_area_px=15)
    assert out["topology_class"] == "closed_loop"
    assert polylines_are_real_geometry(out["polylines"], out["source_pixel_bbox"], BOX)


def test_dim_colored_laser_over_background() -> None:
    img = Image.new("RGB", (200, 200), (45, 45, 50))
    px = img.load()
    dim_cyan = (50, 120, 130)
    for x in range(40, 160):
        px[x, 100] = dim_cyan
    out = extract_shape_from_image(img, BOX, min_area_px=10, threshold_k=2.5)
    assert out["shape_point_count"] > 0 or "low_contrast" in out["quality_flags"]
