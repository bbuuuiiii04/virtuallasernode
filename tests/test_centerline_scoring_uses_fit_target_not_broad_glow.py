"""Stroke coverage must score against fit target, not broad glow support."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox  # noqa: E402
from tools.shape_laser_maps import build_laser_maps  # noqa: E402
from tools.shape_hysteresis_support import build_hysteresis_support  # noqa: E402
from tools.shape_stroke_vectorization import (  # noqa: E402
    _fit_target_pixels,
    classify_shape_type,
    score_geometry_fit,
    vectorize_continuous_stroke,
)

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (14, 14, 18)


def _line_with_glow(img: Image.Image) -> None:
    px = img.load()
    for x in range(40, 160):
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 8:
                    continue
                if d <= 1.2:
                    px[x + dx, 100 + dy] = (255, 255, 255)
                else:
                    fade = max(0, int(80 * (1.0 - d / 8.0)))
                    px[x + dx, 100 + dy] = (BG[0] + fade, BG[1] + fade, BG[2] + fade)


def test_fit_target_smaller_than_broad_support() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _line_with_glow(img)
    maps = build_laser_maps(img.load(), 200, 200)
    support = build_hysteresis_support(maps, min_area_px=6)
    fit = _fit_target_pixels(support, maps)
    assert len(fit) < len(support.support_pixels)
    assert len(fit) >= 4


def test_centerline_scores_higher_on_fit_target_than_broad_denominator_would() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _line_with_glow(img)
    maps = build_laser_maps(img.load(), 200, 200)
    support = build_hysteresis_support(maps, min_area_px=6)
    shape_type = classify_shape_type(support, maps)
    fit = _fit_target_pixels(support, maps)
    scored = score_geometry_fit(
        vectorize_continuous_stroke(support, BOX, maps),
        support,
        maps,
        BOX,
        shape_type,
    )
    assert scored.geometry_scores["stroke_coverage_score"] >= 0.35
    assert "broad_support_coverage_score" in scored.geometry_scores
    assert scored.geometry_scores.get("centerline_alignment_score", 0.0) >= 0.3
    # Fit target is a thinner set than broad support — primary score uses fit target.
    assert len(fit) < len(support.support_pixels)
