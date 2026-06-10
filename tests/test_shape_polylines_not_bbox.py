"""PR-G1 polylines must be real geometry, not bbox-corner rectangles."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402
from tools.shape_polyline_utils import (  # noqa: E402
    polylines_are_real_geometry,
    polyline_is_broad_outer_contour,
    polyline_is_fat_closed_band,
    polyline_is_only_bbox_corners,
    polyline_is_thin_centerline,
    polyline_span_ratio,
)

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)
BRIGHT = (255, 255, 255)
DARK = (10, 10, 10)


def _blank() -> Image.Image:
    return Image.new("RGB", (200, 200), DARK)


def test_line_polyline_not_bbox_rectangle() -> None:
    img = _blank()
    px = img.load()
    for x in range(20, 180):
        px[x, 100] = BRIGHT
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["topology_class"] == "line"
    assert polylines_are_real_geometry(out["polylines"], out["source_pixel_bbox"], BOX)
    line_poly = out["polylines"][0]["points"]
    assert polyline_span_ratio(line_poly) >= 3.0
    assert out["polylines"][0].get("closed") is False


def test_two_clusters_have_separate_polylines() -> None:
    img = _blank()
    px = img.load()
    for y in range(80, 120):
        for x in range(30, 70):
            px[x, y] = BRIGHT
        for x in range(130, 170):
            px[x, y] = BRIGHT
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["topology_class"] == "two_clusters"
    assert len(out["polylines"]) >= 2
    for poly in out["polylines"]:
        assert not polyline_is_only_bbox_corners(poly["points"], poly.get("source_pixel_bbox", out["source_pixel_bbox"]), BOX)


def test_closed_loop_polyline_is_contour_not_bbox() -> None:
    img = _blank()
    px = img.load()
    for x in range(60, 140):
        px[x, 60] = BRIGHT
        px[x, 139] = BRIGHT
    for y in range(60, 140):
        px[60, y] = BRIGHT
        px[139, y] = BRIGHT
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    assert out["topology_class"] == "closed_loop"
    assert polylines_are_real_geometry(out["polylines"], out["source_pixel_bbox"], BOX)
    assert out["polylines"][0]["closed"] is True
    assert len(out["polylines"][0]["points"]) >= 4


def test_ring_not_only_bbox_corners() -> None:
    img = _blank()
    px = img.load()
    for x in range(50, 150):
        px[x, 50] = BRIGHT
        px[x, 149] = BRIGHT
    for y in range(50, 150):
        px[50, y] = BRIGHT
        px[149, y] = BRIGHT
    out = extract_shape_from_image(img, BOX, min_area_px=20)
    for poly in out["polylines"]:
        assert not polyline_is_only_bbox_corners(poly["points"], out["source_pixel_bbox"], BOX)


def test_line_with_glow_not_broad_closed_contour() -> None:
    img = _blank()
    px = img.load()
    for x in range(30, 170):
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 8:
                    continue
                px[x + dx, 100 + dy] = BRIGHT if d <= 1 else (40, 40, 40)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    poly = out["polylines"][0]
    assert poly.get("closed") is False
    assert polyline_is_thin_centerline(poly)
    assert not polyline_is_fat_closed_band(poly)
    assert not polyline_is_broad_outer_contour(
        poly,
        core_span_x=10,
        core_span_y=3,
        soft_span_x=20,
        soft_span_y=18,
    )


def test_straight_line_not_fat_closed_band() -> None:
    img = _blank()
    px = img.load()
    for x in range(20, 180):
        for dy in range(-10, 11):
            for dx in range(-10, 11):
                d = (dx * dx + dy * dy) ** 0.5
                if d > 10:
                    continue
                px[x + dx, 100 + dy] = BRIGHT if d <= 1.5 else (30, 30, 30)
    out = extract_shape_from_image(img, BOX, min_area_px=8)
    assert out["topology_class"] == "line"
    poly = out["polylines"][0]
    assert not polyline_is_fat_closed_band(poly)
    assert polyline_is_thin_centerline(poly)


@pytest.mark.skipif(
    not (ROOT / "artifacts" / "renderer" / "shape_library_v1.json").is_file(),
    reason="shape library not built yet",
)
def test_built_library_polylines_not_bbox_only() -> None:
    import json

    library = json.loads((ROOT / "artifacts" / "renderer" / "shape_library_v1.json").read_text())
    from tools.shape_extraction import load_fixture_boxes

    geom = json.loads((ROOT / "captures/fixture_model/analysis_geometry.json").read_text())
    boxes = load_fixture_boxes(geom)
    for shape in library.get("shapes") or []:
        box = boxes[shape["fixture_box_label"]]
        assert polylines_are_real_geometry(shape["polylines"], shape["source_pixel_bbox"], box), (
            f"shape {shape['shape_ref']} has bbox-only polylines"
        )
