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


def test_compact_blob_with_dash_structure_traces_arc():
    """Glow-fused blob with saturated dashes inside traces a dotted_arc_path.

    Mimics cue_002: the CORE component is a solid blob (white dashes fused
    with bright red glow), but the saturated structure inside is a dotted
    arc. The vectorizer must trace one ordered open polyline through ALL
    dashes — not a tiny partial trace, not the blob outline.
    """
    from tools.shape_vectorize_v7 import (
        extract_structure_submask,
        vectorize_component,
    )

    H = W = 128
    img = np.full((H, W, 3), 20, dtype=np.uint8)
    cy, cx = 64, 64
    # Red glow blob (saturated red, but min-channel stays low)
    mask = np.zeros((H, W), dtype=bool)
    for y in range(H):
        for x in range(W):
            if ((y - cy) ** 2 + (x - cx) ** 2) ** 0.5 <= 22:
                mask[y, x] = True
                img[y, x] = (220, 40, 40)
    # White dashes along an arc inside the blob
    dash_centers = [(-14, -10), (-5, -2), (5, 1), (14, -8)]
    for dx, dy in dash_centers:
        y0, x0 = cy + dy, cx + dx
        img[y0 - 1:y0 + 2, x0 - 3:x0 + 4] = (255, 255, 255)

    score_map = img.astype(np.float64).max(axis=2)

    structure = extract_structure_submask(mask, img)
    assert structure.sum() < mask.sum() * 0.3, (
        "structure submask should isolate dashes, not the whole glow blob"
    )

    polys = vectorize_component(mask, "closed_stroke", score_map, "s0", img_rgb=img)
    kinds = [p["geometry_kind"] for p in polys]
    assert kinds == ["dotted_arc_path"], f"Expected one dotted_arc_path, got {kinds}"

    pts = polys[0]["points_px"]
    assert polys[0]["closed"] is False
    assert polys[0]["ordered"] is True
    # The path must pass near EVERY dash (no partial trace)
    for dx, dy in dash_centers:
        tx, ty = cx + dx, cy + dy
        dmin = min(((p[0] - tx) ** 2 + (p[1] - ty) ** 2) ** 0.5 for p in pts)
        assert dmin <= 4.0, f"arc path misses dash at ({tx},{ty}): min dist {dmin:.1f}"
    # And it must span the full arc extent, not a fragment
    xs = [p[0] for p in pts]
    assert max(xs) - min(xs) >= 24, "arc path is a fragment, not the full dotted arc"


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

    # Rectangle frame: low solidity, classified by its enclosed hole
    assert solidity < 0.65, f"Test setup: solidity {solidity:.3f} should be < 0.65"

    comp_class = classify_component(mask)
    assert comp_class == "closed_stroke", (
        f"Rectangle with hole should be closed_stroke, got {comp_class} "
        f"(solidity={solidity:.3f})"
    )

