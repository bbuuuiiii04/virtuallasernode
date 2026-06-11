# PR-G1.5 Scaling Handoff

Scaling pass rule: do NOT improve visual extraction during scaling. Run, verify, classify, report, and stop on gates only.

## 1. What extractor behavior changed

- Dot-class components now flow through saturated structure extraction before anchoring; single non-ring structure fragments remain `dot_anchor`, while multi-fragment structure can become dashed/curve geometry.
- Multi-component glow groups are vectorized per aperture before per-component fallback.
- Canonical primitives were added for `line_centerline`, `quad_centerline`, and grouped `dotted_arc_path` with bridge metadata.
- Group rejection reasons are recorded on fallback polylines when grouping fails.
- Empty traces get diagnostic dot anchors instead of silent vectorization holes.
- Artifact rejection can mark tiny, dim, far specks as `significant:false` with a machine-readable `artifact_reason`.
- Sibling aperture missing geometry is reported in `sibling_missing_reasons`.
- Bridge samples are excluded from precision, halo, and p95 residual metrics but still count toward recall geometry.
- Authority now gates `vector_fit_residual_px_p95 <= 2.5`.
- `status=authority` with `render_authority=core_mask` is capped to `status=provisional` with `render_authority_core_mask`.

## 2. Shape families now supported or improved

- Lines: fragmented horizontal line groups can become one `line_centerline`.
- Slanted lines: PCA line snap supports slanted fragmented strokes.
- Rectangles, quads, and parallelograms: ring/outline structure can snap to `rect_centerline` first, then `quad_centerline`.
- Open curves: per-component stroke tracing is preserved when group gates reject.
- Arches: glow-connected dash groups can become one grouped `dotted_arc_path`.
- U/V curves: grouped chain allows one sharp turn when all bridge gates pass.
- Dotted/crescent arcs: multi-fragment components and accepted groups emit ordered `dotted_arc_path` geometry.
- Branched shapes: single-path line snap is limited to non-branching skeletons; branched traces keep branch paths.
- Sibling aperture cases: sibling apertures use the same grouping/vectorization and get explicit missing reasons.

## 3. Cases that must remain provisional or quarantined

- Any visually ambiguous grouped result.
- Any group with bridge glow coverage below 0.85.
- Any group bridge longer than `max(18.0 px, 0.45 * group_span)`.
- Any grouped chain with total bridge length above 0.35 of path length.
- Any grouped chain with more than 1 turn above 60 degrees or mean turn above 25 degrees on the 6 px resampled path.
- Any vector set with `core_precision < 0.90`, `core_recall < 0.80`, `halo_spill > 0.05`, or `vector_fit_residual_px_p95 > 2.5`.
- Any selected output with `render_authority != "vector"`.
- Any sibling aperture component that lacks render representation and is not rejected as an artifact.
- Any mask fallback or diagnostic geometry trying to become vector authority.

## 4. Exact authority promotion rules

- Extractor metrics must satisfy:
  - `core_precision >= 0.90`
  - `core_recall >= 0.80`
  - `halo_spill <= 0.05`
  - `vector_fit_residual_px_p95 <= 2.5`
- No `fixture_assignment_ambiguous` quality flag.
- No dot-only validation reasons.
- `fixture_output_accounting_complete` must be true for final `status=authority`.
- Every significant selected-aperture component must be render-represented.
- A component is render-represented only when its cluster is `render` and member structure coverage is at least 0.4.
- Non-dot clusters become `render` only when union structure coverage is at least 0.6.
- Single-dot anchors keep the existing anchor-on-structure rule.
- Builder authority requires:
  - `status == "authority"`
  - `render_authority == "vector"`
  - `geometry_layers.render_vectors == "derived_validated"`
  - `geometry_layers.render_fallback in ("none", null)`
  - at least one selected render polyline.

## 5. Known visual failure risks

