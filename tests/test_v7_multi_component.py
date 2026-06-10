"""V7: 4 synthetic squares + 1 dot => 5 components, 4 closed loops + 1 anchor (kills F4)."""

import numpy as np
import pytest

pytest.importorskip("skimage", reason="scikit-image required")


def _draw_square_outline(img, y0, x0, side, val):
    """Draw a thin square outline (1px thick) at (y0,x0) with given side length."""
    img[y0:y0 + side, x0, :] = val          # left edge
    img[y0:y0 + side, x0 + side - 1, :] = val  # right edge
    img[y0, x0:x0 + side, :] = val          # top edge
    img[y0 + side - 1, x0:x0 + side, :] = val  # bottom edge


def _make_four_squares_one_dot():
    H, W = 80, 300
    img = np.full((H, W, 3), 20, dtype=np.uint8)
    # 4 squares in a row
    for i in range(4):
        _draw_square_outline(img, 30, 20 + i * 60, 20, 230)
    # 1 bright dot
    img[15, 260, :] = 240
    return img


def test_four_squares_one_dot_five_components():
    from tools.shape_core_mask import (
        classify_component,
        compute_bg_model,
        compute_combined_score,
        label_components,
        make_core_mask,
        make_roi_mask,
    )

    img = _make_four_squares_one_dot()
    H, W = img.shape[:2]
    roi = [0, 0, W, H]
    roi_mask = make_roi_mask(img.shape, roi)
    score = compute_combined_score(img)
    bg_med, bg_mad = compute_bg_model(score, roi_mask)
    core = make_core_mask(score, roi_mask, img, bg_med, bg_mad, min_core_area=1)
    labeled, n = label_components(core)

    assert n == 5, f"Expected 5 components (4 squares + 1 dot), got {n}"

    classes = []
    for cid in range(1, n + 1):
        comp_mask = labeled == cid
        classes.append(classify_component(comp_mask))

    n_closed = classes.count("closed_stroke")
    n_dots = classes.count("dot")
    assert n_closed >= 4, f"Expected >=4 closed_stroke, got {n_closed} (classes={classes})"
    assert n_dots >= 1, f"Expected >=1 dot, got {n_dots}"


def test_four_squares_vectorized_no_drop():
    """All 4 squares must produce polylines (no drop — kills F4)."""
    from tools.shape_core_mask import (
        classify_component,
        compute_bg_model,
        compute_combined_score,
        label_components,
        make_core_mask,
        make_roi_mask,
    )
    from tools.shape_vectorize_v7 import vectorize_component

    img = _make_four_squares_one_dot()
    H, W = img.shape[:2]
    roi = [0, 0, W, H]
    roi_mask = make_roi_mask(img.shape, roi)
    score = compute_combined_score(img)
    bg_med, bg_mad = compute_bg_model(score, roi_mask)
    core = make_core_mask(score, roi_mask, img, bg_med, bg_mad, min_core_area=1)
    labeled, n = label_components(core)

    closed_polylines = []
    for cid in range(1, n + 1):
        comp_mask = labeled == cid
        c = classify_component(comp_mask)
        if c == "closed_stroke":
            polys = vectorize_component(comp_mask, c, score, f"c{cid}")
            closed_polylines.extend(polys)

    assert len(closed_polylines) >= 4, (
        f"Expected >=4 closed-stroke polylines (one per square), got {len(closed_polylines)}"
    )
    for pl in closed_polylines:
        assert pl["geometry_kind"] == "closed_centerline"
        assert len(pl["points_px"]) >= 3


def test_dot_produces_single_anchor():
    from tools.shape_core_mask import (
        classify_component,
        compute_bg_model,
        compute_combined_score,
        label_components,
        make_core_mask,
        make_roi_mask,
    )
    from tools.shape_vectorize_v7 import vectorize_component

    img = np.full((40, 40, 3), 20, dtype=np.uint8)
    img[20, 20, :] = 240
    roi_mask = np.ones((40, 40), dtype=bool)
    score = compute_combined_score(img)
    bg_med, bg_mad = compute_bg_model(score, roi_mask)
    core = make_core_mask(score, roi_mask, img, bg_med, bg_mad, min_core_area=1)
    labeled, n = label_components(core)
    assert n >= 1

    for cid in range(1, n + 1):
        comp_mask = labeled == cid
        c = classify_component(comp_mask)
        if c == "dot":
            polys = vectorize_component(comp_mask, c, score, "c0")
            assert len(polys) == 1
            assert polys[0]["geometry_kind"] == "dot_anchor"
            assert len(polys[0]["points_px"]) == 1
            return
    pytest.fail("No dot component found")
