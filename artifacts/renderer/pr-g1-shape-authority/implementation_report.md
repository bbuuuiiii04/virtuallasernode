# PR-G1 Static Shape Authority — Implementation Report (fix pass)

## Summary

Fix pass for PR #1: replaced bbox-corner polylines with real extracted geometry (contour trace + Douglas-Peucker simplify, centerline/skeleton for lines, per-cluster polylines for multi-cluster shapes). Lane A selection now scores distance to `rep_ch3`. Out-of-box detection ignores sibling fixture calibration boxes.

## Files changed

| File | Change |
|---|---|
| `tools/shape_extraction.py` | v2 extraction: contours, centerlines, out-of-box fix |
| `tools/shape_polyline_utils.py` | New — bbox-only polyline detection helpers |
| `tools/shape_library_builder.py` | rep_ch3 scoring, selection_reason, schema, fallback_reason |
| `test-requirements.txt` | New — requires `jsonschema` |
| `tests/test_shape_library_schema.py` | jsonschema mandatory |
| `tests/test_shape_schema_required_fields.py` | New |
| `tests/test_shape_polylines_not_bbox.py` | New |
| `tests/test_shape_selection_rep_distance.py` | New |
| `tests/test_shape_out_of_box_ignores_other_fixture.py` | New |
| `tests/test_shape_extraction_colored_synthetic.py` | New |
| `tests/test_shape_extraction_synthetic.py` | closed_loop + out-of-box fixes |

## Exact fixes

1. **Polylines:** Removed bbox-corner-only `_trace_border_polyline`. Now uses Moore-neighbor contour tracing, Douglas-Peucker simplification, centerline extraction for elongated components, and one polyline per cluster when needed.
2. **Schema:** All PR-G1 shape fields required; `jsonschema` required in tests (no silent fallback).
3. **Lane A selection:** Scores `exact` match to `rep_ch3`, then `-abs(ch3 - rep_ch3)` (not distance to zero). Horizontal line family now selects **CH3=32** exact representative.
4. **Out-of-box:** Full-image scan skips pixels inside other fixture boxes; edge-touch detection within selected crop retained.
5. **Shape records:** Every library shape includes `fallback_reason: null` on success.

## Shape extraction method (v2)

| Topology | Polyline source |
|---|---|
| `line` | Centerline (`skeleton`) along dominant axis |
| `two_clusters` | Per-cluster contour or centerline |
| `closed_loop` | Closed contour trace |
| `multi_cluster` / `complex_shape` | Contour or sampled component points |

`extraction_policy_version`: **v2**

## Proof polylines are not bbox-only

- `tests/test_shape_polylines_not_bbox.py` passes on synthetic and built library (18/18 shapes).
- Built library polyline sources include `contour`, `skeleton`, `simplified_component` — no bbox-corner-only entries.
- Example: horizontal line family shape uses centerline points along the laser stroke, not a 4-corner rectangle.

## Build stats (subset)

Builder: `python3 tools/shape_library_builder.py --phase6-limit 12 --no-merge-index`

| Metric | Count |
|---|---:|
| Lane A (ch3_family) | 12 |
| Lane B (phase6_cue) | 12 |
| Skipped/excluded | 6 |
| Shapes in library | 18 |
| Contact sheets | 18 |

## Schema validation

```bash
pip install -r test-requirements.txt
python3 -m pytest tests/test_shape_schema_required_fields.py tests/test_shape_library_schema.py
```

Result: **PASS** (jsonschema validates `shape_library_v1.json` against strengthened schema)

## Tests run

```text
python3 -m pytest tests/test_shape_selection.py                     → 6 passed
python3 -m pytest tests/test_shape_library_schema.py                → 2 passed
python3 -m pytest tests/test_shape_schema_required_fields.py        → 3 passed
python3 -m pytest tests/test_shape_coordinates.py                   → 5 passed
python3 -m pytest tests/test_shape_extraction_synthetic.py          → 7 passed
python3 -m pytest tests/test_shape_extraction_colored_synthetic.py  → 4 passed
python3 -m pytest tests/test_shape_polylines_not_bbox.py            → 5 passed
python3 -m pytest tests/test_capture_index_runtime_shape_refs.py    → 3 passed
python3 -m pytest tests/test_no_historical_pr_g1_inputs.py          → 3 passed
python3 -m pytest tests/test_shape_ref_stability.py                 → 3 passed
python3 -m pytest tests/test_shape_selection_rep_distance.py        → 3 passed
python3 -m pytest tests/test_shape_out_of_box_ignores_other_fixture.py → 2 passed
node tests/test_renderer_motionstate.js                             → 26 passed
```

**Total: 46 pytest + 26 JS — all pass**

## Contact sheets

`artifacts/renderer/pr-g1-shape-authority/contact_sheets/` — 18 PNGs (regenerated with contour overlays)

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible aerial geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3. Diagnostics unchanged:

- `visible_geometry_source = DECODER_FALLBACK_DRAWFAN`
- `projection_source = NOT_WIRED_PR_G3`
- Warning: `shape_ref_internal_only_visible_geometry_decoder_fallback_until_PR_G3`

## Known limitations

1. Five CH3 families still have no local isolated representative (`no_ch3_family_representative`).
2. Phase6 Lane B limited to 12 cues in subset build.
3. Contour tracing is v1 heuristic; overlay human review still required (`brandon_verdict: pending`).
4. Topology labels remain diagnostic hints, not ground truth.
5. Index merge skipped in this rebuild (`--no-merge-index`); re-run builder without flag to refresh `capture_index_v1.json` shape joins.
