# PR-G1 Static Shape Authority Implementation Spec

**Status:** Active implementation spec (documentation only until coding PR lands)  
**Plan revision:** `RENDERER_WALL_TO_AERIAL_PLAN_V1.md` rev 4  
**Branch policy:** `review/plan-pr1-5-phase1` / `renderer-accuracy-phase1` — **not** `main`  
**Implementation report (required on code PR):** `artifacts/renderer/pr-g1-shape-authority/implementation_report.md`

---

## 1. Purpose

PR-G1 establishes **internal wall-space static shape authority** for the VirtualLaserNode renderer.

Given an exact CH1–19 DMX vector match, PR-G1 must be able to answer:

> “What bright figure did the laser draw on the wall at one instant — expressed in a shared normalized wall coordinate system?”

PR-G1 **is:**

- A **build-time** pipeline that runs on **Brandon’s local Mac** against `captures/fixture_model/**`.
- A **shape library** (`shape_library_v1.json`) keyed by `vector_key` + capture provenance.
- A **selection ledger** (`shape_selection.json`) proving which local captures were chosen and why.
- A **runtime/index join** exposing `shape_ref` and diagnostic shape fields when a static shape exists.
- A **human overlay review** harness (still beside extracted overlay; Brandon yes/no only).

PR-G1 **is not:**

- Visible aerial beam replacement — **`_drawFan()` may remain the visible path until PR-G3**.
- Motion over time — that is **PR-G1b**.
- Rig projection / straight-beam crowd view — that is **PR-G3**.
- A claim that the canvas is capture-driven geometry — **forbidden until PR-G3+ with honest tiers**.
- A substitute for capture corpus mutation, fixture model edits, or physical calibration.

**Baby-language:** PR-G1 teaches the renderer what the laser **drew on the wall** from local photos. It does **not** yet change what the crowd **sees in haze** — that waits for PR-G3.

---

## 2. Scope and Non-goals

### In scope

- Local corpus discovery and media existence checks.
- Dual-lane capture selection (CH3 families + phase6 cues).
- Bright-figure extraction from `still.jpg` / `still_color.jpg` inside per-fixture calibration projection boxes.
- Normalized wall-space polylines/clusters in `wall_norm_per_fixture_calibration_box` coordinates.
- Diagnostic `topology_class` labels (not product truth).
- JSON artifacts + JSON Schema + tests.
- Index/runtime plumbing for `shape_ref` and shape diagnostics.
- Contact sheets for Brandon visual validation.

### Explicit non-goals (forbidden in PR-G1)

| Forbidden | Reason |
|---|---|
| WebGL conversion | AGENTS.md + plan non-negotiable |
| Mutating `captures/**` | Read-only evidence |
| Mutating `data/fixture_model.json` | Policy authority |
| Using `calib/captures/**` or `archive/pre_corpus_*/calib_captures/**` as sources | Historical; not 8k corpus |
| Using `/tmp/vln_wall_ch3_atlas_*.png` or WALL_CH3 legacy still column | Historical paths |
| Treating GitHub clone as raw media source | Stills/videos not in git |
| SoundSwitch cue **names/tags** as behavior authority | DMX vector only |
| `_drawFan()` polish, fan spread tuning, density-from-scalars | Deprecated fan-geometry path |
| Reviving abandoned fan-geometry-from-scalars work | Removed from policy |
| Physical `calibration.json` tuning | PR-F suspended until after PR-G4/PR-H |
| Motion track build/playback | PR-G1b |
| Aerial projection / replacing visible beam draw | PR-G3 |
| Full 8k batch before selected subset passes | Plan atlas-first policy |
| Requiring Brandon to classify geometry vocabulary | Visual yes/no only |

---

## 3. Grounding in Active Plan

| Document | Role |
|---|---|
| `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` **rev 4** | **Active primary plan** — §5.2–5.3, §6.0 |
| `docs/RENDERER_PR_STATUS.md` | Branch/PR state; PR-G1 not started |
| `docs/WALL_CH3_LOOK_ATLAS.md` | CH3 family **checklist only** |
| `artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md` | **BLOCK_MERGE** for “capture-backed geometry” on PR1–5 |
| `artifacts/renderer/renderer-accuracy-phase1/implementation_report.md` | Phase 1 committed; geometry deferred |

**Why PR-G1 exists:** PR1–PR5 + Phase 1 wired capture **metadata** (motion_type, color, strobe, provenance) but left **visible geometry** on `_drawFan()` + `CAL._patternShape()`. Forensic review: capture index is useful; geometry is still decoder-driven. PR-G1 is the first step that makes **wall figure topology** capture-backed in **internal wall space**.

