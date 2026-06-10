# PR-G1 Static Shape Authority — Implementation Report (v6 geometry_kind repair)

## Summary

PR-G1 v6 repair separates **geometry representation** from **mask representation**. Yellow contact-sheet overlays now draw typed authority geometry (thin centerlines, branch paths, dot/segment anchors) and reject mask fills, unordered pixel clouds, and filled glow bands.

Visible aerial geometry remains `DECODER_FALLBACK_DRAWFAN` until PR-G3.

## Visual contact-sheet diagnosis (Brandon / ChatGPT)

| shape_ref | Prior verdict | v6 repair focus | Post-repair automated status |
|---|---|---|---|
| `sh1_e9743d87837d24ad` horizontal dotted/line | weak/noisy | centerline + segment anchors; high-core skeleton | **fail** (fragment coverage) |
| `sh1_2bae89cc023a3c52` angled line | pass/weak baseline | thin ordered centerline | **fail** (fragment; geometry kind correct) |
| `sh1_2e3da0a4330792c3` U-shape | weak/fail | bridged high-core skeleton, ordered centerline | **fail** (fragment coverage) |
| `sh1_ca3a93cf551f850e` multicolor curve | weak | per-color skeleton merge, span scoring | **weak** |
| `sh1_d9c0e1383b952508` diagonal stroke | fail (yellow smear) | reject filled bands; thin centerline only | **fail** (branch paths, no smear) |
| `sh1_542fc5442a80e0dc` blue dot cluster | fail/weak | dot anchors (not blob) | **fail** (still routed branched_complex on real capture) |
| `sh1_6fb79ee6e90df590` three blue strokes | weak/pass baseline | separate component anchors | **weak** |
| `sh1_39cde94194e37010` dotted arc | weak | dot/segment anchors, no smear | **weak** (branch paths; high-core dots merged on still) |
| `sh1_91ebda39c0075cac` compact swirl | weak/fail mask-like | branch polylines, not filled contour | **fail** |

**Honest outcome:** 0 pass / 4 weak / 15 fail / **0 usable authority**. Architecture is improved; real-capture pixel-fit coverage remains below pass threshold.

## geometry_kind contract

New module: `tools/shape_geometry_kind.py`

Authority kinds:

| geometry_kind | Meaning | Overlay draw |
|---|---|---|
| `centerline_polyline` | Ordered thin stroke centerline | 1px yellow line |
| `branch_polyline` | Ordered skeleton branch paths | 1px yellow line per branch |
| `dot_anchor_points` | Individual dot centers | small yellow circles |
| `segment_anchor_points` | Short dash/segment anchors | short yellow marks |
| `closed_loop_contour` | True thin ring contour | 1px closed contour |

Rejected kinds (never authority):

- `rejected_mask_area`
- `mask_area`
- `unordered_pixel_cloud`

Every selected shape and polyline now carries:

- `geometry_kind`
- `ordered` (bool)
- `vectorizer`
- `rejection_reasons` / `reject_reasons`
- `quality_flags`

`shape_point_count` now counts **geometry points only** (not raw support-mask pixels).

## How v6 prevents mask/unordered pixels becoming authority

1. **Annotate + validate** every vectorizer output before scoring (`validate_geometry_candidate`).
2. **Reject** dense mask pixel clouds, unordered sources (`mask_pixels`), filled closed bands on strokes, dotted-pattern smears, collapsed dot clusters.
3. **Hard-fail extraction** when `filled_band_geometry`, `unordered_pixel_cloud`, `dense_mask_pixels_as_polyline`, or `dotted_pattern_smear` — polylines cleared instead of serializing smear.
4. **Ring classification tightened** — `_is_ring_topology` requires thin core ring only (not interior glow gaps on diagonal bands).
5. **Removed** closed-loop support-mask contour fallback that produced filled bands.
6. **Contact-sheet overlay** (`render_overlay_image`) draws by `geometry_kind`; skips rejected kinds entirely.

## Dotted arc handling

- `dotted_component_vectorizer` outputs per-component **dot centroids** or **segment anchors** (line-like dashes).
- High-core component analysis for separated dots when hysteresis merges glow.
- Validation rejects long continuous centerlines on `dotted_pattern` (`dotted_pattern_smear`).
- Real capture `sh1_39cde94194e37010` still merges dots in support mask → routes `branched_complex` (weak, honest).

