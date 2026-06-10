# Opus Capture-Grounded Forensic Review — Renderer PR1 → PR5

**Date:** 2026-06-09
**Reviewer role:** Opus (independent review/audit agent)
**Trigger:** Orchestration policy update — Brandon visually validated that the renderer is still materially inaccurate.
**Verdict:** `BLOCK_MERGE` for the PR1–PR5 line as "capture-backed". **STOP PR6 (physical calibration).**
**Review type:** Capture-grounded (not generic architecture). Findings are tied to committed capture evidence.

---

## 0. Method and evidence cited

Reviewed source:
- `static/renderer.js`, `static/app.js`
- `webserver.py`, `fixture_model_adapter.py`, `capture_index_runtime.py`
- `tools/capture_index_builder.py`, `tools/build_capture_index.py`, `tests/*`

Reviewed evidence corpus:
- `captures/fixture_model/manifest.jsonl` (8324 rows)
- `captures/fixture_model/analysis_geometry.json`
- `captures/fixture_model/setup_geometry.json`
- `captures/fixture_model/checkpoint.json`
- `captures/fixture_model/**/analysis.json`, `**/metadata.json` (phase1/3/6 samples)
- `data/soundswitch_laser_cues.json` (184 cues)
- `data/fixture_model.json`, `data/fixture_model_schema.json`
- `artifacts/renderer/**/*` (PR1 index + report, PR3/4/5 reports + smoke grids)

Quantitative checks were re-run against the committed index `artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json` and the cue corpus; numbers below are reproductions, not report restatements.

---

## 1. Executive finding — the accuracy illusion

The capture corpus is wired in as **provenance metadata plus a thin motion-parameter overlay. It is not the renderer's geometry authority.** The visible beam image — pattern shape, beam count/density, dot scanning, fan layout, position placement, rotation, wave animation — is still produced by the legacy procedural decoder renderer (`decode_36ch` + hand-tuned `CAL` constants). The `EXACT_CAPTURE` label is then stamped on top of that synthetic image.

Concretely, every known SoundSwitch cue resolves to `EXACT_CAPTURE` at runtime:

- All **184/184** cues hit an exact CH1-19 vector in the index (phase 6 captured all 175 unique cue vectors).
- Yet the model's own validation reports **0 validated cues**: `data/fixture_model.json` → `validation.buckets = {pass: 0, higher_order: 0, firmware_locked: 0, unresolved: 293}`, `validation.cues_checked: 0`.

So the UI advertises authoritative "EXACT_CAPTURE" on a beam whose geometry no capture ever constrained, while the model concedes nothing has actually been validated. That gap is exactly what Brandon is seeing: cue matches, motion, scanning, beam animation, and beam count all look wrong because **none of them are driven by the captures — only relabeled by them.**

The data join (PR1) is the strongest part of the stack and is largely correct. The runtime authority wiring (PR2 → PR5) is where capture evidence stops being authoritative and becomes a sticker.

---

## 2. Answers to the 12 required questions

### Q1 — Are cue matches correct, or are display names / duplicate states / cue identity mappings wrong?
**Largely wrong / ambiguous.** Cue matching keys purely on the CH1-19 vector (`capture_index_runtime.py:57-73`) and returns *every* cue sharing that vector, sorted by name and truncated to 8 (`capture_index_runtime.py:79`, `:118`).

Evidence from `data/soundswitch_laser_cues.json` (184 cues):
- 184 cues collapse to **175 unique CH1-19 vectors**.
- **9 vectors map to ≥2 distinct cue names**, e.g. `31,0,28,0,0,128,141,...` → `["BASS HOUSE DROP 139bpm", "white wave gradient 140 bpm"]`; `62,0,28,...` → `["GREEN LASER (pl strobe)", "RAINBOW BEAM"]`. For these, the displayed "Cue Matches" is non-deterministic-by-intent and cannot identify the active cue.
- **6 duplicate cue names** exist (`"LIGHTSPEED EFFECT (COOL!)" x2`, several `... copy copy`).
- Names are unreliable as ground truth: cue `cue_001_off` / name `"OFF"` has `CH1=34` (on) and `CH11=255` (full strobe) (`metadata.json` for `phase6_cue_validation/cue_relevant/cue_001_off`). An "OFF" cue that is actually firing strobe will mislabel the renderer.
- Identity is reverse-derived from DMX, so cues that differ only outside CH1-19 (CH2 sound, CH20-36 second pattern) are indistinguishable by design.

**Classification: BLOCKER (identity ambiguity) + DIAGNOSTIC_GAP (no active-cue disambiguation) + HUMAN_VALIDATION (cue name trustworthiness).**