**Policy branches:** Implement from `renderer-accuracy-phase1` (or synced `review/plan-pr1-5-phase1`). **`main` is not current renderer policy.**

---

## 4. Valid and Invalid Inputs

### Valid local inputs (PR-G1)

All paths relative to repo root unless noted.

| Input | Path pattern | Required for G1 |
|---|---|---|
| Primary still | `captures/fixture_model/**/still.jpg` | Yes (preferred) |
| Color still fallback | `captures/fixture_model/**/still_color.jpg` | If primary missing |
| Vector + phase | `captures/fixture_model/**/metadata.json` | Yes |
| Quality gates | `captures/fixture_model/**/analysis.json` | Yes (selection + flags) |
| Corpus enumeration | `captures/fixture_model/manifest.jsonl` | Yes (Lane A scan) |
| Calibration boxes | `captures/fixture_model/analysis_geometry.json` | **Required** |
| Rig layout | `captures/fixture_model/setup_geometry.json` | Optional (PR-G3; not required for G1 v1) |

**GitHub note:** ~16k `metadata.json` / `analysis.json` files may exist in git. **`still.jpg` / video / motion frames are local-only** (~0 in git). A GitHub-only checkout **cannot pass PR-G1** without local media.

### Invalid PR-G1 inputs (must reject if referenced in selection or extraction)

| Invalid source | Action |
|---|---|
| `calib/captures/**` | Fail test / reject selection entry |
| `archive/pre_corpus_*/calib_captures/**` | Fail test / reject selection entry |
| `/tmp/vln_wall_ch3_atlas_*.png` | Fail test / reject selection entry |
| WALL_CH3 **legacy still** column paths | Never use as `still_path` |
| WALL_CH3 **corpus capture path** column as hardcoded authority | Hint only; selector must re-verify local media |
| SoundSwitch cue names/tags | Never selection or behavior keys |
| `analysis.json` scalars alone | Classification only — not shape topology |

**Conflict rule:** If atlas checklist text conflicts with a local 8k+ `still.jpg`, **the local corpus still wins**.

---

## 5. Local Corpus Discovery

### Capture root

```text
captures/fixture_model/
```

Implementations must resolve this as an absolute path at build time and store the **relative** path `captures/fixture_model` in artifacts (`capture_root`).

### Discovery algorithm (v1)

1. Verify `captures/fixture_model/manifest.jsonl` exists → else **`LOCAL_MEDIA_MISSING: manifest`**.
2. Verify `captures/fixture_model/analysis_geometry.json` exists → else **`LOCAL_GEOMETRY_MISSING`**.
3. Parse `analysis_geometry.json` → require `boxes[]` with at least one labeled fixture box → else **`CALIBRATION_BOX_MISSING`**.
4. For Lane A: load family checklist from `docs/WALL_CH3_LOOK_ATLAS.md` (family names + rep CH3 + priority + optional corpus path hints).
5. Scan manifest rows + filesystem:
   - Match CH3 family representatives by metadata CH1–19 (vector authority).
   - Verify `still.jpg` or `still_color.jpg` exists on disk for each candidate.
6. For Lane B: enumerate directories under:
   ```text
   captures/fixture_model/phase6_cue_validation/cue_relevant/*/
   ```
   Require `metadata.json` + still media per folder.
7. Record `local_media_exists: true|false` per selection entry.

### Missing local media behavior

| Condition | Behavior |
|---|---|
| No `captures/fixture_model/` directory | Exit non-zero; message `PR-G1 requires local capture root captures/fixture_model/` |
| Manifest present, **zero** still files found on disk | Exit non-zero; `PR-G1 local media missing: no still.jpg/still_color.jpg under capture root` |
| Single family/cue missing still | Select alternate per lane rules **or** record `excluded_reason`; do **not** substitute historical PNG |
| GitHub CI without media | PR-G1 extraction tests **skip** with explicit skip reason — **do not mark PR-G1 passed in CI** |

**No silent fallback** to historical images, decoder shapes, or synthetic placeholders in `shape_library_v1.json` without `fallback_reason` + `quality_flags`.

---

## 6. Dual Selection Lanes

### Lane A — CH3 family coverage (“alphabet”)

**Purpose:** Teach/check static shape vocabulary across the 12 CH3 look families in `WALL_CH3_LOOK_ATLAS.md`.

