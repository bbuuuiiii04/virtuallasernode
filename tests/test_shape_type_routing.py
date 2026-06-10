"""Shape-type routing must select the correct vectorizer family."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image, ImageDraw  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_laser_maps import build_laser_maps  # noqa: E402
from tools.shape_hysteresis_support import build_hysteresis_support  # noqa: E402
from tools.shape_stroke_vectorization import classify_shape_type  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (14, 14, 18)


def _line(img: Image.Image) -> None:
    px = img.load()
    for x in range(40, 160):
        for dy in (-1, 0, 1):
            px[x, 100 + dy] = (255, 255, 255)


def _u(img: Image.Image) -> None:
    px = img.load()
    path = []
    for x in range(70, 131):
        path.append((x, 70, 255))
    for y in range(70, 131):
        path.append((130, y, 200))
    for x in range(130, 69, -1):
        path.append((x, 130, 160))
    for cx, cy, peak in path:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx * dx + dy * dy > 9:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    px[xx, yy] = (peak, 40, peak)


def _dots(img: Image.Image, n: int = 5) -> None:
    px = img.load()
    for i in range(n):
        cx, cy = 50 + i * 22, 100 + (i % 2) * 8
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if dx * dx + dy * dy <= 16:
                    px[cx + dx, cy + dy] = (255, 60, 60)


def _ring(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    draw.ellipse([60, 60, 140, 140], outline=(40, 255, 120), width=3)


def test_shape_type_routing_matrix() -> None:
    cases = [
        ("line", _line, "continuous_stroke", "skeleton_graph_stroke"),
        ("u", _u, ("continuous_stroke", "branched_complex"), ("skeleton_graph_stroke", "skeleton_branch_vectorizer")),
        ("dots", _dots, ("dotted_pattern", "dot_cluster"), ("dotted_component_vectorizer", "dot_cluster_vectorizer")),
        ("ring", _ring, "closed_loop", "closed_loop_contour"),
    ]
    for name, draw_fn, expected_type, expected_vec in cases:
        img = Image.new("RGB", (200, 200), BG)
        draw_fn(img)
        maps = build_laser_maps(img.load(), 200, 200)
        support = build_hysteresis_support(maps, min_area_px=4)
        shape_type = classify_shape_type(support, maps)
        if isinstance(expected_type, tuple):
            assert shape_type in expected_type, f"{name}: got {shape_type}"
        else:
            assert shape_type == expected_type, f"{name}: got {shape_type}"
        out = extract_shape_from_image(img, BOX, min_area_px=4)
        if isinstance(expected_vec, tuple):
            assert out["selected_extractor"] in expected_vec
        else:
            assert out["selected_extractor"] == expected_vec
