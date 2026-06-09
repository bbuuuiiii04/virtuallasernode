# Superseded Notice (2026-06-09)
This plan is superseded as primary plan by `docs/RENDERER_CAPTURE_BACKED_PLAN_V1.md` on 2026-06-09 after the capture corpus audit; retained because its MotionState schema, visibility gates, and guardrails are reused by the fallback layer in PR3.

# VirtualLaserNode Renderer Motion-First Review Plan — Rev 3

**Updated:** 2026-06-09  
**Purpose:** revise Rev 2 after a fresh repo-grounded architectural review of the current renderer.

**Primary priority:** beam motion and animation fidelity.  
**Secondary priority:** beam appearance, haze, glow, bloom, and visual polish.  
**Current phase:** design/review and motion-model refactor planning. No fixture-model recapture. No visual restyle.

---

## 1. Executive Verdict

Proceed, but proceed with changes.

Rev 2 was directionally correct, but it understated what the repo already does and missed several current-code realities.

The renderer is not a blank slate. It already has:

- fixed source origins for the two rendered fixtures
- composed-state input preferred over decoded-state input
- browser-side RAF rendering
- render-behind buffering
- calibration.json loading
- CH15/CH16 tristate decoding support
- second-pattern layer rendering
- CH19 wave approximation
- model diagnostics in the UI

However, it is still not motion-first enough. The current renderer still buries movement, visibility, strobe, scan, wave, color, and draw behavior inside `renderer.js` drawing flow, especially `_drawFan()`. The next step is therefore not “make beams prettier.”

The next step is:

```text
composed fixture state + browser time
→ explicit MotionState
→ current draw-compatible beam state
→ existing fan draw path
→ diagnostics
→ visual draw
```

The renderer should remain an aerial beam renderer. Do not convert it back into wall-projection vector glyph thinking.

---

## 2. Repo-Grounded Corrections From Rev 2

### 2.1 Current runtime flow is confirmed

Actual current flow:

```text
SoundSwitch Art-Net
→ artnet.py UniverseState buffer
→ webserver.py SnapshotProducer / _snapshot()
→ fixtures.py decode_fixture()
→ fixture_model_adapter.compose_fixture_model()
→ SSE /stream payload
→ static/app.js
→ LaserRenderer.update()
→ renderer.js RAF loop
→ canvas draw
```

### 2.2 app.js already prefers composed state

The renderer is not only consuming `decoded` anymore.

Current `static/app.js` behavior:

```text
renderState = composed.length ? composed : decoded
laser.update(renderState)
```

Plan language must say **fixture state** or **composed fixture state**, not simply decoded.

### 2.3 fixture_model_adapter.py is not a spatial contract

The adapter:

- deep-copies decoded state
- applies selective mutations
- attaches fixture_model diagnostics
- preserves a decoded-shaped composed contract

It does **not** emit final beam coordinates, physical aim vectors, MotionState, or renderer paths.

That is correct for now. Browser-local time-dependent motion should remain browser-side.

### 2.4 renderer.js already keeps source origins fixed

The current aerial renderer does not move the laser source points for pan/tilt. It calculates fixed fixture/aperture origins and changes beam direction/endpoint behavior. Preserve this.

This is one of the better parts of the current implementation. Do not “fix” it into something worse.

### 2.5 second_pattern is already rendered

Rev 2 allowed PR 1 to warn only for second_pattern. Current renderer already creates a second layer via `_layers()` / `_second()` when `second_pattern` exists.

Do not remove that.

New requirement:

```text
Second pattern must get its own MotionState/layer diagnostics.
```

If the current approximation is incomplete, warn honestly rather than silently under-rendering or deleting the layer.

### 2.6 CH15/CH16 tristate is already partly implemented

Current `_sweep()` already does:

```text
off → 0
position → static offset
speed → sine oscillator
```

But the logic is hidden inside the drawing path and the sine waveform is unverified. Rev 3 should not pretend this is absent, and should not pretend it is exact.

