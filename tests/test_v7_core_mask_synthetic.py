"""V7: synthetic stroke + gaussian halo — core mask excludes halo."""

import numpy as np
import pytest

pytest.importorskip("skimage", reason="scikit-image required")


def _make_synthetic_stroke_image(H=64, W=64, stroke_val=240, halo_sigma=3, bg_val=30):
    """Bright horizontal stroke at row 32 with gaussian halo."""
    img = np.full((H, W, 3), bg_val, dtype=np.uint8)
    # Core: row 32, cols 10-54, brightness stroke_val
    img[32, 10:55, :] = stroke_val
    # Add gaussian-shaped halo around stroke
    from scipy.ndimage import gaussian_filter
    halo_layer = np.zeros((H, W), dtype=np.float32)
    halo_layer[32, 10:55] = stroke_val
    halo_blurred = gaussian_filter(halo_layer, sigma=halo_sigma)
    for c in range(3):
        img[:, :, c] = np.clip(img[:, :, c].astype(np.float32) + halo_blurred * 0.4, 0, 255).astype(np.uint8)
    return img


def _make_roi_mask_full(img):
    H, W = img.shape[:2]
    mask = np.zeros((H, W), dtype=bool)
    mask[:, :] = True
    return mask


def test_core_mask_excludes_halo_at_all_intensities():
    from tools.shape_core_mask import (
        compute_bg_model,
        compute_combined_score,
        make_core_mask,
        make_roi_mask,
    )

    for stroke_val in [180, 210, 240]:
        img = _make_synthetic_stroke_image(stroke_val=stroke_val)
        roi = [0, 0, 64, 64]
        roi_mask = make_roi_mask(img.shape, roi)
        score = compute_combined_score(img)
        bg_med, bg_mad = compute_bg_model(score, roi_mask)
        core = make_core_mask(score, roi_mask, img, bg_med, bg_mad)

        # Core pixels at the stroke center should be detected
        stroke_core_found = bool(np.any(core[32, 10:55]))
        assert stroke_core_found, f"stroke val={stroke_val}: no core detected on stroke"

        # Halo rows (several pixels above/below stroke) should NOT be in core
        halo_rows = list(range(28)) + list(range(36, 64))
        halo_in_core = bool(np.any(core[halo_rows, :]))
        assert not halo_in_core, f"stroke val={stroke_val}: halo pixels included in core mask"


def test_background_model_excludes_laser_pixels():
    from tools.shape_core_mask import compute_bg_model, compute_combined_score

    img = _make_synthetic_stroke_image()
    H, W = img.shape[:2]
    roi_mask = np.ones((H, W), dtype=bool)
    score = compute_combined_score(img)
    bg_med, bg_mad = compute_bg_model(score, roi_mask)

    # Background median should be close to background score, not stroke score
    bg_score_approx = float(np.median(score[:28, :]))
    assert abs(bg_med - bg_score_approx) < bg_score_approx * 0.5, (
        f"bg_med={bg_med:.1f} too far from expected bg level {bg_score_approx:.1f}"
    )
    assert bg_mad > 0, "bg_mad must be positive"


def test_sat_floor_catches_white_core():
    """min(R,G,B) >= sat_floor => included even if score is borderline."""
    from tools.shape_core_mask import (
        compute_bg_model,
        compute_combined_score,
        make_core_mask,
        make_roi_mask,
    )

    img = np.full((32, 32, 3), 20, dtype=np.uint8)
    # White core at center
    img[14:18, 14:18, :] = 220  # min channel = 220 >= default sat_floor=200
    roi_mask = np.ones((32, 32), dtype=bool)
    score = compute_combined_score(img)
    bg_med, bg_mad = compute_bg_model(score, roi_mask)
    core = make_core_mask(score, roi_mask, img, bg_med, bg_mad, sat_floor=200)
    assert np.any(core[14:18, 14:18]), "white pixels with min_channel>=sat_floor not in core"
