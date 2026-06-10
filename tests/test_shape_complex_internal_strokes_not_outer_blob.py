"""Complex multi-stroke shapes must preserve internal strokes, not one outer blob."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polyline_is_fat_closed_band  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (10, 10, 14)
STROKE = (255, 240, 80)


def _draw_petal(x0: int, y0: int, img: Image.Image, glow: int = 6) -> None:
    px = img.load()
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = x0 + dx, y0 + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                if d <= 1.5:
                    px[xx, yy] = STROKE
                else:
                    fade = max(0, int(70 * (1.0 - d / glow)))
                    px[xx, yy] = (BG[0] + fade, BG[1] + fade, BG[2] + fade)


def test_complex_internal_strokes_not_outer_blob() -> None:
    img = Image.new("RGB", (200, 200), BG)
    for cx, cy in ((70, 70), (130, 70), (100, 110), (85, 145), (115, 145)):
        _draw_petal(cx, cy, img)
    out = extract_shape_from_image(img, BOX, min_area_px=4)
    assert out["topology_class"] in ("multi_cluster", "complex_shape")
    assert len(out["polylines"]) >= 3
    assert len(out["clusters"]) >= 3
    assert "internal_strokes_missing" not in out["quality_flags"]
    closed_outer = [p for p in out["polylines"] if p.get("closed") and len(p.get("points") or []) >= 8]
    assert not any(polyline_is_fat_closed_band(p) for p in closed_outer)
