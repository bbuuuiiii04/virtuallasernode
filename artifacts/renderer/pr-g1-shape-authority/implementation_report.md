# PR-G1 Static Shape Authority — Implementation Report

## Summary

PR-G1 builds internal wall-space static shape authority from local `captures/fixture_model/**` stills only. Visible aerial geometry remains `_drawFan()` decoder fallback until PR-G3; diagnostics expose internal `shape_ref` separately from visible geometry.

## Files changed

| File | Change |
|---|---|
| `tools/shape_extraction.py` | New — coordinate conversion, shape_ref, extraction, overlays |
| `tools/shape_library_builder.py` | New — Lane A/B selection, library emit, index merge |
| `capture_index_runtime.py` | Shape fields on `lookup_exact_from_channels()` |
| `static/renderer.js` | Diagnostics-only `shape` block + PR-G3 honesty warning |
| `static/app.js` | Diagnostics panel shape / projection fields |
| `tests/test_shape_selection.py` | New |
| `tests/test_shape_library_schema.py` | New |
| `tests/test_shape_coordinates.py` | New |
| `tests/test_shape_extraction_synthetic.py` | New |
| `tests/test_capture_index_runtime_shape_refs.py` | New |
| `tests/test_no_historical_pr_g1_inputs.py` | New |
| `tests/test_shape_ref_stability.py` | New |
| `tests/test_renderer_motionstate.js` | Extended — shape_ref vs decoder fallback |
| `artifacts/renderer/shape_library_v1.json` | Generated |
| `artifacts/renderer/shape_library_v1.schema.json` | Generated |
| `artifacts/renderer/pr-g1-shape-authority/shape_selection.json` | Generated |
| `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` | Generated |
| `artifacts/renderer/pr-g1-shape-authority/contact_sheets/*.png` | Generated (18) |
| `artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json` | Shape ref join (artifact only) |

## Local capture root

`captures/fixture_model/` (6077 `still.jpg`, 2159 `still_color.jpg` on build host)

Builder run: subset mode with `--phase6-limit 12` (not full 8K batch).

## Selection counts

| Metric | Count |
|---|---:|
| Lane A (ch3_family) entries | 12 |
| Lane B (phase6_cue) entries | 12 |
| Skipped / excluded entries | 6 |
| Extracted shapes in library | 18 |
| Vectors merged with shape_ref in index | 18 |

### Skipped / fallback reasons

- 1 extraction failure: `low_contrast`
- 5 CH3 families: `no_ch3_family_representative` (no local manifest match in CH3 range)

## Schema validation

`artifacts/renderer/shape_library_v1.json` validated via `tests/test_shape_library_schema.py` (minimal structural validation; `jsonschema` optional).

## Tests run

```text
python3 -m pytest tests/test_shape_selection.py               → 6 passed
python3 -m pytest tests/test_shape_library_schema.py          → 2 passed
python3 -m pytest tests/test_shape_coordinates.py             → 5 passed
python3 -m pytest tests/test_shape_extraction_synthetic.py    → 7 passed
python3 -m pytest tests/test_capture_index_runtime_shape_refs.py → 3 passed
python3 -m pytest tests/test_no_historical_pr_g1_inputs.py    → 3 passed
python3 -m pytest tests/test_shape_ref_stability.py           → 3 passed
python3 -m pytest tests/test_capture_index_runtime.py         → 7 passed (regression)
node tests/test_renderer_motionstate.js                       → 26 passed
```

## Example shape_ref entries

| shape_ref | vector (CH3) | topology | capture_path |
|---|---|---|---|
| `sh1_21b9e82ef84b930b` | CH3=0 | closed_loop | `phase1_5_base_dependence/.../CH08_000` |
| `sh1_c2b7857c6e4a5a1f` | CH3=32 | line | horizontal line family |
| `sh1_41c84ad2ac1f458e` | CH3=48 | two_clusters | two-point family |
| `sh1_6fb79ee6e90df590` | phase6 cue | multi_cluster | `phase6_cue_validation/cue_relevant/...` |

## Contact sheets

`artifacts/renderer/pr-g1-shape-authority/contact_sheets/` — 18 PNG contact sheets (still + overlay side-by-side).

Review index: `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` (all `brandon_verdict: pending`).

## Explicit non-mutations

- **`captures/**` was not mutated.** Builder reads local stills only.
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible aerial geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3. When `shape_ref` exists, diagnostics show:

- `visible_geometry_source = DECODER_FALLBACK_DRAWFAN`
- `projection_source = NOT_WIRED_PR_G3`
- Warning: `shape_ref_internal_only_visible_geometry_decoder_fallback_until_PR_G3`

No `EXACT_CAPTURE_RENDER_AUTHORITY` while `validation.pass=0`.

## Known limitations

1. Five CH3 checklist families have no isolated local representative in manifest CH3 ranges; recorded as `excluded_reason: no_ch3_family_representative`.
2. Phase6 Lane B limited to 12 cues in subset build (`--phase6-limit 12`).
3. Topology labels are heuristic; overlay review is the human gate.
4. Extraction v1 uses adaptive luma threshold + connected components; low-contrast stills may fail extraction.
5. `jsonschema` not installed in system Python; schema test uses structural fallback when absent.
6. Full polylines not sent over SSE (diagnostics summary fields only).

## Build command

```bash
python3 tools/shape_library_builder.py --phase6-limit 12
```