### Q2 — Is exact CH1-19 lookup actually renderer authority, or only metadata/provenance?
**Only metadata/provenance.** The render input is built from the decoder/composer shape; the lookup is attached as side-band fields:
- `static/app.js:138-149`: `sourceState = composed.length ? composed : decoded`; each render object is `{ ...fx, __capture_lookup, __provenance_label, __model_status, __model_confidence }`. The drawn geometry is `fx` (decoder/composer), the capture is appended.
- `webserver.py:90-104`: `compose_fixture_model(...)` builds `composed`; the lookup is written to `model["fixture_model"]["capture_lookup"]` only.
- `static/renderer.js:213-251`: `_primary()` / `_second()` read `pattern`, `size`, `position`, `scan`, `movement`, `color` from the decoder shape; `captureLookup` is carried as a label only.

The exact CH1-19 capture never sets beam geometry, count, or position. **Classification: BLOCKER.**

### Q3 — Is measured motion actually driving visible scan behavior, or only aim/fallback labels?
**Barely, and partly incorrectly.** Measured metrics are consumed only for (a) CH15/CH16 *speed-mode* sweep frequency/extent and (b) strobe Hz/duty, and only when `captureLookup.hit && layerKind==="primary"` (`renderer.js:302-330`, `:332-357`, `:374-384`).

Two problems, quantified against the cue set:
- **Direction is unusable.** 183/184 cue-hit captures have `motion_direction_confidence < 0.6` (only 1 ≥ 0.6); 112 are `unknown_from_numeric_analysis`. So `_directionSigns()` falls back to default `h=1,v=1` for essentially all cues and the renderer flags `measured_motion_direction_low_confidence`.
- **Strobe/loop conflation.** `_moveOffset()` (`renderer.js:344-356`) zeroes the sweep only for `motion_type === "static"`. For `strobe_gate`, `wave_deformation`, `pulse_zoom`, `color_chase` it still uses `loopHz = 1/loop_duration_estimate` as the *horizontal/vertical sweep frequency*. Of 77 cues with CH15/CH16 in speed mode, **49 are non-translational motion types with a nonzero loop** → bogus sweeps. Example: cue "OFF" `CH15=148`, `motion_type=strobe_gate`, `loop_duration=0.0667` → renderer pans the beam horizontally at 15 Hz (the strobe period rendered as motion).

So measured motion is mostly inert (direction) or actively wrong (loop conflation). **Classification: BLOCKER.**

### Q4 — Is dot scanning derived from capture evidence, or still decoder/manual approximation?
**Decoder/manual approximation.** `drawMode` is derived from `st.scan.mode` (decoded CH10) at `renderer.js:386-388`; the dot is a synthetic radial burst `_dotBurst()` (`renderer.js:748-758`). No CH10 capture metric (line/dot density) is read. The analysis corpus does not even expose a point/dot-density measurement to consume. **Classification: ACCURACY_DEBT (must be labeled) → BLOCKER if it stays under an EXACT_CAPTURE badge.**

### Q5 — Is beam animation derived from measured per-capture analysis, or still synthetic?
**Synthetic.** Wave deformation uses decoded CH19 with hand-tuned amplitude/rate (`renderer.js:627-640`); rotation/spin uses decoded CH12-14 + `CAL.rates` (`renderer.js:470-485`, `:596-601`); color cycling uses `CAL` rates (`renderer.js:515-536`). Per-capture `wave_deformation` / `smooth_rotation` / `loop_confidence` metrics are not used to drive the animation. **Classification: ACCURACY_DEBT → BLOCKER under EXACT_CAPTURE badge.**

### Q6 — Is beam count/density per look grounded in captured analysis, or guessed from decoded shape?
**Guessed.** `_patternShape()` (`renderer.js:542-552`) maps decoded CH3 group ranges to hard-coded `CAL.patternShape` families and adds `CH4 % 4`. The code comment states it plainly: *"CALIBRATED 2026-06-05 by eye on the real lasers … Approximate (exact shapes aren't in the DMX)."* `_drawFan()` derives `count` from `pat.n`, CH5 size, and zoom (`renderer.js:571-583`) — never from capture analysis. The corpus carries `area_range_frac`, `angle_range_deg`, `x_range`, `y_range`, `dominant_colors` — none feed beam count. **Classification: BLOCKER.**

