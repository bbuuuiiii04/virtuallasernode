"""Dense branch polylines that recreate mask fills must be rejected."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_extraction import FixtureBox  # noqa: E402
from tools.shape_geometry_kind import validate_geometry_candidate  # noqa: E402

BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)


def _dense_grid_branches() -> list[dict]:
    branches = []
    for i in range(8):
        y = -0.4 + i * 0.1
        pts = [[-0.5 + j * 0.05, y] for j in range(20)]
        branches.append(
            {
                "polyline_id": f"b{i}",
                "points": pts,
                "source": "skeleton_branch",
                "closed": False,
                "geometry_kind": "branch_polyline",
                "ordered": True,
            }
        )
    return branches


def test_dense_branch_scribble_rejected() -> None:
    reasons, _ = validate_geometry_candidate(
        _dense_grid_branches(),
        vectorizer="skeleton_branch_vectorizer",
        shape_type="branched_complex",
        routed_shape_type="branched_complex",
        box=BOX,
    )
    assert "dense_branch_scribble" in reasons or "branch_mask_fill_like" in reasons


def test_sparse_branches_not_rejected() -> None:
    sparse = [
        {
            "polyline_id": "b0",
            "points": [[-0.5, -0.2], [0.0, 0.0], [0.5, 0.2]],
            "source": "skeleton_branch",
            "closed": False,
            "geometry_kind": "branch_polyline",
            "ordered": True,
        }
    ]
    reasons, _ = validate_geometry_candidate(
        sparse,
        vectorizer="skeleton_branch_vectorizer",
        shape_type="branched_complex",
        routed_shape_type="branched_complex",
        box=BOX,
    )
    assert "dense_branch_scribble" not in reasons
    assert "branch_mask_fill_like" not in reasons
