# PR-G1 v6 Narrow Follow-Up — Scorer False-Negative + Branch Scribble Fix

## Summary

Narrow patch after ChatGPT/Brandon review of geometry_kind repair. Focuses on scorer false negatives, stale validation bug, dense branch rejection, and dotted routing — without dashboards, PR-G1b, PR-G3, or visible renderer changes.

**Authority remains conservative:** only automated `pass` sets `usable_as_shape_authority=true`. Runtime continues respecting `bucket["shape_authority"]`.

Visible geometry remains `DECODER_FALLBACK_DRAWFAN` until PR-G3.

## Review context

Prior build (geometry_kind repair): pass 0 / weak 4 / fail 15 / usable 0.

Brandon findings driving this patch:
- `sh1_2bae89cc023a3c52` diagonal follows stroke but was hard-fail due to broad glow denominator
- `sh1_d9c0e1383b952508` / `sh1_91ebda39c0075cac` dense branch scribble / filled yellow mass
- `sh1_39cde94194e37010` dotted arc should be dot/segment anchors not branch scribble
- Scorer used `support.support_pixels` (broad glow) as stroke coverage denominator

## Fixes applied

### 1. Stale `poly`/`p` bug in `validate_geometry_candidate`

**File:** `tools/shape_geometry_kind.py`

`long_lines` comprehension used `poly.get("source")` (stale outer variable) instead of `p.get("source")`. Fixed.

Also fixed `infer_polyline_geometry_kind` so dotted vectorizer polylines with `n >= 4` and skeleton source classify as `centerline_polyline` (smear detection), not `dot_anchor_points`.

**Regression test:** `tests/test_validate_geometry_candidate_uses_current_polyline_source.py`

### 2. Scorer false-negative fix — fit target vs broad support

**File:** `tools/shape_stroke_vectorization.py`

Added `_fit_target_pixels()` combining:
- `high_core_pixels`
- per-color high-confidence core pixels (on high-core mask)
- skeleton/ridge pixels from high-core-biased skeletonization

**`stroke_coverage_score`** now uses `fit_target_pixels` as denominator.

**`broad_support_coverage_score`** retained as diagnostic only (computed from `support.support_pixels`).

**`geometry_precision_score`** samples checked against fit-target set, not full support.

Continuity and halo diagnostics still reference broad support mask.

### 3. Centerline alignment score

New `centerline_alignment_score` for `centerline_polyline`:
- geometry samples near fit-target pixels
- span ratio vs fit-target extent
- contributes to total score (+12 weight)
- used in `classify_visual_status` to avoid hard-fail when thin centerline aligns with core but broad glow coverage is low

Centerline with `centerline_alignment >= 0.35` and low fit-target coverage → **weak** (not fail).

### 4. Dense branch scribble rejection

**File:** `tools/shape_geometry_kind.py`

New reject reasons:
- `dense_branch_scribble` — many branch paths with high sample density
- `branch_mask_fill_like` — branches span both axes like a filled band

Penalties in scorer (-50 / -55). Hard reject in extraction and `classify_visual_status`.

`skeleton_branch_vectorizer` now skeletonizes high-core-biased mask (not full support).

**Effect:** `skeleton_graph_stroke` wins over branch vectorizer on most phase6 captures (18 vs 1). Eliminates dense yellow scribble mass on diagonal/swirl cases.

**Test:** `tests/test_dense_branch_scribble_rejected.py`

### 5. Dotted routing correction

**File:** `tools/shape_stroke_vectorization.py`

`_dotted_or_cluster_from_core()` changes:
- Removed elongated-stroke early `return None` that blocked segmented dashes
- Segmented laser dashes along arc/line route to `dotted_pattern` even when elongated
- Guard: single connected support component or multicolor elongated path → continuous stroke (not dotted)
- `_components_for_dotted_vectorizer` uses high-core components when `>= 2` separated

**Tests:**
- `tests/test_dotted_segmented_marks_route_to_dotted_pattern.py`
- `tests/test_dot_cluster_routes_to_dot_anchors_when_core_separated.py`

Real capture `sh1_39cde94194e37010` still routes `branched_complex` when hysteresis merges cores on still — honest weak, not dotted anchors yet.

## Post-patch artifact result

```bash
python3 tools/shape_library_builder.py --phase6-limit 12
```

| Status | Count |
|---|---:|
| pass | 0 |
| weak | 11 |
| fail | 8 |
| **usable_as_shape_authority** | **0** |

Prior build: pass 0 / weak 4 / fail 15. Weak count improved 4 → 11; fail reduced 15 → 8. Still 0 automated pass (authority conservative).

### Target shape outcomes

| shape_ref | Status | geometry_kind | vectorizer |
|---|---|---|---|
| `sh1_2bae89cc023a3c52` | **weak** | centerline_polyline | skeleton_graph_stroke |
| `sh1_2e3da0a4330792c3` | fail | centerline_polyline | skeleton_graph_stroke |
| `sh1_d9c0e1383b952508` | **weak** | centerline_polyline | skeleton_graph_stroke |
| `sh1_ca3a93cf551f850e` | **weak** | centerline_polyline | skeleton_graph_stroke |
| `sh1_542fc5442a80e0dc` | fail | centerline_polyline | skeleton_graph_stroke |
| `sh1_39cde94194e37010` | **weak** | centerline_polyline | skeleton_graph_stroke |
| `sh1_91ebda39c0075cac` | **weak** | centerline_polyline | skeleton_graph_stroke |

Key improvements:
- Branch scribble eliminated — `skeleton_graph_stroke` wins (18/19 shapes)
- Diagonal baseline no longer hard-fail
- Dense yellow mass replaced by thin centerline overlay on diagonal/swirl cases
- Still no automated pass; dotted arc on real still not yet dot anchors

## Tests run

```bash
python3 -m pytest tests/test_shape*.py tests/test_geometry*.py tests/test_dotted*.py \
  tests/test_capture_index*.py tests/test_weak*.py tests/test_validate*.py \
  tests/test_centerline*.py tests/test_good*.py tests/test_dense*.py \
  tests/test_dot_cluster*.py -q
# 94 passed
```

New tests (6):
- `test_validate_geometry_candidate_uses_current_polyline_source.py`
- `test_centerline_scoring_uses_fit_target_not_broad_glow.py`
- `test_good_diagonal_centerline_not_failed_by_broad_support.py`
- `test_dense_branch_scribble_rejected.py`
- `test_dotted_segmented_marks_route_to_dotted_pattern.py`
- `test_dot_cluster_routes_to_dot_anchors_when_core_separated.py`

Updated: `test_geometry_pixel_fit_scoring.py`, `test_shape_type_routing.py`

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3.

## Stop line / next step

This patch improves scorer honesty and eliminates branch-scribble authority geometry. **Pass count did not meaningfully improve (still 0).** Further handcrafted CV on real phase6 stills has diminishing returns.

**Recommended pivot:** optional offline AI extraction prototype (out of PR-G1 scope) if Brandon wants higher pass rate on complex macros, dotted arcs, and multicolor curves.
