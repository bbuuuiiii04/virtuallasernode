"""PR-G1 synthetic shape extraction topology and quality flags."""

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
BRIGHT = (255, 255, 255)
DARK = (10, 10, 10)


def _blank() -> Image.Image:
    return Image.new("RGB", (200, 200), DARK)


def _draw_line(img: Image.Image) -> None:
    px = img.load()
    for x in range(20, 180):
        px[x, 100] = BRIGHT


def _draw_two_clusters(img: Image.Image) -> None:
    px = img.load()
    for y in range(80, 120):
        for x in range(30, 70):
            px[x, y] = BRIGHT
    for y in range(80, 120):
        for x in range(130, 170):
            px[x, y] = BRIGHT


def _draw_closed_loop(img: Image.Image) -> None:
    px = img.load()
    for x in range(60, 140):
        px[x, 60] = BRIGHT
        px[x, 139] = BRIGHT
    for y in range(60, 140):
        px[60, y] = BRIGHT
        px[139, y] = BRIGHT


def _draw_multi_cluster(img: Image.Image) -> None:
    px = img.load()
    for cx, cy in ((40, 40), (100, 100), (160, 160)):
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                px[cx + dx, cy + dy] = BRIGHT


def _draw_out_of_box(img: Image.Image) -> None:
    px = img.load()
    for x in range(0, 200):
        px[x, 0] = BRIGHT
        px[x, 199] = BRIGHT


def test_extract_line() -> None:
    img = _blank()
    _draw_line(img)
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["shape_point_count"] > 0
    assert out["topology_class"] == "line"


def test_extract_two_clusters() -> None:
    img = _blank()
    _draw_two_clusters(img)
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["topology_class"] == "two_clusters"
    assert len(out["clusters"]) >= 2


def test_extract_closed_loop() -> None:
    img = _blank()
    _draw_closed_loop(img)
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["shape_point_count"] > 0
    assert out["topology_class"] == "closed_loop"


def test_extract_multi_cluster() -> None:
    img = _blank()
    _draw_multi_cluster(img)
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["topology_class"] == "multi_cluster"


def test_blank_still() -> None:
    out = extract_shape_from_image(_blank(), BOX)
    assert out["shape_point_count"] == 0
    assert "blank_still" in out["quality_flags"]


def test_low_contrast() -> None:
    img = Image.new("RGB", (200, 200), (50, 50, 50))
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["shape_point_count"] == 0
    assert "low_contrast" in out["quality_flags"] or "blank_still" in out["quality_flags"]


def test_out_of_box_flag() -> None:
    inner = FixtureBox(label="image_left", x0=40, y0=40, x1=160, y1=160)
    right = FixtureBox(label="image_right", x0=160, y0=0, x1=200, y1=200)
    img = Image.new("RGB", (200, 200), DARK)
    px = img.load()
    for x in range(0, 200):
        px[x, 10] = BRIGHT
    out = extract_shape_from_image(img, inner, min_area_px=10, other_boxes={"image_right": right})
    assert "out_of_box" in out["quality_flags"]
