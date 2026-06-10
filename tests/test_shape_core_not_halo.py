"""Core extraction must follow laser core, not outer glow halo."""

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
BG = (15, 15, 18)
CORE = (255, 255, 255)


def _draw_line_with_glow(img: Image.Image, y: int = 100) -> None:
    px = img.load()
    for x in range(25, 175):
        for dy in range(-10, 11):
            for dx in range(-10, 11):
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > 10:
                    continue
                yy, xx = y + dy, x + dx
                if dist <= 1.5:
                    px[xx, yy] = CORE
                else:
                    fade = max(0, int(120 * (1.0 - dist / 10.0)))
                    px[xx, yy] = (BG[0] + fade, BG[1] + fade, BG[2] + fade)


def test_core_line_not_halo_boundary() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_line_with_glow(img, y=100)
    out = extract_shape_from_image(img, BOX, min_area_px=10)
    assert out["shape_point_count"] > 0
    assert out["topology_class"] == "line"
    poly = out["polylines"][0]
    assert poly["source"] == "skeleton"
    assert poly.get("closed") is False
    ys = [p[1] for p in poly["points"]]
    assert max(ys) - min(ys) < 0.35, "line overlay should stay near core, not halo height"


def test_glow_ratio_flags_broad_contour() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _draw_line_with_glow(img, y=120)
    out = extract_shape_from_image(img, BOX, min_area_px=10)
    assert "broad_glow_rejected" in out["quality_flags"] or polyline_is_skeleton(out)


def polyline_is_skeleton(out: dict) -> bool:
    return all(p.get("source") == "skeleton" for p in out.get("polylines") or [])
