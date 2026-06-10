# Step 6 — 2D Canvas Renderer: Implementation Plan

> **Historical (2026-06-09).** Original Step 6 polyline plan. Transform pipeline ideas are reused in PR-G2 (`docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md`). Primary view is aerial beams, not wall glyphs on canvas. See `docs/RENDERER_DOCS_INDEX.md`.

## Goal
Draw the two decoded laser fixtures in the browser on an HTML5 canvas, driven by
the SSE `decoded` feed, at 60fps with interpolation. **v1 target:**
representative pattern library + faithful color / brightness / strobe / position
/ movement / rotation / zoom / waves. Exact manufacturer pattern shapes are NOT
reproducible (not published) — we approximate with a stable representative set.

## Why canvas vector drawing
A galvo laser *is* a vector display (one bright dot swept along a path). So we
model each pattern as polylines in a normalized space, transform them, and draw
with additive blending + glow. The medium matches the fixture.

## Data contract (input)
The renderer consumes the SSE `decoded` array (one object per fixture) already
produced by `fixtures.decode_fixture`. Relevant fields per fixture:
```
power(bool), dimmer(0..1),
pattern:{kind,group,folder,selection:{index,play_all},size(0..255)},
position:{x(-1..1),y(-1..1),centered,blanked},
color:{mode,rgb|null,label,speed('off'|'forward'|'reverse'),animated,raw},
strobe:{on,speed(0..255)},
rotation:{z|x|y:{mode:'off'|'angle'|'speed',val}},
movement:{h|v:{mode:'off'|'position'|'speed',val}},
zoom:{mode:'off'|'size'|'speed',val}, waves:{axis:'off'|'x'|'y',speed},
second_pattern:{...}|null
```
No backend decode change needed for the renderer itself (but see "Backend" below).

## Architecture
- **`static/renderer.js`** (new) — `LaserRenderer` class: pattern library,
  transform pipeline, color/strobe, draw, and its OWN `requestAnimationFrame`
  loop (~60fps) with a local animation clock.
- **`static/app.js`** — on each SSE message calls `renderer.update(decoded)`;
  the inspector panels stay as-is below the stage.
- **`static/index.html`** — adds a `<canvas id="stage">` section at the top +
  `<script src="renderer.js">`.
- **`static/style.css`** — stage styling (black, full-width, aspect-locked).

### Stage layout
ONE combined stage canvas showing BOTH fixtures overlaid (realistic room view) —
each fixture is translated by its decoded `position`. This is the real visual
goal; the existing per-fixture "Decoded fixture state" panel remains for
validation. (Structure the draw so per-fixture tiles are an easy later toggle.)

## Pattern library (~20 shapes, static generators)
Each pattern is a pure function returning an array of polylines, each polyline an
array of `[x,y]` in `[-1,1]`. Patterns are pure SHAPE; all motion comes from the
transform pipeline (keeps patterns simple). Set: dot, dot-grid, h-lines,
v-lines, grid, cross, X, circle, concentric circles, square, triangle, star,
spiral, sine wave, zigzag, radial burst/fan, lissajous, tunnel (nested),
diamond, scatter.

**Selection mapping:** decoded `pattern.selection.index` (+ `group`) → a stable
library index, e.g. `lib[(index + groupBias) % lib.length]`. Deterministic so
the same DMX always yields the same shape. `folder=='animation'` can bias toward
the more dynamic shapes (spiral/lissajous/tunnel). Dot scan vs line scan
(`scan.mode`) can pick dot-rendering vs line-rendering of the same shape.

## Transform pipeline (per fixture, per frame)
Applied to every point, in order:
1. **size** (CH5, "large→small"): `scale = lerp(SMAX, SMIN, size/255)`.
2. **zoom** (CH17): `size` mode multiplies scale by `val/127`; `speed` mode
   pulses scale via `sin(clock * rate(val))`.
3. **rotation Z**: `angle` mode = fixed `val`; `speed` mode = `angle += rate*dt`.
   2D rotate.
4. **rotation X / Y**: pseudo-3D — X scales Y by `cos(ax)` (+ slight perspective
   shear), Y scales X by `cos(ay)`; speed accumulates over time.
5. **waves** (CH19): x-wave warps `y += A·sin(k·x + phase)`, y-wave warps
   `x += A·sin(k·y + phase)`; `phase` advances at wave speed.