### Q7 — Is geometry from `analysis_geometry.json` used correctly (ROI, aperture boxes, px_per_inch, wall conversion)?
**Used correctly at build time only; the renderer ignores it.**
- Build time (correct): `capture_index_builder.py:126-149` validates `analysis_roi` + `scale.px_per_inch` (10.5185); `:190-195` converts `x_range/y_range` px → inches and normalizes by ROI width/height.
- Two real defects:
  1. **Normalization base is wrong for a single fixture.** `x_norm = x_range_px / roi_width` uses the full ROI width (1280) while a single aperture box spans ~495–574 px (`analysis_geometry.json.boxes`). Per-fixture extents are therefore understated ~2–2.5×.
  2. **The renderer never reads any of it.** `static/renderer.js` contains no reference to `px_per_inch`, `analysis_roi`, `boxes`, `combined_bbox`, or wall coordinates. Source/aperture placement uses `CAL.geometry.fixGapFrac/apGapFrac` screen fractions (`renderer.js:564-566`, `:617-619`), unrelated to the measured `image_left`/`image_right` box positions. `px_per_inch` and `x_range_in` are computed and discarded. The only geometry that reaches the renderer is `x/y_range_norm_roi` as a sweep amplitude (`renderer.js:312-313`, `:350-351`).

**Classification: BLOCKER (renderer ignores measured geometry) + ACCURACY_DEBT (ROI normalization base).**

### Q8 — Are manifest rows joined to fresh per-capture `analysis.json`, not stale inline manifest analysis?
**Yes — this is correct.** `capture_index_builder.py:291-307` loads `<folder>/analysis.json` for all motion/strobe/geometry metrics; `_record_from_joined_row()` (`:230-251`) sources metrics from per-capture analysis. Manifest inline `analysis` is used only for the three context flags `recapture_pending` / `expected_blank` / `blank_zone_observed` (`:218-228`), and the report asserts `manifest_inline_analysis_used_as_analysis_authority: false`. Verified: manifest inline `analysis` keys differ from per-capture keys, and the builder does not read motion metrics from the manifest. **Classification: PASS.** (Residual: freshness of `analysis.json` vs the regenerated `analysis_geometry.json` is asserted by process, not stamped in each file — see DIAGNOSTIC_GAP D4.)

### Q9 — Are duplicate `test_id`s and duplicate CH1-19 vectors handled correctly?
**Handled, with one conflation caveat.**
- Duplicate `test_id`: `dedup_latest_test_id()` (`:104-123`) keeps latest by `(timestamp, __line_number)`. Report: 88 duplicate test_ids / 176 rows collapsed correctly.
- Duplicate vectors: `vector_buckets` ranked by `_rank_capture()` (`:167-178`) preferring `usable_evidence`, not-clipped, not-recapture-pending, `geometry_motion` track, `loop_confidence`, timestamp; `preferred_capture_id` chosen deterministically. 2051 duplicate vectors handled; geometry/color exposure-track pairs retained via `by_exposure_track`.
- **Caveat:** the vector key is CH1-19 only, so captures with identical CH1-19 but different phase/base context (and different CH20-36) collapse into one bucket; the "preferred" capture can come from a different phase than the cue context. Acceptable for a CH1-19-scoped model but should be surfaced. **Classification: PASS + DIAGNOSTIC_GAP (bucket cross-phase provenance).**

### Q10 — Are higher-order / channel-interaction failures hidden behind misleading EXACT_CAPTURE labels?
**Yes.** `lookup_exact_from_channels()` returns `provenance_label: "EXACT_CAPTURE"` on *any* vector match (`capture_index_runtime.py:101-119`), independent of whether that vector came from an isolated single-channel sweep (phase1) or a validated multi-channel cue, and independent of model validation. Consequences:
- All 184 cues → `EXACT_CAPTURE`, but `validation.pass = 0`, `validation.unresolved = 293`, `validation.cues_checked = 0` (`data/fixture_model.json`).
- 10 of the 184 cue-hit preferred captures have `usable_evidence = false` yet remain `EXACT_CAPTURE`.
- Index-wide: `usable_evidence_false = 763`, `recapture_pending_true = 212`, `geometry_clipped_low_true = 86` — all still labeled `EXACT_CAPTURE`, mitigated only by side-band warnings the badge does not reflect.

The label asserts evidentiary authority the pipeline cannot back. **Classification: BLOCKER.**

