"""Segmented dashes along an arc/line must route to dotted_pattern."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_laser_maps import build_laser_maps  # noqa: E402
from tools.shape_hysteresis_support import build_hysteresis_support  # noqa: E402
from tools.shape_stroke_vectorization import classify_shape_type  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (16, 16, 20)


def _dash(px, cx: int, cy: int, color: tuple[int, int, int] = (255, 200, 80)) -> None:
    for dy in range(-2, 3):
        for dx in range(-6, 7):
            xx, yy = cx + dx, cy + dy
            if 0 <= xx < 200 and 0 <= yy < 200 and abs(dx) <= 5:
                px[xx, yy] = color


def test_elongated_segmented_marks_route_dotted_pattern() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for i, cx in enumerate(range(45, 165, 18)):
        cy = 115 - i * 3
        _dash(px, cx, cy)

    maps = build_laser_maps(px, 200, 200)
    support = build_hysteresis_support(maps, min_area_px=4)
    assert classify_shape_type(support, maps) == "dotted_pattern"

    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert out.get("shape_type") == "dotted_pattern"
    assert out.get("selected_extractor") in ("dotted_component_vectorizer", "dot_cluster_vectorizer")
    kinds = {p.get("geometry_kind") for p in out.get("polylines") or []}
    assert kinds <= {"dot_anchor_points", "segment_anchor_points"}
