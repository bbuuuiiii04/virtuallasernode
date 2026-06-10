# Renderer Accuracy Plan V1 — Capture-Driven Authority (PR-A → PR-E)

> **Status (2026-06-09):** PR-A / PR-B / PR-C / PR-E sections remain active.  
> **PR-D is superseded** by `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` (do not merge fan geometry PR-D).  
> **Primary plan:** wall figure → rig projection → aerial beams.  
> **Doc index:** `docs/RENDERER_DOCS_INDEX.md`

**Date:** 2026-06-09
**Owner (orchestrator + checkpoint reviewer):** Opus (Claude 4.8)
**Implementer:** Codex (gpt-5.3-codex)
**Routine reviewer:** gpt-5.5-high
**Checkpoint reviewer (sparingly, big/architectural changes only):** Opus
**Authority for this plan:** `artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md`

This plan supersedes the jump to PR6. PR6 (physical calibration) stays SUSPENDED until PR-A…PR-E land.

---

## 0. Mission

Make committed capture evidence the **render authority** for visible laser behavior — color, motion, density, spread, strobe, geometry — instead of the legacy `decode_36ch` + `CAL` approximations. Today captures are attached as provenance metadata only (`renderer_contract = decoded_shape_composed_values`); the beam image is still synthetic.

## 1. NON-NEGOTIABLES (read first)

1. **DO NOT trust SoundSwitch cue names, tags, `is_motion`, or `calibration_type` as ground truth.** The ONLY trusted field from `data/soundswitch_laser_cues.json` is `dmx` (the CH1-19 vector), used solely to enumerate which captured vectors correspond to operator cues. Laser behavior is derived from **capture analysis** of that vector, never from its name. Cue names are display-only "aliases" and must be labeled non-authoritative.
   - Concretely: no renderer/runtime code may branch on `cue_name`, `tags`, `is_motion`, or `calibration_type`.
   - Example of the trap: cue `cue_001_off` is named "OFF" but its DMX has `CH1=34` (on) + `CH11=255` (full strobe). The renderer must show a strobing beam (from capture), not "off" (from the name).
2. Do NOT mutate `data/fixture_model.json` or any capture data under `captures/`.
3. Do NOT convert to WebGL. Keep the 2D canvas renderer.
4. Do NOT remove `second_pattern` rendering; keep it decoder-driven + warning-labeled (CH20-36 is out of capture scope).
5. Do NOT move fixture/aperture source origins arbitrarily; in PR-D origins move ONLY to measured `analysis_geometry.json` box positions, documented.
6. Do NOT visual-polish; correctness before polish. No new glow/tint passes.
7. Never emit a "render authority"/"validated" tier unless `data/fixture_model.json.validation` backs that vector (today `validation.pass = 0`, so the strongest currently truthful tier is "measured, unvalidated").
8. Every PR ships: an implementation report, tests/smoke, and a committed review (gpt-5.5 routine; Opus for checkpoints). No self-certification.

---

## 2. Current architecture truth (what we are replacing)

- `webserver.py` decodes 36ch → `compose_fixture_model()` (decoder shape + gate masks) → attaches `capture_lookup` to `fixture_model.capture_lookup`.
- `static/app.js:138-149` builds render state = composed/decoded shape + `__capture_lookup`/`__provenance_label` side-band.
- `static/renderer.js` draws from the decoder shape; capture metrics only adjust CH15/16 *speed-mode* sweep + strobe; everything else is `CAL`-tuned.
- `capture_index_runtime.py:101-119` stamps `EXACT_CAPTURE` on any vector match regardless of validation/quality.

## 3. Target architecture — per-parameter authority resolver

Replace the per-fixture single label with a **per-parameter authority resolver**. For each visible render parameter, pick the highest tier whose evidence exists and is permitted, and emit the tier alongside the value.

### 3.1 Provenance tiers (replaces flat `EXACT_CAPTURE`)
```
Per PARAMETER (color, motion, spread, count, position, strobe, dots):
  EXACT_CAPTURE_RENDER_AUTHORITY  measured value applied AND validation backs this vector
  MEASURED_PARAM                  measured value applied, validation pending  (amber)
  MODEL_COMPOSED                  value from fixture_model.json composition
  DECODER_FALLBACK                decode_36ch + CAL                            (red)

Vector-level (cue/lookup):
  EXACT_VECTOR_MATCH              vector found in index (provenance only; NOT authority)
  NO_VECTOR_MATCH                 fell back to model/decoder

Fixture headline badge = MIN tier across visible parameters.
(So one measured strobe cannot make the whole tile read "EXACT".)
"EXACT_CAPTURE_METADATA_ONLY" is the ABSENCE of any *_RENDER_AUTHORITY / MEASURED_PARAM
parameter, i.e. matched-but-nothing-applied.
```