### 2.7 CH2 sound_gated reaches fixture state but is not used by the renderer

`fixtures.py` decodes CH2 sound mode as `control.sound_gated = true`, and `decode_36ch()` includes `control` in the fixture state. `webserver.py` includes that decoded/composed fixture state in the SSE payload, and `static/app.js` passes the chosen fixture state into `LaserRenderer.update()`.

The missing piece is inside `static/renderer.js`: `_primary()` and `_second()` currently do not copy `fx.control` into layer state, and `_interp()` / `_drawFan()` do not use `control.sound_gated` as a visibility gate.

This is a PR 1 fix.

### 2.8 Strobe is currently too fake

Current strobe is a sine-threshold gate in `_strobeVisible()`:

```text
Math.sin(clock * rate) > 0
```

Rev 3 requires square-wave phase gating, with a duty field exposed in MotionState.

PR 1 may use a conservative fixed duty, but the model contains measured duty/strobe data and later PRs should use or approximate that more honestly.

### 2.9 CH10 dot mode is not yet a real dot path

Current CH10 dot mode changes beam count/brightness behavior, but it does not clearly bypass line drawing.

PR 1 must expose:

```text
scan.drawMode = "dot"
```

Actual dot-path rendering can be PR 2 or PR 3 if needed.

---

## 3. Non-Negotiable Design Boundary

The renderer is a **DMX laser motion simulator with an aerial beam renderer attached**.

Do not begin with:

```text
beam thickness
bloom
haze
glow
cinematic color grading
new visual style
WebGL
```

Begin with:

```text
visibility gates
source origins
position blanking
static aim
movement mode semantics
movement phase
strobe phase
scan draw mode
rotation phase
zoom phase
wave phase
color phase
second-pattern layer state
confidence warnings
```

Visual polish only starts after motion is inspectable.

---

## 4. Current Renderer Architecture Assessment

### 4.1 What is good enough to preserve

Preserve:

- fixed fixture/aperture origins
- two fixture layout
- current RAF loop
- current render-behind buffer
- current calibration fetch
- current composed-state input preference
- current basic fan rendering
- current second-pattern layering
- current adapter fallback behavior
- current model diagnostics panel, expanded rather than replaced

### 4.2 What must change

Change:

- movement logic must move out of opaque `_drawFan()` math into MotionState construction
- CH2 sound gating must become a first-order visibility gate
- strobe must become explicit square phase/gate logic
- CH10 dot mode must be represented as drawMode
- second pattern must have per-layer MotionState diagnostics
- approximation warnings must be visible in Debug View
- renderer comments and names must stop saying only `decoded` when app.js feeds composed state

---

## 5. Corrected Input Contract

Renderer input is an array of fixture states. In live UI this usually means `composed`; if adapter/model loading fails, it may mean `decoded` fallback.

Each fixture state may include:

```text
name
universe
power
dimmer
control
pattern
position
color
scan
strobe
rotation
movement
zoom
gradient
waves
second_pattern
```

The renderer must tolerate missing fields and never produce NaN, undefined geometry, or a crashed RAF loop.

### 5.1 Renderer should expose whether input was composed or decoded fallback

Future improvement:

```text
app.js should pass fixture_models or a compact modelStatus into LaserRenderer.update()
```

PR 1 may avoid changing the update signature if that would enlarge scope, but debug output should eventually show:

```text
inputContract: composed | decoded_fallback | adapter_error
```

This is useful but not a blocker for PR 1 if MotionState itself is otherwise inspectable.

---

## 6. Corrected Visibility Chain

Visibility must be computed before draw, but motion math must continue even when strobe is closed.

### 6.1 Hard kill conditions

A layer should not draw if any are true:

```text
power == false
dimmer <= 0
position.blanked == true
control.sound_gated == true and soundOverride == false
```

### 6.2 Dynamic macro caveat

Current renderer lets dynamic patterns bypass `position.blanked`. Do not blindly keep or remove this without making it visible.

PR 1 behavior:

