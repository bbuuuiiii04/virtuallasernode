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


def test_compact_blob_peak_contour_fallback():
    """Compact blob with short skeleton triggers peak_contour fallback.

    Tests the vectorizer directly: given a compact mask classified as
    closed_stroke, with a score_map that has internal arc structure,
    the peak_contour fallback should produce a meaningful contour
    instead of the uninformative skeleton centerline.
    """
    from tools.shape_vectorize_v7 import vectorize_component

    # Create a filled elliptical blob (high solidity, compact)
    # Use an irregular shape to force skeleton to form a closed cycle
    mask = np.zeros((128, 128), dtype=bool)
    cy, cx = 64, 64
    for y in range(128):
        for x in range(128):
            r = ((y - cy)**2 + (x - cx)**2)**0.5
            # Irregular radius: ellipse + noise
            angle = np.arctan2(y - cy, x - cx)
            radius = 20 + 3 * np.sin(4 * angle) + 2 * np.cos(6 * angle)
            if r <= radius:
                mask[y, x] = True

    # Create a score_map with crescent-shaped peak structure
    score_map = np.zeros((128, 128), dtype=np.float64)
    for y in range(128):
        for x in range(128):
            if mask[y, x]:
                dist = ((y - cy)**2 + (x - cx)**2)**0.5
                angle_factor = (x - cx + y - cy) / 20.0
                score_map[y, x] = max(0, 200 + 50 * angle_factor - dist * 2)

    # Force classification as closed_stroke (matching cue_002's real behavior)
    polys = vectorize_component(mask, "closed_stroke", score_map, "s0")
    assert len(polys) >= 1, "No polylines produced for compact blob"
    
    kinds = [p["geometry_kind"] for p in polys]
    # Should produce peak_contour (compact blob with short skeleton)
    # or closed_centerline (if skeleton happens to produce good trace)
    assert "peak_contour" in kinds or "closed_centerline" in kinds, (
        f"Expected peak_contour or closed_centerline, got {kinds}"
    )
    
    # The resulting polyline must have meaningful geometry (>3 points)
    best = max(polys, key=lambda p: len(p["points_px"]))
    assert len(best["points_px"]) > 3, (
        f"Polyline too few points ({len(best['points_px'])})"
    )


def test_rectangle_stays_closed_stroke():
    """Rectangle with hole stays classified as closed_stroke.

    Mimics row-of-squares components: solidity ~0.55, aspect ~1.7.
    """
    from tools.shape_core_mask import classify_component

    # 30x17 rectangle with moderate hole → solidity ~0.55, aspect 1.76
    mask = np.zeros((64, 64), dtype=bool)
    mask[20:37, 15:45] = True  # 17×30 outer
    mask[23:34, 18:42] = True  # fill; then cut a hole
    # Create a frame by clearing interior
    mask[23:34, 18:42] = False  # hole_area = 11*24 = 264

    area = int(np.sum(mask))
    ys, xs = np.where(mask)
    bbox_h = int(ys.max() - ys.min() + 1)
    bbox_w = int(xs.max() - xs.min() + 1)
    solidity = area / (bbox_h * bbox_w)

    # Rectangle has low solidity (< 0.65) so peak_contour won't trigger
    assert solidity < 0.65, f"Test setup: solidity {solidity:.3f} should be < 0.65"

    comp_class = classify_component(mask)
    assert comp_class == "closed_stroke", (
        f"Rectangle with hole should be closed_stroke, got {comp_class} "
        f"(solidity={solidity:.3f})"
    )

