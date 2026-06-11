# PR-G1 v7 Slice 1: Mask-Backed Fallback Fix

## Summary

The pipeline was failing to accurately represent the captured laser evidence for `cue_002` (`sh1_adb58093da473f3e`). The vector trace (a peak-contour arc) was merely a diagnostic approximation and failed to capture the full visual extent of the laser dotted arc. Furthermore, the sibling aperture region was acknowledged via accounting but not traced or mask-represented.

Following user direction, the previous vector-only approaches were replaced with **Mask-Backed Fallback**. When vector tracing is inadequate (as with compact blobs where the skeleton is uninformative), the vectors are demoted to diagnostic-only (`render_role="diagnostic"`), and the extraction claims `render_authority="core_mask"`. The final contact sheets visually prove what the system truly found by rendering the CORE mask evidence as a semi-transparent overlay.

### Mask-Backed Fallback Implementation

1.  **Render Roles**: The vectorizer loop now evaluates the quality of `closed_centerline` traces. If the source mask is a compact blob (solidity > 0.65), the resulting trace is demoted to `render_role="diagnostic"`. `peak_contour` fallbacks are explicitly diagnostic. Only faithful traces (e.g., straight squares with low solidity, or dots) retain `render_role="render"`.
2.  **Authority Hand-off**: If all non-dot vectors are diagnostic, `render_authority` switches to `"core_mask"`. `render_vectors` becomes `null`, and `render_fallback` is `"core_mask"`.
3.  **Visual Evidence Layer**: The `render_contact_sheet` was completely rewritten to support mask overlays. It now takes the *full* core mask (across all apertures) and renders:
    *   **Orange fill (90 alpha)** for components assigned to the selected aperture.
    *   **Teal fill (90 alpha)** for sibling aperture components.
    *   **Dim purple fill** for unaccounted components.
4.  **Vector Hierarchy on Contact Sheet**: Vectors with `render_role="render"` are drawn brightly and 2px wide. Vectors with `render_role="diagnostic"` are drawn 1px wide with 50% opacity, clearly showing they are not the primary authority.

## Results vs Acceptance Criteria

*   **cue_002 represents dotted arc**: YES. The contact sheet shows the true full extent of the laser light using the orange mask overlay. The tiny peak-contour is visibly dim (diagnostic).
*   **Both apertures accounted**: YES. The sibling dot arc on the right is fully filled with a teal mask overlay and labeled "sibling".
*   **Bad vectors are diagnostic**: YES. Compact blob centerlines and peak contours are demoted and visually dim.
*   **CORE mask remains truth**: YES. The visible output *is* the CORE mask.
*   **No regressions**: YES.
    *   `row-of-squares`: Remains `render_authority="vector"`. The vector traces are bright. The mask fill is also present beneath them as evidence.
    *   `dual-dot`: Remains `render_authority="core_mask"` because it's just dots. Dot anchors are bright, mask fill shows the core. Glow traces (previous regression) are gone.
*   **Tests updated**: YES. `test_cue_002_arcs_detected_no_fragment_only` now strictly asserts that `render_authority == "core_mask"` and `render_vectors is None`.
*   **Tests passing**: YES. 30/30 tests pass.

## Changes

### `tools/shape_extract_v7.py`
- Added `render_role` assignment logic.
- Implemented `render_authority` determination based on vector roles.
- Plumbed `full_core_rle` into the extraction record and passed it to the renderer.
- Completely rewrote `render_contact_sheet` to draw transparent mask layers and differentiate diagnostic vs render vectors.

### `tests/test_v7_real_media_smoke.py`
- Updated `test_cue_002_arcs_detected_no_fragment_only` to verify mask-backed fallback schema states.
- Added `render_authority` to required schema test.

### `tests/test_v7_core_mask_synthetic.py`
- Kept the `test_compact_blob_peak_contour_fallback` to ensure the vectorizer logic itself (even as a diagnostic fallback) functions.

## Explicit Non-Mutations
- `captures/**` not mutated
- `data/fixture_model.json` not mutated
- `tools/shape_core_mask.py` not mutated
- `tools/shape_validation_v2.py` not mutated