```text
MotionState.visibility.positionBlanked = true/false
MotionState.visibility.dynamicBlankingBypassed = true/false
```

Default should be conservative hard kill unless repo evidence says dynamic macros truly ignore CH6/CH7 blanking.

### 6.3 Strobe is not a hard kill for motion

Correct:

```text
compute MotionState fully
compute strobe gate
apply strobe at draw stage
show gate state in diagnostics
```

Wrong:

```text
if strobe closed: skip motion math
```

---

## 7. MotionState Layer

Introduce browser-local MotionState.

Preferred location:

```text
static/motionState.js
```

Acceptable PR 1 alternative:

```text
isolated MotionState builder section inside static/renderer.js
```

Do not put time-dependent MotionState in `fixture_model_adapter.py`.

### 7.1 Why browser-local

Browser-local is correct because:

- RAF timing is browser-side
- animation phase is browser-side
- strobe preview is browser-side
- render-behind interpolation is browser-side
- debug overlays are browser-side
- the adapter does not produce spatial coordinates
- the web server pushes 30 Hz snapshots, while visual motion phase is browser-RAF cadence

### 7.2 MotionState output should feed current renderer first

PR 1 should preserve current visuals as much as possible.

Target shape:

```text
fixture state + layer + browser time
→ MotionState
→ draw-compatible state object
→ existing _drawFan() path
```

Do not rewrite the entire renderer in the first PR. That is how scope creep gets a driver’s license.

### 7.3 MotionState integration with _drawFan()

The safest PR 1 path is a compatibility bridge, not a draw rewrite.

Current `_drawFan(ctx, st, idx, total, dims)` expects a compact interpolated state with fields like:

```text
visible
dimmer
posX
posY
size
color
strobeOn
strobeSpeed
gradient
rotation
movement
zoom
scan
waves
patternGroup
patternIndex
dynamic
```

PR 1 should either:

1. build MotionState first, then derive this same draw-compatible object; or
2. extend the draw-compatible object with a `motionState` property while preserving the existing fields.

Recommended PR 1 bridge:

```text
primary/second layer fixture state
→ buildMotionStateV1(layer, clock, calibration, options)
→ toDrawState(motionState, legacyInterpolatedFields)
→ _drawFan(ctx, drawState, idx, total, dims)
```

Do not force `_drawFan()` to understand the whole MotionState schema in PR 1. Make `_drawFan()` consume only the fields it already needs, plus maybe:

```text
drawMode
visibleBeforeStrobe
visibleAfterStrobe
strobeGateOpen
motionState
```

This preserves visuals while making motion semantics inspectable. The refactor can then peel more logic out of `_drawFan()` in later PRs without detonating the renderer like a tiny JavaScript confetti bomb.

---

## 8. MotionState PR 1 Schema

Keep PR 1 schema small but honest.

```ts
interface MotionStateV1 {
  epochMs: number;

  fixture: {
    index: number;
    total: number;
    name?: string;
    mirror: boolean;
  };

  layer: {
    kind: "primary" | "second_pattern";
    active: boolean;
    approximate: boolean;
  };

  visibility: {
    power: boolean;
    dimmer: number;
    positionBlanked: boolean;
    soundGated: boolean;
    soundOverride: boolean;
    dynamicBlankingBypassed: boolean;
    visibleBeforeStrobe: boolean;
    visibleAfterStrobe: boolean;
    killReason: null |
      "power_off" |
      "dimmer_zero" |
      "position_blanked" |
      "sound_gated";
  };

  pattern: {
    kind: "static" | "dynamic";
    group: number;
    folder?: string;
    index: number | null;
    playAll: boolean;
    sizeRaw: number;
    secondPattern: boolean;
  };

  scan: {
    mode: "line-bright" | "line" | "dot";
    speedRaw: number;
    drawMode: "bright_line" | "beam_line" | "dot";
    confidence: "measured" | "approximate";
  };

  aim: {
    hStatic: number;
    vStatic: number;

    hMoveMode: "off" | "position" | "speed";
    hMoveValue: number;
    hMoveOffset: number;
    hMovePhase: number;
    hMoveWaveform: "sine" | "triangle" | "pingpong" | "saw";
    hMoveConfidence: "measured" | "insufficient" | "approximate";

    vMoveMode: "off" | "position" | "speed";
    vMoveValue: number;
    vMoveOffset: number;
    vMovePhase: number;
    vMoveWaveform: "sine" | "triangle" | "pingpong" | "saw";
    vMoveConfidence: "measured" | "measured_interfere" | "approximate";

    hFinal: number;
    vFinal: number;
  };

  strobe: {
    active: boolean;
    speedRaw: number;
    phase: number;
    duty: number;
    gateOpen: boolean;
    waveform: "square";
  };

  warnings: string[];
}
```