### 3.2 Capture-derived behavior map (THE CORE)

Measured fields available per vector (committed `analysis.json`, fixed 29-field schema):
`motion_type, motion_direction, motion_direction_confidence, motion_signed_slope_per_second,`
`loop_duration_estimate, loop_confidence, full_loop_captured, periodic_motion,`
`strobe_frequency_hz, duty_cycle, strobe_crossings, x_range(px), y_range(px),`
`angle_range_deg, area_range_frac, brightness_cv, dominant_colors[], usable_evidence, geometry_clipped_low`.
Geometry (`analysis_geometry.json`): `scale.px_per_inch=10.5185`, `analysis_roi`, `boxes[]` (per-aperture bbox `image_left`/`image_right`).

| Render param | Measured source | Derivation | Tier when measured | Fallback |
|---|---|---|---|---|
| **Color** | `dominant_colors[]` | name→RGB palette (see 3.3); blend up to 2 | MEASURED_PARAM | decoder `_color` |
| **Strobe on/Hz/duty** | `strobe_frequency_hz`,`duty_cycle` | square gate (already correct) | MEASURED_PARAM | `CAL.rates.strobeHz`×CH11 |
| **Motion model** | `motion_type` | pick model (see 3.4); NOT from CH15/16 alone | MEASURED_PARAM | decoder sine |
| **Motion rate** | `loop_duration_estimate`+`periodic_motion`+`loop_confidence` | rateHz=1/loop only if periodic & loop_confidence≥0.5 | MEASURED_PARAM | `_sweepHz(CH)` |
| **Direction** | `motion_direction`+`motion_direction_confidence` | apply sign ONLY if confidence≥0.6 AND concrete label | MEASURED_PARAM | unsigned (no default sign) |
| **Sweep extent** | `x_range`,`y_range`,`px_per_inch`,per-aperture box width | px→inch→normalize by aperture box width/height (PR-D) | MEASURED_PARAM | clamp 1.0 |
| **Fan angular spread** | `angle_range_deg` | radians = deg·π/180 (PR-D) | MEASURED_PARAM | `CAL.geometry.spreadAng*` |
| **Beam count/density** | `area_range_frac`+`angle_range_deg`(+analyzer count, PR-D) | DERIVED bins; label DERIVED not MEASURED until analyzer count exists | DERIVED (sub-tier of MEASURED_PARAM, flagged) | `_patternShape` |
| **Aperture origins** | `boxes[].bbox` centroids + gap | map measured box centers→canvas (PR-D) | MEASURED_PARAM | `CAL.geometry.*Frac` |
| **Dot vs line scan** | (none in numeric corpus) | keep decoder CH10; label DECODER_FALLBACK; do NOT badge measured | DECODER_FALLBACK | decoder `_scan` |
| **Position/aim centroid** | (extent only, no centroid in corpus) | keep decoder CH6/CH7; label DECODER_FALLBACK | DECODER_FALLBACK | decoder `_position` |

### 3.3 dominant_colors → RGB palette (canonical)
```
red [255,40,40]  green [40,255,70]  blue [60,90,255]  cyan [40,230,230]
magenta [255,60,220]  yellow [255,230,60]  white [255,255,255]
orange [255,150,40]  purple [150,60,255]  pink [255,120,200]
```
- 1 color → solid. 2 colors → per-beam alternation or 2-stop gradient across the fan. Unknown name → DECODER_FALLBACK color + warning.

### 3.4 motion_type → motion model (fixes the strobe/loop conflation)
```
static            -> no translation, no rotation, no wave
horizontal_sweep  -> translate along H; rate from loop; extent from x_range; direction-gated
vertical_sweep    -> translate along V; rate from loop; extent from y_range; direction-gated
smooth_rotation   -> rotate fan; rate from loop; direction-gated (cw/ccw if confident)
wave_deformation  -> wave deform; rate from loop; amplitude from angle_range_deg/area
pulse_zoom        -> zoom pulse; rate from loop; amplitude from area_range_frac
color_chase       -> animate color only; rate from loop; NO translation
strobe_gate       -> strobe only; NO translation (THIS is the OFF-cue bug fix)
unknown           -> DECODER_FALLBACK motion + warning
```
Rule: translation is driven by `motion_type`, NOT by "CH15/CH16 > 127". CH15/CH16 may still gate engagement, but the *kind* of motion comes from the capture. A `strobe_gate`/`wave_deformation`/`pulse_zoom`/`color_chase` cue must NOT produce a horizontal/vertical beam sweep.