**Checklist families (minimum):**

| family_or_checkpoint | rep CH3 | Notes |
|---|---:|---|
| circle/ring static | 0 | partial corpus coverage OK |
| horizontal line static | 32 | high priority |
| two-point / dual-dot static | 48 | |
| dotted arc / compact swirl static-animation bank | 96 | high priority |
| U-wave dynamic macro | 128 | may use phase6-like vector; thin isolated coverage |
| three-star dynamic macro | 144 | **GAP** in manifest — nearest_family or phase6 substitute |
| compact swirl dynamic macro | 160 | |
| large star polygon dynamic macro | 176 | **GAP** |
| horizontal line dynamic variants | 216 | **GAP** |
| low dotted-row dynamic macro | 200 | **GAP** |
| compact point/dot dynamic macro | 224 | **GAP** |
| late ring dynamic macro | 248 | **GAP** |

**Selection heuristics (ordered):**

1. `selection_lane: ch3_family`
2. Prefer `exposure_track: geometry_motion` when multiple captures match vector.
3. Prefer `analysis.json` signals: `usable_evidence: true`, non-blank, not `geometry_clipped_low` when field exists.
4. Prefer neutral/stable modifiers (CH5≈90, CH6/7≈128, CH8≈20) when choosing among matches — **vector still wins**; modifiers are tie-breakers only.
5. Prefer captures with both `still.jpg` and local video/motion folders present (quality signal, not G1 input).
6. If exact clean atlas baseline unavailable → `selection_tier: nearest_family` + explicit `selection_reason`.
7. For **GAP** families: best-effort nearest CH3 / phase6 motion_type match; mark tier + reason; **do not** invent captures.

**Baby-language:** Lane A is the **spelling list → pick a textbook photo** for each letter-shape.

### Lane B — Phase6 cue coverage (“SoundSwitch words”)

**Purpose:** Ensure shapes work on **real cue vectors**, not only clean CH3 sweeps.

**Source root:**

```text
captures/fixture_model/phase6_cue_validation/cue_relevant/
```

**Rules:**

1. `selection_lane: phase6_cue`
2. One entry per selected cue folder (minimum: all cue folders with usable still + metadata on disk for v1 subset smoke; full 175 for batch phase after subset passes).
3. **Authority:** `metadata.json` CH1–19 only — **never** infer behavior from folder name (`cue_023_green_solid_sinewaves` is an id, not semantics).
4. `selection_tier: phase6_cue`
5. `family_or_checkpoint` = cue folder basename (e.g. `cue_001_off`).

**Baby-language:** Lane B checks whether the renderer can read **actual show cues**, not just alphabet drills.

### Minimum selection counts (v1 smoke subset)

Before full 8k expansion:

- **Lane A:** ≥1 entry per checklist family (12), or explicit `excluded_reason` for GAP families with no local media.
- **Lane B:** ≥10 representative phase6 cues spanning static + motion_type diversity, or all available if fewer; target ≥175 only after subset extraction passes Brandon overlay review.

Both lanes **must appear** in `shape_selection.json.entries[]`.

---

## 7. Per-Fixture Calibration Projection Box

### Definition

**Per-fixture calibration projection box** — the fixed rectangle on the wall where one laser projects, detected during wall calibration (pencil ticks / boundary marks / aperture box detection). It is the laser’s **wall canvas**.

In `captures/fixture_model/analysis_geometry.json`:

```json
"boxes": [
  { "label": "image_left",  "bbox": [x0, y0, x1, y1], ... },
  { "label": "image_right", "bbox": [x0, y0, x1, y1], ... }
]
```

Current committed geometry (example — use file on disk as authority):

| label | bbox (pixels) | width × height |
|---|---|---|
| `image_left` | `[60, 156, 554, 578]` | 495 × 423 |
| `image_right` | `[646, 153, 1219, 581]` | 574 × 429 |

### Baby-language

- The **wall box** is the laser’s **fixed canvas** on the wall.
- The **laser shape** is the **bright drawing inside** that canvas.
- Every capture uses the **same graph paper** (normalization frame), not the shape’s own bounding box.

### Rules

1. Extract bright pixels **only inside** the selected fixture box (crop/mask to box).
2. Normalize coordinates **relative to that box**.
3. **Forbidden:** normalize to `source_pixel_bbox` of the bright figure alone.
4. **Forbidden:** scale every shape to fill `[-1,+1]²` — a dot stays small; a line stays where it appeared.
5. Record `selected_fixture_box` / `fixture_box_label` on every selection and shape entry.

