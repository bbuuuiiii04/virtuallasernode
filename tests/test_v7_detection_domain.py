"""V7: figure at/beyond box edge detected; out_of_box_geometry flagged (kills F1/F6)."""

import numpy as np
import pytest

pytest.importorskip("skimage", reason="scikit-image required")


def _make_boxes():
    from tools.shape_core_mask import FixtureBox
    left = FixtureBox("image_left", x0=10, y0=10, x1=60, y1=50)
    right = FixtureBox("image_right", x0=70, y0=10, x1=120, y1=50)
    return {"image_left": left, "image_right": right}


def test_figure_at_box_edge_fully_detected():
    """A stroke crossing the box right edge is detected and normalized with |x_norm|>1."""
    from tools.shape_core_mask import (
        assign_fixture,
        compute_bg_model,
        compute_combined_score,
        label_components,
        make_core_mask,
        make_roi_mask,
        pixel_to_wall_norm,
    )

    H, W = 60, 130
    img = np.full((H, W, 3), 20, dtype=np.uint8)
    # Horizontal stroke spanning box boundary: x 50..70 (left box ends at 60)
    img[30, 50:71, :] = 230
    roi = [0, 0, W, H]
    roi_mask = make_roi_mask(img.shape, roi)
    score = compute_combined_score(img)
    bg_med, bg_mad = compute_bg_model(score, roi_mask)
    core = make_core_mask(score, roi_mask, img, bg_med, bg_mad, min_core_area=1)
    labeled, n = label_components(core)

    assert n >= 1, "Stroke not detected"

    boxes = _make_boxes()
    # At least one component should span beyond image_left boundary
    found_out_of_box = False
    for cid in range(1, n + 1):
        comp = labeled == cid
        a_type, a_label, out_of_box = assign_fixture(comp, boxes)
        if a_label == "image_left" and out_of_box:
            found_out_of_box = True
            # Pixels strictly beyond x1 must normalize to > 1.0 (x=x1 maps to exactly 1.0)
            ys, xs = np.where(comp)
            left_box = boxes["image_left"]
            out_xs = xs[xs > left_box.x1]
            if len(out_xs) > 0:
                for ox in out_xs:
                    wn_x, _ = pixel_to_wall_norm(float(ox), float(ys[0]), left_box)
                    assert wn_x > 1.0, f"Out-of-box pixel x={ox} has wall_norm_x={wn_x:.2f} <= 1.0"

    assert found_out_of_box, "No image_left component with out_of_box_geometry=True"


def test_out_of_box_geometry_not_clamped():
    """Wall norm values outside [-1,1] are preserved, not clamped."""
    from tools.shape_core_mask import FixtureBox, bbox_wall_norm, pixel_to_wall_norm

    box = FixtureBox("image_left", x0=100, y0=100, x1=200, y1=200)
    # Pixel beyond right edge
    wx, wy = pixel_to_wall_norm(210.0, 150.0, box)
    assert wx > 1.0, f"Expected x_norm > 1.0 for pixel beyond box, got {wx}"

    # bbox spanning beyond box
    wn = bbox_wall_norm(90.0, 110.0, 210.0, 190.0, box)
    assert wn[0] < -1.0, f"Expected min_x_norm < -1.0, got {wn[0]}"
    assert wn[2] > 1.0, f"Expected max_x_norm > 1.0, got {wn[2]}"


def test_full_frame_out_of_box_flag_retired():
    """Old behavior: ALL 19 shapes flagged out_of_box from fixture glow. V7 flags per-component."""
    from tools.shape_core_mask import FixtureBox, assign_fixture

    H, W = 60, 130
    img_shape = (H, W, 3)

    # Component fully inside image_left
    comp = np.zeros((H, W), dtype=bool)
    comp[20:30, 15:55] = True
    boxes = {"image_left": FixtureBox("image_left", 10, 10, 60, 50)}
    _, label, out_of_box = assign_fixture(comp, boxes)
    assert label == "image_left"
    assert not out_of_box, "Fully-contained component should not be flagged out_of_box"