### Q11 — Does the renderer overclaim accuracy when dense / higher-order validation is missing?
**Yes.** Dense and higher-order validation are absent:
- `checkpoint.json`: `captured_exact_vectors_source = "phase0_record_dense_root_absent"`; the 118 dense rows are *cited from prior provenance*, raw root gone (`FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md`).
- `fixture_model.json.provenance.contaminated_physical_run_deleted = true`; `validation.unresolved = 293`, `pass = 0`.
- The adapter does flag this (`fixture_model_adapter.py:94-99` coverage `dense_validation: "missing"`, `higher_order: "pending"`; `:181` unsupported `["higher_order_validation_pending","118_dense_missing"]`), and `model_status` is downgraded to `measured_estimated` confidence in the badge.
- **But** the per-fixture `EXACT_CAPTURE` capture badge (app.js diagnostics "Capture Provenance") visually outranks the amber confidence note, so the dominant signal still reads "exact." The headline overclaims relative to `validation.pass = 0`. **Classification: BLOCKER (label hierarchy) + ACCURACY_DEBT.**

### Q12 — What concrete renderer changes are needed before PR6 physical calibration?
See §4 (Recommended PR sequence). In short: demote `EXACT_CAPTURE` to a *measured-but-unvalidated* tier gated on `validation`, fix the strobe/loop motion conflation, ground beam count/shape and dot scanning in capture analysis (or honestly label them decoder-approximate and strip the exact badge), and have the renderer consume `analysis_geometry.json` for aperture placement + extent normalization. Physical calibration (PR6) cannot calibrate a pipeline whose visible geometry is not yet capture-driven.

---

## 3. Cross-cutting governance finding (process BLOCKER)

The orchestration guarantee in `docs/RENDERER_AGENT_ORCHESTRATION.md` (§2, §7, §8) — *"No implementation PR may merge without … Opus review of the actual diff"* and a committed `artifacts/renderer/<pr-name>/opus_review.md` — was not met:

- **No `opus_review.md` exists for any PR** (`artifacts/renderer/*/` contains implementation reports and smoke grids only).
- PR1–PR5 are **5 sequential commits on a single branch** `renderer-capture-index-pr1` (`61b5b9f6 … 4afd0aae`); there were no separate PR branches/diffs to independently review. The branch name does not even match PR2–PR5.
- `docs/RENDERER_PR_STATUS.md` self-certifies *"Opus review: completed (APPROVE_WITH_MINOR_FIXES)"* with no supporting artifact — i.e., the build agent graded its own homework, the exact failure mode the orchestration guide warned about.

This is why an inaccurate "capture-backed" renderer reached a PR6-ready state. **Classification: BLOCKER (review gate was never actually enforced).**

---

## 4. Blocker Report (classified)

### BLOCKER — must fix before PR6
- **B1.** Capture lookup is metadata only; decoder/`CAL` constants still own all visible geometry (Q2). `static/app.js:138-149`, `webserver.py:90-104`, `static/renderer.js:213-251`.
- **B2.** `EXACT_CAPTURE` is applied to any vector match regardless of model validation, evidence quality, or interaction order (Q10/Q11). `capture_index_runtime.py:101-119`; `fixture_model.json.validation.pass = 0`.
- **B3.** Beam count/density guessed from decoded CH3/CH4, not capture analysis (Q6). `static/renderer.js:542-552`, `:571-583`.
- **B4.** Strobe/loop motion conflation: non-translational `motion_type` with nonzero `loop_duration_estimate` drives a bogus CH15/CH16 sweep (49/77 speed-mode cues) (Q3). `static/renderer.js:344-356`.
- **B5.** Renderer ignores `analysis_geometry.json` (aperture boxes, ROI, px_per_inch, wall conversion); source/aperture placement is hand-tuned screen fractions (Q7). `static/renderer.js:564-566`, `:617-619`.
- **B6.** Cue identity ambiguity: 9 vectors map to multiple distinct cue names; names unreliable ("OFF" = strobe on) (Q1). `data/soundswitch_laser_cues.json`, `capture_index_runtime.py:57-73`.
- **B7.** Governance: no committed Opus review per PR; PR1–PR5 self-certified on one branch (§3).

### ACCURACY_DEBT — acceptable only if clearly labeled (and badge demoted accordingly)
- **A1.** Dot scanning is synthetic from decoded CH10, not capture-derived (Q4). `static/renderer.js:386-388`, `:748-758`.
- **A2.** Beam animation (waves/rotation/color cycle) is synthetic, not from measured wave/rotation metrics (Q5). `static/renderer.js:470-485`, `:515-536`, `:627-640`.
- **A3.** ROI normalization divides per-fixture extent by full ROI width instead of per-aperture width — extents understated ~2–2.5× (Q7). `tools/capture_index_builder.py:190-195`.
- **A4.** Second pattern (CH20-36) and CH2 remain decoder-driven — in-scope per plan, but must stay explicitly warned and never badge `EXACT_CAPTURE`.
- **A5.** 763 `usable_evidence=false` / 212 `recapture_pending=true` / 86 `geometry_clipped_low=true` captures remain selectable as preferred when no better capture exists.

