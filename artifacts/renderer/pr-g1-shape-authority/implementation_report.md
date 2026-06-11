# PR-G1 v7 Slice 1: Peak-Contour Arc Tracing

## Summary

The pipeline was failing to trace the visible red arc in `cue_002` (`sh1_adb58093da473f3e`). The CORE mask correctly captures the bright laser region (1,314px, 44×39), but the skeleton of this compact blob produces a tiny closed loop (60pts, 67px path_len vs 151px mask perimeter) that doesn't represent the visible arc features.

### Previous Failed Approaches

1. **Dot classification gate** (solidity > 0.7): Classified the blob as a dot, producing just a single point. The user rejected this — the visible arc was not being traced.
2. **Mask contour rendering**: Drew the outer CORE mask boundary on the contact sheet. Regressed dual-dot by tracing into the glow region.
3. **mask_contour_fallback**: Tried tracing the CORE mask boundary as geometry. Regressed row-of-squares (threshold couldn't discriminate).

### Correct Approach: Peak-Intensity Sub-Masking

The arc structure IS present inside the CORE mask — at a higher intensity threshold. At p75 (brightness ≥ 206), the core mask's 1,314px blob resolves into the actual arc/crescent features (335px, solidity 0.52). Tracing the contour of this sub-mask produces a 28-point closed polyline that faithfully traces the visible arc.

## Changes

### `tools/shape_vectorize_v7.py`
- Pass `score_map` through to `_vectorize_closed_stroke`
- Added peak-contour fallback: when a closed_stroke's skeleton centerline path_len is < 50% of the mask perimeter AND solidity > 0.65, threshold the score_map at p75 within the mask and trace the resulting sub-mask contour
- New geometry_kind: `peak_contour` — traces the peak-intensity arc features
- Guard conditions prevent false triggering on row-of-squares (solidity ≤ 0.61)

### `tools/shape_extract_v7.py`
- Removed `_draw_dot_mask_contours` (glow-tracing regression)
- Removed `core_mask_rle` parameter from `render_contact_sheet`
- Sibling aperture rendering (dim cyan bboxes) preserved

### `tools/shape_core_mask.py`
- **Unmodified** — classification is correct as-is

### `tools/shape_validation_v2.py`
- **Unmodified** — peak_contour validates through standard precision/recall

## Tests

```bash
python3 -m pytest tests/test_v7_*.py -v
# 30 passed in 8.77s
```

## Extraction Results

| Ref | Status | Topology | Precision | Recall | Geometry |
|-----|--------|----------|-----------|--------|----------|
| sh1_21b9e82ef84b930b | provisional | 4 closed + 1 dot | 1.00 | 0.94 | closed_centerline × 4, dot_anchor × 1 |
| sh1_41c84ad2ac1f458e | provisional | 2 dots | 1.00 | 1.00 | dot_anchor × 2 |
| sh1_adb58093da473f3e | provisional | 1 closed | 1.00 | 0.64 | **peak_contour × 1 (28 pts)** |

Note: cue_002 recall = 0.64 because the peak_contour traces only the brightest 25% of the CORE mask (the actual arc features), not the full glow region. This is correct — the contour is physically meaningful and visually faithful.

## Explicit Non-Mutations
- `captures/**` not mutated
- `data/fixture_model.json` not mutated
- `tools/shape_core_mask.py` not mutated
- `tools/shape_validation_v2.py` not mutated