### `selected_fixture_box` policy (v1)

| Rule | Detail |
|---|---|
| Default | `image_left` |
| Rationale | `WALL_CH3_LOOK_ATLAS.md`: master fixture ROI / identical DMX to both units; left projection used in atlas readiness |
| Future | Support `image_right` independently when dual-fixture rendering requires it |
| Missing label | Fail extraction for that entry with `fixture_box_missing` — no silent default to full frame |

PR-G1 v1 extracts **one shape per selection** using the chosen box. Dual-aperture rendering is PR-G3 concern; G1 must still record which box was used.

---

## 8. Coordinate Convention

### Coordinate space identifier

```text
wall_norm_per_fixture_calibration_box
```

Store verbatim in `shape_library_v1.json.coordinate_space`.

### Fixture box

Given selected box bbox in **image pixels** (inclusive-exclusive convention: `x0,y0` top-left, `x1,y1` bottom-right):

```text
box_width  = x1 - x0
box_height = y1 - y0
```

Require `box_width > 0` and `box_height > 0`.

### Pixel → normalized wall coordinates

For source pixel point `(px, py)`:

```text
x_norm = 2 * ((px - x0) / box_width)  - 1
y_norm = 1 - 2 * ((py - y0) / box_height)
```

| Axis | Convention |
|---|---|
| x | Increases **right**; left edge `−1`, right edge `+1`, center `0` |
| y | Increases **upward**; image pixel y **flipped**; bottom edge `−1`, top edge `+1`, center `0` |

### Bbox normalization

For pixel bbox `[px0, py0, px1, py1]` of bright figure (full image coords):

Convert all four corners through the formulas above → store axis-aligned `bbox_wall_norm` as `[min_x, min_y, max_x, max_y]` in normalized space (not independent per-corner if using AABB).

Centroid:

```text
cx_px = (px0 + px1) / 2
cy_px = (py0 + py1) / 2
→ centroid_wall_norm = [x_norm(cx_px), y_norm(cy_px)]
```

### Out-of-box points

- **Do not silently clamp** geometry into `[-1,+1]` during extraction.
- If any extracted point has `x_norm` or `y_norm` outside `[-1,+1]` (within epsilon), set quality flag **`out_of_box`**.
- Diagnostics may clamp for display; stored polylines must preserve true values + flag.

### Anti-patterns (must fail review)

| Anti-pattern | Why forbidden |
|---|---|
| Normalize to shape’s own bbox | Destroys cross-capture comparability |
| Scale shape to fill unit square | Dot becomes false macro |
| Use full `analysis_roi` instead of fixture box | Wrong canvas |
| Use `combined_bbox` for per-fixture shapes | Collapses dual fixtures |

---

## 9. Shape Extraction Algorithm v1

Implementation may adjust thresholds if documented in `extraction_params` and tests still pass. Minimum contract:

### Pipeline

```text
1. Resolve still_path (still.jpg → still_color.jpg fallback)
2. Load image (RGB or grayscale)
3. Load fixture box from analysis_geometry.json
4. Crop to box; record crop offset for pixel coords
5. Compute luma / brightness mask inside crop
6. Adaptive/local threshold: background median + k * MAD (document k)
7. Remove connected components below min_area_px (document value)
8. Connected component analysis → clusters
9. For each cluster: bbox, area, centroid, pixel lists
10. Optional: contour trace → simplify (Ramer-Douglas epsilon documented) → polylines
11. Compute source_pixel_bbox (full image coords)
12. Convert cluster geometry + polylines to wall_norm coords (§8)
13. Assign topology_class (diagnostic)
14. Set quality_flags + shape_point_count
15. Emit shape entry or explicit fallback_reason if failed
```

### Suggested v1 parameters (starting point — tune with tests)

| Parameter | Starting value | Stored in |
|---|---|---|
| `luma_source` | max(R,G,B) or Rec.709 luma | `extraction_params` |
| `threshold_k` | 3.0–5.0 (MAD multiplier) | `extraction_params` |
| `min_area_px` | 25–100 | `extraction_params` |
| `max_components` | 32 (warn above) | `extraction_params` |
| `contour_simplify_epsilon_px` | 1.5 | `extraction_params` |

### topology_class diagnostic rules

Labels are **hints for engineers**, not truths Brandon must confirm.

