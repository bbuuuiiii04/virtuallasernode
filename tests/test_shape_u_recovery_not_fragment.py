"""U-shape with uneven brightness must not collapse to endpoint fragments."""

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


def _draw_u_uneven(img: Image.Image) -> None:
    px = img.load()
    path = []
    for x in range(60, 141):
        path.append((x, 60, 255))
    for y in range(60, 141):
        path.append((140, y, 180))
    for x in range(140, 59, -1):
        path.append((x, 140, 120))
    for cx, cy, peak in path:
        for dy in range(-7, 8):
            for dx in range(-7, 8):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 7:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    if d <= 1.2:
                        px[xx, yy] = (peak, 40, peak)
                    else:
                        fade = max(0, int(70 * (1.0 - d / 7.0)))
                        px[xx, yy] = (BG[0] + fade, BG[1], BG[2] + fade)


def test_u_recovery_not_fragment() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_u_uneven(img)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    assert len(out["polylines"]) >= 1
    poly = out["polylines"][0]
    assert len(poly.get("points") or []) >= 5
    px, py = polyline_point_span(poly["points"])
    assert px > 0.35
    rejected = out.get("rejected_candidate_reasons") or {}
    selected = out.get("selected_extractor") or ""
    assert "fragment_only" not in (rejected.get(selected) or [])
