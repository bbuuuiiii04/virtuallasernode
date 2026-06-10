# PR-G1 Static Shape Authority — Implementation Report (merge-ready)

## Summary

PR-G1 builds internal wall-space static shape authority from local `captures/fixture_model/**` stills. Extraction v2 produces real contour/centerline polylines (not bbox corners). Runtime capture index shape joins were regenerated after v2 extraction. Visible aerial geometry remains `_drawFan()` decoder fallback until PR-G3.

## Files changed (implementation)

| File | Role |
|---|---|
| `tools/shape_extraction.py` | v2 contour/centerline extraction |
| `tools/shape_polyline_utils.py` | bbox-only polyline detection |
| `tools/shape_library_builder.py` | Lane A/B selection, library emit, index merge |
| `capture_index_runtime.py` | shape_ref lookup + shape_authority semantics |
| `static/renderer.js` | diagnostics-only shape block |
| `static/app.js` | diagnostics panel fields |
| `test-requirements.txt` | jsonschema for strict schema tests |
| `tests/test_shape_*.py` | selection, schema, geometry, runtime tests |
| `tests/test_renderer_motionstate.js` | shape_ref vs visible fallback |

## Artifacts regenerated

Final build command:

```bash
python3 tools/shape_library_builder.py --phase6-limit 12
```

| Artifact | Path |
|---|---|
| Selection | `artifacts/renderer/pr-g1-shape-authority/shape_selection.json` |
| Shape library | `artifacts/renderer/shape_library_v1.json` |
| Schema | `artifacts/renderer/shape_library_v1.schema.json` |
| Contact sheets | `artifacts/renderer/pr-g1-shape-authority/contact_sheets/` (18 PNGs) |
| Overlay index | `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` |
| Capture index join | `artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json` |

## Build stats

| Metric | Count |
|---|---:|
| Lane A (ch3_family) | 12 |
| Lane B (phase6_cue) | 12 |
| Skipped/excluded | 6 |
| Shapes in library | 18 |
| Vectors with shape_ref (index merge) | 18 |

## Capture index regeneration

- Builder run **with index merge** (no `--no-merge-index`)
- `merge_stats.vectors_with_shape_ref`: **18**
- Runtime index shape joins verified after v2 extraction polylines
- `capture_index_v1.json` updated (+56 / −21 lines in shape join fields)

## Extraction method (v2)

| Topology | Polyline source |
|---|---|
| `line` | Centerline (`skeleton`) |
| `two_clusters` | Per-cluster contour or centerline |
| `closed_loop` | Closed contour trace |
| `multi_cluster` / `complex_shape` | Contour or sampled component points |

`extraction_policy_version`: **v2**

## Proof polylines are not bbox-only

- Automated check: **0 bbox-only polylines** across 18 library shapes
- `tests/test_shape_polylines_not_bbox.py` passes on synthetic + built library
- Horizontal line (CH3=32): contour/centerline geometry, not 5-point rectangle

## Lane A verification

- **horizontal line static** → CH3=32, tier `exact_family`
- Selection reason: `exact CH3=32 representative in range 16-40`

## Schema validation

```bash
pip install -r test-requirements.txt
python3 -m pytest tests/test_shape_schema_required_fields.py tests/test_shape_library_schema.py
```

Result: **PASS** (jsonschema validates strengthened schema)

## Tests run

```bash
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

`artifacts/renderer/pr-g1-shape-authority/contact_sheets/` — 18 PNGs (still + contour overlay)

## Diagnostics honesty (unchanged)

When internal `shape_ref` exists:

- `visible_geometry_source = DECODER_FALLBACK_DRAWFAN`
- `projection_source = NOT_WIRED_PR_G3`
- Warning: `shape_ref_internal_only_visible_geometry_decoder_fallback_until_PR_G3`

Exact vector match alone does **not** imply shape authority without non-empty `shape_ref` and `shape_point_count > 0`.

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible aerial geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3. No `_drawFan()` changes in this PR.

## Known limitations

1. Subset build (`--phase6-limit 12`), not full ~8K corpus
2. Five CH3 families have `no_ch3_family_representative`
3. Contour extraction is heuristic; overlay review verdicts remain `pending`
4. Topology labels are diagnostic hints only
5. Local stills not in git — full extraction verification requires local media
