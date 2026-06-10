# Renderer Wall → Aerial Plan V1 — Capture-Driven Beam Simulation

**Date:** 2026-06-09 (rev 3 — ChatGPT review additions + Brandon decisions)  
**Status:** Active primary renderer implementation plan (supersedes fan-geometry PR-D)  
**Owner (orchestrator + checkpoint reviewer):** Opus  
**Implementer:** Codex (gpt-5.3-codex)  
**Routine reviewer:** gpt-5.5-high  
**Checkpoint reviewer:** Opus (PR-G1b motion tracks, PR-G2 wall engine, PR-G3 integration)

**Document index:** `docs/RENDERER_DOCS_INDEX.md`

---

## 0. Mission

Simulate a **real DMX galvo laser** the way Brandon intended:

1. **Internal state:** what the fixture is drawing on the wall — from **8,324 stills** (shape) and **8,324 motion clips** (how it moves).
2. **Output view:** what the **crowd sees** — straight volumetric beams in haze — derived from rig geometry, not guessed fan bins.

The canvas shows **aerial beams only**. Wall figures are **simulation state**, not displayed images (optional dev overlay only).

```text
DMX CH1-19 vector
    → capture lookup (exact vector match from index)
    → static shape from still.jpg (topology)
    → timed motion from motion_analysis_* / video (wall figure over time)
    → DMX modifier residual (only where capture vector differs or gates apply)
    → rig projection (aperture → wall hits → rays)
    → aerial beam draw (haze, glow, strobe, color)
    → canvas (crowd view)
```

This plan **supersedes PR-D** as a merge target (§9). PR-A / PR-B / PR-C remain valid and attach to the new draw path. PR-E runs after PR-G. PR-F stays **SUSPENDED** until PR-G + H1–H4.

---

## 1. Corpus truth (what we actually have)

**8,324 captures** in `captures/fixture_model/manifest.jsonl`. Each folder is a **full motion package**, not a still-only reference:

| Per-capture artifact | Typical content | Used today |
|---|---|---|
| `still.jpg` (or `still_color.jpg`) | Wall figure at one instant | **Not** wired to renderer |
| `video.mp4` (or `video_color.mp4`) | ~3 s clip @ ~60 fps | **Not** wired to renderer |
| `motion_analysis_60fps/` | ~180 JPEGs extracted from video (320px-wide) | **Not** wired to renderer |
| `motion_analysis_30fps/` | Downsampled frame sequence | **Not** wired to renderer |
| `analysis.json` | 29-field **summary** over the clip | Index + thin renderer overlay |
| `metadata.json` | DMX CH1–19, phase, exposure track | Manifest join only |

Post-capture audit: sampled folders contain **video + still + metadata + analysis** (`docs/FIXTURE_MODEL_POST_CAPTURE_ANALYSIS.md` §4.3).

The **analyzer already processes motion over time** (`calib/dense_cue_breakpoints.py`, orchestrator pipeline): per-frame bright-pixel centroid, bbox, PCA angle, period estimate, strobe crossings, `motion_type` classification. That work runs on every clip — then **collapses to scalars** in `analysis.json`. The frame sequences and time series are **discarded before the renderer**.

```text
TODAY (broken):
  8k stills + 8k motion clips
        → analyze → analysis.json (x_range, loop_duration, motion_type, …)
        → capture index → renderer fan + scalar overlay

TARGET (this plan):
  8k stills  → static wall shape (topology per vector)
  8k clips   → motion shape track (wall figure vs time)
        → index artifacts (read-only derived from captures/, not mutating captures/)
        → renderer plays back capture motion, projects rays, draws aerial beams
```

`data/fixture_model.json` `base_looks` point at representative capture paths but store **no drawable geometry or motion tracks**. `setup_geometry.json` + `analysis_geometry.json` provide rig math the renderer has not used for projection.

---

## 2. Why the current renderer fails

| Current path | Problem |
|---|---|
| `decode_36ch` + `CAL._patternShape()` | Synthetic fan bins; ignores 8k stills |
| `_drawFan()` | Rigid ray fan; ignores 8k motion clips |
| Capture index | Scalars only (strobe, color, motion_type); **no shape, no frame track** |
| PR-C motion_type | Gates sweep vs strobe correctly but **does not drive wall figure animation** |
| PR-D (unmerged) | Fan spread/count from scalars — wrong abstraction |

Brandon has **both** evidence types the simulator needs. The failure is **consumption**, not collection.

---

## 3. Target architecture

### 3.1 Dual authority: still + motion

