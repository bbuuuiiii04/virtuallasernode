# PR-G1 Static Shape Authority — Implementation Report (v6 typed stroke-vectorization)

## Summary

PR-G1 builds internal wall-space static shape authority from local `captures/fixture_model/**` stills. Extraction **v6** replaces v5’s competing threshold-mask candidates with **typed stroke-vectorization**: per-channel laser maps, hysteresis support, shape-type routing, skeleton-graph tracing, and **pixel-to-geometry fit scoring**.

Visible aerial geometry remains `_drawFan()` decoder fallback until PR-G3.

**Brandon instruction:** Pass only if the yellow overlay roughly follows the actual bright laser drawing, not just the glow around it.

## Why v5 was the wrong abstraction

v5 ran six variants of the same pipeline (score pixels → threshold mask → connected components → greedy/ridge polyline → bbox/span scoring) and picked the highest heuristic score. That could not reliably distinguish:

- thin centerline vs glow halo contour
- continuous U/curve vs fragmented components
- multicolor hue spans vs brightest endpoint only
- dot/cluster layouts vs smeared continuous strokes

v6 changes the abstraction to **recover support first, classify shape type, route to a typed vectorizer, score by pixel fit**.

## v6 architecture

### 1. Per-channel laser maps (`tools/shape_laser_maps.py`)

Inside fixture crop: `combined_laser_score`, `red_score`, `green_score`, `blue_score`, `cyan_score`, `magenta_score`, `yellow_score`, `white_score`. Color evidence is preserved until support union.

### 2. Hysteresis support (`tools/shape_hysteresis_support.py`)

- `high_core_mask` — confident laser pixels (seeds)
- `low_support_mask` — possible laser pixels
- `support_mask` — low-support pixels connected to high-core seeds + per-color union + gap bridging
- Recovers dim U-legs and dim purple/cyan sections without accepting full glow halo

### 3. Shape-type routing (`tools/shape_stroke_vectorization.py`)

`shape_type` ∈ `continuous_stroke`, `dotted_pattern`, `dot_cluster`, `closed_loop`, `branched_complex`, `unknown`

Routing rules include: ring topology, rectangular frame detection, compact dot arcs, separated dual blobs, broken-stroke component groups, branch-point density.

### 4. Typed vectorizers (eligible per shape type only)

| Vectorizer | Use |
|---|---|
| `skeleton_graph_stroke` | Continuous lines, U, curves — Zhang-Suen skeleton + longest geodesic path |
| `dotted_component_vectorizer` | Dotted arcs — per-dot centroids |
| `dot_cluster_vectorizer` | Separated dot/cluster blobs |
| `closed_loop_contour` | True rings — thin contour or union boundary |
| `skeleton_branch_vectorizer` | Complex/branched shapes — skeleton branch paths |

### 5. Pixel-to-geometry fit scoring

Primary metrics (not bbox span):

- `stroke_coverage_score` — support pixels near output geometry
- `geometry_precision_score` — geometry samples on support
- `color_span_score` — per-hue components covered
- `dot_preservation_score` — dot count/layout for dotted shapes
- `continuity_score` — continuous stroke path length vs support skeleton
- `topology_match_score` — vectorizer matches routed shape type
- `halo_leakage_score` — penalize geometry on glow boundary only
- `fragment_score` — penalize endpoint-only paths

### 6. Authority policy (strict)

- `pass` → `usable_as_shape_authority=true` (automated pixel-fit threshold)
- `weak` → `usable_as_shape_authority=false`
- `fail` → `usable_as_shape_authority=false`

No weak shape is promoted to clean authority.

## Files changed (v6)

| File | Role |
|---|---|
| `tools/shape_laser_maps.py` | **New** — per-channel laser probability maps |
| `tools/shape_hysteresis_support.py` | **New** — hysteresis support + per-color union |
| `tools/shape_skeleton_graph.py` | **New** — skeleton thinning + graph path tracing |
| `tools/shape_stroke_vectorization.py` | **New** — routing, vectorizers, pixel-fit scoring, visual classification |
| `tools/shape_candidate_extraction.py` | v6 compatibility shim |
| `tools/shape_extraction.py` | v6 entry point (`EXTRACTION_POLICY_VERSION = "v6"`) |
| `tools/shape_library_builder.py` | shape_type / selected_vectorizer in review summary |
| `tests/test_skeleton_graph_vectorization.py` | **New** |
| `tests/test_hysteresis_support_recovers_dim_u.py` | **New** |
| `tests/test_per_color_support_union.py` | **New** |
| `tests/test_dotted_arc_vectorizer.py` | **New** |
| `tests/test_shape_type_routing.py` | **New** |
| `tests/test_geometry_pixel_fit_scoring.py` | **New** |
| `tests/test_weak_shapes_not_authority.py` | **New** |
| Updated existing shape extraction tests for v6 flags/routing |

## Artifacts regenerated

```bash
python3 tools/shape_library_builder.py --phase6-limit 12
```

| Artifact | Path |
|---|---|
| Shape library | `artifacts/renderer/shape_library_v1.json` (19 shapes, policy **v6**) |
| Schema | `artifacts/renderer/shape_library_v1.schema.json` |
| Selection | `artifacts/renderer/pr-g1-shape-authority/shape_selection.json` |
| Contact sheets | `artifacts/renderer/pr-g1-shape-authority/contact_sheets/` (19 PNGs) |
| Overlay index | `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` |
| Visual review summary | `artifacts/renderer/pr-g1-shape-authority/visual_review_summary.md` |
| Capture index join | `artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json` |

## Build stats

| Metric | Count |
|---|---:|
| Shapes in library | 19 |
| Vectors with shape_ref | 19 |

## Shape type counts (automated)

| shape_type | Count |
|---|---:|
| continuous_stroke | 7 |
| branched_complex | 7 |
| closed_loop | 4 |
| dot_cluster | 1 |

## Selected vectorizer counts

| Vectorizer | Count |
|---|---:|
| `skeleton_branch_vectorizer` | 7 |
| `skeleton_graph_stroke` | 7 |
| `closed_loop_contour` | 4 |
| `dot_cluster_vectorizer` | 1 |

## Visual pre-review (automated, honest)

| Status | Count |
|---|---:|
| pass | 0 |
| weak | 2 |
| fail | 17 |
| **usable_as_shape_authority** | **0** |

Automated pixel-fit thresholds produce **0 pass** on real captures in this build. All 19 shapes require Brandon contact-sheet review. Weak/fail shapes are **not** usable authority.

## Tests run

```bash
python3 -m pytest (36 shape test modules)  → 74 passed
node tests/test_renderer_motionstate.js    → 26 passed
```

**Total: 74 pytest + 26 JS — all pass**

## Diagnostics honesty (unchanged)

- `visible_geometry_source = DECODER_FALLBACK_DRAWFAN`
- `projection_source = NOT_WIRED_PR_G3`
- Warning: `shape_ref_internal_only_visible_geometry_decoder_fallback_until_PR_G3`

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible aerial geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3.

## Known limitations

1. Subset build (`--phase6-limit 12`)
2. Automated pass threshold is strict — real captures still fail pixel-fit on complex macros
3. `branched_complex` routing still common on intricate shapes — needs Brandon visual review
4. Contact-sheet quality must be validated by human overlay review before any merge claim