| Class | Heuristic (v1) |
|---|---|
| `line` | One dominant component; elongation ratio > threshold (e.g. 4:1) |
| `two_clusters` | Exactly two dominant components above min_area |
| `closed_loop` | Single component with hole topology **or** contour closed with sufficient perimeter/area ratio |
| `multi_cluster` | ≥3 dominant separated components |
| `complex_shape` | Recognizable extraction but no simple class |
| `unknown` | Extraction failed, blank, or ambiguous |

**Do not overfit labels.** Overlay review (§15) overrides label correctness.

### Empty / failed extraction

If no bright pixels above threshold:

- Emit shape entry **only if** policy requires audit trail, with `shape_point_count: 0`, `topology_class: unknown`, `fallback_reason: blank_still` or similar.
- Otherwise omit from library but retain selection entry with `excluded_reason`.
- **Never** synthesize a fan or decoder shape.

---

## 10. shape_selection.json Contract

**Path:**

```text
artifacts/renderer/pr-g1-shape-authority/shape_selection.json
```

### Top-level schema

| Field | Type | Required | Description |
|---|---|---|---|
| `artifact_version` | string | yes | e.g. `"pr-g1-shape-selection-v1"` |
| `generated_at` | string (ISO 8601) | yes | Build timestamp |
| `capture_root` | string | yes | Relative: `captures/fixture_model` |
| `plan_revision` | string | yes | e.g. `"RENDERER_WALL_TO_AERIAL_PLAN_V1 rev 4"` |
| `selection_policy_version` | string | yes | e.g. `"v1"` |
| `entries` | array | yes | Selection records |

### Entry object

| Field | Type | Required | Description |
|---|---|---|---|
| `selection_lane` | enum | yes | `ch3_family` \| `phase6_cue` |
| `family_or_checkpoint` | string | yes | Atlas family name or cue folder id |
| `capture_path` | string | yes | Relative folder under capture root |
| `still_path` | string | yes | Relative path to still used |
| `metadata_path` | string | yes | Relative path |
| `analysis_path` | string | yes | Relative path |
| `vector_key` | string | yes | e.g. `v1:200,0,32,...` |
| `ch1_19` | object | yes | CH1–CH19 map |
| `phase` | string | yes | From metadata |
| `exposure_track` | string | yes | From metadata |
| `quality_flags` | string[] | yes | May be empty |
| `selected_fixture_box` | string | yes | `image_left` \| `image_right` |
| `selection_reason` | string | yes | Human-readable |
| `selection_tier` | enum | yes | `exact_family` \| `nearest_family` \| `phase6_cue` \| `fallback_candidate` |
| `local_media_exists` | boolean | yes | Must be `true` for included extractions |
| `excluded_reason` | string | no | Present if skipped |

**Path rule:** All paths relative to repo root. **No absolute paths.** No `calib/captures` paths.

---

## 11. shape_library_v1.json Contract

**Path:**

```text
artifacts/renderer/shape_library_v1.json
```

### Top-level fields

| Field | Type | Required |
|---|---|---|
| `artifact_version` | string | yes — e.g. `"shape-library-v1"` |
| `generated_at` | string | yes |
| `capture_root` | string | yes |
| `coordinate_space` | string | yes — `wall_norm_per_fixture_calibration_box` |
| `geometry_source` | string | yes — e.g. `"captures/fixture_model/analysis_geometry.json"` |
| `selection_artifact` | string | yes — relative path to `shape_selection.json` |
| `extraction_policy_version` | string | yes |
| `shapes` | array | yes |

### Shape object

| Field | Type | Required |
|---|---|---|
| `shape_ref` | string | yes |
| `vector_key` | string | yes |
| `capture_path` | string | yes |
| `source_still` | string | yes |
| `test_id` | string | yes |
| `phase` | string | yes |
| `exposure_track` | string | yes |
| `ch1_19` | object | yes |
| `fixture_box_label` | string | yes |
| `source_pixel_bbox` | [4] number | yes — full image px |
| `bbox_wall_norm` | [4] number | yes |
| `centroid_wall_norm` | [2] number | yes |
| `topology_class` | enum | yes |
| `shape_point_count` | integer | yes |
| `clusters` | array | yes — may be empty |
| `polylines` | array | yes — may be empty |
| `extraction_params` | object | yes |
| `quality_flags` | string[] | yes |
| `fallback_reason` | string | no |

### Cluster object

| Field | Type |
|---|---|
| `cluster_id` | string |
| `source_pixel_bbox` | [4] number |
| `bbox_wall_norm` | [4] number |
| `centroid_wall_norm` | [2] number |
| `area_px` | number |
| `point_count` | integer |

