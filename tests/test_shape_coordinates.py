"""PR-G1 coordinate conversion tests against analysis_geometry image_left box."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_extraction import FixtureBox, pixel_to_wall_norm  # noqa: E402

IMAGE_LEFT = FixtureBox(label="image_left", x0=60, y0=156, x1=554, y1=578)


def test_center_point() -> None:
    x, y = pixel_to_wall_norm(307, 367, IMAGE_LEFT)
    assert abs(x) < 1e-4
    assert abs(y) < 1e-4


def test_left_edge() -> None:
    x, y = pixel_to_wall_norm(60, 367, IMAGE_LEFT)
    assert abs(x + 1.0) < 1e-4
    assert abs(y) < 1e-4


def test_right_edge() -> None:
    x, y = pixel_to_wall_norm(554, 367, IMAGE_LEFT)
    assert abs(x - 1.0) < 1e-4
    assert abs(y) < 1e-4


def test_top_edge() -> None:
    x, y = pixel_to_wall_norm(307, 156, IMAGE_LEFT)
    assert abs(x) < 1e-4
    assert abs(y - 1.0) < 1e-4


def test_bottom_edge() -> None:
    x, y = pixel_to_wall_norm(307, 578, IMAGE_LEFT)
    assert abs(x) < 1e-4
    assert abs(y + 1.0) < 1e-4
