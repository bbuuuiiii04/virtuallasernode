"""Regression: validate_geometry_candidate must use each polyline's own source."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_extraction import FixtureBox  # noqa: E402
from tools.shape_geometry_kind import validate_geometry_candidate  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)


def test_dotted_pattern_smear_uses_per_polyline_source_not_stale_outer() -> None:
    """If comprehension used outer poly.get('source'), segment anchors would be misread."""
    polylines = [
        {
            "polyline_id": "seg0",
            "points": [[-0.4, 0.0], [-0.2, 0.0]],
            "source": "segment_anchor",
            "closed": False,
            "geometry_kind": "segment_anchor_points",
        },
        {
            "polyline_id": "smear",
            "points": [[-0.5, 0.1], [-0.3, 0.1], [-0.1, 0.1], [0.1, 0.1]],
            "source": "skeleton",
            "closed": False,
            "geometry_kind": "centerline_polyline",
        },
    ]
    reasons, _ = validate_geometry_candidate(
        polylines,
        vectorizer="dotted_component_vectorizer",
        shape_type="dotted_pattern",
        routed_shape_type="dotted_pattern",
        box=BOX,
    )
    assert "dotted_pattern_smear" in reasons

    polylines[1]["source"] = "segment_anchor"
    polylines[1]["geometry_kind"] = "segment_anchor_points"
    reasons2, _ = validate_geometry_candidate(
        polylines,
        vectorizer="dotted_component_vectorizer",
        shape_type="dotted_pattern",
        routed_shape_type="dotted_pattern",
        box=BOX,
    )
    assert "dotted_pattern_smear" not in reasons2
