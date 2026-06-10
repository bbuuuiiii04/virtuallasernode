# PR-G1 Static Shape Authority — Implementation Report (v5 multi-candidate fix)

## Summary

PR-G1 builds internal wall-space static shape authority from local `captures/fixture_model/**` stills. Extraction **v5** replaces the single global threshold with **six candidate extractors per capture**, shape-sanity scoring, and best-candidate selection. Visible aerial geometry remains `_drawFan()` decoder fallback until PR-G3.

**Brandon instruction:** Pass only if the yellow overlay roughly follows the actual bright laser drawing, not just the glow around it.

## Why v4 over-tightened

The first visual-quality fix (v3→v4) tightened core thresholds to stop broad glow blobs. That single-threshold approach was unstable:

- **Too loose** → broad glow halo traced as shape authority
- **Too strict** → tiny stroke fragments, missing U-legs, dropped purple/cyan/green sections, dot clusters collapsed or clipped at fixture-box edges

v5 stops tuning one global gate and instead runs multiple extraction strategies, scores them for coverage vs fragments vs broad area, and selects the best viable candidate — or marks the shape weak/fail when none are plausible.

## Multi-candidate extraction strategy

New module: `tools/shape_candidate_extraction.py`

| Candidate | Role |
|---|---|
| `bright_core_centerline` | High-confidence bright core; good for simple lines; penalized if fragment-only |
| `color_saturation_centerline` | Color-aware mask (max RGB + saturation + channel bonuses); preserves blue/cyan/purple/magenta/red/green/yellow |
| `adaptive_local_core` | Per-glow-region adaptive percentile threshold; recovers dim stroke without full halo |
| `segmented_components` | Separate polylines per dot/segment/cluster; good for dotted lines and multi-dot patterns |
| `thin_stroke_skeleton_from_soft_mask` | Softer mask + medial ridge / path trace; connects full visible stroke without outer halo contour |
| `contour_only_closed_loop` | Thin closed rings only; not used for ordinary arcs/U-shapes unless centerline fails and is flagged weak |

### Scoring (shape sanity, not pixel count)

Each candidate is scored on:

- Path coverage vs glow bbox (x/y span, path length vs diagonal)
- Broad blob penalty (core area vs glow area ratio)
- Fragment-only penalty (tiny span, endpoint-only capture)
- Missing color span penalty (multicolor strokes)
- Over-segmentation penalty (many tiny polylines on continuous strokes)
- Fixture-edge clipping penalty (geometry stuck to box edge when laser is interior)
- Conditional bonuses (e.g. segmented_components only when multiple small glow blobs are present)

### Debug fields on every shape entry

- `extraction_candidates_tried`
- `selected_extractor`
- `selected_extractor_reason`
- `candidate_scores`
- `rejected_candidate_reasons`

### Shape authority policy

If no candidate is visually plausible:

- `visual_status = weak` or `fail`
- `usable_as_shape_authority = false` for `fail`
- Bad fragments are not silently promoted to clean authority
- Metadata retained for Brandon review

Automated visual classification defaults to **weak** pending human overlay check; only synthetic/unit tests assert pass. Real captures require Brandon eye review on contact sheets.

## Files changed (v5 fix pass)

| File | Role |
|---|---|
| `tools/shape_candidate_extraction.py` | **New** — six candidates, scoring, selection, visual classification |
| `tools/shape_extraction.py` | v5 entry point; delegates to candidate pipeline; `EXTRACTION_POLICY_VERSION = "v5"` |
| `tools/shape_library_builder.py` | Candidate debug fields, visual review summary columns, schema extensions |
| `tools/shape_polyline_utils.py` | `polyline_is_fat_closed_band`, `polyline_is_thin_centerline` helpers |
| `tests/test_shape_candidate_selection.py` | Fragment vs halo vs thin-stroke selection |
| `tests/test_shape_u_recovery_not_fragment.py` | U-shape with uneven brightness |
| `tests/test_shape_multicolor_curve_full_recovery.py` | Cyan/green/yellow/purple curve |
| `tests/test_shape_dot_cluster_preserves_components.py` | Red/blue dot cluster components |
| `tests/test_shape_fixture_edge_clipping_detection.py` | Box-edge clipping detection |
| `tests/test_shape_visual_review_summary.py` | Summary field honesty; fail → not usable |
| `tests/test_shape_schema_required_fields.py` | New required shape fields |
| `tests/test_shape_extraction_colored_synthetic.py` | Updated for v5 pipeline |
| `tests/test_shape_polylines_not_bbox.py` | Fat-band rejection retained |

## Artifacts regenerated

```bash
python3 tools/shape_library_builder.py --phase6-limit 12
```

| Artifact | Path |
|---|---|
| Selection | `artifacts/renderer/pr-g1-shape-authority/shape_selection.json` |
| Shape library | `artifacts/renderer/shape_library_v1.json` (19 shapes, policy **v5**) |
| Schema | `artifacts/renderer/shape_library_v1.schema.json` |
| Contact sheets | `artifacts/renderer/pr-g1-shape-authority/contact_sheets/` (19 PNGs) |
| Overlay index | `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` |
| Visual review summary | `artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md` |
| Capture index join | `artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json` (19 vectors) |

