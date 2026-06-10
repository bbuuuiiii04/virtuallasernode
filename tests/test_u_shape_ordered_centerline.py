"""U-shape must produce ordered centerline path."""

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
BG = (12, 12, 16)


def _draw_u(img: Image.Image) -> None:
    px = img.load()
    path = []
    for x in range(60, 141):
        path.append((x, 60))
    for y in range(60, 141):
        path.append((140, y))
    for x in range(140, 59, -1):
        path.append((x, 140))
    for cx, cy in path:
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 6:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    px[xx, yy] = (220, 40, 220) if d <= 1.2 else tuple(min(255, BG[i] + int(60 * (1 - d / 6))) for i in range(3))


def test_u_shape_ordered_centerline() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_u(img)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out.get("polylines")
    poly = out["polylines"][0]
    assert poly.get("ordered") is True
    assert poly.get("geometry_kind") in ("centerline_polyline", "branch_polyline")
    assert not poly.get("closed")
    assert len(poly.get("points") or []) >= 4
