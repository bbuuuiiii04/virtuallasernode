"""U-shaped strokes with glow must follow U centerline, not outer blob."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polyline_is_fat_closed_band, polyline_point_span  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (12, 12, 16)
MAGENTA = (220, 40, 220)


def _draw_u_with_glow(img: Image.Image) -> None:
    px = img.load()
    path = []
    for x in range(60, 141):
        path.append((x, 60))
    for y in range(60, 141):
        path.append((140, y))
    for x in range(140, 59, -1):
        path.append((x, 140))
    for cx, cy in path:
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 8:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    if d <= 1.2:
                        px[xx, yy] = MAGENTA
                    else:
                        fade = max(0, int(90 * (1.0 - d / 8.0)))
                        px[xx, yy] = (BG[0] + fade, BG[1], BG[2] + fade)


def test_u_centerline_not_outer_blob() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_u_with_glow(img)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    poly = out["polylines"][0]
    assert poly.get("closed") is False
    assert not polyline_is_fat_closed_band(poly)
    assert len(poly.get("points") or []) >= 4
    px, py = polyline_point_span(poly["points"])
    assert px > 0.2 and py > 0.2, "U path should span both axes"
    assert "skeleton_graph_used" in out["quality_flags"] or "skeleton_branches_used" in out["quality_flags"]