---

## 4. PR breakdown (A → E)

Each PR: own scope, tests, report, committed review. Branch per phase.

### PR-A — Provenance honesty (authority resolver + tier split + validation gate)  [routine: gpt-5.5]
- Add per-parameter authority resolver + tier vocabulary (3.1).
- `capture_index_runtime.py`: return `vector_match`, `validation_backed` (read `fixture_model.json.validation`; currently always false), and stop returning flat `EXACT_CAPTURE`. Emit `EXACT_VECTOR_MATCH` for provenance.
- `renderer.js`: compute `headlineTier = min(param tiers)`; emit per-param tiers in MotionState; remove `EXACT_CAPTURE` headline.
- `app.js`: diagnostics show "Headline Authority" (RED unless `*_RENDER_AUTHORITY`) + per-parameter tier table.
- No beam-geometry change.
- Tests: tier-resolution unit tests; renderer headline-min test.
- Accept: no parameter reads as `EXACT_CAPTURE_RENDER_AUTHORITY` while `validation.pass=0`; headline downgrades if any param is decoder.

### PR-B — Cue identity / aliases (no name trust)  [routine: gpt-5.5]
- `capture_index_runtime.py`: return `cue_aliases:[{cue_id,cue_name}]` + `cue_identity_resolved` (true only if exactly one distinct name) + `cue_alias_count`. Keep `dmx` as the only trusted cue field.
- `app.js`: render "Cue Aliases (N): …" + "Identity resolved: <bool>"; never present a single confident cue.
- Tests: multi-name vector (e.g. the 9 known collisions) → `cue_identity_resolved=false`, `len(cue_aliases)>1`.
- Accept: no runtime/renderer code branches on `cue_name`/`tags`/`is_motion`/`calibration_type` (grep-clean).

### PR-C — Motion truth + measured color  [routine: gpt-5.5]
- Implement 3.4 motion-type model + 3.3 color from `dominant_colors`.
- Direction applied only when `motion_direction_confidence ≥ 0.6` and concrete; otherwise unsigned (no default sign).
- Rate from `loop_duration_estimate` only when `periodic_motion` and `loop_confidence ≥ 0.5`.
- Keep measured strobe (already correct). `strobe_gate`/non-translational types must not sweep.
- Add a **capture-aware smoke harness** (`calib/render_grid_capture.py`) that feeds render state shaped like `app.js` (composed + `__capture_lookup` from the real index + cues) so motion/color are exercised; reuse `LaserRenderer`.
- Tests: `tests/test_renderer_motionstate.js` — strobe_gate cue with CH15>127 produces zero translational offset; low-confidence direction → unsigned; color from dominant_colors applied; headline tier reflects measured color+strobe but decoder count.
- Accept: the `cue_001_off` "OFF" case renders blue/cyan, strobing, NO horizontal sweep.

### PR-D — Capture-driven geometry + density  [SUPERSEDED — do not merge]

> **Superseded 2026-06-09** by `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` PR-G3.  
> Fan spread/count/density from scalars is the wrong model. Salvage: `analysis_geometry` SSE wiring, aperture box helpers, `x_range_norm_aperture` for motion extents.  
> Opus review of PR-D is cancelled; review PR-G2/G3 instead.

**Implementation note (2026-06-09):** PR-D was implemented by **Composer 2.5** (Codex API limit
fallback). It is **NOT merge-ready**. Requires **extensive strict review** by Opus or an
equivalent high-capability subagent before acceptance. Routine gpt-5.5 review is insufficient.
See `artifacts/renderer/renderer-accuracy-pr-d/implementation_report.md` and
`docs/RENDERER_AGENT_ORCHESTRATION.md` §12b.

