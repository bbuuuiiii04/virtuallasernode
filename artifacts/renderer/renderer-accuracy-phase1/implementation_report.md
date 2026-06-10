# Renderer Accuracy Phase 1 Implementation Report

## 1. Scope implemented

Implemented Phase 1 exactly as requested (PR-A + PR-B + PR-C) for runtime honesty, cue identity honesty, and capture-driven motion/color authority:

- Replaced flat exact-capture headline assumptions with vector-level provenance + validation-backed gating.
- Added cue alias identity reporting (no single trusted cue name).
- Added capture-driven dominant color mapping and capture-driven motion-type modeling.
- Fixed OFF-case conflation where `strobe_gate` loop timing incorrectly generated translational sweeps.
- Added capture-aware smoke harness to drive `LaserRenderer` with composed state + real capture lookup metadata.

Deferred intentionally: geometry/aperture-origin rewrites, per-aperture extent normalization, angular spread replacement, density rewrite, visual polish (PR-D/PR-E).

## 2. Files changed

- `capture_index_runtime.py`
- `webserver.py`
- `fixture_model_adapter.py`
- `fixtures.py` (post-review Fix 1: CH1 binary gate)
- `static/renderer.js`
- `static/app.js`
- `calib/render_grid_capture.py` (new)
- `docs/RENDERER_PR_STATUS.md` (routine-review minor: Active PR Checklist refreshed to Phase 1)
- `tests/test_capture_index_runtime.py`
- `tests/test_renderer_motionstate.js`
- `tests/test_fixtures_decode.py` (new, post-review Fix 1)
- `tests/test_app_diagnostics.js` (new, routine-review Blocker 1 guard)

## 2b. Routine review (gpt-5.5) BLOCK_MERGE fixes

Addressed the two blockers plus the doc minor from the gpt-5.5 routine review. All prior Phase 1 work retained; no `_drawFan` geometry/origin/extent/spread changes; `coreWhiteBoost` untouched.

### Blocker 1 — diagnostics crash in `static/app.js`

- `appendLine()` returned `undefined`, but the "Headline Authority" line used
  `headline.style.color = ...`, throwing inside the SSE `onmessage` handler and
  crashing the diagnostics panel / live feed.
- Fix: `appendLine()` now returns the created value `span`, and the headline
  styling is null-guarded (`if (headline && headline.style) { ... }`) so a
  missing element can never dereference `.style`.
- Guard test: `tests/test_app_diagnostics.js` loads `renderer.js` + `app.js` in
  a DOM-stubbed VM, drives the real SSE `onmessage` with a crafted frame, and
  asserts it does not throw and that a colour-styled headline element exists.

### Blocker 2 — per-axis motion model (plan 3.4) in `static/renderer.js`

- The measured branch collapsed `motion_type` into a broad `translational`
  boolean and `_moveOffset` applied measured translation to BOTH axes.
- Fix: `_moveOffset` is now per-axis. Measured translation is applied only when
  `motion_type` matches the axis (`horizontal_sweep` -> H only; `vertical_sweep`
  -> V only). Other known types (`static`, `smooth_rotation`,
  `wave_deformation`, `pulse_zoom`, `color_chase`, `strobe_gate`) yield zero
  measured offset on both axes. Unknown `motion_type` falls back to the
  decoder/CAL sine (NOT zeroed) for whichever axis is in CH15/CH16 speed mode,
  and emits `measured_motion_type_unknown_fallback` +
  `CH15_CH16_sine_waveform_approximate_unverified`. Direction-confidence gate
  (>=0.6 concrete) and rate gate (periodic && loop_confidence >= 0.5) preserved.
- Tests: `testHorizontalSweepTranslatesHAxisOnly` (both CH15/CH16 speed; offset
  on H only, zero on V) and `testUnknownMotionTypeUsesDecoderFallbackSine`
  (nonzero decoder sine + unknown/fallback warning + motion tier
  `DECODER_FALLBACK`).

### Minor — `docs/RENDERER_PR_STATUS.md`

- "Active PR Checklist" updated from the stale `renderer-visual-polish-pr5` /
  `renderer-capture-index-pr1` content to the current
  `renderer-accuracy-phase1` Phase 1 reality.

### Post-fix verification

`node tests/test_renderer_motionstate.js` -> `ok 19 renderer MotionState checks`

`node tests/test_app_diagnostics.js` -> `ok 1 app diagnostics checks`

