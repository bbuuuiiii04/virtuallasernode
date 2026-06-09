# PR3 Implementation Report — renderer-measured-motion-pr3

## 1. Scope Implemented

- Renderer now consumes measured motion parameters from exact-capture lookup metrics when available (`MEASURED_MOTION_ANALYSIS` source).
- Reduced fallback MotionState core retained and explicitly labeled (`FALLBACK_MOTIONSTATE`) for:
  - visibility gates (power/dimmer/position blank/sound gate),
  - square-wave strobe gating,
  - CH2 sound gate override path,
  - CH10 drawMode mapping.
- Existing second-pattern rendering preserved and labeled as decoder-driven.
- Existing fixed fixture/aperture source-origin behavior preserved.

## 2. Files Changed

- `static/renderer.js`
- `static/app.js`
- `tests/test_renderer_motionstate.js`
- `artifacts/renderer/renderer-measured-motion-pr3/smoke_cases.txt`
- `artifacts/renderer/renderer-measured-motion-pr3/render_grid_pr3.html`
- `artifacts/renderer/renderer-measured-motion-pr3/render_grid_pr3.png`

## 3. Design Summary

- PR2 already injects `capture_lookup` into SSE fixture-model payload.
- `static/app.js` now enriches renderer fixture input with:
  - `__capture_lookup`
  - `__provenance_label`
- `static/renderer.js` now:
  - carries control/provenance/capture lookup through primary/second layer shaping,
  - builds explicit per-layer MotionState (`_buildMotionState`),
  - applies measured metrics (`loop_duration_estimate`, `motion_direction`, `x/y extents`, `strobe_frequency_hz`, `duty_cycle`) when an exact capture hit is present for the primary layer,
  - uses deterministic fallback waveform behavior when measured motion is unavailable,
  - uses square-wave strobe gating with visible phase/duty,
  - keeps CH10 draw mode explicit (`bright_line` / `beam_line` / `dot`),
  - exposes renderer debug state (`getDebugState`, `setSoundOverride`) for diagnostics.
- Diagnostics in `static/app.js` now surface MotionState-derived fields (provenance, kill reason, draw mode, strobe gate, warnings, sound override state).

## 4. How Existing Renderer Behavior Was Preserved

- `_drawFan()` still uses the same fan geometry, fixed source layout, and existing visual beam pipeline.
- Second pattern layer remains rendered through `_layers()` / `_second()` and is not removed.
- Dynamic macro handling and existing beam/color/wave draw logic remain intact; PR3 adds source-labeled motion decisioning, not visual-polish rewrites.

## 5. Tests Run

- `node tests/test_renderer_motionstate.js`
  - Result: pass (`ok 8 renderer MotionState checks`)
- `python3 -m pytest tests/test_capture_index_builder.py tests/test_capture_index_runtime.py`
  - Result: pass (`9 passed`)

## 6. Renderer Smoke Checks

- Generated smoke grid:
  - `artifacts/renderer/renderer-measured-motion-pr3/render_grid_pr3.html`
  - `artifacts/renderer/renderer-measured-motion-pr3/render_grid_pr3.png`
- Command:
  - `python3 calib/render_grid.py ...` (see `smoke_cases.txt` for full case list)
- Cases include power-off, CH6/CH7 blanking, CH10 dot, CH11 strobe, CH15/CH16 position/speed, CH19 wave, and second pattern.

## 7. Known Approximations

- CH15/CH16 speed waveform fallback remains sine-based when measured motion is unavailable.
- CH19 wave path deformation remains approximate/unverified.
- Second pattern remains decoder-driven and warning-labeled because capture corpus authority is CH1-19 first-pattern scoped.
- Measured-motion application currently targets exact-capture hit path for the primary layer only.

## 8. Deferred PR4+ Items

- Expanded diagnostics/trust tooling (PR4).
- Visual polish and beam-look refinements (PR5).
- Physical comparison/calibration hardening (PR6).

## 9. Risks / Manual Checks Needed

- Visual parity should be spot-checked in browser with live stream to confirm no unintended regressions in dynamic cue feel.
- Sound-gate override currently uses URL toggle (`?soundOverride=1`) and should remain debug-only.