6. **movement** (CH15/16): `position` mode = fixed offset from `val`; `speed`
   mode = oscillate offset over time.
7. **position** (CH6/7 → decoded x,y): absolute translate.
8. Map `[-1,1]` → canvas px with padding.

## Color
- solid `rgb` → stroke color, scaled by `dimmer`.
- animated (`rgb===null`): compute color from `color.mode` + `color.speed` on the
  local clock — `colorful`/`original_colorful` = hue cycle; `rgb_change` = R→G→B
  cycle; `flowing`/`gradient` = hue gradient ALONG the path (per-segment),
  offset animates. `speed==='reverse'` negates the rate; `'off'` freezes.
- brightness: multiply rgb by `dimmer` (and/or globalAlpha).

## Strobe
`strobe.on` → gate whole-fixture visibility with a duty cycle at a rate from
`strobe.speed` (local clock). Else steady.

## Blanking / off
Skip drawing a fixture when `!power`, `dimmer==0`, or `position.blanked`.

## Laser glow + trails
- `ctx.globalCompositeOperation = 'lighter'` (additive).
- Each polyline drawn in 2 passes: wide low-alpha halo + thin bright core
  (cheaper and more controllable than `shadowBlur`).
- **Motion trails:** instead of hard-clearing, fill the canvas each frame with
  `rgba(0,0,0,~0.30)` so prior frames fade → beam persistence (very laser-like).

## Interpolation (decouple visual smoothness from the ~37fps DMX)
- Keep `prev` + `next` decoded snapshots with timestamps; lerp CONTINUOUS fields
  (position x/y, size, dimmer, zoom val) by `(now-prevT)/(nextT-prevT)`.
- DISCRETE fields (pattern index, color mode, strobe on, scan mode) switch at the
  frame boundary (no lerp).
- SPEED-mode animations integrate on the renderer's own continuous clock (never
  interpolated) — so motion is smooth regardless of DMX cadence.

## Second pattern
If `second_pattern` present, render it as an additional layer on the same stage
with its own transforms/color (static-only group/select per the manual).

## Performance budget
~20 patterns ≤ a few hundred points each; ≤4 layers (2 fixtures × up to 2
patterns) at 60fps; additive 2-pass strokes; trail-fill instead of full clear.
Canvas 2D is sufficient. Avoid `shadowBlur` in the hot path. Cap canvas backing
resolution (e.g. devicePixelRatio clamped) to bound fill cost.

## Backend (optional, recommended — the deferred review item)
Add a single shared snapshot producer: one thread builds the SSE JSON at
`WEB_PUSH_HZ` into a cached string; SSE handlers send the cached frame. This
(a) decodes once per tick regardless of client count, (b) gives every client a
consistent, tear-free frame — which matters more now the renderer consumes it.
Small change in `webserver.py`; keep behavior identical otherwise.

## Test / acceptance
- Page loads, renderer initializes, no console errors; idle show → blank stage.
- With a live look: beams appear with correct color + brightness; move/rotate
  per channels; blink on strobe; blank when off/out-of-bounds; the stage visibly
  agrees with the "Decoded fixture state" panel.
- Validate against a moving look (positions/rotations changing) and a strobe look.

## REVISIONS FROM SUB-AGENT REVIEW (locked decisions — these override the above)

**Transform order (graphics H1):** size → zoom → **waves → rotZ → rotX/Y → movement** → position → px. Waves warp the pattern in its local frame BEFORE rotation so the ripple rotates with the shape.

**Dimmer (graphics H2):** apply dimmer by **scaling RGB** (`r*dimmer,…`), never via `globalAlpha`. Alpha is reserved solely for the halo/core glow ratio and the strobe gate (under `'lighter'`, alpha-dimming double-dims and breaks additive overlap).

**Trail fade (graphics H3 / arch L1):** each frame: set `globalCompositeOperation='source-over'`, fill `rgba(0,0,0,FADE)` (FADE≈0.35), THEN switch to `'lighter'` for all beam passes. Otherwise black is the additive identity and trails never decay. Periodic hard `clearRect` when a fixture is fully off, to flush 8-bit residue. Reduce trail strength (or hard-clear contribution) on a strobe OFF phase so blinks stay crisp.

**X/Y rotation (graphics M1):** real 3D — treat points as `(x,y,0)`, apply X/Y rotation as 3D rotations, then one perspective divide `f=d/(d-z)` (focal `d≈4`). Replaces cos-scale.

