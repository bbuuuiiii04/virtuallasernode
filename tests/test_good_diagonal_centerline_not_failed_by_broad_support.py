"""A good thin diagonal centerline should not hard-fail due to broad glow denominator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_stroke_vectorization import classify_visual_status  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BG = (12, 12, 16)


def _diagonal_with_glow(img: Image.Image) -> None:
    px = img.load()
    for t in range(45):
        cx = 35 + t * 3
        cy = 145 - t * 2
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 8:
                    continue
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 200 and 0 <= yy < 200:
                    px[xx, yy] = (240, 230, 60) if d <= 1.2 else tuple(
                        min(255, BG[i] + int(70 * (1 - d / 8))) for i in range(3)
                    )


def test_diagonal_centerline_not_hard_fail() -> None:
    img = Image.new("RGB", (200, 200), BG)
    _diagonal_with_glow(img)
    out = extract_shape_from_image(img, BOX, min_area_px=6)
    shape = {
        "shape_point_count": out["shape_point_count"],
        "polylines": out["polylines"],
        "geometry_scores": out.get("geometry_scores") or {},
        "geometry_kind": out.get("geometry_kind"),
        "ordered": out.get("ordered", True),
        "quality_flags": out.get("quality_flags") or [],
        "rejection_reasons": out.get("rejection_reasons") or [],
        "selected_extractor": out.get("selected_extractor"),
        "candidate_scores": out.get("candidate_scores") or {},
        "rejected_candidate_reasons": out.get("rejected_candidate_reasons") or {},
    }
    status, _, _ = classify_visual_status(shape)
    assert status in ("pass", "weak")
    assert out.get("geometry_kind") in ("centerline_polyline", "branch_polyline")