### Polyline object

| Field | Type |
|---|---|
| `polyline_id` | string |
| `points` | array of `[x_norm, y_norm]` |
| `source` | enum: `contour` \| `skeleton` \| `simplified_component` |
| `closed` | boolean |
| `point_count` | integer |

### shape_ref stability

Must be **deterministic** and **portable**:

```text
shape_ref = "sh1_" + first_16_hex(SHA256(
  artifact_version + "|" +
  vector_key + "|" +
  capture_path + "|" +
  fixture_box_label
))
```

- **Must not** embed absolute local filesystem paths.
- Changing `artifact_version` intentionally rotates ids on library regen.

---

## 12. shape_library_v1.schema.json Contract

**Path:**

```text
artifacts/renderer/shape_library_v1.schema.json
```

- JSON Schema (draft 2020-12 or draft-07 — document choice in schema `$schema`).
- Must validate all required fields in §11.
- `tests/test_shape_library_schema.py` loads library + schema and validates.
- CI may skip if library not built; **implementation PR must not skip**.

Optional: also provide `shape_selection.schema.json` (recommended but not blocking v1).

---

## 13. Capture Index and Runtime Contract

### Index artifact extension (build time)

Extend `tools/capture_index_builder.py` / index regen to join shape library into `capture_index_v1.json` **without mutating captures/**.

Per capture / vector bucket, add when shape exists:

| Field | Description |
|---|---|
| `shape_ref` | Join key into shape library |
| `shape_point_count` | Integer |
| `topology_class` | Diagnostic enum |
| `shape_evidence` | `"still"` |
| `shape_fallback_reason` | string \| null |
| `shape_quality_flags` | string[] |
| `shape_source_capture_path` | Relative capture folder |

### Lookup semantics

`capture_index_runtime.py` → `lookup_exact_from_channels()`:

1. Existing behavior unchanged for vector match / provenance.
2. When index entry includes `shape_ref`:
   - Expose all shape fields in returned dict.
   - `shape_authority: true` when `shape_ref` non-empty **and** `shape_point_count > 0`.
3. When vector matches but **no** `shape_ref`:
   - `shape_authority: false`
   - `shape_fallback_reason: "no_static_shape_for_vector"` (or similar)
4. **Exact vector match alone ≠ shape authority.** Shape authority requires joined library entry with non-empty geometry (or explicit documented fallback tier).

### webserver.py / SSE

PR-G1 may add shape fields to fixture snapshot / composed payload for diagnostics. **Do not** embed full polylines in SSE (PR-H4 concern). Pass `shape_ref` + summary fields only.

---

## 14. Diagnostics Contract

### Required diagnostic fields (when shape join exists)

Display via `static/app.js` diagnostics panel (extend Phase 1):

| Field | Example |
|---|---|
| `shape_ref` | `sh1_a3f2...` |
| `topology_class` | `line` |
| `shape_point_count` | `842` |
| `shape_evidence` | `still` |
| `shape_fallback_reason` | null or explicit |
| `visible_geometry_source` | `DECODER_FALLBACK` until PR-G3 |
| `internal_shape_authority` | `true` when shape_ref valid |

### Mandatory honesty rules

1. If `shape_ref` exists but renderer still calls `_drawFan()` for visible output → diagnostics **must** show visible path as **`DECODER_FALLBACK`** (or equivalent) distinct from internal shape.
2. **No `EXACT_CAPTURE_RENDER_AUTHORITY`** headline while `validation.pass=0` (Phase 1 policy — unchanged).
3. Vector match label (`EXACT_VECTOR_MATCH`) must **not** imply visible geometry is capture-driven.
4. PR-G1 must **not** claim “beams now match captures” in UI copy, docs, or tests.

### renderer.js (PR-G1 minimal)

- May load shape summary for diagnostics / future wall debug overlay (`?wallDebug=1` optional, not required for G1 done).
- **Must not** replace `_drawFan()` visible path in PR-G1.

---

## 15. Overlay Review / Human Validation

### Brandon workflow (only human gate for G1)

For each Lane A family representative + Lane B phase6 example:

1. Show **original local still** (cropped to fixture box optional).
2. Show **extracted overlay** (clusters/contours in contrasting color).
3. Brandon answers: **“Does the overlay roughly trace what the laser actually drew?”** → `yes` / `no`.
4. Brandon does **not** assign topology labels.

### Artifacts

| Artifact | Path |
|---|---|
| Contact sheets | `artifacts/renderer/pr-g1-shape-authority/contact_sheets/` |
| Review index | `artifacts/renderer/pr-g1-shape-authority/overlay_review_index.json` |

### overlay_review_index.json (minimum)

| Field | Description |
|---|---|
| `shape_ref` | Link to library entry |
| `still_path` | Source |
| `contact_sheet_path` | PNG path |
| `lane` | `ch3_family` \| `phase6_cue` |
| `brandon_verdict` | `yes` \| `no` \| `pending` |

PR-G1 coding PR is **not done** until Lane A + Lane B sheets exist and at least subset reviewed (implementation report documents pending vs passed).

---

## 16. Tests

Exact test files required for PR-G1 implementation PR:

| Test file | Validates |
|---|---|
| `tests/test_shape_selection.py` | Both lanes present; rejects historical paths; `local_media_exists` checks |
| `tests/test_shape_library_schema.py` | `shape_library_v1.json` validates against schema |
| `tests/test_shape_coordinates.py` | §8 formulas against known box + pixel fixtures |
| `tests/test_shape_extraction_synthetic.py` | Synthetic images: line, two_clusters, closed_loop, multi_cluster, blank |
| `tests/test_capture_index_runtime_shape_refs.py` | Exact vector lookup exposes `shape_ref` when index joined |
| `tests/test_no_historical_pr_g1_inputs.py` | No `calib/captures`, `/tmp/vln_wall`, `archive/pre_corpus` in selection artifact |
| Extend `tests/test_renderer_motionstate.js` **or** `tests/test_app_diagnostics.js` | Diagnostics distinguish internal `shape_ref` from visible decoder fallback |

### Synthetic coordinate test vectors (minimum)

Use box `[60, 156, 554, 578]` (`image_left`):

| Pixel point | Expected x_norm | Expected y_norm |
|---|---:|---:|
| Center (307, 367) | ≈ 0.0 | ≈ 0.0 |
| Left edge (60, 367) | −1.0 | ≈ 0.0 |
| Right edge (554, 367) | +1.0 | ≈ 0.0 |
| Top edge (307, 156) | ≈ 0.0 | +1.0 |
| Bottom edge (307, 578) | ≈ 0.0 | −1.0 |

Tests use tolerances (e.g. 1e-4).

### Local media tests

Tests that require real stills must `@pytest.mark.skipif(not local_media_available)` with message explaining GitHub CI limitation.

---

## 17. Acceptance Criteria

PR-G1 implementation PR is acceptable only when **all** are true:

- [ ] `artifacts/renderer/pr-g1-shape-authority/shape_selection.json` exists
- [ ] `shape_selection.json` includes **both** lanes (`ch3_family` + `phase6_cue`)
- [ ] Every included entry has `local_media_exists: true` (verified on disk)
- [ ] No selection `still_path` references historical/archive/calib paths
- [ ] `artifacts/renderer/shape_library_v1.json` exists
- [ ] `artifacts/renderer/shape_library_v1.schema.json` exists
- [ ] Library validates against schema
- [ ] ≥1 selected local capture per required CH3 checklist family has non-empty `shape_ref` **unless** explicit `fallback_reason` + `quality_flags`
- [ ] Selected phase6 cues with usable evidence expose `shape_ref` through `lookup_exact_from_channels()` after index join
- [ ] Contact sheets generated under `contact_sheets/`
- [ ] Diagnostics expose shape fields (§14)
- [ ] Visible geometry labeled decoder fallback until PR-G3
- [ ] No mutation under `captures/**`
- [ ] No mutation of `data/fixture_model.json`
- [ ] No historical calib/captures inputs
- [ ] No SoundSwitch cue-name behavior authority in selector
- [ ] All §16 tests pass locally with media present
- [ ] `artifacts/renderer/pr-g1-shape-authority/implementation_report.md` complete

**Explicit non-acceptance:**

- Claiming visible aerial geometry is capture-driven after PR-G1 only.
- Passing PR-G1 in CI without local media while claiming full extraction passed.
- Using atlas legacy PNG column as extraction source.

---

## 18. Failure Modes

Each failure must produce an **explicit reason** — no silent success.

| Failure | Detection | Output |
|---|---|---|
| Missing capture root | Preflight | Exit: `LOCAL_MEDIA_MISSING` |
| Missing manifest / geometry | Preflight | Exit: `LOCAL_GEOMETRY_MISSING` |
| Missing still + still_color | Per entry | `excluded_reason: no_still_media` |
| Missing analysis_geometry.json | Preflight | Exit: `CALIBRATION_GEOMETRY_MISSING` |
| Fixture box label missing | Parse geometry | `fixture_box_missing` |
| Blank still | Extraction | `fallback_reason: blank_still`, `topology_class: unknown` |
| Low contrast | Extraction | `quality_flags: [low_contrast]` |
| Noisy over-segmentation | Extraction | `quality_flags: [noisy_components]` |
| Shape outside box | Coord check | `quality_flags: [out_of_box]` |
| Schema validation failure | Test/build | Exit non-zero |
| No phase6 folders found | Lane B scan | Exit or empty lane with explicit blocker in report |
| No CH3 family match | Lane A scan | `excluded_reason` per family in selection file |
| Historical path in selection | Test | Fail `test_no_historical_pr_g1_inputs` |
| GitHub clone without media | CI | Skip extraction tests; report `local_media_absent` |

---

## 19. Implementation Report Requirements

**Path:**

```text
artifacts/renderer/pr-g1-shape-authority/implementation_report.md
```

Required sections:

1. **Scope** — files changed (list exact paths)
2. **Local capture root** — absolute path used on Brandon’s machine
3. **Selection counts** — Lane A / Lane B entry counts
4. **Shape library count** — total shapes; non-empty vs fallback
5. **Schema validation** — command + pass/fail
6. **Tests** — commands + results
7. **Example shape_ref entries** — 3–5 representative (CH3=32 line, CH3=48 two_clusters, one phase6 cue)
8. **Contact sheet paths**
9. **Explicit non-mutation statement** — `captures/**` and `data/fixture_model.json` untouched
10. **Visible geometry statement** — aerial remains `_drawFan()` / decoder fallback until PR-G3
11. **Known limitations** — GAP families, low contrast macros, dual-fixture box default
12. **Brandon overlay verdict summary** — yes/no counts pending

---

## 20. PR-G1 Done Definition

PR-G1 is **done** when:

1. Selected-subset shape extraction works locally (not full 8k batch).
2. Both selection lanes present in `shape_selection.json`.
3. `shape_library_v1.json` validates against schema.
4. Runtime/index exposes `shape_ref` + shape diagnostics on exact vector hits.
5. Diagnostics **clearly separate** internal wall-space shape authority from visible decoder fallback.
6. Contact sheets exist for Lane A + Lane B representatives.
7. All §16 tests pass on Brandon’s machine with local media.
8. Implementation report complete.
9. No forbidden sources, mutations, or overclaims.

PR-G1 is **not done** if:

- Only Lane A or only Lane B populated.
- Visible `_drawFan()` replaced (that is PR-G3 scope creep).
- Motion tracks implemented (PR-G1b).
- Full 8k batch run before subset passes Brandon overlay review.

---

## 21. Open Questions / Non-blocking Notes

| Topic | Note |
|---|---|
| `image_left` default vs `image_right` | v1 defaults left; PR-G3 may require per-fixture rendering from both boxes |
| Dynamic macro GAP families (144, 176, 200, 216, 224, 248) | Expect `nearest_family` or phase6 substitutes; document in selection_reason |
| `topology_class` | Diagnostic only; overlay review is acceptance truth |
| Full 8k expansion | Wait until 12-family + phase6 subset passes |
| Visible renderer | Stays decoder fallback until PR-G3 — not a PR-G1 blocker |
| `setup_geometry.json` | Not required for G1 extraction; PR-G3 projection |
| SSE polyline payload | Out of scope; refs only until PR-H4 |
| Opus review | PR-G1 routine (gpt-5.5); not Opus checkpoint — G1b/G2/G3 are |

---

## Appendix A — Planned build tools (PR-G1 code PR — not this doc)

| Tool | Role |
|---|---|
| `tools/shape_library_builder.py` | Select + extract + emit artifacts (or split selector/extractor) |
| `tools/capture_index_builder.py` | Join shape fields into index |

**This spec document does not authorize creating those tools until a separate implementation PR is opened.**

---

## Appendix B — Related paths

```text
docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md    # Plan rev 4 §6.0
docs/WALL_CH3_LOOK_ATLAS.md                 # Lane A checklist
captures/fixture_model/analysis_geometry.json
artifacts/renderer/pr-g1-shape-authority/shape_selection.json
artifacts/renderer/shape_library_v1.json
artifacts/renderer/shape_library_v1.schema.json
artifacts/renderer/pr-g1-shape-authority/implementation_report.md
```