```text
┌──────────────────────────────────────────────────────────────────┐
│  STATIC SHAPE AUTHORITY (PR-G1)                                   │
│  still.jpg → wall-space contour / polyline / cluster topology     │
│  Key: exact CH1-19 vector (+ exposure track when paired)          │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  MOTION SHAPE AUTHORITY (PR-G1b)                                  │
│  motion_analysis_60fps/* (or re-extract from video.mp4)           │
│  → per-frame wall figure OR compact track (centroid+bbox+contour) │
│  → playback rate from loop_duration + periodic_motion gates       │
│  Key: same vector as static; phase from clip alignment            │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  ANALYSIS SCALARS (existing index — classification + gates)       │
│  motion_type, strobe_hz, duty, dominant_colors, quality flags     │
│  Use for: motion CLASS, strobe gate, fallback rate, tier labels   │
│  Do NOT use as sole motion driver when frame track exists           │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  DMX MODIFIER RESIDUAL (PR-G2)                                    │
│  Interpolate/nudge only when live DMX ≠ captured vector           │
│  Or when modifier not isolated in capture program                 │
│  Fallback oscillators labeled DECODER_FALLBACK / APPROXIMATE      │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  RIG PROJECTION (PR-G3)                                           │
│  analysis_geometry + setup_geometry → aperture rays → aerial      │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  AERIAL DRAW (visible) — straight beams, additive haze            │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Authority map (per parameter)

| Parameter | Primary authority | Secondary / fallback |
|---|---|---|
| **Shape topology** | Still contour / clusters (PR-G1) | Atlas family preset → `MODEL_COMPOSED` → decoder |
| **Shape over time** | Motion frame track (PR-G1b) | Scalar-driven oscillator using `motion_type` + `loop_duration` → `MEASURED_PARAM` (approx) |
| **Color** | `dominant_colors[]` (PR-C) | decoder |
| **Strobe on/Hz/duty** | `strobe_frequency_hz`, `duty_cycle` (PR-C) | CAL strobe |
| **Motion class** | `motion_type` (PR-C) — gates what animation means | decoder |
| **Motion rate** | Track playback fps × `loop_duration` when `periodic_motion` + confidence | CH speed / CAL |
| **Wave (CH19)** | **Wall figure oscillation from motion track** (straight rays, aim changes) | sine on wall points labeled APPROXIMATE |
| **Sweep (CH15/16)** | **Centroid path from motion track** | sine sweep labeled APPROXIMATE |
| **Direction** | Track displacement sign when confident; else `motion_direction` ≥ 0.6 | unsigned |
| **Ray origin** | `analysis_geometry` + `setup_geometry` | CAL fractions |
| **Beam count** | Points/clusters in shape + track | never fan `density_beam_count_derived` on hit path |
| **Second pattern** | Decoder + warning (CH20–36) | unchanged |

Headline tier = MIN across visible parameters (PR-A).  
When frame track drives motion: tier **`MEASURED_PARAM`** (unvalidated until `validation.pass>0`).  
When oscillator fallback used while track exists: warning **`motion_track_bypassed`**.

### 3.3 What motion tracks must capture (physics alignment)

Real laser behavior Brandon described (e.g. CH19):

- **Beam rays stay straight** in haze.
- **Galvo aim** (wall figure) oscillates — often sinusoidal — over time.
- Motion track records **wall figure motion**; projection derives **beam direction changes**, not curved ray polylines.

The quarantined CH19 `fixed` fan-endpoint hack is **not** the target model. Target: deform **wall-space shape** from capture frames → project straight rays.

---

## 4. NON-NEGOTIABLES

1. **DO NOT trust SoundSwitch cue names/tags** — DMX vector only for cue enumeration.
2. Do NOT mutate `data/fixture_model.json` or any file under `captures/` (read-only evidence).
3. Derived artifacts (`shape_library_v1.json`, `motion_tracks_v1.json`, index extensions) are written under `artifacts/renderer/` only.
4. Do NOT convert to WebGL. Canvas 2D.
5. Do NOT remove `second_pattern` rendering.
6. Do NOT display wall figure as primary view (aerial only; `?wallDebug=1` dev overlay OK).
7. Do NOT merge PR-D fan geometry as-is (§9).
8. Do NOT treat `analysis.json` scalars as a substitute for frame tracks when tracks exist for that vector.
9. Every PR: implementation report, tests/smoke, review artifact.
10. No visual polish before shape + motion playback + projection correctness.

---

## 5. Evidence inputs (committed + local)

| Asset | Count / scope | PR-G role |
|---|---|---|
| `manifest.jsonl` | 8324 rows | Vector enumeration, folder join |
| `still.jpg` per folder | ~8324 | **PR-G1** static shape |
| `video.mp4` per folder | ~8324 | Source of truth for re-extract if needed |
| `motion_analysis_60fps/` | ~180 frames × clip | **PR-G1b** primary motion input |
| `motion_analysis_30fps/` | downsampled | Fallback / cross-check |
| `analysis.json` | per folder | Classification, strobe, quality gates, fallback rates |
| `analysis_geometry.json` | 1 rig file | Wall ROI, boxes, `px_per_inch` |
| `setup_geometry.json` | 1 rig file | Fixture-to-wall, aperture layout |
| `base_looks` in fixture_model | CH3/CH4 → capture path | Seed keys for family fallback |
| `phase6_cue_validation/` | **175** cue folders (durable) | **Primary cue-vector motion** for SoundSwitch looks |
| `data/soundswitch_cue_motion_coverage.json` | dense pass summaries | Cue timing metadata; not video |
| `capture_index_v1.json` | runtime | Extend with shape_ref + motion_track_ref |
| `WALL_CH3_LOOK_ATLAS.md` | 12 families | Smoke acceptance matrix |

**Exposure tracks:** `geometry_motion` vs `color` — index must pair or select correct still/track per vector variant.

### 5.1 Dense 118 vs Phase 6 — corrected (2026-06-09)

Two different cue-timing sources are often conflated:

| Source | Location | Status on disk | What it provides |
|---|---|---|---|
| **Dense breakpoint pass** (118 exact cue captures) | `/tmp/vln_dense_cue_breakpoints_20260605_200426` | **Absent** — ephemeral `/tmp` not present on this machine | Was 118× video + 60 fps analysis for breakpoint timing |
| **Derived dense analysis** | `data/soundswitch_cue_motion_coverage.json` | **Present** in repo | Statistics + per-cue motion summaries from that pass (no video) |
| **Phase 6 cue validation** | `captures/fixture_model/phase6_cue_validation/cue_relevant/` | **Present** — 175 folders | Full package: `video.mp4`, `still.jpg`, `motion_analysis_60fps/`, `analysis.json` |
| **Main corpus** | `captures/fixture_model/` (8324 rows) | **Present** | Exhaustive CH sweeps + phase3 combos |

`fixture_model.json` records `phase0_validated_existing_dense_rows: 118` with `captured_exact_vectors_source: "phase0_record_dense_root_absent"` — the orchestrator **cited** the prior dense count when `/tmp` was already gone; it did **not** mean cue timing evidence is unavailable.

**Plan policy:**

1. **PR-G1b cue tracks:** build from **phase6** folders first (175 SoundSwitch cue vectors), then exact vector hits anywhere in the 8324 manifest.
2. **Timing metadata:** join `soundswitch_cue_motion_coverage.json` for dense-pass classifications where useful; do not require the old `/tmp` tree.
3. **H4 recapture:** only vectors that **fail track quality gates** after G1b+H1 — not a blanket “restore 118.”
4. **Optional:** if Brandon finds the dense folder on Time Machine / another disk, copy to a stable path and run a one-off ingest — **supplemental**, not blocking.

**Known corpus gaps (honest):**

- Dense **`/tmp` raw media** absent; **substitute:** phase6 (175) + 8324 corpus + coverage JSON summaries.
- ~**9** SoundSwitch cue vectors may lack a phase6 folder (184 cues − 175 captures) — index build should list gaps; H4 targets gaps only.
- Analyzer stores centroid/bbox time series internally but **not** full contours in `analysis.json` — PR-G1b extracts from `motion_analysis_*` JPEGs.
- `fast_motion_timing_inferred: true` on many wave/spin clips — label APPROXIMATE; track autocorr (PR-H1) preferred over scalar guess.
- `wave_direction_requires_visual_review` — direction may need H2 visual sign-off.
- Timed-motion `/tmp` pass (`vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855`) also absent; phase1/1.5 CH19 sweeps in main corpus substitute for isolated timing probes.

**Out of scope v1:** firmware ILDA point order, 15 kpps blanking, sub-5% homography claims, CH20–36 capture.

---

## 6. PR breakdown (PR-G1 → PR-G4)

### PR-G1 — Static shape authority (stills) [routine: gpt-5.5]

**Goal:** 8k stills define wall figure **topology**, not `_patternShape()`.

- Build-time: extract bright-pixel contour / skeleton / clusters from each `still.jpg` → normalized wall-space polylines in aperture ROI (`analysis_geometry`).
- Output: `artifacts/renderer/shape_library_v1.json` (+ index fields `shape_ref`, `shape_point_count`, `shape_evidence: still`).
- Key: exact CH1–19 vector (+ exposure track).
- Family fallback: nearest CH3/CH4 atlas representative, labeled `MODEL_COMPOSED`.
- Runtime: load shape for vector hit; diagnostics show shape tier + point/cluster count.
- Renderer: internal wall-space only (no aerial projection yet).

**Accept:** CH3=48 → two-cluster topology (dual-dot). CH3=32 → line topology. Not 8-ray fan bin.

---

### PR-G1b — Motion shape tracks (clips) [CHECKPOINT: Opus]

**Goal:** 8k motion captures drive **wall figure over time**, not scalar oscillators on a fan.

**Capture priority for cue vectors:**

1. `phase6_cue_validation/cue_relevant/` (175 SoundSwitch cues — durable, full motion)
2. Exact vector match anywhere in 8324-row manifest
3. Nearest combo / base fallback (PR-H2 — deferred to H pass for non-cue vectors)

- Build-time: for each capture with usable `motion_analysis_60fps/` (or extract from `video.mp4`):
  - Per frame: bright-pixel contour **or** compact `(centroid, bbox, optional contour hash)` in wall-normalized coords.
  - Store clip metadata: frame count, analysis fps, `loop_duration_estimate`, phase anchor frame.
  - Compress: keyframes every N frames + deltas, or full sequence for high-priority atlas families first.
- Output: `artifacts/renderer/motion_tracks_v1.json` (or chunked shards) + index fields `motion_track_ref`, `motion_track_frames`, `motion_track_evidence: motion_analysis_60fps`.
- Quality gates: skip or flag `blank`, `usable_evidence: false`, `geometry_clipped_low` per existing analysis.
- Runtime: at `renderTime`, sample track frame (loop when `periodic_motion` + confidence ≥ 0.5); interpolate between frames.
- **Do not mutate** `captures/` — read frames from disk at build time only.

**Accept:**

- `cue_023_green_solid_sinewaves`: playback shows periodic wall deformation; aerial rays straight, aim oscillates.
- CH19 sweep captures: track period correlates with `loop_duration_estimate` within labeled tolerance.
- Static captures (`motion_type: static`): track degenerates to single frame (still equivalent).

**Review focus:** track compression fidelity, loop seam, exposure-track pairing, strobe vs motion disambiguation on brightness.

---

### PR-G2 — Wall-space engine + playback [CHECKPOINT: Opus]

**Goal:** Combine static shape + motion track + DMX residual; animate internal wall figure.

- Playback pipeline:
  1. Load static shape (G1) as base topology when track lacks contour detail.
  2. Apply motion track transform (G1b) — **primary** animation source.
  3. Apply DMX modifier residual (size, zoom, rot, position) only for deltas not in captured vector.
  4. When no track: fallback using `motion_type` + gated scalars (labeled APPROXIMATE).
- CH19 / wave: deform wall points from **track**; project straight rays (not fan-endpoint sine hack).
- CH15/16 sweep: prefer **centroid path from track** over `_periodicSweepOffset` sine.
- CH3≥128 macros: loop motion track (required — macros are inherently temporal).
- CH10: dot vs line on wall segments.
- Dev overlay: `?wallDebug=1` shows internal wall figure (not primary view).

**Accept:** `strobe_gate` animates visibility only, no spurious translation. Wave cues show straight-beam sinusoidal aim from track.

---

### PR-G3 — Rig projection + aerial beam draw [CHECKPOINT: Opus]

**Goal:** Crowd view from time-varying wall figure + rig geometry.

- Reuse PR-D salvage: `analysis_geometry` SSE, aperture box origins (§9).
- For each wall hit point on figure: ray from aperture → point → aerial beam segment.
- Replace `_drawFan` when shape+motion hit; keep `_drawFan` as `DECODER_FALLBACK`.
- Deprecate on hit path: `density_beam_count_derived`, fan spread from `angle_range_deg`.
- Strobe/color/MotionState from PR-A/B/C on projected beams.

**Accept (smoke):**

| Vector / cue family | Expectation |
|---|---|
| CH3=48 dual-dot | Two beam pairs from wall clusters |
| CH3=32 + CH6 pan | Beams follow wall line translation |
| `cue_001_off` (strobe_gate) | Strobing beams, no bogus sweep |
| CH19 wave cue | Straight rays, sinusoidal aim from **track** |
| CH3=128 U-wave | Macro loop from motion track |

---

### PR-G4 — Integration, diagnostics, harness [routine: gpt-5.5]

- Diagnostics: tiers for `shape_static`, `shape_motion_track`, `projection`, `motion_playback`, color, strobe.
- Warnings: `motion_track_missing`, `motion_track_bypassed`, `scalar_fallback`, `fast_motion_timing_inferred`.
- `calib/render_grid_capture.py`: load shape + motion refs; atlas + phase6 cue grid.
- Document deprecated PR-D fan fields.

**Accept:** Headline never `EXACT_CAPTURE_RENDER_AUTHORITY` while `validation.pass=0`. Per-parameter table shows still vs track vs fallback sources.

**Mandatory additions (locked — external review 2026-06-09):**

1. **CI / test assertion:** On any capture-hit path where `shape_ref` exists, the renderer must **not** call `_patternShape()`. Temporary fallbacks must fail tests, not silently persist.
2. **Fixture-vector debug panel:** Show `vector_key`, `shape_ref`, `motion_track_ref`, `track_source`, `projection_source`, `fallback_reason` (extend Phase 1 diagnostics in `static/app.js`).
3. **Atlas-first golden fixtures:** 12 CH3 families × still shape × one motion example each (`WALL_CH3_LOOK_ATLAS.md`). Do **not** begin G1/G1b validation with full 8k batch.
4. **`wallDebug` side-by-side harness:** Captured frame strip / video scrub beside simulated wall-space playback (`?wallDebug=1`). Catches motion-track errors before aerial projection hides them.
5. **Per-cue fallback budget:** For each smoke cue, define which parameters may remain `DECODER_FALLBACK`. Unexpected shape or motion fallback fails the harness.

---

## 7. Sequencing

```text
DONE (merge target):    PR-A, PR-B, PR-C — honesty/motion-labeling foundation only
SUPERSEDED:             PR-D
ACTIVE:                 PR-G1 → PR-G1b → PR-G2 → PR-G3 → PR-G4
THEN:                   PR-E
SUSPENDED:              PR-F
```

PR-G1 and PR-G1b may share a branch but **separate reports/reviews**. G1b is Opus checkpoint — highest risk.

Recommended: atlas families first in G1/G1b (12 CH3 families), then full corpus batch job.

---

## 8. PR-D supersession

| PR-D artifact | Disposition |
|---|---|
| `analysis_geometry` SSE | **Keep** → PR-G3 |
| `x_range_norm_aperture` | **Keep** → extent labels only |
| `derive_beam_count()` / fan spread | **Deprecate** on hit path |
| Opus PR-D review | **Cancelled** → review G1b, G2, G3 |

---

## 9. Smoke / validation protocol

```text
# Build shape + motion artifacts (after G1/G1b)
python3 tools/shape_library_builder.py      # new
python3 tools/motion_track_builder.py       # new
python3 tools/build_capture_index.py