Do not implement the full Rev 2 mega-schema in PR 1. Add rotation/zoom/wave/color state in PR 2.

---

## 9. Channel-by-Channel PR 1 Behavior

### CH1 — Master dimmer

PR 1:

```text
power false or dimmer zero → visibleBeforeStrobe false
motion phase still allowed to continue globally
```

### CH2 — Auto / sound mode

PR 1:

```text
if control.sound_gated and no soundOverride:
  visibleBeforeStrobe = false
  killReason = "sound_gated"
```

Important current-code fact:

```text
fixtures.py decodes control.sound_gated
webserver.py sends decoded/composed fixture state
app.js passes fixture state to LaserRenderer.update()
renderer.js currently drops/ignores control in _primary()/_second()
```

So PR 1 must carry `control` into layer/MotionState construction before applying the gate.

Add debug control:

```text
Simulate sound trigger: off/on
```

Default should be off for honesty.

### CH3/CH4 — Pattern

PR 1:

```text
preserve current pattern/folder/index behavior
record dynamicMacro = pattern.kind === "dynamic"
record playAll/index null without NaN
```

Do not overclaim that all dynamic macros ignore CH5–19 unless evidence supports it.

### CH5 — Pattern size

PR 1:

```text
preserve existing spread/count behavior
include sizeRaw in MotionState
```

### CH6/CH7 — Static aim and blanking

PR 1:

```text
hStatic = position.x
vStatic = position.y
position.blanked is hard visibility kill
```

If dynamic bypass is kept temporarily, show it in MotionState warnings.

### CH8/CH9 — Color

PR 1:

```text
preserve existing _beamColor behavior
no color redesign
```

PR 2 adds explicit color MotionState.

### CH10 — Scan

PR 1:

```text
line-bright → drawMode bright_line
line → drawMode beam_line
dot → drawMode dot
```

Actual dot rendering can be deferred but the MotionState must expose it.

### CH11 — Strobe

PR 1:

```text
strobe.on false → gateOpen true
strobe.on true → square-wave gate
phase continues while closed
duty field exists
```

Initial duty may be fixed, but do not pretend it is final. Later use measured duty maps or calibrated approximation.

### CH12/CH13/CH14 — Rotation

PR 1:

```text
preserve current behavior
not yet full MotionState except warnings if needed
```

PR 2 formalizes rotation state.

### CH15/CH16 — Movement

PR 1:

```text
off → offset 0
position → static offset
speed → oscillator offset
```

Default waveform may remain sine for continuity, but it must be configurable or centralized as a constant:

```text
motion.sweepWaveform = "sine"
```

Diagnostic label:

```text
CH15/CH16 sine waveform approximate/unverified
```

### CH17 — Zoom

PR 1:

```text
preserve existing size mode behavior
speed mode may remain non-goal
```

PR 2 must implement speed/pulse.

### CH18 — Gradient

PR 1:

```text
preserve existing gradient/color behavior
surface approximation warning when gradient_override or CH18 active
```

### CH19 — Wave

PR 1:

```text
preserve current wave path deformation
```

Diagnostic label:

```text
CH19 sine path deformation approximate/unverified
```

PR 2 adds wave phase and trace.