### DIAGNOSTIC_GAP — needs better visibility
- **D1.** No "active cue" disambiguation when one vector matches multiple cues (Q1).
- **D2.** `EXACT_CAPTURE` badge visually outranks the `measured_estimated`/unsupported confidence; the UI should fuse capture provenance with `validation` state so the badge cannot read "exact" while `validation.pass = 0` (Q11).
- **D3.** Motion provenance does not distinguish "measured but conflated/low-confidence" from "measured and trustworthy" beyond a single warning string (Q3).
- **D4.** Per-capture `analysis.json` does not stamp the `analysis_geometry.json` version/timestamp it was computed against, so freshness after geometry regeneration is process-asserted, not provable (Q8).
- **D5.** Vector buckets can mix phases/CH20-36 contexts under one CH1-19 key with no surfaced provenance (Q9).

### HUMAN_VALIDATION — requires Brandon's eyes or the physical fixture
- **H1.** Cue name trustworthiness (e.g., "OFF" firing strobe) — confirm whether SoundSwitch names are reliable labels or arbitrary keys (Q1).
- **H2.** Motion direction for the 183/184 low-confidence cues — numeric regression cannot resolve direction; needs visual review of representative clips (Q3).
- **H3.** Per-look beam count/shape ground truth — physical/visual confirmation of representative CH3/CH4 looks before count can be modeled (Q6).
- **H4.** Whether the dense (118-row) and higher-order validation must be recaptured before any "exact"/"validated" claim is permitted (Q10/Q11).

---

## 5. Recommended next PR sequence (replaces the jump to PR6)

PR6 physical calibration is **suspended**. Calibrating a rig against a renderer whose geometry is not capture-driven would bake in the current inaccuracy. Proposed re-sequencing, each gated by a committed capture-grounded `opus_review.md`:

1. **PR-A — Provenance honesty (label correctness).**
   Demote `EXACT_CAPTURE` to a tier that fuses `fixture_model.json.validation` + per-capture quality. A vector match with `validation.pass = 0` must render as `MEASURED_UNVALIDATED` (or similar), never `EXACT_CAPTURE`. Fixes B2, B7-adjacent, D2. Tests: label-tier unit tests against quality/validation matrices.

2. **PR-B — Cue identity correctness.**
   Disambiguate multi-name vectors; expose all colliding names + a "cannot uniquely identify" flag; stop trusting cue names as truth. Fixes B6, D1; flags H1.

3. **PR-C — Motion truth.**
   Fix the strobe/loop conflation (only translational `motion_type` may drive CH15/CH16 sweeps); separate strobe Hz from movement loop; suppress measured direction below confidence threshold instead of defaulting to a sign. Fixes B4, D3; flags H2.

4. **PR-D — Capture-driven geometry & density.**
   Make the renderer consume `analysis_geometry.json` for aperture placement and per-aperture extent normalization; ground beam count/extent in capture analysis or strip the exact badge from guessed shapes. Fixes B1, B3, B5, A3; flags H3.

5. **PR-E — Diagnostic completeness.**
   Stamp geometry version into per-capture analysis provenance; surface bucket cross-phase provenance; visualize measured-vs-decoder source per visible parameter. Fixes D4, D5.

6. **PR-F (was PR6) — Physical calibration / hardening.**
   Only after PR-A…PR-E land and Brandon validates representative cues (H1–H4). Resume physical calibration.

**Process gate (effective immediately):** every renderer PR henceforth requires a committed capture-grounded `artifacts/renderer/<pr-name>/opus_review.md` that answers the relevant subset of the 12 questions against the cited corpus, on its own branch/diff, before acceptance. No self-certification in `RENDERER_PR_STATUS.md`.

---

## 6. What is genuinely good (keep)

- PR1 index build is sound: deterministic dedup, per-capture analysis as authority (not manifest inline), quality gates encoded, exposure-track pairing, deterministic preferred selection (Q8, Q9). Keep it.
- The warning/diagnostic plumbing (PR3/PR4) already computes most of the truth signals; the failure is that the headline `EXACT_CAPTURE` badge and the decoder-driven geometry override them. The fix is mostly authority/labeling and motion correctness, not a rewrite.
- No guardrail violations detected: no `fixture_model.json`/capture mutation, no WebGL, `second_pattern` preserved, source origins unmoved.