# Unit tests
python3 -m pytest tests/test_shape_extraction.py tests/test_motion_track_builder.py
node tests/test_renderer_motionstate.js

# Grid — include static + motion cues
python3 calib/render_grid_capture.py /tmp/vln_pr_g.html \
  cue_023_green_solid_sinewaves cue_027_purple_dazzled_waves \
  cue_dual_dot cue_line32 cue_001_off

# Headless aerial screenshot
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --screenshot=/tmp/vln_pr_g3.png --window-size=900,760 --virtual-time-budget=5000 \
  file:///tmp/vln_pr_g.html
```

### Human validation (H1–H4)

- **H1:** Cue names non-authoritative  
- **H2:** Wave/sweep direction on low-confidence cues  
- **H3:** Atlas family topology + motion plausibility (still **and** clip)  
- **H4:** Recapture only for vectors **without** phase6/corpus track or failing quality gates — not blanket dense restore

### Look-family exit matrix (minimum)

Pass/fail per family in `WALL_CH3_LOOK_ATLAS.md`: static shape correct (G1) **and** motion plausible for timed families (G1b). 12 families × {shape, motion} = exit gate for plan v1.

---

## 10. Files agents may touch

**New build tools**

- `tools/shape_library_builder.py` — still → wall polylines  
- `tools/motion_track_builder.py` — motion_analysis_60fps → tracks  
- `tools/capture_index_builder.py` — extend joins  

**New artifacts**

- `artifacts/renderer/shape_library_v1.json`  
- `artifacts/renderer/motion_tracks_v1/` (or single JSON + shards)  
- `capture_index_v1.json` — regenerate  

**Runtime**

- `capture_index_runtime.py`, `webserver.py`, `static/renderer.js`  
- Optional: `static/wall_engine.js`, `static/motion_playback.js`, `static/beam_projection.js`  
- `calib/render_grid_capture.py`, `static/app.js`  

**Tests**

- `tests/test_shape_extraction.py`, `tests/test_motion_track_builder.py`  
- `tests/test_renderer_motionstate.js` (extend)  

**Do not touch:** `captures/**` contents, `data/fixture_model.json`, `calibration.json` (PR-F deferred).

---

## 11. Review model

| PR | Reviewer |
|---|---|
| PR-G1 static shape | gpt-5.5-high |
| PR-G1b motion tracks | **Opus checkpoint** |
| PR-G2 wall playback | **Opus checkpoint** |
| PR-G3 projection + aerial | **Opus checkpoint** |
| PR-G4 integration | gpt-5.5-high |

Extend forensic review with:

- Q13: Is static shape from still.jpg used as topology authority?  
- Q14: Is motion from frame track (not scalar-only) when track exists?  
- Q15: Are aerial beams straight rays from projection (not fan bins / spaghetti)?  

---

## 12. Realistic outcomes (honest)

With **8k stills + 8k motion clips** wired as specified:

| Category | Expected match |
|---|---|
| Static shape families | High — exhaustive CH3/CH4 atlas |
| Strobe + color | High — PR-C + brightness track |
| Sweep / pan / tilt | High when track + motion_type agree |
| CH19 / wave | Good — track-driven; phase may need H2 |
| CH3≥128 macros | Good — requires G1b loop playback |
| Fast spin / aliased timing | Moderate — label APPROXIMATE |
| Modifier combos not isolated in capture | Moderate — DMX residual + fallback |
| Second pattern, CH2 | Unchanged — decoder + warning |
| Haze photoreal | Deferred — shape/motion first |

This plan fixes the **simulation model** and **uses the full corpus**. It does not promise pixel-identical haze on every cue without H3/H4 and PR-F tuning after geometry is correct.

---

## 13. Success criteria (plan exit)

Brandon loads live cues and sees:

1. **Shape** from stills — dots, lines, rings recognizable in aerial view.  
2. **Motion** from clips — wave/sweep/macros animate from tracks, straight beams.  
3. **Color/strobe** from capture analysis (PR-C).  
4. Diagnostics distinguish still authority, motion-track authority, and fallback.  
5. Atlas look-family matrix (§9) passed for shape; motion passed for timed families.  
6. No false `EXACT_CAPTURE_RENDER_AUTHORITY` while `validation.pass=0`.

---

## 14. Phase 2 hardening (PR-H) — after PR-G4 exit

PR-G fixes the simulation model and wires stills + motion tracks. **PR-H** tackles the residual gaps that PR-G labels `APPROXIMATE` but does not fully resolve. Run after atlas look-family matrix (§9) passes for G1–G4.

**Sequencing:**

```text
PR-G1 → G1b → G2 → G3 → G4   (core simulator — required first)
PR-H1 → H2 → H3 → H4         (hardening — can parallelize H3/H4 after H1 design)
PR-E                            (diagnostics — absorb H-tier labels)
PR-F                            (physical calibration — still last)
```

---

### PR-H1 — Fast motion timing fidelity [routine: gpt-5.5 + targeted recapture optional]

**Problem:** Many wave/spin clips have `fast_motion_timing_inferred: true` and/or low `loop_confidence` because 30→60 fps analysis and the `0.07s` period floor alias fast motion (`FIXTURE_MODEL_PROGRAM.md`).

**Strategy:** Tracks are primary; **refine playback rate from the track itself**, not only `loop_duration_estimate`.

**Build-time (`tools/motion_track_builder.py` extend):**

1. Prefer **`motion_analysis_60fps/`** over 30fps when both exist.
2. After track extraction, compute **track-native period**:
   - Autocorrelation on centroid displacement magnitude (or bbox area for strobe-like gates).
   - Peak picking with Nyquist cap at `analysis_fps / 2` (30 Hz at 60 fps).
3. Emit index fields:
   - `motion_track_period_s`, `motion_track_period_confidence`
   - `motion_rate_source: track_autocorr | analysis_loop | ch_speed_fallback`
4. **Reconcile** with `analysis.json`:
   - If `|track_period - loop_duration| / track_period > 0.15` and track confidence ≥ 0.6 → **track wins**, flag `analysis_loop_mismatch`.
   - If `fast_motion_timing_inferred` and track confidence ≥ 0.5 → use track period, tier stays `MEASURED_PARAM`, warning `fast_motion_track_derived`.
   - If both low confidence → `APPROXIMATE` + CH19/CH15/16 speed fallback.

**Corpus use (no new capture required for v1):**

- **Priority 1:** `phase6_cue_validation/cue_relevant/` — 175 cue vectors with full motion packages.
- Re-build tracks from **60 fps** frame folders for CH19 / CH12–16 sweeps in phase1 + phase1.5.
- Cross-check timing metadata in `data/soundswitch_cue_motion_coverage.json` (dense-pass summaries).
- Cross-check against **phase1 `CH19_x_y_wave/`** sweeps (isolated CH19 vs speed).

**Optional recapture (H4 gate — Brandon physical time):**

- Vectors **missing** from phase6 + manifest with no acceptable track quality — not “restore 118.”
- Atlas families (wave, spin, fast sweep): **~20–40 vectors** only if track autocorr fails quality gate on >30% of family.

**Accept:** `cue_023_green_solid_sinewaves` playback rate within ±10% of visible loop in side-by-side wallDebug vs `video.mp4` scrub (human H3 spot check). Diagnostics show `motion_rate_source: track_autocorr`.

---

### PR-H2 — Modifier combo resolution [CHECKPOINT: Opus]

**Problem:** Live SoundSwitch cues combine CH3/CH4 base + many modifiers (CH5–19). Not every combo has an exact capture vector; phase1 is mostly single-channel sweeps.

**Key asset:** Index already includes **`phase3_composition: 3664`** combo captures (pair grids + orientation grids on real bases). Combo audit docs (`COMBINATION_CHANNEL_AUDIT.md`) define representative modifier stacks.

**Resolution order (runtime lookup):**

```text
1. EXACT_VECTOR_MATCH     → shape + track from that folder (preferred_capture_id)
2. COMBO_CAPTURE_NEAREST  → same CH3/CH4 base; minimize L1 distance on changed CH5–19
                           among phase3_composition + phase6 cue captures
3. BASE + MODIFIER_STACK  → static shape from base_looks still; motion track from
                           isolated modifier capture applied as DMX residual (G2 engine)
4. DECODER_FALLBACK       → labeled; no EXACT badge
```

**Build-time (`tools/capture_index_builder.py` + new `tools/combo_resolver.py`):**

- For each SoundSwitch cue vector in index: precompute `combo_match`:
  - `match_tier: exact | combo_nearest | base_plus_residual | none`
  - `matched_capture_id`, `matched_phase`, `channel_delta` (live − matched on CH5–19)
  - `residual_channels: [CH6, CH17, …]` when tier = base_plus_residual
- Index **phase3** rows at full weight — do not collapse combo vectors into single-channel buckets incorrectly (forensic Q9 caveat: surface `bucket_cross_phase_provenance` in diagnostics).

**Runtime (PR-G2 engine):**

- Load matched track; if `channel_delta` non-empty, apply **residual transforms** only for channels that differ from matched capture baseline (document order in G2 transform stack).
- When residual channels include fast motion (CH19, CH12 speed): prefer **residual channel’s isolated track** blended or sequenced — not scalar guess.

**Accept:**

- Combo audit vectors (ring_zoom, line_offset, uwave_spin) resolve tier ≥ `combo_nearest` or exact.
- Diagnostics show `combo_match_tier` + `residual_channels`; headline tier reflects weakest param.

**Human (H3):** Spot-check 10 combo audit stills vs aerial render.

---

### PR-H3 — Direction authority [routine: gpt-5.5 + human H2 workflow]

**Problem:** 183/184 cue hits have `motion_direction_confidence < 0.6`; wave cues use `wave_direction_requires_visual_review`. Numeric regression on centroid failed for symmetric figures.

**Strategy:** Derive direction from **motion tracks** first; human review writes **index-only overrides** (never mutate `captures/`).

**Build-time:**

1. From track centroid `(x,y)` over one loop:
   - Horizontal sweep: sign of `Δx` peak-to-peak or regression slope → `left` / `right`.
   - Vertical sweep: sign of `Δy` → `up` / `down`.
   - Wave: axis from CH19 decode (x vs y wave); sign from dominant displacement axis.
2. Emit:
   - `motion_direction_derived`, `motion_direction_derived_confidence` (0–1)
   - `motion_direction_source: track_displacement | analysis_regression | visual_review_override`
3. **Confidence rules:**
   - Symmetric figures (ring, dual-dot): require larger displacement threshold; if below → `confidence: 0`, flag `H2_REQUIRED`.

**Human H2 workflow (Brandon — minimal):**

1. Harness exports **contact sheet**: 6-frame strip from `motion_analysis_60fps` for each `H2_REQUIRED` cue family representative (~20–30 sheets, not 184).
2. Brandon marks direction on sheet (or confirms track-derived sign).
3. Agent writes overrides to `artifacts/renderer/direction_overrides_v1.json` keyed by vector hash.
4. Index join: override beats track beats analysis when `direction_source: visual_review`.

**Accept:** Forensic Q3 class cues (horizontal sweep with CH15 speed) show consistent pan sign vs wall capture; zero silent default `h=1,v=1` when track-derived confidence ≥ 0.6.

---

### PR-H4 — Track storage, compression, lazy load [routine: gpt-5.5]

**Problem:** 8324 clips × ~180 frames × contour data cannot ship inline in SSE or a single JSON.

**Strategy:** Sharded artifacts + client lazy fetch; SSE carries **refs only**.

**Build-time layout:**

```text
artifacts/renderer/motion_tracks_v1/
  manifest.json              # vector_hash → shard, offset, frames, codec
  shards/
    shard_000.msgpack.gz     # bucket of tracks

artifacts/renderer/shape_library_v1/
  (same shard pattern)
```

**Track codec (v1):**

- **Keyframe + delta:** every 3rd frame full `{centroid, bbox, contour_rle}`; intermediate frames linear centroid interp.
- **Static clips:** single keyframe, `frames: 1`.
- Target: **< 4 KB median** per vector track (measure in H4 report; adjust keyframe spacing).

**Runtime:**

- `capture_index_v1.json` entries: `motion_track_ref`, `shape_ref` (string IDs only).
- New HTTP routes in `webserver.py`:
  - `GET /artifacts/motion_track/{ref}` — `Cache-Control: immutable` + content hash in filename for browser cache.
- `app.js` / renderer: fetch track on first vector hit; LRU cache in memory (cap ~50 tracks).
- **SSE payload unchanged in size** — no track blobs on `/stream`.

**Accept:**

- SSE snapshot size increase from G4 **< 5%** vs today (refs only).
- Cold-load fetch + render for a new cue **< 200 ms** on localhost for one track shard.
- Unit test: round-trip keyframe codec vs full frame list on 10 sample captures.

---

## 15. PR-H summary table

| PR | Targets | Primary inputs | Human gate |
|---|---|---|---|
| **H1** Fast timing | `fast_motion_timing_inferred`, rate aliasing | 60fps tracks, CH19 sweeps | H3 spot loop rate |
| **H2** Modifier combos | Non-isolated cue vectors | phase3_composition (3664), combo audit | H3 combo stills |
| **H3** Direction | 183/184 low-confidence | Track displacement, overrides file | **H2** contact sheets |
| **H4** Index size | SSE bloat, load time | Sharded msgpack, lazy HTTP | None (automated budgets) |

---

## 16. Updated realistic outcomes (after PR-H)

| Category | After PR-G4 | After PR-H |
|---|---|---|
| Fast wave/spin timing | APPROXIMATE common | Good when track autocorr confident |
| Modifier combos | Residual fallback common | Good for phase3-covered stacks |
| Sweep direction | Often unsigned | Track-derived or H2 override |
| Index/SSE size | Risk if tracks inline | Bounded — lazy load |
| Remaining gaps | CH20–36, CH2, firmware blanking | Unchanged |
| Dense `/tmp` media | N/A — use phase6 + corpus | Not a blocker if phase6 tracks pass H3 |

---

## 17. Postmortem — why motion was summarized (agent context)

The 8k capture program **intentionally** produced classified scalars for `fixture_model.json` while **`renderer_untouched`** (`FIXTURE_MODEL_PROGRAM.md`, manifest `scope_guard`). PR1 indexed **`analysis.json` only** by design (“committed corpus is numeric”). The renderer kept **`_drawFan()`** and borrowed strobe/loop scalars (PR3) without frame playback. Phase 5 never wired consumption. **PR-G + PR-H** are the planned stage-3 bridge: dual still+motion authority, then hardening for timing, combos, direction, and storage.

---

## 18. Brandon decisions (locked for v1 — 2026-06-09)

External review asked five product questions. Defaults below are **locked for agent execution** unless Brandon overrides.

| # | Question | Decision |
|---|---|---|
| 1 | Cue-family recognizability vs exact beam count when they conflict? | **Topology first.** Beam count stays `DECODER_FALLBACK` until capture-derived density is proven. Wrong fan count on correct shape beats correct count on wrong fan. |
| 2 | Phase6 cue captures as first priority for SoundSwitch design accuracy? | **Yes.** 175 phase6 folders with full motion packages are the primary validation set; main corpus fills gaps. |
| 3 | Ambiguous cue aliases sharing one CH1–19 vector — UI behavior? | **Show all aliases** with neutral “same DMX look” grouping. No single trusted cue name (PR-B policy). |
| 4 | G1/G1b starting with 12 atlas families before 8,324 captures? | **Yes.** Atlas-first smoke matrix (`WALL_CH3_LOOK_ATLAS.md`); expand to full corpus after atlas exit gate. |
| 5 | H2 direction: manual contact sheets vs unsigned motion? | **Unsigned until G3 is visibly close** on atlas + phase6 subset; then manual H2/H3 on a small matrix. Do not block G1–G3 on direction authority. |

**Merge policy (same review):** **APPROVE** Phase 1 (PR-A/B/C) as foundation. **BLOCK** any claim that Phase 1 or PR1–PR5 is capture-driven geometry/motion. **BLOCK** PR-D as merge target. Next implementation PR: **PR-G1** (atlas-first static shapes).
