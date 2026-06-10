"""Dot clusters must preserve separate components."""

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
BG = (16, 16, 20)


def _dot(px, cx: int, cy: int, color: tuple[int, int, int], glow: int = 6) -> None:
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = cx + dx, cy + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                if d <= 1.2:
                    px[xx, yy] = color
                else:
                    fade = max(0, int(70 * (1.0 - d / glow)))
                    px[xx, yy] = tuple(min(255, BG[i] + fade) for i in range(3))


def test_red_blue_dot_cluster_preserves_components() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    red = (255, 50, 50)
    blue = (50, 90, 255)
    for cx in (45, 75, 105):
        _dot(px, cx, 90, red)
    for cx in (125, 155):
        _dot(px, cx, 110, blue)

    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert out["shape_point_count"] > 0
    assert len(out["polylines"]) >= 3
    assert len(out["clusters"]) >= 3
    assert out.get("topology_class") in ("multi_cluster", "two_clusters")
