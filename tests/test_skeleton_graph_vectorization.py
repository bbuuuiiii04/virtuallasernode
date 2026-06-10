"""Skeleton graph must return ordered continuous paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_skeleton_graph import (  # noqa: E402
    build_skeleton_graph,
    longest_geodesic_path,
    skeletonize_support_mask,
)
from tools.shape_laser_maps import build_laser_maps  # noqa: E402
from tools.shape_hysteresis_support import build_hysteresis_support  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (14, 14, 18)


def _stroke(px, x: int, y: int, color: tuple[int, int, int] = (255, 255, 255), glow: int = 5) -> None:
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = x + dx, y + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                px[xx, yy] = color if d <= 1.2 else tuple(min(255, BG[i] + int(60 * (1 - d / glow))) for i in range(3))


def test_skeleton_graph_line_and_diagonal() -> None:
    for y in (100, 60):
        img = Image.new("RGB", (200, 200), BG)
        px = img.load()
        if y == 100:
            for x in range(40, 160):
                _stroke(px, x, y)
        else:
            for i, x in enumerate(range(40, 160)):
                _stroke(px, x, y + i // 3)
        maps = build_laser_maps(px, 200, 200)
        support = build_hysteresis_support(maps, min_area_px=6)
        skel = skeletonize_support_mask(support.support_mask)
        graph = build_skeleton_graph(skel)
        path = longest_geodesic_path(graph)
        assert len(path) >= 4
        out = extract_shape_from_image(img, BOX, min_area_px=6)
        assert out["selected_extractor"] == "skeleton_graph_stroke"
        assert out["polylines"][0]["source"] == "skeleton"
