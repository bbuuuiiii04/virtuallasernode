"""out_of_box must ignore sibling fixture calibration boxes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402

LEFT = FixtureBox(label="image_left", x0=0, y0=0, x1=100, y1=200)
RIGHT = FixtureBox(label="image_right", x0=100, y0=0, x1=200, y1=200)
DARK = (10, 10, 10)
BRIGHT = (255, 255, 255)


def test_other_fixture_bright_pixels_do_not_trigger_out_of_box() -> None:
    img = Image.new("RGB", (200, 200), DARK)
    px = img.load()
    for y in range(80, 120):
        for x in range(120, 180):
            px[x, y] = BRIGHT
    out = extract_shape_from_image(img, LEFT, min_area_px=10, other_boxes={"image_right": RIGHT})
    assert "out_of_box" not in out["quality_flags"]


def test_leak_outside_selected_box_still_flags() -> None:
    img = Image.new("RGB", (200, 200), DARK)
    px = img.load()
    for y in range(85, 115):
        for x in range(92, 100):
            px[x, y] = BRIGHT
    out = extract_shape_from_image(img, LEFT, min_area_px=10, other_boxes={"image_right": RIGHT})
    assert "out_of_box" in out["quality_flags"]