- Renderer consumes `analysis_geometry.json`: aperture origins from `boxes[].bbox` centroids; per-aperture extent normalization (replace full-ROI/screen-fraction math).
- Fan angular spread from `angle_range_deg`.
- Density: derive beam-count bins from `area_range_frac`+`angle_range_deg`, labeled DERIVED (not MEASURED) until an analyzer count field exists. Add `area_range_frac`→occupancy mapping.
- Add (if local raw video available) an analyzer pass emitting `beam_blob_count`/`contour_count` into a NEW index field (do NOT mutate existing capture data; write to the index artifact only). If raw media absent, mark `density_evidence: inferred` and flag HUMAN_VALIDATION.
- Tests: geometry-conversion unit tests; smoke grid before/after.
- Accept: aperture placement matches measured box geometry; spread reflects `angle_range_deg`; density labeled honestly.

### PR-E — Diagnostics completeness + provenance UX + harness  [routine: gpt-5.5]

> **Sequencing (2026-06-09):** Run **after PR-G4** (wall→aerial integration), not before PR-G. Diagnostics must reflect shape/projection authority tiers.

- Per-parameter source overlay; geometry-version stamp surfaced; bucket cross-phase provenance; alias UI polish; capture-aware harness as the default smoke path.
- Tests: diagnostics snapshot tests.

---

## 5. THIS DEPLOYMENT — Phase 1 = PR-A + PR-B + PR-C (+ capture-aware harness)

Codex implements PR-A, PR-B, PR-C together as one cohesive "runtime honesty + motion truth" phase (they share the authority/label/MotionState core and contain no beam-geometry rewrite). PR-D and PR-E are deferred to the next checkpoint (PR-D is the Opus-reviewed massive change).

Files Codex may touch in Phase 1:
- `capture_index_runtime.py` (tiers, validation_backed, aliases)
- `fixture_model_adapter.py` (per-param authority summary; do NOT change composed values)
- `webserver.py` (pass validation state + aliases through; no behavior change to SSE shape beyond additive fields)
- `static/renderer.js` (MotionState: motion_type model, color, direction gate, headline tier; NO `_drawFan` origin/geometry rewrite — that is PR-D)
- `static/app.js` (diagnostics: headline authority, per-param tiers, aliases)
- `calib/render_grid_capture.py` (NEW capture-aware harness)
- `tests/test_capture_index_runtime.py`, `tests/test_renderer_motionstate.js`
- `artifacts/renderer/renderer-accuracy-phase1/implementation_report.md`

Explicit Phase-1 non-goals (defer to PR-D/E): aperture origin remap, per-aperture extent normalization, angular-spread-from-angle_range_deg, analyzer count field, density rewrite.

### Phase 1 acceptance (Codex must verify)
1. `node tests/test_renderer_motionstate.js` passes incl. new motion-type/color/direction tests.
2. `python3 -m pytest tests/test_capture_index_builder.py tests/test_capture_index_runtime.py` passes incl. alias + validation_backed tests.
3. Grep shows no runtime/renderer branch on cue name/tags/is_motion/calibration_type.
4. `calib/render_grid_capture.py` produces an HTML grid driving `LaserRenderer` with real per-cue `__capture_lookup`.
5. `cue_001_off`: blue/cyan, strobing 15Hz, NO horizontal sweep; headline tier NOT `EXACT_CAPTURE_RENDER_AUTHORITY` (validation.pass=0).
6. No fixture_model/capture mutation; second_pattern preserved; aperture origins unchanged.

---

## 6. Smoke / view protocol (orchestrator runs after Codex)
```
node tests/test_renderer_motionstate.js
python3 -m pytest tests/test_capture_index_builder.py tests/test_capture_index_runtime.py
python3 calib/render_grid_capture.py /tmp/vln_phase1.html \
   cue_001_off cue_002_green cue_003_intro_techno <sweep cue> <rotation cue> <wave cue>
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
   --screenshot=/tmp/vln_phase1.png --window-size=900,760 --virtual-time-budget=2000 \
   --hide-scrollbars file:///tmp/vln_phase1.html
```
Opus then reads the PNG and confirms color/motion correctness vs the cue's `analysis.json`.

## 7. Review model
- Codex (gpt-5.3-codex): implements each PR.
- gpt-5.5-high: reviews PR-A, PR-B, PR-C, PR-E (routine), against this plan + diff + tests.
- Opus (Claude 4.8): reviews PR-D (massive geometry/density checkpoint) and the final integration, capture-grounded; intervenes earlier only if a phase review escalates a blocker.
