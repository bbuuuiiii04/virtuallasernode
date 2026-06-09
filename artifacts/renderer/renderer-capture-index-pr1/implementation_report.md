# PR1 Implementation Report — renderer-capture-index-pr1

## 1. Scope implemented

- Implemented a deterministic build-time capture index generator joining:
  - `captures/fixture_model/manifest.jsonl`
  - per-capture `captures/fixture_model/**/analysis.json`
  - `captures/fixture_model/analysis_geometry.json`
- Implemented test-id latest-timestamp deduplication.
- Implemented exact CH1-19 normalized vector lookup support.
- Implemented exposure-track pair retention in vector buckets.
- Implemented quality gate encoding (`usable_evidence`, `geometry_clipped_low`, `recapture_pending`).
- Implemented metric conversions from px to inches using `px_per_inch` from `analysis_geometry.json`.
- Generated compact index artifact and generation reports in artifacts.
- Added targeted unit tests for PR1-specific behaviors.

## 2. Files changed

- `tools/capture_index_builder.py` (new core generator module)
- `tools/build_capture_index.py` (new CLI entrypoint)
- `tests/test_capture_index_builder.py` (new PR1 unit tests)
- `docs/RENDERER_PR_STATUS.md` (PR status progression update)

## 3. Design summary

- Manifest rows are parsed with strict JSONL validation (`ManifestJsonlError` on invalid lines).
- Dedup policy for duplicate `test_id`:
  - keep latest by parsed ISO timestamp;
  - tie-break by higher manifest line number.
- Per-capture `analysis.json` is used as analysis authority; manifest inline analysis is not used as analysis authority.
- Output index structure:
  - `captures[]`: capture identity + normalized vector + quality + metrics + provenance-ready fields
  - `vector_index{vector_key}`: capture IDs, preferred capture ID, by-exposure-track grouping, phase counts
  - `unit_conversion`: ROI + `px_per_inch` sourced from `analysis_geometry.json`
  - `provenance_labels`: predeclared authority labels for PR2/PR3 plumbing compatibility.

## 4. How existing renderer behavior was preserved

- No changes were made to:
  - `static/`
  - `webserver.py`
  - `fixture_model_adapter.py`
  - `fixtures.py`
  - any runtime SSE or renderer path.
- PR1 is build-time only and does not alter renderer visuals or runtime behavior.

## 5. Tests run

- `python3 -m pytest tests/test_capture_index_builder.py -q`
  - Result: `4 passed`
- `python3 tools/build_capture_index.py`
  - Result: index + report artifacts generated successfully.
- `python3 tools/validate_model_adapter.py`
  - Result: all validator checks passed.

## 6. Renderer smoke checks

- Not applicable for PR1 by design (no renderer/webserver code path changes).

## 7. Known approximations

- Wall-space normalization currently uses ROI-size normalization plus scalar `px_per_inch` conversion (no homography correction in PR1).
- Index marks provenance compatibility fields but does not wire provenance into runtime payload yet (deferred to PR2).

## 8. Deferred PR2+ items

- PR2:
  - load index in webserver/adapter
  - exact vector/cue lookup in runtime path
  - SSE provenance labels + diagnostics
- PR3:
  - measured-parameter consumption in renderer
  - reduced MotionState fallback layer integration and labels

## 9. Risks / manual checks needed

- Full `python3 -m pytest` run hangs during collection in this repo environment (process was stopped and reported; not fixed in PR1 scope).
- No physical or visual validation required at this stage because PR1 does not change runtime rendering behavior.
