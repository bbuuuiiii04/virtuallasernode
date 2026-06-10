"""Multi-candidate selector must prefer full thin stroke over fragment or halo."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import polyline_is_fat_closed_band, polyline_is_thin_centerline  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (14, 14, 18)
CORE = (255, 255, 255)


def _line_with_glow(img: Image.Image, y: int = 100) -> None:
    px = img.load()
    for x in range(30, 170):
        for dy in range(-10, 11):
            for dx in range(-10, 11):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 10:
                    continue
                xx, yy = x + dx, y + dy
                if d <= 1.5:
                    px[xx, yy] = CORE
                else:
                    fade = max(0, int(100 * (1.0 - d / 10.0)))
                    px[xx, yy] = (BG[0] + fade, BG[1] + fade, BG[2] + fade)


def test_candidate_selector_prefers_full_line_not_fragment_or_halo() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _line_with_glow(img)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["shape_point_count"] > 0
    assert out.get("selected_extractor")
    assert len(out.get("extraction_candidates_tried") or []) >= 4
    assert out["topology_class"] == "line"
    poly = out["polylines"][0]
    assert not polyline_is_fat_closed_band(poly)
    assert polyline_is_thin_centerline(poly)
    assert len(poly.get("points") or []) >= 3
    scores = out.get("candidate_scores") or {}
    selected = out["selected_extractor"]
    assert scores.get(selected, -999) == max(scores.values())
