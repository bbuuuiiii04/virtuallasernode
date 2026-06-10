"""Separated high-core dots must route to dot_cluster with dot anchors."""

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


def _dot(px, cx: int, cy: int, color: tuple[int, int, int]) -> None:
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            if dx * dx + dy * dy <= 16:
                px[cx + dx, cy + dy] = color


def test_separated_core_dots_route_dot_cluster() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    for cx in (40, 80, 120, 160):
        _dot(px, cx, 90, (50, 90, 255))

    maps = build_laser_maps(px, 200, 200)
    support = build_hysteresis_support(maps, min_area_px=4)
    assert classify_shape_type(support, maps) in ("dot_cluster", "dotted_pattern")

    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert out.get("shape_type") in ("dot_cluster", "dotted_pattern")
    assert len(out.get("polylines") or []) >= 3
    for poly in out.get("polylines") or []:
        assert poly.get("geometry_kind") in ("dot_anchor_points", "segment_anchor_points")