## Build stats

| Metric | Count |
|---|---:|
| Lane A (ch3_family) | 12 |
| Lane B (phase6_cue) | 12 |
| Skipped/excluded | 5 |
| Shapes in library | 19 |
| Vectors with shape_ref | 19 |

## Selected extractor counts

| Extractor | Count |
|---|---:|
| `color_saturation_centerline` | 7 |
| `segmented_components` | 7 |
| `adaptive_local_core` | 3 |
| `contour_only_closed_loop` | 2 |
| `bright_core_centerline` | 0 |
| `thin_stroke_skeleton_from_soft_mask` | 0 |

Note: no real capture selected `bright_core_centerline` or `thin_stroke_skeleton_from_soft_mask` in this build — scoring rejected them (fragment_only, missing_color_span, missing_vertical_stroke_span) while other candidates scored higher. Synthetic tests confirm these candidates work when appropriate.

## Visual pre-review (automated, honest)

| Status | Count |
|---|---:|
| pass | 0 |
| weak | 19 |
| fail | 0 |
| usable_as_shape_authority | 17 |
| **not usable / low-confidence** | **2** |

Shapes marked **not usable** (`usable_as_shape_authority = false`):

- `sh1_2e3da0a4330792c3` — U-wave dynamic macro (`segmented_components`, fragment risk)
- `sh1_91ebda39c0075cac` — compact swirl dynamic macro (`segmented_components`, fragment risk)

All 19 shapes require Brandon contact-sheet review before any pass claim. Automated summary intentionally reports **0 pass** until human overlay confirmation.

## Tests run

```bash
python3 -m pytest tests/test_shape_selection.py                     → 6 passed
python3 -m pytest tests/test_shape_library_schema.py                → 2 passed
python3 -m pytest tests/test_shape_schema_required_fields.py        → 3 passed
python3 -m pytest tests/test_shape_coordinates.py                   → 5 passed
python3 -m pytest tests/test_shape_extraction_synthetic.py          → 7 passed
python3 -m pytest tests/test_shape_extraction_colored_synthetic.py  → 5 passed
python3 -m pytest tests/test_shape_polylines_not_bbox.py            → 7 passed
python3 -m pytest tests/test_shape_candidate_selection.py           → 1 passed
python3 -m pytest tests/test_shape_u_recovery_not_fragment.py       → 1 passed
python3 -m pytest tests/test_shape_multicolor_curve_full_recovery.py → 1 passed
python3 -m pytest tests/test_shape_dot_cluster_preserves_components.py → 1 passed
python3 -m pytest tests/test_shape_fixture_edge_clipping_detection.py → 1 passed
python3 -m pytest tests/test_shape_visual_review_summary.py         → 2 passed
python3 -m pytest tests/test_capture_index_runtime_shape_refs.py    → 3 passed
python3 -m pytest tests/test_no_historical_pr_g1_inputs.py          → 3 passed
python3 -m pytest tests/test_shape_ref_stability.py                 → 3 passed
python3 -m pytest tests/test_shape_selection_rep_distance.py        → 3 passed
python3 -m pytest tests/test_shape_out_of_box_ignores_other_fixture.py → 2 passed
python3 -m pytest tests/test_shape_core_centerline_not_glow_band.py → 1 passed
python3 -m pytest tests/test_shape_dotted_line_preserves_segments.py → 1 passed
python3 -m pytest tests/test_shape_purple_blue_recovery.py          → 1 passed
python3 -m pytest tests/test_shape_u_centerline_not_blob.py         → 1 passed
python3 -m pytest tests/test_shape_complex_internal_strokes_not_outer_blob.py → 1 passed
python3 -m pytest tests/test_shape_core_not_halo.py                 → 2 passed
python3 -m pytest tests/test_shape_u_arc_centerline.py              → 1 passed
python3 -m pytest tests/test_shape_complex_internal_strokes.py     → 1 passed
node tests/test_renderer_motionstate.js                             → 26 passed
```

**Total: 65 pytest + 26 JS — all pass**

## Diagnostics honesty (unchanged)

- `visible_geometry_source = DECODER_FALLBACK_DRAWFAN`
- `projection_source = NOT_WIRED_PR_G3`
- Warning: `shape_ref_internal_only_visible_geometry_decoder_fallback_until_PR_G3`
- No `EXACT_CAPTURE_RENDER_AUTHORITY` while visible geometry is fallback

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible aerial geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3.

## Known limitations

1. Subset build (`--phase6-limit 12`), not full corpus
2. Five CH3 families have `no_ch3_family_representative`
3. Real U-wave / multicolor curve captures may still lose stroke span when `segmented_components` wins over skeleton centerline — marked weak/unusable pending Brandon review
4. Automated visual summary reports **0 pass** — human overlay check is the acceptance gate
5. Local stills not in git — full verification requires local media
6. `thin_stroke_skeleton_from_soft_mask` not selected on any real capture in this build; may need scoring tuning after Brandon review
