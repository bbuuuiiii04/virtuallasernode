"""Multicolor curved stroke must include cyan/green/yellow/purple sections."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image, pixel_to_wall_norm  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (18, 18, 22)


def _stroke(px, x: int, y: int, color: tuple[int, int, int], glow: int = 6) -> None:
    for dy in range(-glow, glow + 1):
        for dx in range(-glow, glow + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if d > glow:
                continue
            xx, yy = x + dx, y + dy
            if 0 <= xx < 200 and 0 <= yy < 200:
                if d <= 1.2:
                    px[xx, yy] = color
                else:
                    fade = max(0, int(65 * (1.0 - d / glow)))
                    px[xx, yy] = tuple(min(255, BG[i] + fade) for i in range(3))


def test_multicolor_curve_full_recovery() -> None:
    img = Image.new("RGB", (200, 200), BG)
    px = img.load()
    cyan = (40, 220, 220)
    green = (40, 230, 80)
    yellow = (240, 230, 60)
    purple = (190, 40, 220)
    for i, x in enumerate(range(35, 85)):
        _stroke(px, x, 110 - i // 3, cyan)
    for i, x in enumerate(range(85, 120)):
        _stroke(px, x, 95 + i // 4, green)
    for i, x in enumerate(range(120, 150)):
        _stroke(px, x, 100 + i // 3, yellow)
    for i, x in enumerate(range(150, 175)):
        _stroke(px, x, 108 + i // 2, purple)

    out = extract_shape_from_image(img, BOX, min_area_px=6)
    assert out["shape_point_count"] > 0
    all_pts = [p for poly in out["polylines"] for p in poly.get("points") or []]
    xs = [p[0] for p in all_pts if len(p) >= 2]
    assert max(xs) - min(xs) > 0.45

    cyan_x, _ = pixel_to_wall_norm(50, 100, BOX)
    purple_x, _ = pixel_to_wall_norm(165, 120, BOX)
    assert any(abs(p[0] - cyan_x) < 0.4 for p in all_pts)
    assert any(abs(p[0] - purple_x) < 0.4 for p in all_pts)
    rejected = out.get("rejected_candidate_reasons") or {}
    for reasons in rejected.values():
        assert "missing_color_span" not in reasons or out["selected_extractor"] not in rejected