## Diagonal line filled-band fix

- Diagonal yellow smear was caused by `closed_loop_contour` on glow bands with interior holes.
- Ring detection now requires `_is_thin_core_ring` only.
- Continuous strokes skeletonize **high-core** when glow dominates support.
- Synthetic diagonal test: thin ordered `centerline_polyline`, no fat closed band.

## U-shape centerline fix

- Morphological bridge on high-core mask before skeletonization.
- Per-color skeleton path merge for multicolor U legs.
- Ordered path validation rejects unordered skeleton fallbacks.
- Real U capture still **fail** on fragment coverage (honest; geometry kind is centerline).

## Multicolor span coverage fix

- Per-color skeleton paths merged left-to-right when support is elongated.
- Multicolor routing prefers `continuous_stroke` over dot_cluster/branched when hue spans are stroke-like.
- `color_span_score` still gates pass/weak.
- `sh1_ca3a93cf551f850e`: **weak** (partial fragment).

## Dot cluster anchor fix

- `dot_cluster_vectorizer` preserves separate dot/segment anchors.
- High-core component routing for separated dots.
- `polylines_are_real_geometry` accepts multi-anchor dot layouts.
- Real `sh1_542fc5442a80e0dc` still routes `branched_complex` when cores do not separate cleanly.

## Runtime authority fix

`capture_index_runtime.py`:

```python
shape_authority = (
    bucket.get("shape_authority") is True
    and bool(shape_ref)
    and shape_point_count > 0
)
```

Weak/fail shapes with `shape_authority=false` in capture index do not expose authoritative `shape_ref` at runtime.

## Pass / weak / fail counts

| Status | Count |
|---|---:|
| pass | 0 |
| weak | 4 |
| fail | 15 |
| **usable_as_shape_authority** | **0** |

## geometry_kind distribution

| geometry_kind | Count |
|---|---:|
| centerline_polyline | 9 |
| branch_polyline | 9 |
| dot_anchor_points | 1 |

## Tests run

```bash
python3 -m pytest tests/test_shape*.py tests/test_geometry*.py tests/test_dotted*.py tests/test_capture_index*.py tests/test_weak*.py -q
# 85 passed

# New v6 geometry_kind contract tests (10):
# test_geometry_kind_contract.py
# test_no_unordered_mask_pixels_as_polyline.py
# test_contact_sheet_draws_geometry_kind.py
# test_dotted_arc_outputs_dot_anchors.py
# test_diagonal_line_rejects_filled_band.py
# test_u_shape_ordered_centerline.py
# test_multicolor_curve_geometry_covers_color_spans.py
# test_dot_cluster_outputs_separate_anchors.py
# test_capture_index_runtime_respects_shape_authority_flag.py
# + updated test_shape_type_routing, test_geometry_pixel_fit_scoring,
#   test_shape_polylines_not_bbox, test_shape_dot_cluster_preserves_components,
#   test_dotted_arc_vectorizer, test_shape_schema_required_fields
```

## Files changed (v6 geometry_kind repair)

| File | Role |
|---|---|
| `tools/shape_geometry_kind.py` | **New** — geometry kinds, validation, annotation |
| `tools/shape_stroke_vectorization.py` | geometry metadata, high-core skeleton, dotted/ring fixes |
| `tools/shape_extraction.py` | geometry_point_count, kind-aware overlay, hard reject |
| `tools/shape_polyline_utils.py` | dot-anchor real-geometry acceptance |
| `capture_index_runtime.py` | respect `bucket.shape_authority` |
| `tools/shape_library_builder.py` | schema fields: geometry_kind, ordered, rejection_reasons |
| 10 new/updated tests under `tests/` |

## Artifacts regenerated

```bash
python3 tools/shape_library_builder.py --phase6-limit 12
```

| Artifact | Path |
|---|---|
| Shape library | `artifacts/renderer/shape_library_v1.json` |
| Schema | `artifacts/renderer/shape_library_v1.schema.json` |
| Selection | `artifacts/renderer/pr-g1-shape-authority/shape_selection.json` |
| Contact sheets | `artifacts/renderer/pr-g1-shape-authority/contact_sheets/` |
| Overlay index | `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` |
| Visual review summary | `artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md` |
| Capture index join | `artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json` |

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3. Shape refs are internal authority plumbing only.
