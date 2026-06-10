"""Dense unordered mask pixels must not serialize as authority polyline."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_geometry_kind import validate_geometry_candidate  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)


def test_unordered_mask_polyline_is_rejected() -> None:
    fake = [
        {
            "polyline_id": "mask0",
            "points": [[-0.8 + i * 0.01, 0.0] for i in range(80)],
            "source": "mask_pixels",
            "closed": False,
            "point_count": 80,
        }
    ]
    reasons, _ = validate_geometry_candidate(
        fake,
        vectorizer="skeleton_graph_stroke",
        shape_type="continuous_stroke",
        routed_shape_type="continuous_stroke",
        box=BOX,
    )
    assert "unordered_pixel_cloud" in reasons or any(r.startswith("rejected_geometry_kind:") for r in reasons)


def test_diagonal_glow_not_dense_mask_polyline() -> None:
    img = Image.new("RGB", (200, 200), (12, 12, 16))
    px = img.load()
    for x in range(30, 170):
        for dy in range(-10, 11):
            for dx in range(-10, 11):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 10:
                    continue
                px[x + dx, 100 + dy] = (255, 255, 255) if d <= 1.5 else (35, 35, 35)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    for poly in out.get("polylines") or []:
        assert poly.get("geometry_kind") != "unordered_pixel_cloud"
        assert poly.get("source") != "mask_pixels"