**Color (graphics M2/M3):** precompute a 256-entry **HSL hue LUT** once; animate by an integer offset (zero per-frame allocation — no `createLinearGradient`). Solid-color paths: one `strokeStyle` + one `stroke()` per glow pass. `flowing`/`gradient`/animated colors: render as **dot-scan** (filled dots colored from the LUT per point) — cheaper than per-segment strokes and more authentic.

**Scan (arch H4):** `scan.mode` has **three** values — `line-bright` (brighter core pass), `line` (normal stroke), `dot` (discrete dots). Use it to choose stroke-vs-dot rendering.

**Fields to consume (arch H4):** also read top-level `gradient` (CH18 raw 0–255, drives along-path hue spread — distinct from `color.mode==='gradient'`); acknowledge `control` (auto/sound) as out-of-scope (real fixture self-animates). `pattern.kind`/`folder` bias shape choice.

**size vs zoom (arch H5):** `pattern.size` = base scale (`lerp(SMAX,SMIN,size/255)`); `zoom` = modulation on top. `zoom.mode==='off'` → factor **1.0** (not 0). `zoom.size` (val 1–127) → factor `0.3 + val/127*1.2` ([0.3,1.5], can grow or shrink); `zoom.speed` pulses.

**Interpolation (arch H1/H2/H3) — render-behind buffer, NOT lerp-to-latest:**
- Keep a small queue of `{decoded, arrivalT}` stamped with **client** `performance.now()` at `onmessage` (payload has no timestamp). SSE cadence is **30Hz** (`WEB_PUSH_HZ`), not 37 — the DMX is ~37fps but the feed is 30Hz.
- Render at `renderTime = now - DELAY`, `DELAY≈50ms` (~1.5× the 33ms frame). Find the two snapshots bracketing `renderTime`, lerp continuous fields by the clamped `[0,1]` fraction. Underrun (no newer frame) → hold last (fraction=1), don't extrapolate. Cap queue size (drop stale) for backgrounded tabs.
- First frame / SSE reconnect: `prev=next` (no lerp across the gap).
- **Visibility gating:** draw if `prev.power || next.power` (so fade-out isn't truncated); `dimmer` lerps to drive the fade; `position.blanked` is a HARD gate on `next` (snap, never lerp). Discrete fields (pattern index, color mode, strobe.on, scan.mode) switch at the boundary.

**Speed→rate (arch M1):** one module-level `RATES` block. Normalize rot/move/zoom/wave speed as `s=val/128`; **strobe is raw 0–255** → `s=speed/255` (different!). Rotation-Z speed has no direction bit (fixed sign). **Color speed exposes only off/forward/reverse — no magnitude** → fixed hue rate × sign.

**play_all / null index (arch M2):** `index===null` (dynamic CH4≤1, `play_all`) → cycle the library on the local clock; guard against `NaN`.

**Second pattern (arch M3):** has its OWN full transform set (position CH23/24, color, scan, strobe, rotation, movement, zoom, gradient, waves) — run the SAME pipeline on it with its own fields (not a stripped one), using its own position.

**Backend shared producer (arch M4): DO IT NOW.** One producer thread builds the SSE JSON once per tick into a shared latest-frame (guarded by a `Condition`); `/stream` handlers send the cached frame. Removes per-client decode + phase-skew, gives every client identical tear-free frames. Keep payload identical.

**Robustness (arch L3):** resize handler (backing store = cssSize × `min(DPR,1.5)`, aspect letterbox so positions don't distort, max ~1500px wide); clamp per-frame `dt` to ≤0.05s and rebaseline clock on `visibilitychange` (rAF throttles when hidden); `renderer.update()` only STORES the snapshot — all drawing stays in the renderer's own rAF (never blocks app.js).

**Stage:** one combined overlaid stage (both fixtures at their decoded positions); identical mirrored content overlapping → brighter is physically correct. Per-fixture tile toggle deferred.

## Risks / open questions
- Pattern-shape fidelity is approximate by design (v1). Acceptable per plan.
- Pseudo-3D X/Y rotation is a visual approximation, not true projection.
- Exact mapping of pattern index→shape is arbitrary but stable; fine for preview.
- Strobe/zoom/movement "speed" → rate scaling constants need tuning by eye.
