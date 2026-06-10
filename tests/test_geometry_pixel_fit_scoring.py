"""Pixel-to-geometry fit must rank centerline above halo or fragment."""

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


def test_geometry_pixel_fit_prefers_centerline() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _line_with_glow(img)
    maps = build_laser_maps(img.load(), 200, 200)
    support = build_hysteresis_support(maps, min_area_px=6)
    shape_type = classify_shape_type(support, maps)
    good = score_geometry_fit(
        vectorize_continuous_stroke(support, BOX, maps),
        support,
        maps,
        BOX,
        shape_type,
    )

    fragment = good.__class__(
        vectorizer="fragment",
        shape_type=shape_type,
        polylines=[
            {
                "polyline_id": "frag",
                "points": [[-0.7, 0.0], [-0.65, 0.0]],
                "source": "skeleton",
                "closed": False,
                "point_count": 2,
            }
        ],
        support_components=support.support_components,
        topology="line",
    )
    fragment = score_geometry_fit(fragment, support, maps, BOX, shape_type)

    assert good.geometry_scores["stroke_coverage_score"] > fragment.geometry_scores["stroke_coverage_score"]
    assert good.score > fragment.score