`python3 -m pytest tests/test_capture_index_builder.py tests/test_capture_index_runtime.py tests/test_fixtures_decode.py`
-> `15 passed`

## 2a. Post-Phase-1 visual review fixes (Opus)

Two focused fixes applied after Phase 1 visual review. All prior Phase 1 work retained; no `_drawFan` geometry/origin/extent/spread changes; `coreWhiteBoost` untouched.

### Fix 1 — CH1 binary on/off (correctness bug)

- `fixtures.py:decode_36ch` previously treated CH1 as a 0-255 master dimmer
  (`power = ch(1) > 0`, `dimmer = round(ch(1)/255, 3)`). The fixture model and
  `docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md` (lines 58, 134) are explicit:
  CH1 is a BINARY on/off gate, not a dimmer.
- Impact before fix: 159/184 SoundSwitch cues have CH1 <= 63, rendering at
  <= 25% brightness (29 cues <= 6%), crushing measured colours to faint white.
- Fix: `power = ch(1) > 0`; `dimmer = 1.0` when on, `0.0` when off. Added a
  comment citing the readiness doc.
- Consumer audit (`grep dimmer`): the only place computing a fractional CH1
  dimmer was `fixtures.py`. Other consumers read the decoded value for
  visibility gates (`renderer.js` `dimmer <= 0.002`), the renderer brightness
  multiplier `dim` (now full for on cues), the diagnostics display
  (`app.js`, shows 100% when on), and the compose power-off path
  (`fixture_model_adapter.py` sets `dimmer = 0.0`). None depend on a fractional
  CH1 dimmer.
- Test: `tests/test_fixtures_decode.py` asserts CH1=3 -> power true & dimmer
  == 1.0, CH1=220 -> dimmer == 1.0, CH1=0 -> power false & dimmer == 0.0.

### Fix 2 — multi-color dominant_colors (>= 3 colors)

- `_extractMeasuredColor` previously capped mapped measured colours to 2
  (`mapped.slice(0, 2)`). For analysis `dominant_colors` with >= 3 entries
  (e.g. `cue_008` -> `[blue, cyan, green, magenta, red, white]`) this dropped
  measured palette colours.
- Fix: keep all mapped measured colours. `_beamColor` already cycles per-beam
  via `colors[i % colors.length]`, so 1 = solid, 2 = per-beam alternation,
  >= 3 = per-beam cycle (measured rainbow spread). Still tagged
  `MEASURED_PARAM`. Unknown colour names still fall back to decoder + warning
  (`measured_color_unknown_name_fallback`); no colours are invented.
- Test: `tests/test_renderer_motionstate.js::testMultiDominantColorsCyclePerBeam`
  asserts a 6-colour cue cycles beam colours through the measured palette and
  wraps, with colour tier remaining `MEASURED_PARAM`.

### Post-fix verification

`node tests/test_renderer_motionstate.js` -> `ok 17 renderer MotionState checks`

`python3 -m pytest tests/test_capture_index_builder.py tests/test_capture_index_runtime.py tests/test_fixtures_decode.py`
-> `15 passed`

End-to-end decode + renderer check (composed state + real capture lookup):

- `cue_001_off` (CH1=34): `dimmer=1.0`, `dim=1.0` (bright_line), beams blue
  `[60,90,255]` / cyan `[40,230,230]`, colour tier `MEASURED_PARAM`,
  `hMoveOffset=0` (strobe_gate, no sweep), headline `DECODER_FALLBACK`.
- `cue_004_breakdown_1` (CH1=3): `dimmer=1.0`, `dim=1.0` (bright_line), beams
  blue `[60,90,255]` / cyan `[40,230,230]`, colour tier `MEASURED_PARAM`
  (was ~1.2% brightness before Fix 1). Motion is a `horizontal_sweep`, so the
  expected non-zero translational oscillation remains.

## 3. Per-parameter authority design

Implemented tier vocabulary in renderer MotionState:

- `EXACT_CAPTURE_RENDER_AUTHORITY`
- `MEASURED_PARAM`
- `MODEL_COMPOSED`
- `DECODER_FALLBACK`

Runtime split:

- Vector-level provenance from lookup is now `EXACT_VECTOR_MATCH` or `NO_VECTOR_MATCH`.
- `validation_backed` is derived from fixture model validation pass/validated vector lists (currently false with present model data because `validation.buckets.pass` is numeric/empty for vectors).

Per-parameter authority behavior:

- `color`: `MEASURED_PARAM` when dominant capture colors map cleanly and capture is exact-vector + usable evidence; otherwise `DECODER_FALLBACK`.
- `motion`: `MEASURED_PARAM` when measured motion type is known; otherwise fallback.
- `strobe`: `MEASURED_PARAM` when measured strobe fields are usable.
- `spread`, `count`, `position`, `dots`: `DECODER_FALLBACK` in Phase 1 by design.

Headline authority is the minimum tier across visible parameters and is emitted as `fixture.headlineTier`.

Critical validation gate:

- Renderer never emits `EXACT_CAPTURE_RENDER_AUTHORITY` unless `validation_backed` is true.

## 4. OFF conflation fix

Fixed the core bug where non-translational capture motion types were incorrectly converted into CH15/CH16 beam sweeps:

- Motion model now keys off `metrics.motion_type` categories.
- Translational offsets are only applied for `horizontal_sweep` / `vertical_sweep`.
- `strobe_gate`, `wave_deformation`, `pulse_zoom`, `color_chase`, `smooth_rotation`, and `static` produce zero translational offsets.
- Loop-derived rate (`1/loop_duration_estimate`) is only used when `periodic_motion` is true and `loop_confidence >= 0.5`.
- Direction sign is applied only when `motion_direction_confidence >= 0.6` and a concrete directional label is present; otherwise unsigned.

Manual OFF-case check (`cue_001_off`) confirms:

- dominant colors: blue/cyan
- motion type: strobe_gate
- translational offset: zero
- measured strobe frequency: 15 Hz
- headline tier: not `EXACT_CAPTURE_RENDER_AUTHORITY`

## 5. Cue names non-authoritative

Cue handling now reports aliases without asserting a single authoritative identity:

- `cue_aliases: [{cue_id, cue_name}]`
- `cue_alias_count`
- `cue_identity_resolved` true only when exactly one distinct cue name maps to the vector

No runtime/renderer branching on `cue_name`, `tags`, `is_motion`, or `calibration_type`.

Targeted grep (runtime + renderer related files):

```bash
rg "cue_name|tags|is_motion|calibration_type" \
  capture_index_runtime.py webserver.py fixture_model_adapter.py fixtures.py \
  static/app.js static/renderer.js calib/render_grid_capture.py
```

Result: only display/alias plumbing references in `capture_index_runtime.py` and `static/app.js`; no behavioral branching by cue metadata.

## 6. Tests run

Executed required test commands:

```bash
node tests/test_renderer_motionstate.js
python3 -m pytest tests/test_capture_index_builder.py tests/test_capture_index_runtime.py
```

Results:

- `ok 16 renderer MotionState checks`
- `============================== 12 passed in 0.14s ==============================`

Added coverage includes:

- `strobe_gate` with CH15 speed-mode yields zero translational offset
- low-confidence measured direction yields unsigned direction
- dominant colors map to capture palette and drive rendered colors
- headline tier downgrades to decoder when any visible param is decoder fallback
- `validation_backed=false` prevents `*_RENDER_AUTHORITY`
- multi-name vector alias collision yields unresolved cue identity
- normal hit with current fixture model yields `validation_backed=false`

## 7. Capture-aware harness usage

New harness:

- `calib/render_grid_capture.py`

What it does:

- Resolves phase6 cue-folder names from capture metadata (`captures/.../metadata.json`) to CH1-19 vectors.
- Builds composed state via `compose_fixture_model`.
- Looks up exact capture authority via real runtime index (`capture_index_v1.json`) and cues.
- Injects app-like metadata fields (`__capture_lookup`, `__provenance_label`, `__model_status`, `__model_confidence`) into each rendered fixture state.
- Emits an HTML grid for headless screenshotting and prints `output_path width height`.

Example:

```bash
python3 calib/render_grid_capture.py /tmp/vln_phase1.html cue_001_off cue_002_green cue_003_intro_techno
```

## 8. Known approximations

Phase 1 intentionally keeps these as fallback-labeled approximations:

- Fan geometry/aperture placement still decoder/CAL driven.
- Spread/count/position/dots remain decoder fallback.
- second_pattern remains decoder-driven and warning-labeled.

## 9. Explicit deferrals

Deferred to PR-D / PR-E:

- aperture origin remap to `analysis_geometry.json` boxes
- per-aperture extent normalization
- angular spread from `angle_range_deg`
- density/count derivation rewrite
- geometry version/provenance UX expansion beyond Phase 1 additions