### CH20–CH36 — Second pattern

PR 1:

```text
keep current second-pattern rendering
create per-layer MotionState
if incomplete/approximate, show warning
add acceptance check that second-pattern layering is not broken
```

Do not downgrade to warning-only unless current layer rendering breaks.

---

## 10. Corrected Transform Order

Recommended semantic order:

```text
1. Read composed fixture state.
2. Split into layers:
   - primary
   - second_pattern if active
3. Compute hard visibility gates:
   - power
   - dimmer
   - position.blanked
   - sound_gated
4. Compute strobe gate, but continue motion math.
5. Compute static aim:
   - CH6/CH7 or CH23/CH24 for second pattern
6. Compute movement contribution:
   - CH15/CH16 or CH32/CH33
7. Combine aim:
   - hFinal = hStatic + hMoveOffset
   - vFinal = vStatic + vMoveOffset
8. Compute pattern basis:
   - pattern group/index
   - size
   - scan drawMode
9. Compute zoom.
10. Compute rotation.
11. Generate beam paths from fixed origins.
12. Apply wave deformation.
13. Compute color/gradient.
14. Apply strobe at draw stage.
15. Draw.
16. Render diagnostics/debug overlays.
```

Open transform questions remain:

```text
Does dynamic macro bypass CH6/CH7 blanking?
Should wave remain path-space or move to local pattern-space?
Should zoom apply before or after rotation for aerial fan approximation?
Should dot mode draw literal dots, dotted beams, or source-to-point bursts?
```

---

## 11. Oscillator Policy

All oscillators must be:

```text
deterministic
phase-continuous
centralized/configurable
labeled approximate unless measured
```

### PR 1 defaults

```text
CH15 speed waveform: sine, approximate/unverified
CH16 speed waveform: sine, approximate/unverified
CH11 strobe: square wave
CH19 wave deformation: existing sine path deformation, approximate/unverified
```

### PR 2 additions

Add calibration/debug option:

```json
{
  "motion": {
    "sweepWaveform": "sine",
    "sweepWaveformOptions": ["sine", "triangle", "pingpong", "saw"]
  }
}
```

Do not add a broad UI first. A code constant or calibration key is enough.

---

## 12. Debug Tooling Required Before Visual Polish

### 12.1 MotionState JSON panel

Show current MotionState for each layer.

### 12.2 Aim crosshair overlay

Show:

```text
static aim
movement offset
final aim
blanking boundary
```

### 12.3 Sound gate override

Show:

```text
sound_gated: true
soundOverride: true/false
```

### 12.4 Strobe indicator

Show:

```text
phase
duty
gateOpen
speedRaw
```

### 12.5 Second-pattern layer indicator

Show:

```text
primary layer active
second layer active
second layer approximate
```

### 12.6 Approximation warnings

At minimum:

```text
CH15 speed waveform approximate/unverified
CH16 speed waveform approximate/unverified
CH19 wave deformation approximate/unverified
CH6xCH15 insufficient_reference_rows
CH7xCH16 measured_interfere
CH18 gradient approximate
higher_order_validation_pending
118_dense_missing
adapter decoded_fallback
```

### 12.7 Input contract diagnostic

Useful if low-scope:

```text
renderer input: composed | decoded_fallback | adapter_error | unknown
```

This can come from `fixture_models[].confidence` / `model_status` in the SSE payload. If adding this requires changing `LaserRenderer.update()` signature too much, defer it, but do not lose the existing model diagnostics.

### 12.8 Show View vs Debug View

Show View should stay clean.

Debug View should be brutally honest.

Do not spam warnings over the performance canvas unless Debug View is active.

---

## 13. Calibration Architecture

Current `calibration.json` already contains rates, timing, geometry, beam, zoom, dynamic, patternShape, color, and position blanking values.

Rev 3 recommendation:

Separate motion constants from visual constants more clearly over time.

Suggested future grouping:

```json
{
  "motion": {
    "sweepWaveform": "sine",
    "sweepMinHz": 0.08,
    "sweepMaxHz": 0.9,
    "strobeDefaultDuty": 0.5,
    "soundOverrideDefault": false
  },
  "visual": {
    "beam": {},
    "haze": {},
    "trail": {}
  }
}
```

PR 1 does not need a calibration migration. It may use current `rates` and a local constant.

---

## 14. Minimal First PR — Rev 3

### Goal

Make renderer motion semantics explicit and inspectable without visual redesign.

### Before coding, inspect again

```text
static/renderer.js
static/app.js
static/index.html
static/style.css
fixtures.py
fixture_model_adapter.py
webserver.py
calibration.json
calib/render_test.py
calib/render_grid.py
```

Confirm:

```text
app.js still prefers composed over decoded
renderer.js still fetches calibration.json
second_pattern still renders as layer
CH2 control exists in fixture state but is not carried into renderer layers
strobe still uses sine-threshold gate
CH10 dot mode still lacks a true dot drawMode path
```

### PR 1 deliverables

1. Add `docs/RENDERER_MOTION_MODEL_V1.md`.
2. Add MotionState construction in `static/motionState.js` or isolated renderer.js section.
3. Add a small MotionState-to-`_drawFan()` compatibility bridge.
4. MotionState handles:
   - CH1 power/dimmer visibility
   - CH2 sound_gated visibility
   - CH6/CH7 blanking
   - CH6/CH7 static aim
   - CH15/CH16 off/position/speed modes
   - CH11 square-wave strobe gate
   - CH10 drawMode
   - second_pattern per-layer state
5. Preserve current visual rendering as much as possible.
6. Add MotionState debug output/panel or console inspection.
7. Add sound gate override.
8. Add warnings for approximate/unresolved zones.
9. Add pure-JS tests for the MotionState builder.
10. Add visual smoke/regression baseline using `calib/render_test.py` or `calib/render_grid.py`.

### PR 1 explicit non-goals

```text
No fixture_model.json changes.
No capture changes.
No WebGL.
No visual restyle.
No full CH17 speed/pulse redesign.
No full CH19 wave redesign.
No full CH18 gradient redesign.
No final dot-mode renderer unless trivial.
No claim of exact digital twin behavior.
```

### PR 1 acceptance checks

Use synthetic/live DMX states:

```text
CH1=0 → no output, MotionState killReason="power_off"
CH1>0, CH6=128, CH7=128 → centered output
CH6 below blankLow → no output, killReason="position_blanked"
CH7 below blankLow → no output, killReason="position_blanked"
CH2 sound_gated true → no output unless override
CH15=0 → hMoveMode off, hMoveOffset 0
CH15=64 → hMoveMode position, no oscillator
CH15=200 → hMoveMode speed, oscillator active
CH16=64 → vMoveMode position, no oscillator
CH16=200 → vMoveMode speed, oscillator active
CH11>0 → square strobe gate active
CH10 dot → drawMode="dot"
second_pattern active → second layer MotionState exists
second_pattern active → existing second-layer rendering is not broken
CH15/CH16 speed → warning includes approximate/unverified waveform
CH19 active → warning includes approximate/unverified wave deformation
No NaN/undefined in MotionState
RAF loop does not crash on missing fields
```

### PR 1 visual baseline checks

Use existing render harnesses before and after PR 1:

```text
calib/render_test.py
calib/render_grid.py
```

Minimum cases:

```text
power off
centered static fan
blanked CH6
blanked CH7
CH10 dot
CH11 strobe on
CH15 position
CH15 speed
CH16 position
CH16 speed
CH19 wave x/y
second_pattern active
```

The visual baseline does not need perfect pixel matching forever. It needs to catch obvious regressions: missing output, moved origins, broken second layer, inverted blanking, and wildly changed fan geometry.

---

## 15. PR 2 — Motion Fidelity Expansion

After PR 1:

```text
add full CH12/13/14 rotation MotionState
add CH17 size/speed/pulse MotionState
formalize CH19 wave phase/amplitude
add oscillator trace graph
add sweep waveform toggle or calibration key
add true dot draw path if PR 1 only exposed drawMode
```

Acceptance:

```text
CH12 spin phase continuous
CH13/CH14 deformation visible and inspectable
CH17 speed pulses spread/zoom
CH19 X/Y waves visibly distinct
CH15/CH16 waveform can be compared
```

---

## 16. PR 3 — Diagnostics and Confidence

After PR 2:

```text
show per-layer MotionState
show approximation badges
show adapter/model status in renderer debug panel
show CH18 warning
show CH6xCH15 warning
show CH7xCH16 measured-interfere warning
show higher-order stack warning
show decoded_fallback warning
```

Acceptance:

```text
show view is clean
debug view is honest
second_pattern cues are not silent mystery meat
```

---

## 17. PR 4 — Visual Polish Only After Motion

Only after PR 1–3:

```text
beam core/mid/halo tuning
haze tuning
trail tuning
source glow tuning
fixture spacing tuning
camera/stage view tuning
```

Visual polish must not mask wrong motion.

---

## 18. Validation Strategy Without More Capture

No new physical capture is required before PR 1.

Validate with:

```text
synthetic DMX states
live SoundSwitch cue banks
MotionState JSON
aim crosshair
strobe indicator
oscillator traces
browser visual inspection
headless render harnesses
visual smoke/regression screenshot baselines
```

Existing useful tools:

```text
calib/render_test.py
calib/render_grid.py
tools/validate_model_adapter.py
calib/test_fixture_model_readiness.py
```

Add MotionState-specific tests.

### 18.1 Required PR 1 MotionState tests

Pure-JS unit tests should cover:

```text
CH1 power/dimmer gate
CH2 sound_gated gate and override
CH6/CH7 blanking gate
CH15 off/position/speed classification
CH16 off/position/speed classification
CH11 square strobe phase/gate/duty
CH10 drawMode mapping
second_pattern layer MotionState creation
warning generation for approximate CH15/CH16 waveform
warning generation for approximate CH19 wave deformation
missing-field tolerance / no NaN
```

These tests should not require canvas.

### 18.2 Required PR 1 visual smoke checks

Use `calib/render_test.py` or `calib/render_grid.py` to generate before/after screenshots for representative synthetic DMX states.

The purpose is not fine-grained artistic pixel matching. The purpose is regression detection for:

```text
source origins moved by accident
second_pattern disappeared
blanked channels still render
sound_gated channels still render without override
CH10 dot destroys the fan unexpectedly
CH15/CH16 movement explodes geometry
strobe permanently dark or permanently open
```

If screenshot automation is too heavy in PR 1, at least require committed/manual screenshot artifacts in the PR report.

---

## 19. Remaining Unknowns

Keep these explicit:

```text
Exact CH15 position-mode semantics.
Exact CH16 position-mode semantics.
CH15/CH16 waveform: sine vs triangle vs ping-pong vs saw.
Whether CH15/CH16 speed controls frequency, amplitude, or both.
Whether dynamic CH3>=128 macros obey or ignore CH5–19.
Whether dynamic macros bypass CH6/CH7 blanking.
Exact CH10 dot-mode visual behavior.
Exact CH10 speed mapping.
Exact CH17 speed/pulse behavior.
How CH20–36 second pattern visually combines with primary.
How to preview sound_gated cues without real audio.
How to use measured strobe duty maps without overfitting.
```

Do not pretend these are solved.

---

## 20. Updated Codex / Sonnet Implementation Prompt

Use this for PR 1 only.

