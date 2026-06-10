"""V7: contact sheet yellow only for status==authority; rejected/provisional use non-yellow colors (§16)."""

import io
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PIL", reason="Pillow required")
pytest.importorskip("skimage", reason="scikit-image required")


def _make_still(H=64, W=128):
    from PIL import Image
    img = Image.fromarray(np.full((H, W, 3), 40, dtype=np.uint8))
    return img


def _make_dummy_record(shape_ref, status, polylines=None):
    if polylines is None:
        polylines = [{
            "polyline_id": "p0",
            "component_id": "c0",
            "geometry_kind": "open_centerline",
            "closed": False,
            "ordered": True,
            "points_px": [[20.0, 32.0], [60.0, 32.0]],
            "points_wall_norm": [[-0.5, 0.0], [0.5, 0.0]],
            "point_count": 2,
        }]
    return {
        "record_version": "shape-authority-v2",
        "shape_ref": shape_ref,
        "status": status,
        "authority_eligible": status == "authority",
        "fixture_box_label": "image_left",
        "components": [{"component_id": "c0", "bbox_px": [15, 28, 65, 36]}],
        "polylines": polylines,
        "topology_summary": {"dots": 0, "closed_strokes": 0, "open_strokes": 1},
        "metrics": {"core_precision": 0.95, "core_recall": 0.90, "halo_spill": 0.01,
                    "vector_fit_residual_px_p95": 0.5, "components_detected": 1, "components_vectorized": 1},
        "status_reasons": [],
    }


def _render_and_load_overlay(record, still_img):
    from PIL import Image
    from tools.shape_core_mask import FixtureBox
    from tools.shape_extract_v7 import render_contact_sheet

    fixture_boxes = {"image_left": FixtureBox("image_left", 10, 10, 90, 54)}
    with tempfile.TemporaryDirectory() as td:
        still_path = Path(td) / "still.jpg"
        still_img.save(still_path)
        out_path = Path(td) / "cs.png"
        render_contact_sheet(record, still_path, out_path, fixture_boxes, [0, 0, 128, 64])
        result = Image.open(out_path).convert("RGB")
    return np.array(result)


def _has_yellow_pixels(arr, x_offset=128):
    """Check if the overlay (right half) has any yellow pixels."""
    overlay = arr[:, x_offset:]
    # Yellow: R>200, G>200, B<80
    yellow = (overlay[:, :, 0] > 200) & (overlay[:, :, 1] > 200) & (overlay[:, :, 2] < 80)
    return bool(yellow.any())


def _has_magenta_pixels(arr, x_offset=128):
    overlay = arr[:, x_offset:]
    magenta = (overlay[:, :, 0] > 200) & (overlay[:, :, 1] < 80) & (overlay[:, :, 2] > 200)
    return bool(magenta.any())


def _has_orange_pixels(arr, x_offset=128):
    overlay = arr[:, x_offset:]
    orange = (overlay[:, :, 0] > 200) & (overlay[:, :, 1] > 100) & (overlay[:, :, 1] < 200) & (overlay[:, :, 2] < 80)
    return bool(orange.any())


def test_authority_record_uses_yellow():
    still = _make_still()
    record = _make_dummy_record("sh1_test_auth", "authority")
    arr = _render_and_load_overlay(record, still)
    assert _has_yellow_pixels(arr), "authority record should have yellow geometry pixels"
    assert not _has_magenta_pixels(arr), "authority record must not have magenta pixels"


def test_quarantined_record_uses_magenta_not_yellow():
    still = _make_still()
    record = _make_dummy_record("sh1_test_quar", "quarantined")
    arr = _render_and_load_overlay(record, still)
    assert _has_magenta_pixels(arr), "quarantined record should have magenta geometry pixels"
    assert not _has_yellow_pixels(arr), "quarantined record must NOT have yellow pixels"


def test_provisional_record_uses_orange_not_yellow():
    still = _make_still()
    record = _make_dummy_record("sh1_test_prov", "provisional")
    arr = _render_and_load_overlay(record, still)
    assert _has_orange_pixels(arr), "provisional record should have orange geometry pixels"
    assert not _has_yellow_pixels(arr), "provisional record must NOT have yellow pixels"


def test_no_ai_imports_in_extract_v7():
    """CI gate: shape_extract_v7 must not import any AI modules."""
    import ast
    src = Path("tools/shape_extract_v7.py").read_text()
    tree = ast.parse(src)
    ai_keywords = ["ai_shape", "gemini", "google.generativeai", "anthropic"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in getattr(node, "names", [])]
            module = getattr(node, "module", "") or ""
            all_names = names + [module]
            for name in all_names:
                for kw in ai_keywords:
                    assert kw not in (name or ""), f"Forbidden AI import in shape_extract_v7: {name}"
