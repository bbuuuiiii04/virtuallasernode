# Capture-Backed Renderer Implementation Spec V2

**Status:** Proposed implementation spec (supersedes `docs/PR_G1_STATIC_SHAPE_IMPLEMENTATION_SPEC.md` for extraction/authority; inherits its selection, coordinate, and honesty contracts where noted)
**Date:** 2026-06-10
**Branch context:** `renderer-pr-g1-static-shape-authority` (PR #1, base `renderer-accuracy-phase1`)
**Evidence basis:** repo audit of PR #1 diff, v6 artifacts (19 shapes, 0 authority), contact-sheet visual inspection, AI extraction artifacts, 179 passing tests
**Labeling convention:** facts are marked **[CONFIRMED]** (verified in repo/artifacts this review), **[ASSUMED]** (reasonable default, tune with data), or **[UNKNOWN]** (must be measured before relying on it).

---

## 0. Architecture Decision Summary

**Recommended direction: deterministic, mask-first, capture-grounded authority pipeline.**

1. **Authority representation flips from "vector polylines as authority" to "validated laser-core stroke mask as authority, vectors as derived views."** The v1–v6 failures are dominated by trying to produce vector geometry directly from glow-contaminated masks and then scoring those vectors against the same contaminated masks. A core mask has a crisp physical definition (saturated laser core vs. colored bloom), is directly checkable against pixels, and cannot be faked by idealized geometry. Vectors (centerlines, contours, dot anchors) are derived from the mask and validated against it with two-sided pixel-distance metrics.
2. **Extraction is rewritten as deterministic classical CV on numpy + scikit-image (v7).** The current pure-Python/PIL stack (no numpy, no cv2 anywhere in the venv — [CONFIRMED]) is both the quality ceiling and the scaling blocker. No AI on the critical path.
3. **Detection runs on the full `analysis_roi`, not hard-cropped to the calibration box.** Audit proof: `cue_002_green`'s figure sits at/beyond the right edge of `image_left` and was cropped away before extraction (contact sheet `sh1_adb58093da473f3e.png`) — the box is the *normalization frame*, not a containment guarantee. Components are assigned to fixtures afterward; out-of-box geometry is preserved and flagged, never clamped.
4. **Current PR-G1 approach disposition: split + partially rewrite + quarantine.**
   - **Keep:** selection lanes, artifact/schema contracts, `shape_ref` hashing, coordinate convention + tests, runtime `shape_authority` gating, diagnostics honesty, conservative "0 usable authority" policy, contact-sheet/human-review workflow, test culture.
   - **Rewrite:** the extraction core (support masks, vectorizers, scorer, `classify_visual_status`) as v7 mask-first.
   - **Quarantine (keep, off the critical path, experimental-only):** all `tools/ai_*` (Gemini raw-coordinate path, CV refinement, mask tracer spike). Do not commit the uncommitted mask-tracer WIP into PR-G1; park it on a spike branch.
   - **Delete from the critical path (not from history):** `_detect_out_of_box_leak` full-frame scan (systematic false positive — 19/19 shapes flagged `out_of_box` from the fixtures' own glow at frame bottom [CONFIRMED]), single-path-only vectorization, glow-flood hysteresis support as a geometry source.
5. **AI/Gemini does NOT belong on the critical path.** Evidence: Gemini returns schematic geometry in a self-chosen canvas (640×480 vs. the real 495×423 crop, never rescaled — [CONFIRMED] in `artifacts/renderer/pr-g1-ai-extraction/generated/ai_extractions.json` + `tools/ai_shape_extractor.py`); spatial gates correctly reject it; CV refinement floods halo; usage limits block iteration; 8k-scale cost is unjustified. AI remains an optional, offline, cached, quarantined-cases-only assistant whose output can never become authority without passing the same deterministic core-mask validation **and** human review.
6. **Safest next implementation step:** the v7 core-mask extractor + validation v2 on exactly 3 named captures (row-of-squares, dual-dot, cue_002) with corrected overlay semantics, touching no runtime, no builder selection, no AI files (§19).

**Roadmap verdict:** sequence is rearranged, not discarded: `G1 (rewritten, subset) → G1.5 (batch/coverage, new) → G2a (static wall playback + wallDebug, moved earlier) → G1b (motion tracks) → G2b (motion playback + residual) → G3 (aerial) → G4 (consolidated regression)`. Rationale in §6.

---

## 1. Renderer Mission

VirtualLaserNode previews Brandon's real DMX laser fixtures from SoundSwitch so EDM laser shows can be designed without physically setting up the rig. Long-term target: a near-1:1, capture-grounded renderer built from the 8,324-package wall-capture corpus (8,324 manifest rows, 175 phase6 cue folders, stills at 1280×720, ~60 fps motion frame folders — [CONFIRMED]).

**"Near 1:1" means, in order:**

1. Captured wall patterns are reproduced accurately **in wall space** wherever capture coverage exists.
2. Static shape geometry comes from **real captured laser-core/stroke pixels** — never guessed decoder geometry.
3. Motion behavior comes from capture clips/motion analysis where available.
4. Decoder logic, `fixture_model` summaries, MotionState math, and fan geometry are **fallback only**, used when capture-backed authority is missing for a vector/parameter.
5. The runtime **never silently presents fallback as capture authority** (already enforced in `capture_index_runtime.py:195-237` and `static/renderer.js:719-724` — keep).

**Must be capture-backed:** wall figure geometry (shape, multiplicity, position-in-box), wall figure motion (deformation/translation/loop timing), color palette (PR-C, done), strobe rate/duty (PR-C, done).

**May remain approximate/fallback (labeled):** aerial haze look (scattering, bloom, falloff), beam intensity profile, modifier residuals for DMX deltas not isolated in captures, direction sign below confidence threshold, CH20–36 second pattern, CH2 sound mode.

**Must never be guessed:** any geometry presented under a capture-authority label; cue identity from SoundSwitch names (e.g., `cue_002_green` is actually red dotted arcs — [CONFIRMED] from its still); coverage claims ("works on all stills") without a coverage report.

---

## 2. Source-of-Truth Hierarchy

Priority order; an earlier source beats a later one wherever both speak to the same question. Items marked *frame* define coordinate context rather than content.

| # | Source | Role | Authority scope |
|---|---|---|---|
| 1 | `captures/fixture_model/**` stills + videos + `motion_analysis_*` frames | **Primary evidence.** Immutable. | What the laser actually drew, and how it moved |
| 2 | `captures/**/metadata.json` CH1–19 vectors | **Identity key.** | Which DMX state produced the evidence; the only cue-matching key |
| 3 | `captures/**/analysis.json` | Quality gates + motion classification | Selection/quarantine signals, strobe/loop/motion_type; **never shape topology** |
| 4 | `captures/fixture_model/analysis_geometry.json` (boxes, `analysis_roi`, px_per_inch) | *Frame.* Calibration boxes = per-fixture wall canvas; ROI = detection domain | Normalization + detection domain; PR-G3 wall plane scale |
| 5 | `captures/fixture_model/setup_geometry.json` | *Frame.* Physical rig layout ([CONFIRMED]: wall distance ≈ 6′1″, fixture spacing 30.5″, 2 apertures/fixture 5″ apart producing mirror images, aperture 2″×1.5″) | PR-G3 fixture pose; approximate, labeled `approximate_user_measured` |
| 6 | Manual overrides (`artifacts/renderer/*_overrides_*.json`, human review verdicts) | Human corrections, index-side only | Beats automated classification where present; never mutates captures |
| 7 | `data/fixture_model.json` | Composed channel-semantics model | Fallback composition (`MODEL_COMPOSED`); never shape authority |
| 8 | Decoder semantics (`fixtures.py` `decode_36ch`, `CAL`) | Channel meaning + last-resort visuals | `DECODER_FALLBACK` only |
| 9 | AI outputs (Gemini or other) | **Not a source of truth.** Offline hints for quarantined cases | Never authority; never on the runtime path; must be re-validated deterministically against #1 |

Rules: sources 1–5 are read-only (`captures/**` and `data/fixture_model.json` must never be mutated — repo policy, unchanged). All derived data lives under `artifacts/renderer/**`. Conflict rule (kept from PR-G1 spec §4): local corpus stills beat atlas/checklist text.

---

## 3. Runtime Authority Hierarchy

Per parameter and per vector, the runtime resolves the highest available tier. Tier must be displayed; downgrades must be loud.

| Tier | Name | When usable |
|---|---|---|
| T0 | `CAPTURE_STATIC_AUTHORITY` | Vector bucket joins a shape record with `status: authority` (validated core-mask geometry, §15) |
| T1 | `CAPTURE_MOTION_AUTHORITY` | T0 plus a motion track record with `status: authority` for the same vector (or same-bucket exposure pair) |
| T2 | `CALIBRATED_PROJECTION` | PR-G3: aerial geometry derived from T0/T1 wall geometry + rig pose; inherits min(T0/T1) and adds `projection_source` label |
| T3 | `MODEL_COMPOSED` | `fixture_model` composition where no shape/motion record exists |
| T4 | `DECODER_FALLBACK` | Decoder/CAL synthetic behavior |
| T5 | `QUARANTINED / NO_AUTHORITY` | Record exists but failed validation: runtime treats as T3/T4 and surfaces `shape_fallback_reason` = quarantine reason |

Hard rules (most already implemented — keep):

- `shape_authority: true` requires bucket flag AND non-empty `shape_ref` AND `shape_point_count > 0` (`capture_index_runtime.py:195-206` [CONFIRMED]).
- A quarantined or provisional record must never set `shape_authority: true` (builder already merges `usable_as_shape_authority` into the bucket flag — `tools/shape_library_builder.py:485` [CONFIRMED]).
- Exact vector match alone is `EXACT_VECTOR_MATCH` provenance, never geometry authority (Phase 1 policy, unchanged).
- Headline tier = MIN across visible parameters (PR-A, unchanged). No `EXACT_CAPTURE_RENDER_AUTHORITY` while `data/fixture_model.json` `validation.pass = 0`.
- Partial authority is allowed and must be per-parameter: e.g., shape T0 + motion T4 renders static shape with decoder animation, labeled per-parameter.

---

## 4. Clean-Sheet Target Architecture

The layering the system converges to (PASS 1 result, reconciled with repo reality):

```text
EVIDENCE (immutable)
  stills / videos / motion frames / metadata / analysis / geometry files
        │  (build time, local Mac, deterministic, resumable)
        ▼
EXTRACTION v7 (per capture, per fixture)
  background model → laser score maps → CORE mask (saturated stroke) vs GLOW mask
  detection domain = analysis_roi          (never hard-crop to calibration box)
  component → fixture assignment           (box geometry; ambiguity ⇒ quarantine)
  vector decomposition per core component  (loops / open strokes / dots)
        ▼
VALIDATION v2 (two-sided, pixel-grounded; §15)
  precision: geometry samples ON core      recall: core skeleton covered by geometry
  halo exclusion by construction           status: authority | provisional | quarantined
        ▼
AUTHORITY STORE (artifacts/renderer/shape_authority_v2/)
  per-capture record JSON + RLE core mask + derived vectors + metrics + status
  coverage_report.json + quarantine_report.json (machine-readable reasons)
        ▼
INDEX JOIN (capture_index_v1.json buckets: shape_ref, status, conflicts)
        ▼
RUNTIME RESOLVER (tiers T0–T5, per parameter; §3)
        ▼
WALL ENGINE (PR-G2a/b: static playback → motion tracks → DMX residual)
        ▼
RIG PROJECTION (PR-G3: pose from setup/analysis geometry → rays)
        ▼
AERIAL DRAW (beams, haze, strobe/color from PR-C)   +   wallDebug side-by-side
```

Clean-sheet principles that drive every PR below:

1. **Physics first:** the laser core saturates the sensor (white-ish: high min(R,G,B)) while bloom is colored and dimmer ([CONFIRMED] visually on contact sheets: white square outlines inside blue/purple halo). Core/glow separation is a thresholding problem with local statistics, not a topology-guessing problem.
2. **Authority must be cheap to verify and hard to fake.** A raster core mask is both. Idealized vectors are neither.
3. **Multi-part figures are the norm, not the exception** (row of 4–5 square outlines for CH3=0/CH4=195 [CONFIRMED]). Every stage must handle N components, N polylines, mixed kinds.
4. **Batch-first:** 8,324 packages ⇒ streaming, multiprocessing, resumable, sharded artifacts, coverage accounting. A pipeline that only works as a one-off screenshot success fails PR-G1.
5. **Humans audit samples, machines audit everything:** automated gates run on every capture; Brandon reviews the smoke subset fully and stratified samples at scale.

---

## 5. Repo Audit — What Exists and Its Disposition

### 5.1 Extraction failure diagnosis (PASS 2 core findings, all [CONFIRMED])

| # | Root cause | Evidence |
|---|---|---|
| F1 | **Hard crop to calibration box drops figures.** Figures move with position channels; calibration box ≠ containment. | `tools/shape_extraction.py:774` crops to box; `sh1_adb58093da473f3e.png` (cue_002) shows both dotted arcs at/beyond box edges — only the in-box sliver was traced ⇒ `partial_fragment`, weak |
| F2 | **Support mask floods halo.** Low hysteresis threshold `max(med+1.2·MAD, P58)` sits barely above background; per-color bridging (radius 4) + 3× dilate spreads further. | `tools/shape_hysteresis_support.py:126-146` |
| F3 | **Fit target contaminated by F2.** Scoring target includes the skeleton of the flooded support mask, so a *correct* multi-stroke trace scores worse than a blob-skeleton meander. | `tools/shape_stroke_vectorization.py:640-656`; meander visible in `sh1_21b9e82ef84b930b.png` |
| F4 | **Vectorizers structurally single-path.** `continuous_stroke` emits at most one polyline (`paths[:1]`); skeleton splitting drops disconnected components with no branch points (each clean square loop!) and traces cycles as open paths. | `tools/shape_stroke_vectorization.py:313-348,388`; `tools/shape_skeleton_graph.py:134-186` |
| F5 | **Scorer fails correct sparse geometry.** Dual-dot: two anchors sit exactly on the dot cores yet fail as "fragment-only" because coverage is measured against halo-inflated support. | `sh1_41c84ad2ac1f458e.png`; `classify_visual_status` thresholds `tools/shape_stroke_vectorization.py:981-998` |
| F6 | **`out_of_box` flag is a universal false positive.** Counts ≥5 bright pixels anywhere in the full frame outside boxes; the fixtures' own glow at the frame bottom triggers it on 19/19 shapes. The real out-of-box signal (cue_002) is drowned. | `tools/shape_extraction.py:717-753`; `shape_library_v1.json` quality_flags |
| F7 | **Pure-Python CV everywhere; no numpy/cv2/skimage in the venv.** Hand-rolled Zhang–Suen, BFS floods, per-pixel dilation; the leak detector scans 921k px per capture in Python. Quality ceiling + 8k-scale blocker. AGENTS.md imposes no such dependency restriction. | `tools/shape_*.py`, `.venv` probe; `AGENTS.md` |
| F8 | **Crop-global statistics.** med/MAD/percentiles over the whole crop assume background dominance; macro looks with large glow shift the statistics. | `tools/shape_laser_maps.py:110-113`, `_percentile` uses |
| F9 | **Gemini reference-frame mismatch never normalized.** Extractor sends the true 495×423 crop; Gemini answers in its own 640×480 canvas; `parsed.setdefault("image_width", …)` keeps Gemini's dims; coordinates map 1:1 onto the smaller crop ⇒ systematic "too low/right" offset. Even rescaled, output is schematic (perfect 20×20 squares). | `tools/ai_shape_extractor.py:258-259`; `generated/ai_extractions.json`; AI contact sheet |
| F10 | **CV refinement re-derives everything from local pixels anyway.** Snap/split/halo machinery (1,406 lines) ends at `halo_flood_component`; the AI contributes only a topology hint. | `tools/ai_shape_cv_refinement.py`; latest run: `cv_refined: 0` |
| F11 | **Overlay semantics violated:** all candidate polylines are drawn yellow on contact sheets even with `usable_as_shape_authority=false` (all 19). | `tools/shape_extraction.py:924-960` |

The five prior CV-refinement attempts (global shift, strict component match, merged-loop splitting, halo flood, latest reject) all failed on consequences of F2/F4/F9 — none addressed the root causes.

### 5.2 Disposition table

**KEEP (works, verified):**

- Selection lanes A/B + ledger with forbidden-path checks and `excluded_reason` (`tools/shape_library_builder.py:50-347`).
- Artifact contracts and schema validation; `shape_ref` hashing (`compute_shape_ref`); geometry-source sha256 stamping.
- Coordinate convention + tests (`pixel_to_wall_norm`, y-flip; `tests/test_shape_coordinates.py`).
- Runtime authority gating (`capture_index_runtime.py`), index merge honoring `usable_as_shape_authority`, diagnostics fields (`static/app.js:245-254`, `static/renderer.js:719-724,801-810`), `DECODER_FALLBACK_DRAWFAN` + `NOT_WIRED_PR_G3` labels.
- Human-review workflow artifacts (contact sheets, `overlay_review_index.json`, `visual_review_summary.md`).
- Test discipline: 179 passing tests including anti-regression tests for every historical failure mode.
- Conservative outcome itself: **zero fake authority shipped.** The honesty machinery did its job.

**REWRITE (v7, new modules — do not patch v6 in place):**

- Core extraction: replace `build_hysteresis_support` + `classify_shape_type` + the five vectorizers + `score_geometry_fit` + `classify_visual_status` with mask-first v7 (§7). v6 files stay frozen for reference/fallback until v7 passes Stage C, then retire from the builder path.
- `render_overlay_image` overlay palette (§16).
- Out-of-box detection: domain-aware (analysis_roi), per-component, replaces `_detect_out_of_box_leak`.

**DELETE from critical path (retain in git history only):**

- Full-frame leak scan, `_trace_core_path` greedy walk, `_brightest_ridge_core` per-column ridge (meander generators), `paths[:1]` truncation, P58 support flooding.

**QUARANTINE (keep in repo, experimental, never default, never authority):**

- `tools/ai_shape_extractor.py`, `ai_shape_extractor_adapter.py`, `ai_shape_geometry_convert.py`, `ai_shape_cv_refinement.py`, `ai_shape_spatial_gate.py` (the spatial gate's core/strict-core mask helpers may be *imported* by v7 validation — they are deterministic), plus the **uncommitted** `ai_shape_mask_tracer.py` spike → park on a spike branch, do not include in PR-G1. Generated AI outputs stay gitignored ([CONFIRMED] `.gitignore:18-22`).

**SPLIT into later PRs:** batch/coverage machinery (G1.5), wallDebug viewer (G2a), motion tracks (G1b), projection (G3), consolidated regression (G4).

**EXPERIMENTAL ONLY:** Gemini mask tracer; any future AI assistance (§14.3).

### 5.3 PR #1 disposition

PR #1 (104 files, +36k/−5.7k) is honest but overgrown: infra + 6 extraction rewrites + AI spike in one diff. Recommendation: **re-scope and merge the infrastructure** (selection, contracts, runtime gating, diagnostics, tests, frozen v6 as non-authority fallback, quarantined AI tools) with the title "PR-G1 infrastructure + honest zero-authority state", then implement v7 as a focused follow-up PR on the same branch line. Do not merge anything titled "static shape authority" while `usable_as_shape_authority = 0`.

---

## 6. Revised Roadmap

Original: `G1 → G1b → G2 → G3 → G4`. Verdict: right pieces, two sequencing errors and one missing stage.

1. **Missing stage:** "full 8k expansion" was a bullet inside G1; it is its own engineering problem (sharding, resume, coverage, conflict handling) → promoted to **PR-G1.5**.
2. **Wall playback before motion:** the wallDebug side-by-side harness (currently buried in G4 item #4) is the natural validation instrument for *static* authority at scale and de-risks coordinate/rendering conventions before the highest-risk motion work. → **PR-G2a** (static wall playback + wallDebug) moves ahead of G1b. Motion tracks then get validated inside an existing playback harness instead of standing up playback and tracks simultaneously.
3. **G4 becomes consolidation**, not the first appearance of regression tooling — every PR lands its own tests/coverage hooks.

```text
PR-G1   Static shape authority v7 (mask-first, deterministic, subset scale)   [routine review]
PR-G1.5 Batch + coverage + quarantine reporting, staged rollout to full corpus [routine review]
PR-G2a  Wall-space static playback + wallDebug side-by-side (?wallDebug=1)     [Opus checkpoint]
PR-G1b  Motion shape tracks from capture clips                                 [Opus checkpoint]
PR-G2b  Motion playback + DMX modifier residual                                [Opus checkpoint]
PR-G3   Rig projection + aerial beam/haze draw (replace _drawFan on hit path)  [Opus checkpoint]
PR-G4   Consolidated diagnostics, regression harness, fallback budgets         [routine review]
PR-H1–H4 unchanged (timing, combos, direction, storage) — after G4
PR-F    physical calibration — stays SUSPENDED
```

Numbering note: "PR-G1b = motion" is kept to match existing docs; G1.5 and G2a/G2b are insertions, not renames.

---

## 7. PR-G1 — Static Wall-Shape Authority v7

### 7.1 Objective

For each selected still, produce a **validated record of what the laser drew on the wall**: a laser-core stroke mask (authority) plus derived vector geometry (renderable), in per-fixture calibration-box wall coordinates, with machine-checkable validation metrics and explicit quarantine on failure. No visible runtime renderer changes.

### 7.2 Inputs (unchanged from PR-G1 spec §4–5, all [CONFIRMED] present)

- `captures/fixture_model/**/still.jpg` (1280×720; `still_color.jpg` fallback), `metadata.json` (CH1–19), `analysis.json` (gates), `manifest.jsonl` (8,324 rows), `analysis_geometry.json` (`analysis_roi: [0,129,1280,589]`, boxes `image_left [60,156,554,578]`, `image_right [646,153,1219,581]`), `phase6_cue_validation/cue_relevant/` (175 folders).
- Forbidden inputs unchanged: `calib/captures/**`, `archive/pre_corpus_*`, `/tmp` atlas PNGs, cue names as behavior keys, GitHub-only clones.
- **New dependencies:** `numpy`, `scikit-image` (pure-wheel installs; add to `test-requirements.txt` or new `tools-requirements.txt`). Tests skip with explicit reason when missing, same pattern as local-media skips. AGENTS.md does not forbid this [CONFIRMED].

### 7.3 Extraction algorithm v7 (deterministic)

```text
 1. Load still RGB; restrict to detection domain = analysis_roi.
 2. Background model: per-channel median over domain (excluding top-percentile
    pixels) [ASSUMED: median is adequate; verify vs. per-tile median on macros].
 3. Laser score maps: background-subtracted per-channel + combined max-channel
    score (reuse the *idea* of tools/shape_laser_maps.py; reimplement in numpy).
 4. CORE mask:  score ≥ max(P99.5(domain), bg + k_core·MAD)  AND local-max ridge
    OR saturation test (min(R,G,B) ≥ sat_floor for white cores)
    [ASSUMED k_core≈8–12, sat_floor≈200; tune on Stage A/B set].
 5. GLOW mask:  score ≥ bg + k_glow·MAD (k_glow≈3–4). Used ONLY for diagnostics,
    fixture assignment hints, and halo metrics — never as geometry source.
 6. Morphology on CORE only: remove specks (< min_core_area≈4 px), close 1 px
    gaps (radius 1) [ASSUMED]. NEVER bridge with glow-level thresholds.
 7. Connected components on CORE (8-conn, skimage.measure.label).
 8. Fixture assignment per component: containing box → nearest box center within
    margin → ambiguous ⇒ quality flag `fixture_assignment_ambiguous`, quarantine
    that fixture's record (both-fixture overlap is the cue_002 risk case).
 9. Per component, classify by geometry of the COMPONENT ITSELF:
    dot (area ≤ dot_max≈80 px AND aspect < 2 AND no hole) |
    closed_stroke (cycle: skeleton has no endpoints / filled-hole test) |
    open_stroke (otherwise).
10. Vectorize per component (skimage.morphology.skeletonize +
    skimage.measure.find_contours):
    dot          → 1 anchor point (intensity-weighted centroid)
    closed_stroke→ closed centerline loop (skeleton cycle trace; fallback:
                   mid-contour between outer/inner contour at stroke width)
    open_stroke  → ordered skeleton path(s); ALL paths ≥ min_len, not just the
                   longest; branch points preserved as graph → emitted as
                   multiple polylines with shared endpoints.
11. Simplify (Douglas-Peucker ε≈0.75 px [ASSUMED]); keep px-space geometry.
12. Normalize to wall space per assigned fixture box (§7.6). DO NOT CLAMP.
13. Validate (§15). Emit record with status + reasons + metrics.
14. Render contact sheet from the FINAL stored geometry only (§16).
```

Performance target: ≤ 1 s/capture single-process, ≥ 8 captures/s with multiprocessing on the local Mac [ASSUMED; measure in Stage B and record in the report].

### 7.4 Representation decision (explicit)

**Hybrid, mask-first.**

- **Primary authority = core stroke mask** (RLE-encoded, crop/domain pixel space + the affine to wall space). It *is* "real captured laser-core/stroke pixels," satisfying the PR-G1 acceptance bar by construction.
- **Secondary derived geometry = typed vector set** per fixture: closed centerline loops, open centerline polylines, dot anchors — each tagged `geometry_kind`, `ordered`, `closed`, validated against the mask (§15). PR-G2 renders vectors when their fit passes, else falls back to drawing the mask directly (mask rendering is always pixel-grounded, so partial vectorization degrades gracefully instead of quarantining the whole capture).
- **Not chosen as primary:** skeleton paths alone (lossy on stroke width, fragile on loops), contours alone (double-line artifacts on thin strokes), topology graphs (premature abstraction), wall-space splines and canonical shape families (deferred until G2 data shows they're needed; families re-enter only as *labels*, never as geometry).
- **Why this supports G2 and G3:** wall playback needs drawable wall geometry (vectors or mask — both available); aerial projection needs sampled wall hit points along strokes — sampled from vectors when present, from mask skeleton otherwise. Motion tracks (G1b) need a stable per-figure anchor (mask centroid/bbox + component correspondence), which masks give robustly.

### 7.5 Outputs and artifact paths

```text
artifacts/renderer/shape_authority_v2/
  manifest.json                 # batch header: policy versions, geometry sha, counts
  records/<shape_ref>.json      # per-capture-per-fixture record (committed for smoke subset)
  masks/<shape_ref>.rle.json    # core mask RLE (committed for smoke subset; sharded later)
  contact_sheets/<shape_ref>.png
  coverage_report.json          # §8
  quarantine_report.json        # §8
artifacts/renderer/pr-g1-shape-authority/shape_selection.json   # unchanged contract
```

`shape_library_v1.json` remains as the index-facing aggregation; v7 regenerates it from records with `extraction_policy_version: "v7"`. Batch-scale sharding moves to G1.5/PR-H4 layout.

### 7.6 Coordinate systems (kept; one addition)

- `wall_norm_per_fixture_calibration_box` exactly as PR-G1 spec §8 (x→right, y→up, box edges ±1; verified formulas in `tools/shape_extraction.py:69-72` + `tests/test_shape_coordinates.py` — keep both).
- Records store **both** `*_px` (full-image pixel) and `*_wall_norm` fields for every geometry element, plus `detection_domain: analysis_roi` and `fixture_box_label`.
- **Out-of-box geometry is preserved with true values** and per-component flag `out_of_box_geometry` (true normalized extent recorded). The old full-frame `out_of_box` leak flag is retired (F6).

### 7.7 Record schema (per capture × fixture)

```jsonc
{
  "record_version": "shape-authority-v2",
  "shape_ref": "sh2_<16hex>",            // sha256(version|vector_key|capture_path|box_label)
  "vector_key": "v1:…", "ch1_19": {…},
  "capture_path": "…", "source_still": "…", "test_id": "…",
  "phase": "…", "exposure_track": "…",
  "fixture_box_label": "image_left",
  "detection_domain_px": [0,129,1280,589],
  "geometry_source": {"path": "...analysis_geometry.json", "sha256": "…"},   // keep v6 pattern
  "extraction": {
    "policy_version": "v7", "params": { "k_core": …, "k_glow": …, "sat_floor": …, "min_core_area_px": … },
    "background": {"median_rgb": […], "mad": …}, "timing_ms": …
  },
  "core_mask": {"rle_path": "masks/<ref>.rle.json", "pixel_count": …,
                 "bbox_px": […], "bbox_wall_norm": […], "centroid_wall_norm": […]},
  "components": [{
    "component_id": "c0", "class": "dot|closed_stroke|open_stroke",
    "area_px": …, "bbox_px": […], "bbox_wall_norm": […],
    "out_of_box_geometry": false, "fixture_assignment": "contained|nearest|ambiguous"
  }],
  "polylines": [{
    "polyline_id": "p0", "component_id": "c0",
    "geometry_kind": "closed_centerline|open_centerline|dot_anchor",
    "closed": true, "ordered": true,
    "points_px": [[x,y],…], "points_wall_norm": [[x,y],…], "point_count": …
  }],
  "topology_summary": {"dots": 1, "closed_strokes": 4, "open_strokes": 0},   // diagnostic only
  "metrics": {                                  // §15 definitions
    "core_precision": 0.0, "core_recall": 0.0, "halo_spill": 0.0,
    "components_detected": 0, "components_vectorized": 0,
    "vector_fit_residual_px_p95": 0.0
  },
  "status": "authority|provisional|quarantined",
  "authority_eligible": false,                  // true ⇒ status may be authority
  "status_reasons": ["…"],                      // §8 enumerated reasons; empty for authority
  "human_review": {"verdict": "yes|no|pending", "date": null},
  "quality_flags": ["…"]
}
```

Per-DMX-bucket join (extends current bucket fields): `shape_ref`, `shape_authority`, `shape_status`, `shape_point_count`, `topology_summary`, `shape_quality_flags`, `shape_source_capture_path`, `shape_fallback_reason`, plus `bucket_alternates: [shape_ref…]` and `bucket_conflict: bool` (two authority records for one vector with normalized-mask IoU < 0.5 [ASSUMED threshold] ⇒ conflict flag, ranked-preferred wins, both retained).

### 7.8 Commands

```bash
# v7 smoke subset (selection unchanged)
python3 tools/shape_extract_v7.py --selection artifacts/renderer/pr-g1-shape-authority/shape_selection.json --limit 3
python3 tools/shape_extract_v7.py --all-selected            # 19-shape subset
python3 tools/shape_library_builder.py --extractor v7       # regenerate library + index join
python3 -m pytest tests/test_v7_*.py -q
```

### 7.9 Tests (PR-G1 scope)

- `test_v7_core_mask_synthetic.py` — synthetic strokes + gaussian halo: core mask excludes halo at all tested intensities.
- `test_v7_multi_component.py` — synthetic 4 squares + dot ⇒ 5 components, 4 closed loops + 1 anchor, no drops (kills F4).
- `test_v7_detection_domain.py` — figure at/beyond box edge is fully detected and normalized with |x|>1 preserved, `out_of_box_geometry` flagged (kills F1/F6).
- `test_v7_validation_two_sided.py` — §15 metric math on fixtures: shifted geometry fails precision; missing stroke fails recall; halo trace fails spill.
- `test_v7_no_truncation.py` — N open strokes in ⇒ N polylines out.
- `test_v7_determinism.py` — two runs byte-identical records (modulo timestamps).
- `test_v7_overlay_semantics.py` — contact sheet yellow pixels drawn only when `status == "authority"`; rejected/provisional rendered in non-yellow palette (§16).
- Real-media tests for the 3 named captures (skipif no local media): assert expected component counts and status transitions.
- Keep: schema test, coordinate test, `test_no_historical_pr_g1_inputs.py`, runtime shape-ref tests.

### 7.10 Acceptance criteria (PR-G1 done)

- All §7.9 tests pass locally with media; suite remains green (179 + new).
- On the 19-capture subset: **every record is authority, provisional, or quarantined with a correct machine-readable reason** — zero unexplained empties.
- On the 3 named captures: row-of-squares ⇒ ≥4 closed loops traced on the square outlines; dual-dot ⇒ exactly 2 anchors, authority; cue_002 ⇒ both-arc geometry detected with out-of-box preserved (authority or quarantined `fixture_assignment_ambiguous` — honest either way).
- Brandon reviews all subset contact sheets: **no sheet shows yellow off the laser core** (yellow drawn only for authority records); any "no" verdict on an authority record is a hard fail and auto-quarantines it.
- `authority_eligible=true` only via §15 gates; no AI invoked anywhere in the run.
- No mutation under `captures/**` or `data/fixture_model.json`; no visible renderer change (`_drawFan()` untouched); diagnostics unchanged except new status field pass-through.
- Implementation report with per-capture metric table + timing.

### 7.11 Explicit non-goals

Motion tracks; visible geometry changes; aerial projection; full-corpus batch (G1.5); canonical shape families; CH20–36; recapture requests; AI integration of any kind.

---

## 8. PR-G1.5 — Batch, Coverage, Quarantine, Staged Rollout

**Objective:** run v7 over progressively larger slices with hard gates between stages; produce coverage/quarantine reporting that makes "design scales to all usable wall still captures" checkable.

**Machinery:** multiprocessing worker pool; resumable by `shape_ref` (skip existing record with same policy version + still mtime); sharded `records/<NN>/` by hash prefix; batch summary appended to `manifest.json`.

**`coverage_report.json`:** per lane, per CH3 family, per phase, per phase6 cue: `{selected, extracted, authority, provisional, quarantined: {reason: count}}`; plus global counts and per-vector-bucket dedupe stats (8,324 rows → 2,051 duplicate vectors known from PR1 [CONFIRMED]).

**Enumerated quarantine reasons (closed vocabulary, extend only via spec change):**
`blank_still`, `low_contrast`, `fixture_assignment_ambiguous`, `core_recall_below_threshold`, `core_precision_below_threshold`, `halo_spill_above_threshold`, `vectorization_incomplete` (mask authority may still hold — record stays `provisional`), `multi_capture_conflict`, `geometry_clipped_low` (from analysis.json), `human_review_rejected`.

**Stages and gates** (thresholds [ASSUMED] — recalibrate after Stage B and record changes in the report):

| Stage | Scope | Pass gate to next stage |
|---|---|---|
| A | `--limit 1` (row-of-squares `sh1_21b9e82ef84b930b` source) | ≥4 closed loops on square outlines; precision ≥0.90, recall ≥0.80; Brandon yes |
| B | 5 named hard captures (A + dual-dot + cue_002 + CH01_220 line + one swirl/branched) | ≥4/5 authority or correctly-quarantined; **zero false authority** (Brandon "no" on an authority sheet = stage fail); runtime <5 s/capture |
| C | 19-capture current selection | ≥60% authority; 100% of authority sheets pass Brandon; re-run determinism (identical statuses); PR #1 merge gate |
| D | 175 phase6 cues | batch <30 min; coverage report; authority ≥70% of non-blank cues else publish failure-mode analysis before proceeding; Brandon reviews 20 stratified samples |
| E | full usable stills (~8k rows pre-dedupe) | resumable run completes; conflicts surfaced; coverage by family ≥ Stage D rates; Brandon reviews 30 stratified samples + every new failure-mode cluster |

**What blocks forward motion:** any false authority at any stage (hard stop, fix validator before resuming); coverage regression vs. previous stage; nondeterministic statuses.

---

## 9. PR-G2a — Wall-Space Static Playback + wallDebug

**Objective:** render T0 static authority in wall space behind `?wallDebug=1`, side-by-side with the source still, proving authority vs. fallback visually. Default view unchanged.

- Wall canvas: per fixture, draw the calibration box frame; render authority geometry (vectors; mask fallback when `vectorization_incomplete`) in its true normalized position/scale — a dot stays small, an off-center line stays off-center (anti-patterns from PR-G1 spec §8 still apply).
- DMX selection: exact vector bucket → `shape_ref`; no shape ⇒ wall panel explicitly renders "NO CAPTURE AUTHORITY — decoder fallback" and (optionally, clearly labeled magenta) the decoder's wall-equivalent guess. Never draw fallback in the authority color (§16).
- Side-by-side: left = still (cropped to box, toggle full ROI), right = wall engine output; footer = `shape_ref`, status, metrics, tier.
- DMX residual: **not in G2a** (G2b); static authority renders as captured even if live CH5/6/7 differ — the delta is listed in the panel as `residual_pending`.
- Tests: JS render test (node, headless canvas stub) asserting geometry placement math; pytest for the snapshot payload fields (`shape_status`, `wall_debug` block, refs only — no polylines in SSE; fetch geometry via new `GET /artifacts/shape/<ref>` route with immutable caching, consistent with PR-H4 direction).
- Acceptance: Brandon loads 5 authority cues + 2 fallback cues; wall view matches stills (yes/no per cue); default aerial view byte-identical behavior.

## 10. PR-G1b — Motion Shape Tracks (capture clips)

**Objective:** wall-figure motion over time from `motion_analysis_60fps/` frames (320 px wide [CONFIRMED from plan §1]; re-extract from `video.mp4` only when frames missing).

- **Reuse v7 extraction at reduced resolution:** per frame, core mask + components with relaxed `min_core_area` (scale thresholds by resolution ratio [ASSUMED]). Per-frame full vectorization is *not* required.
- **Track representation (mask-anchored, transform-first):** per frame, per fixture: `centroid_wall_norm`, `bbox_wall_norm`, area, component count; per-component correspondence to the still-authority components by nearest-centroid + class (Hungarian matching at N≤8 components [ASSUMED]); keyframe core-mask RLE every K frames (K≈3, PR-H4 codec).
- **Deformation model:** frame-to-frame per-component similarity transform (translate/scale/rotate) applied to still-authority geometry; residual shape change beyond transform tolerance ⇒ keyframe mask playback for that span, flag `nonrigid_motion`.
- **Temporal alignment:** loop period from autocorrelation of centroid/area series (Nyquist cap at fps/2); `phase_anchor_frame` = max-displacement frame. Reconcile with `analysis.json` `loop_duration_estimate` (PR-H1 rules apply early: track wins at confidence ≥0.6 with mismatch >15%, flag `analysis_loop_mismatch`).
- **DMX residual relationship:** track stores the *captured* vector; playback-time deltas are G2b's job. Tracks never bake in residuals.
- **Confidence/quarantine:** `track_confidence` from (frame coverage %, correspondence stability, period confidence); quarantine reasons `track_frames_missing`, `correspondence_unstable`, `blank_clip`, `strobe_only_clip` (brightness gates, no geometry motion — degenerate single-keyframe track is valid for `motion_type: static`).
- **What PR-G1 must preserve now for G1b (already in §7):** component decomposition with stable ids, mask centroids/bboxes per component, px↔wall transforms, RLE codec.
- Artifacts: `artifacts/renderer/motion_tracks_v2/` mirroring §7.5 layout; index fields `motion_track_ref`, `motion_track_status`, `motion_track_frames`, `motion_rate_source`.
- Acceptance (plan §6 kept): `cue_023_green_solid_sinewaves` periodic deformation in wallDebug beside `video.mp4` scrub; CH19 sweeps correlate with `loop_duration_estimate` within labeled tolerance; static captures degenerate to single keyframe.

## 11. PR-G2b — Motion Playback + DMX Modifier Residual

- Playback at `renderTime`: sample track (loop when periodic ∧ confidence ≥0.5), interpolate transforms between frames/keyframes; apply to still authority geometry.
- Residual order (document in code): captured-vector baseline → size (CH5) → position (CH6/7) → rotation (CH12–14) → motion overlays — only for channels whose live value ≠ captured value; each applied residual emits `residual_channels` + per-parameter tier downgrade to `MEASURED_PARAM`/`APPROXIMATE`.
- No track ⇒ `motion_type`-gated scalar oscillator fallback (PR-C semantics), labeled `APPROXIMATE`, warning `motion_track_missing`; bypassing an existing track is a test failure (`motion_track_bypassed`).
- wallDebug gains scrub + capture-frame strip comparison (the G4 item #4 harness, landed here where it's first needed).

## 12. PR-G3 — Aerial Beam/Haze Projection

**Pose model** [CONFIRMED inputs, APPROXIMATE values]: wall plane from `analysis_geometry` boxes + px_per_inch (10.5185); fixture origins from `setup_geometry`: wall distance ≈ 6′1″, fixture spacing 30.5″ center-to-center, **two apertures per fixture 5″ apart producing mirrored images**, aperture exit 2″×1.5″, height "7–9 ft adjustable" [UNKNOWN exact → expose as a labeled scene parameter with default + on-screen `APPROXIMATE_POSE` badge].

- **Wall hit → beam:** sample wall points along authority geometry (arc-length sampling, density budget per figure [ASSUMED start: 64 samples/figure]); each sample back-projects to a 3D ray from the aperture origin; draw the segment aperture→wall in screen space.
- **Beam geometry:** straight rays only (plan §3.3 kept); wave/sweep = wall-point motion from tracks, never curved beams; mirrored-aperture pairing renders both apertures per fixture once G3 enables `image_right`/second-aperture rendering.
- **Brightness/color:** color + strobe from PR-C measured params (T0-adjacent); per-beam intensity ∝ dwell ≈ 1/(local scan arc length) [ASSUMED model, label APPROXIMATE]; core white boost preserved.
- **Haze/scattering:** additive blending, exponential falloff along ray `exp(-d/λ)` with λ a scene parameter; bloom via separable blur on the beam layer — all `APPROXIMATE`, never claimed capture-backed.
- **Persistence/trails:** temporal accumulation buffer with decay for fast scans [ASSUMED decay 80–120 ms].
- **Scan density:** beam count = wall sample count from authority geometry — **never** `density_beam_count_derived`/fan bins on the hit path (forensic B3 kept).
- **Safety/debug:** `?aerialDebug=1` shows aperture origins, wall plane grid, per-beam hit markers; fallback beams (no shape authority) render via `_drawFan()` and keep the `DECODER_FALLBACK_DRAWFAN` label.
- **From captures:** wall geometry, motion, color, strobe. **From fixture_model/decoder:** residual channel semantics. **From approximation:** haze, bloom, falloff, intensity profile (labeled).
- Acceptance: plan §6 PR-G3 smoke table kept verbatim (dual-dot ⇒ two beam pairs; CH3=32+pan ⇒ line translation; cue_001 strobe without sweep; CH19 wave straight rays; U-wave macro loop).

## 13. PR-G4 — Diagnostics, Coverage, Regression (consolidation)

- **Coverage dashboard:** render `coverage_report.json` + per-cue authority/fallback budget table in the diagnostics panel; SoundSwitch 184-cue view: per cue, tier per parameter.
- **Golden captures:** freeze Stage B/C records + 12-family representatives + 10 phase6 cues as golden JSON; regression test re-extracts and diffs metrics within ε; any status downgrade fails CI-local.
- **Runtime proof of authority:** snapshot field `authority_proof = {shape_ref, status, record_sha}` surfaced in UI; test asserts a capture-hit path with `shape_ref` never calls `_patternShape()` (plan G4 item #1 kept).
- **Silent-fallback tripwires:** test that `shape_authority=false ⇒ visible_geometry_source != CAPTURE*`; test that fixture_model-composed geometry can never set `shape_authority`; per-cue fallback budgets (plan G4 item #5) enforced on the smoke cue list.
- **Quarantine stability:** golden quarantined captures assert stable reasons across runs/versions (intentional changes update goldens explicitly).

---

## 14. Extraction Strategy (decision record)

### 14.1 Why v1–v6 failed (root causes, §5.1)

Not image quality (cores are visibly crisp [CONFIRMED]); not topology modeling per se; the chain was: **glow-flooded support masks (F2) → vectorizers structurally limited to one path (F4) → scorer validating against the contaminated support (F3/F5) → patch loop adding constants per failure**. Validation and authority representation were entangled: there was no clean target to validate against. Mask-first separates them.

### 14.2 Decisions

| Question | Decision |
|---|---|
| Gemini + CV refinement | **Demote to experimental/offline.** Keep code quarantined; the deterministic spatial-gate/strict-core helpers may be reused by v7 validation. |
| Return to deterministic non-AI-first extraction? | **Yes — v7 is the critical path.** Failure of v1–v6 is explained by specific fixable defects, not by deterministic CV being impossible. |
| Is `shape_library_builder` / `shape_extraction` salvageable? | Builder: **yes** (selection, artifacts, schema, index merge). `shape_extraction.py`: coordinate/ref helpers **yes**; extraction core **no — replace** (freeze as fallback until Stage C, then retire from builder path). |
| AI for quarantined/hard cases only? | **Allowed, offline, opt-in, cached, gitignored** — as a *hint generator* (topology suggestion, threshold seed) whose output must still pass v7 deterministic validation against the core mask, and which can never flip `authority_eligible` by itself. |
| AI optional/offline/cached/validated only? | **Yes — codified:** never imported by `tools/shape_extract_v7.py`, the builder default path, or anything under runtime; CI test greps for forbidden imports. |
| Replace current PR-G1 extraction architecture entirely? | **Yes** (new modules; no in-place patching of v6). |

### 14.3 AI usage policy (binding)

1. Never on the runtime path; never wired into authority by default; no AI invocation in any default command.
2. Inputs to AI must be the true crop with explicit canvas dimensions; any returned canvas mismatch is rescaled or rejected (fixes F9 if the experiment continues).
3. All AI outputs cached under gitignored paths ([CONFIRMED] `.gitignore:18-22`); never committed.
4. An AI-assisted record is marked `assist_source: ai_hint` and still requires v7 validation + human yes to reach `authority`; the hint itself is never stored as geometry.
5. Scale economics: 8k captures × API calls is not justified while deterministic extraction is unproven at Stage C–E; revisit only with a measured quarantine cluster that resists deterministic fixes.

---

## 15. Validation Strategy (authority gate)

**Definitions** (all in px, computed in detection-domain space):

- `CORE` = v7 core mask; `SKEL(CORE)` = its skeleton; `G` = sampled final geometry (polylines sampled at ≤1 px spacing; dot anchors as points; if vectorization incomplete, `G` = mask pixels).
- **core_precision** = |{g ∈ G : dist(g, CORE) ≤ r_p}| / |G|, r_p = 2 px [ASSUMED].
- **core_recall** = |{s ∈ SKEL(CORE) : dist(s, G) ≤ r_r}| / |SKEL(CORE)|, r_r = 3 px [ASSUMED].
- **halo_spill** = fraction of G farther than r_p from CORE but inside GLOW (distinguishes "traces halo" from "off-image garbage" — both fail, different reasons).
- **vector_fit_residual_px_p95** = 95th percentile of dist(g, CORE) over G.

**Authority gate (`authority_eligible = true`)**: core_precision ≥ 0.90 ∧ core_recall ≥ 0.80 ∧ halo_spill ≤ 0.05 ∧ components_vectorized = components_detected ∧ no `fixture_assignment_ambiguous` [ASSUMED thresholds; Stage B calibrates; changes are spec amendments].

**How each failure mode is rejected:**

| Failure | Killed by |
|---|---|
| Halo flood (magenta-loop case) | precision + halo_spill: halo pixels are not CORE |
| Shifted geometry (Gemini offset) | precision ≈ 0 off-core; plus canvas-dimension equality check before any conversion |
| Bounding-box false authority | a bbox trace crosses non-core interior ⇒ precision fails; recall of stroke skeleton fails |
| Raw AI coordinates as authority | AI path cannot set `authority_eligible` (§14.3); even in experiments, same gates apply |
| Color/topology mismatch | recall per color-component: every CORE component must be covered; missing component ⇒ recall < threshold |
| Debug/generated mask as authority | only the v7 CORE mask derived from the source still (sha-stamped) is a valid target; records store `geometry_source` + still path + extractor version; contact sheets regenerate from stored geometry |
| Merely "close enough" | p95 residual recorded; Brandon spot-check is a hard veto on authority |
| Silent runtime fallback | §3 gating + §13 tripwire tests |

**Human layer:** Brandon's yes/no remains the final veto on the smoke subset and stratified batch samples; a "no" auto-quarantines (`human_review_rejected`) and adds the capture to the golden regression set.

---

## 16. Debug Overlay Semantics (binding palette)

| Color | Meaning | May appear when |
|---|---|---|
| **Yellow** | **Final validated authority geometry only** (`status == authority`) | Authority records only — never for provisional/quarantined/candidate/AI output |
| Cyan | Calibration box / detection domain frames | Always (frame, not geometry) |
| Red | Source bbox / component bboxes | Debug only |
| Magenta | Rejected candidate geometry (any source) + rejection reason text | Debug sheets |
| Orange | Provisional geometry (mask authority pending vectorization or review) | Debug sheets |
| Blue/grey | Raw AI hints (experimental sheets only) | Quarantined experiments |

Rules: overlays drawn from **stored final geometry**, never from intermediate buffers; every sheet prints `status` + reasons; debug colors never imply authority; the v6 `render_overlay_image` behavior of drawing all candidates yellow (F11) is corrected in v7's sheet renderer; tests enforce (§7.9 `test_v7_overlay_semantics`).

---

## 17. Runtime Fallback Rules

| Situation | Behavior |
|---|---|
| Vector bucket has authority shape | T0: expose `shape_ref` + status; G2a+ renders it in wall view; G3+ projects it. `shape_authority: true` |
| Bucket has provisional/quarantined record | `shape_authority: false`, `shape_fallback_reason` = status reason; renderer uses T3/T4; wallDebug may show orange/magenta with explicit label |
| Partial authority (shape yes, motion no) | Per-parameter tiers split: shape T0, motion T4 + `motion_track_missing`; headline = MIN |
| No record for vector | `shape_fallback_reason: no_static_shape_for_vector` (current behavior kept) |
| Conflicting records | Preferred wins; `bucket_conflict: true` surfaced in diagnostics |
| Diagnostics proof | `authority_proof {shape_ref, status, record_sha}` + `visible_geometry_source` + `projection_source` (current fields kept); per-cue fallback budget table (G4) |
| Regression prevention | §13 tripwires: fixture_model/decoder can never set `shape_authority`; capture-hit with `shape_ref` never calls `_patternShape()`; budget tests on smoke cues |

---

## 18. Consolidated Test & Acceptance Matrix

Each row = required test (file exists by the listed PR; many exist today [CONFIRMED]):

| Concern | Test | PR |
|---|---|---|
| Valid stroke authority accepted | `test_v7_validation_two_sided.py` (synthetic pass case) + 3 real-media cases | G1 |
| Halo flood rejected | same file, halo-trace fixture ⇒ `halo_spill` fail | G1 |
| Shifted geometry rejected | shift fixture ⇒ precision fail | G1 |
| Bounding-box false authority rejected | bbox-trace fixture ⇒ precision+recall fail (extends existing `test_shape_polylines_not_bbox.py`) | G1 |
| Raw AI coordinates rejected | keep `tests/test_ai_shape_spatial_gate.py` + new forbidden-import test for v7/builder/runtime | G1 |
| Generated masks not committed | extend `test_ai_extraction_schema.py` gitignore checks to v7 batch dirs | G1.5 |
| No visible runtime change in G1 | existing `test_renderer_motionstate.js` + `test_app_diagnostics.js` unchanged-behavior assertions | G1 |
| Authority/fallback diagnostics | existing `test_capture_index_runtime_shape_refs.py`, `test_capture_index_runtime_respects_shape_authority_flag.py` (keep) + status field | G1 |
| Quarantine reason stability | golden quarantine fixtures, re-run diff | G1.5 |
| Batch coverage reporting | `test_coverage_report_schema.py` + counts reconcile with records | G1.5 |
| fixture_model fallback never promoted | tripwire: composed state cannot set `shape_authority` | G2a/G4 |
| Capture authority wins when available | wall engine selects T0 over T3/T4 given both | G2a |
| Partial authority behavior | shape-without-track renders static + `motion_track_missing` | G2b |
| Runtime fallback proof | `authority_proof` present and consistent with record sha | G4 |
| Motion track fidelity | track vs. `video.mp4` scrub harness + autocorr unit tests | G1b |
| Projection correctness | known pose fixture: wall point ↔ ray round-trip math | G3 |

---

## 19. Minimal Next Patch (the smallest serious step)

**Name:** PR-G1 v7 slice 1 — deterministic core-mask extractor + two-sided validation on 3 named captures.

**Exact files to ADD:**

- `tools/shape_core_mask.py` — background model, score maps, CORE/GLOW masks, components, fixture assignment (numpy + scikit-image).
- `tools/shape_validation_v2.py` — §15 metrics + authority gate + status assignment.
- `tools/shape_vectorize_v7.py` — per-component dot/loop/path vectorization (multi-polyline).
- `tools/shape_extract_v7.py` — CLI: selection-entry → record + mask RLE + contact sheet (v7 palette per §16).
- `tests/test_v7_core_mask_synthetic.py`, `tests/test_v7_multi_component.py`, `tests/test_v7_detection_domain.py`, `tests/test_v7_validation_two_sided.py`, `tests/test_v7_overlay_semantics.py`, `tests/test_v7_real_media_smoke.py` (skipif no media/no numpy).
- `tools-requirements.txt` (`numpy`, `scikit-image`).

**Exact files NOT to change:** `tools/shape_extraction.py` and all v6 modules (frozen), `tools/shape_library_builder.py` (wired to v7 only in slice 2), all `tools/ai_*` (and do **not** commit the currently-uncommitted `ai_shape_mask_tracer.py` WIP in this patch), `capture_index_runtime.py`, `webserver.py`, `static/**`, `captures/**`, `data/fixture_model.json`.

**Expected command:**

```bash
source .venv/bin/activate && pip install -r tools-requirements.txt
python3 tools/shape_extract_v7.py \
  --selection artifacts/renderer/pr-g1-shape-authority/shape_selection.json \
  --refs sh1_21b9e82ef84b930b sh1_41c84ad2ac1f458e sh1_adb58093da473f3e \
  --out artifacts/renderer/shape_authority_v2/
python3 -m pytest tests/test_v7_*.py -q
```

**Expected artifacts:** 3 records + 3 RLE masks + 3 contact sheets under `artifacts/renderer/shape_authority_v2/` (committed — they are small, deterministic, and non-AI), `manifest.json` with policy version + geometry sha.

**Expected outcomes / how to tell it worked:**

- Row-of-squares: `topology_summary.closed_strokes ≥ 4`, yellow traces the square outlines (Brandon yes), status `authority` if gates pass.
- Dual-dot: exactly 2 `dot_anchor` polylines on the dot cores; status `authority`.
- cue_002: both arcs detected in-domain; out-of-box wall coords preserved + flagged; status `authority` **or** `quarantined: fixture_assignment_ambiguous` — both acceptable; cropping-induced `fragment_only` must NOT recur.
- Failure/quarantine behavior: any gate miss yields `status: quarantined|provisional` with an enumerated reason and a non-yellow contact sheet — never an empty record, never yellow off-core.
- All new tests pass; existing 179 remain green; `git status` shows no changes outside the listed paths.

If slice 1 meets the Stage A/B bars, slice 2 wires the builder (`--extractor v7`), regenerates the 19-shape library + index join, and proceeds to Stage C as the PR #1 merge gate.

---

## Appendix A — Knowns / Assumptions / Unknowns ledger

- [CONFIRMED] 8,324 manifest rows; 175 phase6 folders; stills 1280×720; boxes/ROI values; setup geometry measurements (approximate by origin); 179 tests pass; v6 result 0/11/8 with 0 usable; all 19 shapes flagged `out_of_box`; no numpy/cv2 in venv; Gemini canvas mismatch in latest run; gitignore quarantine for AI outputs; runtime authority gating logic.
- [ASSUMED — tune in Stage A/B, record in report] k_core/k_glow/sat_floor, min areas, DP ε, r_p=2 px, r_r=3 px, gate thresholds (0.90/0.80/0.05), conflict IoU 0.5, sampling densities, perf targets, rollout percentage gates.
- [UNKNOWN — measure before relying] exact fixture height + aperture pose (PR-G3 parameterized); macro-look background statistics (F8 risk) — validate the per-tile background option in Stage B; phase6 blank/strobe-only fraction (affects Stage D authority-rate expectations); whether both-aperture mirror rendering is needed for wall fidelity pre-G3 (cue_002 suggests yes for some cues).