```text
You are operating inside ~/virtuallasernode.

We are implementing Renderer Motion-First Plan Rev 3.

Do not modify fixture_model.json.
Do not modify capture data.
Do not request more physical capture.
Do not redesign visuals first.
Do not convert to WebGL.
Do not hide diagnostics.
Do not claim exact digital twin behavior.
Do not remove existing second_pattern rendering unless it is demonstrably broken.

Primary goal:
Make renderer motion semantics explicit and inspectable before visual polish.

Before coding, inspect:
- static/renderer.js
- static/app.js
- static/index.html
- static/style.css
- fixtures.py
- fixture_model_adapter.py
- webserver.py
- calibration.json
- calib/render_test.py
- calib/render_grid.py

Confirm current behavior:
1. app.js prefers composed state over decoded state.
2. renderer.js fetches calibration.json.
3. renderer.js already uses position.blanked partially.
4. fixtures.py decodes CH2 as control.sound_gated, and fixture state reaches LaserRenderer.update(), but renderer.js currently drops/ignores control in _primary()/_second().
5. renderer.js already renders second_pattern as a layer.
6. renderer.js currently implements CH15/CH16 off/position/speed in _sweep().
7. renderer.js currently uses sine-threshold strobe.
8. renderer.js treats CH10 dot mostly as count/brightness, not a true drawMode path.
9. renderer.js keeps fixture/aperture origins fixed while changing beam direction/endpoints.

Implement PR 1 only.

PR 1 scope:
1. Add docs/RENDERER_MOTION_MODEL_V1.md.
2. Add browser-local MotionState construction in static/motionState.js or an isolated renderer.js section.
3. Add a small compatibility bridge from MotionState into the current _drawFan() path.
4. MotionState must handle:
   - CH1 power/dimmer visibility
   - CH2 sound_gated visibility
   - CH6/CH7 position.blanked hard kill
   - CH6/CH7 static aim
   - CH15/CH16 off/position/speed modes
   - CH11 square-wave strobe gate
   - CH10 drawMode line-bright/line/dot
   - second_pattern per-layer state
5. Preserve current visual rendering as much as possible.
6. Add MotionState debug output/panel or console inspection.
7. Add a debug sound gate override.
8. Add warnings for approximate/unresolved zones, including CH15/CH16 waveform and CH19 wave deformation.
9. Add pure-JS tests for the MotionState builder.
10. Add visual smoke/regression baseline using calib/render_test.py or calib/render_grid.py.

Acceptance checks:
- CH1=0 draws nothing and MotionState killReason is power_off.
- CH6/CH7 center draws centered.
- CH6 or CH7 outside blank window draws nothing and killReason is position_blanked.
- CH2 sound_gated draws nothing unless debug override is enabled.
- CH15 position mode creates static movement contribution, not oscillator.
- CH15 speed mode creates oscillator and approximate/unverified waveform warning.
- CH16 position mode creates static vertical contribution, not oscillator.
- CH16 speed mode creates oscillator and approximate/unverified waveform warning.
- CH11 strobe uses square-wave gate.
- CH10 dot produces drawMode=dot.
- second_pattern active produces a second layer MotionState.
- second_pattern active does not break existing second-layer rendering.
- CH19 active produces approximate/unverified wave warning.
- No NaN/undefined fields in MotionState.
- Existing visuals are preserved as much as possible.
- Existing fixed fixture/aperture origins remain fixed.
- Visual smoke output from calib/render_test.py or calib/render_grid.py catches obvious regressions.

After implementation:
- run existing tests
- run MotionState unit tests
- run renderer smoke harness / screenshot baseline
- manually smoke test browser if available
- produce a report explaining:
  - files changed
  - how MotionState is inserted
  - how MotionState bridges into _drawFan()
  - which acceptance checks passed
  - what visual baseline was used
  - what remains approximate
  - what should be PR 2

Stop after PR 1.
Do not commit unless explicitly asked by the human operator.
```

---

## 21. Final Principle

The renderer is successful only if:

```text
beam motion feels plausible
animation timing is inspectable
visibility gates are respected
sound-gated cues do not lie
strobe snaps correctly
position blanking works
movement modes are not confused
source origins stay fixed
second-pattern layers are explicit
warnings remain honest
```

Once that is true, visual polish can begin.

Pretty wrong motion is still wrong. It just wastes GPU with better manners.
