"""U/arc strokes with glow should extract centerline-like paths, not fat blobs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polyline_point_span  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (12, 12, 16)
MAGENTA_CORE = (220, 40, 220)


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
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > 8:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    if dist <= 1.2:
                        px[xx, yy] = MAGENTA_CORE
                    else:
                        fade = max(0, int(90 * (1.0 - dist / 8.0)))
                        px[xx, yy] = (BG[0] + fade, BG[1], BG[2] + fade)


def test_u_arc_centerline_not_closed_blob() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_u_with_glow(img)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    poly = out["polylines"][0]
    assert poly.get("closed") is False
    assert len(poly.get("points") or []) >= 5
    assert poly.get("source") in ("skeleton", "simplified_component")