- Fragmented quads can remain too noisy for `quad_centerline` and fall back to per-component render traces.
- Dot-class curve components can remain provisional/quarantined because dot-only validation is intentionally conservative.
- Long tail bridges may reject a grouped chain even when part of the local curve is traced.
- Bright sibling aperture artifacts can block full fixture accounting unless they earn render geometry or a rejection reason.
- `line_centerline` is intentionally tight; gently curved authority arcs must not be flattened.
- Contact sheets are mandatory for visual review; JSON metrics alone are not visual certification.

## 6. Scaling gates

1. Rerun the 19 selected PR-G1 records and review the contact sheets.
2. Run a 100-record stratified sample only if the 19-record gate passes.
3. Run a 500-record stratified sample only if the 100-record gate passes.
4. Run the full 8k corpus only if the 500-record gate passes.

## 7. Required failure conditions

- Fail on fake authority.
- Fail on silent missing records.
- Fail on sibling-aperture drop without reason.
- Fail on `core_mask` promoted as vector authority.
- Fail on nondeterministic artifacts.
- Fail on visual review ambiguity that is promoted to authority instead of provisional/quarantined.

## 8. Required reports for the scaling pass

- Manifest counts.
- Authority/provisional/quarantine/conflict/missing counts.
- Failure taxonomy.
- Quarantine report.
- Stratified contact-sheet review packet.
- Deterministic rerun comparison.
- Per-family summary of promoted, provisional, quarantined, and blocked examples.

## 9. Exact commands used successfully

```bash
cd /Users/bbui/virtuallasernode

.venv/bin/python tools/shape_extract_v7.py \
  --selection artifacts/renderer/pr-g1-shape-authority/shape_selection.json \
  --out artifacts/renderer/shape_authority_v2/

.venv/bin/python tools/shape_library_builder.py --extractor v7

cp -R artifacts/renderer/shape_authority_v2 /tmp/v2_run1
cp artifacts/renderer/shape_library_v1.json /tmp/lib_run1.json
cp artifacts/renderer/pr-g1-shape-authority/shape_selection.json /tmp/selection_run1.json
cp artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json /tmp/overlay_run1.json
cp artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md /tmp/summary_run1.md
cp artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json /tmp/capture_index_run1.json

.venv/bin/python tools/shape_extract_v7.py \
  --selection artifacts/renderer/pr-g1-shape-authority/shape_selection.json \
  --out artifacts/renderer/shape_authority_v2/

.venv/bin/python tools/shape_library_builder.py --extractor v7

diff -r /tmp/v2_run1 artifacts/renderer/shape_authority_v2
diff /tmp/lib_run1.json artifacts/renderer/shape_library_v1.json
diff /tmp/selection_run1.json artifacts/renderer/pr-g1-shape-authority/shape_selection.json
diff /tmp/overlay_run1.json artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json
diff /tmp/summary_run1.md artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md
diff /tmp/capture_index_run1.json artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json

.venv/bin/python -m pytest tests/test_v7_*.py -q
.venv/bin/python -m pytest tests/test_shape_library*.py tests/test_capture_index_runtime*.py tests/test_no_historical_pr_g1_inputs.py -q
node tests/test_renderer_motionstate.js
git diff --check
```

## 10. Remaining blockers before wallDebug or corpus scaling

- Operator/image-model review must inspect the PR-G1 contact sheets in `artifacts/renderer/pr-g1-shape-authority/v7_retune_review_packet/`.
- `sh1_b92cc7b21e95ce78` remains quarantined by precision, halo, and p95 residual gates.
- `sh1_39cde94194e37010` remains quarantined by dot-only validation after rendering crescent paths.
- `sh1_298397439f5ce2a9` remains provisional because the long tail bridge was rejected and sibling geometry is incomplete.
- `sh1_ca3a93cf551f850e` remains provisional because sibling aperture accounting is incomplete and dot-only validation is conservative.
- Do not begin corpus scaling until the 19-record visual review gate is accepted.
