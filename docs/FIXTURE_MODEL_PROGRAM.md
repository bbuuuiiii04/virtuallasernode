# VirtualLaserNode - Complete CH1-19 Fixture Model Program

**Status:** v2 program spec, with current operational readiness consolidated in `docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md`.
**Owner workflow:** Claude drafts -> Codex reviews/revises -> Claude final verdict -> execute phase-by-phase
**Goal:** Produce a reference-grade, machine-readable model of the *RGB Fullcolor Beam Effect Light* (36CH mode, CH1-19 subset) that describes how every modeled channel behaves across its useful 0-255 range and how channels affect one another, accurate enough that designing a look against the model is close to designing it on the real rig for resolved CH1-19 SoundSwitch cue states.

> This document remains the program specification. The current runbook, code-readiness findings, ENTTEC Pro safety model, exact command, and current hardware assumptions are in `docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md`, which supersedes stale operational details here. This is a measurement program only: no renderer behavior tuning, no haze/glow/bloom tuning, and no `calibration.json` render-value changes during measurement phases.

---

## 0. Why this exists (purpose and honest ceiling)

### Purpose
VirtualLaserNode is a **previsualization tool**: design SoundSwitch laser looks on a laptop without setting up the physical rig, and trust that the preview matches reality. To make the preview trustworthy beyond one-off screenshots, we need a behavioral model of the fixture: the transfer function from DMX bytes to observed light behavior, plus the interaction rules between channels.

### What "complete" means here
A model that, given any resolved CH1-19 vector in the static-pattern scope, predicts:
- the **base look** selected by CH3 bank + CH4 program,
- every **modifier effect** (size, position, color, scan, strobe, rotation, movement, zoom, gradient, wave), including direction, rate, and range where measurable,
- the **interaction rules** (which channels gate others, which compose, which are independent, which require higher-order handling).

### The honest ceiling
Three things are **not** recoverable from DMX/wall observation and are explicitly out of model scope:
1. **Firmware-internal galvo geometry**: exact point lists / scan paths. We model shape families and measurable envelopes, not exact ILDA figures.
2. **Firmware-internal easing/accel curves**: observable loop timing and endpoints are modeled; hidden interpolation is not.
3. **Timing above the camera and analyzer ceiling**: 60fps footage analyzed at 30fps can support periodic evidence up to about 15 Hz when the analyzer minimum lag allows a 2-frame 30fps period. A 60fps re-analysis has a Nyquist ceiling near 30 Hz, but the current dense analyzer's `0.07s` lag floor still caps it near 15 Hz unless the 60fps path explicitly permits a 2-frame lag. Anything faster must be labeled "too fast / firmware ceiling" instead of guessed.

Estimated reachable completeness from this program: **about 85-90%** of the information needed for useful previz. The remaining 10-15% is firmware-locked or capture-limited. This is acceptable for preview; pinpoint photo-accuracy remains out of scope.

### Artifact facts verified / corrected for current run
- `data/soundswitch_laser_cues.json`: 184 cues; all contain resolved CH1-19 values; 5 cues have CH3 >= 128 dynamic macros.
- `data/soundswitch_cue_motion_coverage.json`: current corrected buckets are `ready_static_color_strobe=78`, `ready_motion_mapping=66`, `motion_analysis_pending=35`, `defer=5`. **These live at `statistics.dense_motion_reclassification.after_next_actions`. The top-level `statistics.next_actions` is the STALE pre-dense state (`ready_motion_mapping=50`, `needs_dense_breakpoint_capture=126`) — do not read it.**
- `/tmp/vln_dense_cue_breakpoints_20260605_200426/`: no longer exists. It lived in ephemeral `/tmp`.
- `data/fixture_model.json` records the durable Phase 0 citation `provenance.phase0_validated_existing_dense_rows = 118`; Phase 0/6 cite that recorded count when the raw dense root is absent.
- Dense analysis extracted 69 characterized captures total; of 111 motion-family captures, 65 resolved through the confidence gate and 46 remained pending.
- `calib/dense_cue_breakpoints.py` contains the `0.07s` non-strobe period floor; `calib/timed_motion_ch1_19.py` still contains the old `0.35s` floor and must not be reused for this program without correction.
- `data/fixture_model_schema.json` is generated in Phase 5; its absence before Phase 5 is expected.

---

## 1. Scope

### In scope
CH1, CH3 static range 0-127, CH4, CH5, CH6, CH7, CH8, CH9, CH10, CH11, CH12, CH13, CH14, CH15, CH16, CH17, CH18, CH19.

### Out of scope for this program
- **CH2** (Auto/Sound/Demo): non-deterministic and sound-gated; document only.
- **CH3 >= 128** (dynamic macros): self-animating; only 5 real cues use them; defer to a separate dynamic-macro pass.
- **CH20-36** (second pattern): second-pattern/stacked output; defer until stacked looks are intentionally modeled.
- **Laser 2 independent calibration**: Laser 2 reuses the master model with mirrored placement unless future evidence shows real fixture differences.

### Channel reference
The current decoder in `fixtures.py` supports the following 36CH profile semantics:

| Ch | Name | Program role |
|---|---|---|
| CH1 | On/Off | master dimmer / blackout |
| CH2 | Auto Mode | out of scope |
| CH3 | Static Pattern | bank/family selector |
| CH4 | Static Pattern Selection | program selector within CH3 bank |
| CH5 | Pattern Size | size modifier |
| CH6 | Horizontal Adjustment | static X position modifier |
| CH7 | Vertical Adjustment | static Y position modifier |
| CH8 | Color | color/macro selector |
| CH9 | Color Speed | color speed; gated by CH8 effect ranges |
| CH10 | Pattern Line | line/dot scan modifier |
| CH11 | Strobe | strobe modifier |
| CH12 | Rotation Z | roll/spin modifier |
| CH13 | Rotation X | pitch modifier |
| CH14 | Rotation Y | yaw modifier |
| CH15 | Horizontal Movement | X movement/sweep modifier |
| CH16 | Vertical Movement | Y movement/sweep modifier |
| CH17 | Zoom | scale/zoom speed modifier |
| CH18 | Gradient | gradient modifier; likely gated by CH8 |
| CH19 | X/Y Wave | deformation modifier |

**Channel-role law (user-authoritative and repo-consistent):** CH3 selects the bank, CH4 selects the program/look within that bank, and CH5-19 modify the resulting CH3+CH4 look.

---

## 2. The deliverable - `data/fixture_model.json`

`data/fixture_model.json` is a new measurement artifact. It is not present today and is not yet a runtime dependency. Phase 5 must define how `fixtures.py`, renderer export tooling, and `calibration.json` derive from it without silently changing live renderer behavior.

```jsonc
{
  "fixture": "RGB Fullcolor Beam Effect Light (36CH; CH1-19 modeled)",
  "schema_version": 1,
  "model_version": "fixture-model-v1",
  "model_status": "measured | partial | draft",
  "method": {
    "capture_fps": 60,
    "analysis_fps": 30,
    "reanalysis_fps_allowed": 60,
    "frequency_ceiling_hz_30fps": 15,
    "frequency_ceiling_hz_60fps_if_two_frame_lag_enabled": 30,
    "exposure_tracks": ["geometry_motion", "color"],
    "primary_base": {"label": "line", "ch3": 32, "ch4": 10},
    "rig": "ENTTEC Pro or Open backend via orchestrator, name-resolved AVFoundation camera, wall projection",
    "notes": "resolved-vector behavior only; see layered Attribute Cue caveat"
  },
  "provenance": {
    "cue_dataset": "data/soundswitch_laser_cues.json",
    "coverage": "data/soundswitch_cue_motion_coverage.json",
    "dense_capture_root": "/tmp/vln_dense_cue_breakpoints_20260605_200426"
  },
  "channels": {
    "CH12": {
      "name": "Rotation Z",
      "role": "modifier",
      "breakpoints": [127, 144],
      "blank_zones": [],
      "base_dependence": "invariant | varies | unknown",
      "confidence": "high | medium | low",
      "banks": [
        {
          "range": [0, 127],
          "behavior": "angle_pose",
          "maps": {"roll_deg": [[0, 0], [127, 180]]},
          "interpolation": "linear | step | spline | parametric",
          "direction": "CW+",
          "evidence": ["capture/test/path"]
        },
        {
          "range": [128, 143],
          "behavior": "deadband_static",
          "evidence": ["capture/test/path"]
        },
        {
          "range": [144, 255],
          "behavior": "spin",
          "maps": {"rate_hz": [[144, 0.0], [255, 2.7]]},
          "interpolation": "piecewise_linear",
          "direction": "CW | CCW | requires_visual_review",
          "evidence": ["capture/test/path"]
        }
      ]
    }
  },
  "base_looks": {
    "CH3=28/CH4=0": {
      "shape_family": "measured name",
      "representative_capture": "path",
      "program_range": [0, 4],
      "confidence": "high | medium | low"
    }
  },
  "interactions": {
    "gating": [
      {"gate": "CH8 in [44,255]", "enables": "CH9", "confirmed": true, "evidence": ["..."]}
    ],
    "compositional": [
      {"group": "scale", "channels": ["CH5", "CH17"], "rule": "multiply | add | override | interfere", "evidence": ["..."]}
    ],
    "independent": [
      {"channels": ["CH11", "CH8"], "evidence": ["..."]}
    ],
    "higher_order": [
      {"channels": ["CH11", "CH13", "CH15"], "emergent_effect": "...", "rule": "...", "evidence": ["real-cue composition failure"], "confirmed": true}
    ]
  },
  "composition": {
    "model_form": "predict resolved CH1-19 vector = base(CH3,CH4) + modifier transfer functions adjusted by gating/composition/higher_order rules",
    "higher_order_assumption": "interactions beyond measured pairs/triples are negligible unless Phase 6 real-cue validation proves otherwise"
  },
  "validation": {
    "cues_checked": 184,
    "captured_exact_vectors": 118,
    "agreement_metric": "see spec section 5, Phase 6",
    "mismatches": []
  }
}
```

**Schema rules:**
- Every channel bank needs `range`, `behavior`, `maps` or an explicit reason no numeric map exists, `confidence`, and `evidence`.
- `maps` is a sampled curve `[[dmx_value, measured_property], ...]`. Use dense points near breakpoints and sparse points in flat regions.
- Interpolation must be explicit per map. Use `piecewise_linear` by default; use `step` for discrete program/color banks; use a parametric fit only when it improves prediction and is validated against held-out values.
- Direction uses signed conventions: rotation `CW`/`CCW`; translation `+X=screen-right`, `+Y=screen-up`; scale `+=larger`.
- `base_dependence` comes from Phase 1.5 and controls whether a channel map can be reused across base looks.
- A cue entry must distinguish resolved-vector behavior from SoundSwitch authored-channel behavior; the current cue dataset has no checked/unchecked channel metadata. Carry an `authored_channels_unknown: true` flag in `validation` and on each mismatch.
- **Multi-property channels (v2):** scalar `maps` cannot express CH8 (one value → mode + rgb + animated + gates). For such channels add a `properties` dict per bank (e.g. `{mode, rgb, animated, gates_ch9, gates_ch18}`) alongside any continuous `maps` (e.g. hue index). The CH12 example above is illustrative for single-scalar channels only.
- **Structured gate predicates (v2):** `interactions.gating[].gate` must be machine-parseable, not prose. Use `{"channel":"CH8","op":"in_range","lo":44,"hi":255}`; legal `op`: `in_range`, `eq`, `gte`, `lte`, `kind_eq` (for CH3 static/dynamic). The `"CH8 in [44,255]"` string in the example is shorthand only.
- **Vocabulary (v2):** define `blank_zone` = "DMX range where fixture output is zero regardless of other channels" vs `deadband` = "channel at neutral pose, fixture still lit." They are not interchangeable; consumers gate on them differently.
- **Direction required on all spatial modifier banks (v2):** any bank with `behavior` in {angle_pose, spin, sweep, position, translation, wave} MUST carry `direction` with the §3.1 sign convention (or `requires_visual_review`).
- **Computable composition block (v2):** `composition` must include `evaluation_order` (channel/group application order), `gate_evaluation` ("pre"|"post"), and a `default_combination` + `operand_space` ("dmx"|"transfer_output"|"normalized"); each `compositional` rule must also state its `operand_space`. The prose `model_form` is a description, not the spec.

---

## 3. Cross-cutting methodology (Phase 0)

These are preconditions for all measurement phases.

### 3.1 Signed direction extraction
Prior passes reported magnitude (`x_range`, `angle_range_deg`, `area_range_frac`) and often left direction as visual-review-only. The analyzer must emit signed motion per timed clip:
- centroid drift sign: net `dx`, `dy` via **a linear regression slope over the full centroid time series, not a first-vs-last comparison**. (BUG FOUND v1→v2: `dense_cue_breakpoints.py` derives sweep direction from `xs[-1] > xs[0]`, which is phase-dependent and WRONG for oscillating CH15/CH16 sweeps — the corpus's 15-rightward/8-leftward split is phase noise. Replace with regression slope + report slope confidence before any sweep direction is trusted.)
- signed angular velocity: unwrapped PCA angle slope for asymmetric shapes,
- signed area slope: grow vs shrink for zoom/size,
- per-beam or feature tracking fallback for symmetric rings, multi-beam fans, and wave cases where PCA sign is ambiguous,
- `requires_visual_review` only when the sign confidence is low or the figure symmetry makes the numeric sign unreliable.

PCA-only direction is not sufficient for every wall projection. It is acceptable as a first pass, but Phase 1 cannot claim a signed transfer function for rotations/waves unless the confidence gate or visual review confirms direction. **Visual review is a formal, numbered step, not an informal fallback:** when used, examine the saved frame strip for the test, record the resolved sign in `analysis.json` with `direction_source: "visual_review"`, and treat any direction left unresolved at Phase 1 exit as a Phase 6 deferred-fail (it cannot pass a direction-match test), never as a pass.

### 3.2 Dual evidence tracks, not uncontrolled brightness changes
Bright captures preserve shape/motion contrast; dim captures preserve color. For all non-CH1 channels capture two evidence tracks:
- **geometry/motion track**: enough brightness to preserve centroid, area, and angle metrics without blanking,
- **color track**: lower brightness or camera exposure that avoids washing colors to white.

Do not assume CH1 can be used as a harmless exposure knob until Phase 1 confirms CH1 is brightness-only across the selected baseline. **The CH1 sweep MUST be the first measurement in Phase 1**, before any other channel uses CH1 as a dual-track brightness control. If that sweep shows any non-monotone, threshold, or strobe-like behavior, CH1-based bracketing is forbidden for the rest of the program: hold CH1 fixed and bracket camera exposure instead. For the CH1 sweep itself, the two-track rule is not applicable because CH1 is the measured variable.

### 3.3 Wide, centered ROI
The prior left-cropped ROI caused CH15 horizontal movement to blank out of frame. Use full-frame capture first, then derive an analysis ROI from a static reference frame: detect both aperture boxes, align their height to `captures/fixture_model/setup_geometry.json`, and set the bottom ROI to the detected static-base box bottom plus a small configurable boundary margin (`VLN_ANALYSIS_BOUNDARY_MARGIN_INCHES`, default 0.75 in). The pencil ticks mark the physical laser boundary, and the static base outline must land on those ticks, so no extra dynamic/extreme-reference capture step is required. Persist this as `captures/fixture_model/analysis_geometry.json` and have both frame stats and dense analysis consume it.

ROI geometry is derived from the preflight-only boundary-box look: CH3=0 / CH4~62 / CH5=0 / CH6=128 / CH7=128 / CH17=0. CH5=0 is used because it is the largest static pattern size and should match the pencil-tick physical boundary. The capture baseline remains `PRIMARY_BASE` with CH5=90 for sweeps. Existing raw captures do not need physical recapture solely because of this ROI-anchor fix, but existing manifest analysis is stale after preflight regenerates `analysis_geometry.json`; reanalyze all existing rows before Phase 5/model build so every row uses the same CH5=0 geometry provenance.

Do not silently truncate geometry to avoid table glare. If the desired small boundary margin overlaps a detected glare/baseboard band, record `roi_boundary_glare_conflict` in `analysis_geometry.json`. Rare looks that cross the marked boundary are handled per capture by `geometry_clipped_low`, not by a run-halting framing preflight.

### 3.4 Honest quality gates
- Never use `recapture_needed = blank OR clipped`. In wall captures, `clipped` fires on valid nonblank frames and must not gate usability.
- Exception: ROI-bottom clipping is not the old full-frame clipped flag. If laser geometry reaches the derived ROI bottom, record `geometry_clipped_low`; CH16/CH17 captures with that flag are not clean evidence and must be marked for recapture/reframing instead of accepted silently.
- For timed motion evidence: usable = not truly blank and `loop_confidence >= 0.35`; strobe may pass through the crossing-count Hz path even when period fitting is not the source.
- For static/color evidence: usable = not truly blank plus the relevant static/color metric passes; do not require a motion loop for a static still.
- A capture counts as **motion-ready** only when `motion_type` is non-null and either periodic motion passes confidence or strobe has crossing-count timing.

### 3.5 Frequency floor and analyzer parity
`calib/dense_cue_breakpoints.py` changed non-strobe period detection from a `0.35s` minimum lag to `0.07s`, allowing about 15 Hz at 30fps analysis. Keep that fix.

However, `calib/timed_motion_ch1_19.py` still uses the old `0.35s` floor. Any future Phase 1/1.5/3 measurement script must either use the dense analyzer or update the shared estimator before analysis. Do not mix old-floor and new-floor results in the same model.

For 60fps re-analysis, the theoretical Nyquist ceiling is near 30 Hz, but the `0.07s` coefficient does NOT get you there: at 60fps `min_lag = int(0.07*60) = 4`, giving a `4/60 = 0.067s` floor ≈ **15 Hz — identical to 30fps**. Reaching ~30 Hz requires explicitly changing the coefficient to ≤`0.033` (or hardcoding `min_lag=2`) in the 60fps path and re-verifying. The spec must not claim >15 Hz measurability until that specific change is made and verified.

### 3.6 Adaptive sweep resolution
Baseline: every 4 values (`0,4,...,252,255`, 65 points) for continuous modifier channels. After first analysis, densify to every 1-2 values within +/-6 of each detected breakpoint, bank boundary, onset, deadband edge, or real cue value cluster. Use step-bank handling for discrete CH3/CH4/CH8 program ranges; do not waste timed captures in flat regions.

### 3.7 Rig discipline
- Wall projection, no haze, fixed camera, full pattern visible, no fixture in frame.
- Capture at 60fps; analyze at 30fps unless fast-band (>15 Hz) resolution is needed, then re-analyze at 60fps with `min_lag` coefficient ≤0.033 (§3.5). 30fps is the safe fallback and is sufficient for everything ≤15 Hz.
- **CAMERA FRAMERATE = LIGHTING, NOT THERMAL (verified 2026-06-06).** The Continuity Camera drops 60→30fps via iOS low-light auto-FPS when the scene is too dark — it is NOT thermal (a 4 h-cooled device gave 30fps in the dark, 60fps when lit; and the dense pass's "16-min cliff" was the room darkening, not heat). Verified operating points: luma ~20/32/96/137 → 60fps; near-black → 30fps. **Operating rule:** keep the captured scene at **≥~20 mean luma ("super-dim" — beams still visible)** to hold 60fps; disable iOS Settings → Camera → Record Video → Auto FPS / low-light. No cooling is needed. Earlier thermal/soak guidance is superseded.
- Quit SoundSwitch first; it can hold the FTDI port and cause `[Errno 16] Resource busy`. **Preflight: before starting the daemon, run `lsof` on the chosen `/dev/cu.usbserial-*` port and confirm no process holds the FTDI device. If the daemon reports `[Errno 16]`, the phase is invalid — free the port, re-preflight, restart from rig setup.**
- Final run prefers the ENTTEC Pro backend with explicit `--dmx-port`; the Open backend remains available and requires pyftdi `set_latency_timer(1)`.
- Lock camera position, focus, white balance, and exposure settings within a phase.
- AVFoundation camera must be resolved by name, not by numeric index; `Desk View` and `Capture screen` devices are invalid. The current local fixture-facing name is `brandon Camera`, but the final run must re-list and validate the exact name before capture. Delivers 60fps only at ≥~20 luma (see above).
- Do not re-angle the camera just to hide table glare if that invalidates the wall measurements. Current analysis uses an adaptive laser-core mask plus a box-anchored ROI in `captures/fixture_model/analysis_geometry.json`; if the small boundary margin and glare exclusion conflict, the code surfaces `roi_boundary_glare_conflict` rather than choosing silently.
- **Dual-track interaction with the luma floor:** the *geometry/motion* track needs 60fps → keep it ≥~20 luma. The *colour* track may be dimmer/30fps (colour has no timing requirement), so a darker colour exposure is fine and does not need to hold 60fps.

### 3.8 Safety
At the end of every physical phase: blackout, wait at least 100 ms, stop the daemon cleanly, visually confirm the fixture is dark, and confirm the frame file reports `(all zero)`. The monitor/frame-file check is not hardware readback. The ENTTEC Pro autonomously retransmits its last frame, so a hard-killed Pro daemon can leave the laser lit; never manually `kill -9` the Pro daemon. The physical power switch / kill path is the final failsafe. See `docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md` for the backend-specific safety model.

### 3.9 Capture storage and organization
All captures persist under the repo at `captures/fixture_model/` (NOT `/tmp` — prior passes lost ephemeral evidence on reboot). Layout: **phase → channel/group → test state**, with a single master index.

```
captures/fixture_model/
  manifest.jsonl                          # MASTER INDEX: one line per capture
  phase1_single_channel/
    CH08_color/
      CH08_000/   { video.mp4, still.jpg, video_color.mp4, still_color.jpg, metadata.json, analysis.json, optional frame_strip.jpg }
      CH08_004/
      CH08_008/
    CH12_rotation_z/
      CH12_144/
      CH12_160/
  phase1_5_base_dependence/
    base_CH3_028_CH4_000/
      CH12_rotation_z/ { CH12_144/ ... }
      CH15_horizontal_movement/ { CH15_200/ ... }
  phase2_gating/
    gate_CH08_enables_CH09/ { CH08_060_CH09_128/ ... }
  phase3_composition/
    scale_CH5xCH17/ { CH5_064_CH17_128/ ... }
  phase4_independence/
    CH11xCH08/ { CH11_128_CH08_020/ ... }
  phase6_cue_validation/
    cue_027_rainbow_tall_rectangles/
```

**Naming conventions (strict, machine-parseable):**
- Channel folder: `CHNN_name` (e.g. `CH12_rotation_z`); value folder: `CHNN_VVV` with **zero-padded 3-digit DMX** (e.g. `CH12_144`).
- Base folder: `base_CH3_NNN_CH4_NNN`. Composition: `group_CHaXCHb` (e.g. `scale_CH5xCH17`); state: `CHa_VVV_CHb_VVV`.
- Cue folder: `cue_<id>_<slug>`.
- **Dual evidence tracks** (geometry vs colour): store both in the value folder. Geometry uses `video.mp4`/`still.jpg`; colour uses `video_color.mp4`/`still_color.jpg`; `metadata.json` records `exposure_track`. Do not split tracks into sibling folders (keeps one folder = one DMX state).

**Each test folder contains:** required video/still evidence, `metadata.json`, and `analysis.json`. `frame_strip.jpg` is now optional and only generated with `--frame-strips`; it is not model evidence.

**`metadata.json` (the per-capture log) must record:** `phase`, `test_id`, full `ch1_19` DMX dict, `changed_channels`, `ch3_bank`, `ch4_program`, `baseline`, `exposure_track`, `camera{device,size,fps,exposure,white_balance}`, `fps`, `duration`, `capture_path` (folder-relative), `timestamp`, `scope_guard`.

**`analysis.json` must record:** `motion_type`, signed `direction`(+`direction_source`+confidence), loop/`rate`, strobe `hz`/`duty`, colour metrics, centroid/area metrics, flagged breakpoints, `confidence`, and `quality{blank, usable}` — where `recapture` is keyed on `blank` ONLY (never `clipped`, per §3.4).

**`manifest.jsonl`** is the master index: one JSON line per capture = the metadata summary + key analysis results + the folder-relative path. Every Phase appends to it.

**Provenance link:** `data/fixture_model.json` `evidence` arrays reference these folder-relative paths (e.g. `"phase1_single_channel/CH12_rotation_z/CH12_144"`). Every bank, map, gate, compositional rule, base_look, and higher_order entry must cite the exact folder(s) it was derived from, so the model points back to its evidence and any claim is auditable.

---

## 4. Program structure and ordering gate

```
Phase 0   Methodology/analyzer fixes
Phase 1   Single-channel dense transfer functions on one baseline
Phase 1.5 Base-dependence probe across real and lab bases       HARD GATE
Phase 2   Gating dependencies
Phase 3   Compositional grids, sized by Phase 1.5
Phase 4   Independence spot-checks
Phase 5   Assemble fixture_model.json and composition adapter
Phase 6   Cue-level multi-channel validation and higher-order correction
```

The program does **not** brute-force full CH1-19 combinations. It measures building blocks (single channels plus selected interaction grids), composes them, and then validates the composed result against real full-vector SoundSwitch cues. Where composition fails, Phase 6 measures only the offending channel set.

### The base-dependence gate
Base-dependence asks whether a modifier behaves the same regardless of the selected CH3+CH4 base look.

- **Invariant**: measure modifier once and reuse it.
- **Varies**: measure modifier or interaction grid per affected base.

This gate controls feasibility. If all Phase 3 grids are multiplied across five bases, the base-invariant estimate of about 3,600 captures becomes about 18,000 captures, which is not tractable for this rig without major reduction. Phase 3 must not be finalized until Phase 1.5 decides which channel groups actually need per-base grids.

---

## 5. Phase specifications

### Phase 1 - Single-channel transfer functions

**Objective:** dense, signed transfer functions for every in-scope channel on a stable primary baseline, plus a CH3/CH4 base-look atlas.

**Primary baseline:** start with a deterministic line base such as CH3=32, CH4=10, but also record why that baseline was chosen and confirm it remains visible with strobe off, centered position, neutral size/zoom, and fixed color.

**Method:**
- **Sweep CH1 FIRST** (per §3.2) to validate whether CH1 is brightness-only before any other channel relies on CH1 dual-track bracketing.
- Sweep each modeled channel while holding all others at baseline. Write every capture to `captures/fixture_model/phase1_single_channel/CHNN_name/CHNN_VVV/` per §3.9.
- Use adaptive every-4-value sampling, then densify breakpoints/onsets/deadbands and real cue value clusters.
- Capture two evidence tracks per non-CH1 value: geometry/motion and color.
- Static states can use still evidence; motion/strobe/color-speed/gradient states need timed clips.
- Extract behavior type, property curves, signed direction, confidence, breakpoints, bank boundaries, onsets, deadbands, and blank zones.
- **CH3/CH4 special:** CH3 selects a bank and CH4 selects a program within that bank. CH3 cannot be modeled without CH4 program sampling. Sweep CH3 static banks and sample CH4 programs within each bank enough to identify visual families and ranges.

**Existing evidence to reuse, not blindly re-measure:**
- CH8 fixed-7 color order: white, red, yellow, green, cyan, blue, magenta.
- CH11 strobe has reliable timing evidence for 50 cues; coverage reports 56 strobe cues with evidence.
- Known onsets from prior evidence: CH12 spin about 144 with 128-143 deadband; CH17 zoom-pulse about 152; CH19 wave about 136.
- Dense pass has 66 cues currently marked `ready_motion_mapping`; specifically, 65 motion-family dense captures resolved through the motion confidence gate. Direction remains provisional where analysis says visual review is required.

**Deliverables:** draft `data/fixture_model.json` `channels`, `base_looks`, `method`, and `provenance`; `docs/FIXTURE_MODEL_PHASE1.md`; capture root + manifest + contact sheets + `analysis_manifest.jsonl`; analyzer script with signed-direction fields.

**Exit criteria:** every in-scope channel has banks, breakpoints, at least one property curve or explicit non-numeric behavior, signed direction or explicit unresolved reason, confidence, and evidence paths. **Plus a measurement-precision artifact:** document centroid tolerance (±N px at reference projection distance), area tolerance (±M%), and angle tolerance (±P°) from the static/control captures — these become the Phase 6 `geometry envelope` thresholds (which are otherwise undefined).

**Budget (corrected v2 — measured, not estimated):** the 118 dense captures ran at **16.8 s/capture** (10 s clip + 6.9 s hold/settle/analysis/IO overhead; see `/tmp/vln_dense_cue_breakpoints_20260605_200426`). 18 channels × ~65 values × 2 tracks ≈ 2,340 + ~650 densification ≈ ~3,000 captures → **10–14 h, across ≥2 sessions. An overnight/multi-session run is the expected case, not the worst case.** (The earlier 4–7 h figure was ~2× optimistic — it omitted the 6.9 s/capture overhead.)

---

### Phase 1.5 - Base-dependence probe (hard gate)

**Objective:** decide which modifier groups are base-invariant before Phase 3 is scoped.

**Minimum probe set:** use at least seven modifier representatives:
- CH8 color,
- CH10 scan/line density — **added v2: active on 24/37 cues of the most-used base (CH3=28); no other probe channel proxies its base-dependence; scan density is plausibly figure-topology-dependent (ring vs line vs fan),**
- CH12 Z rotation/spin,
- CH15 horizontal movement,
- CH17 zoom,
- CH18 gradient — **added v2: fires independent of CH8 in 54% of its active cues (so it is not CH8-gated, see Phase 2), 26 cues use it, behavior currently uncharacterized,**
- CH19 wave/deformation.

**Partial-coverage caveat (v2):** CH13 (rot X) is covered by the CH3=0 and CH3=41 probe bases but NOT by CH3=38/CH3=45 (2 cues total — those rely on Phase 6 validation). CH14 (rot Y, 6 cues) is inferred from CH13 (physically analogous tilt axis) plus the CH3=41 base; document this inference rather than adding dedicated CH14 probes.

**Minimum base set:** use both lab-stable and corpus-heavy bases. Start with:
- CH3=32/CH4=10: deterministic line lab baseline,
- CH3=28/CH4=0: most common real cue pair (37 cues),
- CH3=0/CH4=195: common ring/program pair (20 cues),
- CH3=0/CH4=203: second common ring/program pair (18 cues; keep only if visually distinct from CH4=195),
- CH3=41/CH4=0: common non-line static base (11 cues),
- CH3=48/CH4=0 or CH3=96/CH4=0: dual/arc control base from prior sampled-base work.

If CH4 programs within the same CH3 bank visibly change how modifiers behave, treat CH4 as part of the base identity and keep the extra base. Do not collapse CH3-only bases when CH4 changes the figure.

**Method:** for each probe channel/base, sample about 20 values plus known onsets/breakpoints and real cue value clusters, with both evidence tracks. Compare curves by behavior type, signed direction, rate/range, and confidence.

**Deliverables:** `base_dependence` verdict per probed channel; inferred rule per modifier class; Phase 3 multiplier estimate by group; explicit "go / reduce / rescope" decision.

**Exit criteria:** Phase 3 sizing is decided. Phase 3 is blocked until this verdict exists.

**Budget (corrected v2):** 7 channels × ~5 bases × ~20 values × 2 tracks ≈ **1,400 captures** (+~200 if both CH3=0 programs stay separate). At the measured ~16.8 s/capture, plan **~6.5 h** (the earlier 1.5–3 h estimate was ~2× optimistic and assumed 5 probe channels).

---

### Phase 2 - Gating dependencies

**Objective:** confirm which channels enable/disable others.

| Gate | Dependent | Hypothesis |
|---|---|---|
| CH1 | all | CH1=0 blacks out; nonzero is brightness/open behavior |
| CH3 static vs >=128 | CH5-19 | dynamic macros are out of this model; spot-check only, do not deep-capture |
| CH8 effect ranges | CH9 | CH9 is inert outside color-effect ranges — **but test with CH8=0 too: 6 cues use CH9 with CH8=0** |
| CH8 ↔ CH18 | (NOT a gate) | **CORRECTED v2: CH18 is NOT CH8-gated. 54% of CH18-active cues have CH8=0 (and 14 use CH18=120–255 at CH8=0). Test CH18 at CH8=0 AND across CH8 ranges; characterize whether CH8 *modulates* CH18 appearance rather than gating it. The Phase 3 CH8×CH18 grid must not presuppose gating.** |
| CH3+CH4 | base shape | CH3 bank + CH4 program select the figure all modifiers edit |
| CH2 | all | auto/sound behavior is documented skip; spot-check only if needed |

**Deliverables:** `interactions.gating` with confirmed/refuted gates, enabling ranges, and evidence.

**Budget:** about **40-80 captures**, 10-30 minutes. This can run near Phase 1.5, but do not let it bypass the Phase 1.5 gate for Phase 3.

---

### Phase 3 - Compositional grids

**Objective:** for channels that drive the same property, determine whether combination rules are add, multiply, override, or interfere.

| Group | Channels | Property | Coarse grid (default) | Key question |
|---|---|---|---|---|
| Colour | CH8 x CH9, CH8 x CH18 | color/time | 2 x 8x8 | colour speed and gradient behavior across modes (CH18 NOT gated, see Phase 2) |
| Translate | CH6 x CH15, CH7 x CH16 | position | 2 x 8x8 | do static position and movement add? |
| Scale | CH5 x CH17 | size | 8x8 | does zoom multiply size or override? |
| Orientation | CH12 x CH13 x CH14 | rotation | 6x6x6 | composition order / interference of three axes |
| **Rotation×Move (v2)** | **CH12 x CH15** | frame | **8x8** | **does movement operate in base frame or rotated frame? (9 cues; non-additive if rotated-frame)** |
| **Move×Wave (v2)** | **CH15 x CH19** | deform+path | **8x8** | **is wave applied before or after sweep? (59 cues — too common to defer to Phase 6)** |

**Enter Phase 3 with COARSE grids as the default, not as a fallback** (full 16×16/8×8×8 are a named densification option requiring separate sign-off after a coarse grid passes). **Approval is PER GROUP, not one bloc:** run in cost/risk order — (1) colour, (2) translate, (3) scale, (4) rotation×move + move×wave, (5) orientation (most expensive) — and derive each group's composition verdict before starting the next. A failed/indeterminate group stops that group; others may proceed.

**Feasibility rule (corrected for current code):** at measured ~16.8 s/capture, even the base-invariant *coarse* set is a multi-hour, possibly two-day commitment; the old "6–10 h" figure (which assumed ~3,584 captures at clip-only timing) is really **~17 h**. Multiplying every group across all bases is infeasible. If Phase 1.5 shows base dependence, reduce to: only the groups that varied; only the real-cue bases that use the affected group; coarse grids first. Current orchestrator cap is **10,000 captures taken this invocation**, resume-safe and adjustable with `--max-new-captures`.

**Deliverables:** `interactions.compositional` with rules (incl. `operand_space`, see §2), confidence, evidence, and any unresolved groups; per-group go/stop record.

---

### Phase 4 - Independence spot-checks

**Objective:** justify not gridding the rest by confirming orthogonality.

**Method:** for about 6-10 pairs assumed independent (examples: CH11 x CH8, CH11 x CH12, CH17 x CH8, CH19 x CH8, CH12 x CH8, **and CH11 x CH15 — v2: if strobe gates position updates, the translate composition fails for ~40 strobe+movement cues; cheap 8-diagonal check, large payoff**), capture diagonal combinations and confirm each channel's effect is unchanged. Any surprise promotes that pair to a Phase 3 grid or a targeted Phase 6 higher-order test.

**Deliverables:** `interactions.independent` with evidence; escalations noted.

**Budget:** about **80-160 captures**, 20-60 minutes.

---

### Phase 5 - Assemble and compose

**Objective:** finalize the model and define the composition function that predicts a resolved CH1-19 vector.

**Method:**
1. Merge Phases 1-4 into `data/fixture_model.json`.
2. **Deliver a formal JSON Schema** `data/fixture_model_schema.json` (draft-07): `json.tool` only checks parse-validity; it cannot enforce required bank fields, legal `behavior`/`interpolation`/`confidence`/`direction` enums, `maps` shape, structured gate predicates, or compositional-rule fields. Phase 5's "deterministic prediction for any vector" exit is untestable without it.
3. Implement the composition adapter as a **NEW module (e.g. `fixture_model_adapter.py`) that AUGMENTS the decoded state dict — it must NOT modify `decode_36ch()`'s return contract** (the renderer consumes that by field name; changing it is a silent renderer change). Resolved CH1-19 vector → base(CH3,CH4) + modifier transfer functions adjusted by gates and composition rules.
4. Cross-check `fixtures.py` decode against the model's banks/breakpoints. Flag decoder gaps separately; do not change renderer behavior during measurement (`fixtures.py` is in the §8 hash check).
5. Define how renderer/export tooling will consume the model in a later implementation pass.

**Deliverables:** assembled `data/fixture_model.json` + `data/fixture_model_schema.json`; `docs/FIXTURE_MODEL_ASSEMBLY.md`; adapter module/test plan.

**Exit criteria:** a deterministic prediction can be generated for any in-scope resolved CH1-19 vector, with confidence and unsupported-field flags.

---

### Phase 6 - Cue-level multi-channel validation and higher-order correction

**Objective:** prove the composed model predicts real full-vector SoundSwitch cues; measure higher-order interactions only where composition fails.

**Inputs:** composition function; 118 exact dense 60fps cue captures; 184-cue corpus; corrected coverage JSON.

**Validation metric:** compare predicted vs measured behavior with property-specific tolerances:
- nonblank/blank: exact category match,
- base look: CH3+CH4 family/program agreement or documented firmware-locked mismatch,
- color: fixed color within palette label or dynamic color family match; gradient/color-chase timing within 25% when measurable,
- strobe: Hz within max(0.25 Hz, 15%) and duty within 20 percentage points for resolvable strobes,
- motion type: same category (`spin`, `horizontal_sweep`, `vertical_sweep`, `pulse_zoom`, `wave`, etc.),
- signed direction: exact sign match when direction confidence is high; otherwise mark unresolved, not pass,
- rate/period: within 25% for resolvable loops; "too fast" buckets may match only as a fast/unresolved class,
- geometry envelope: center/spread/size within the **centroid ±N px / area ±M% / angle ±P° tolerances recorded as the Phase 1 exit artifact** (no longer a forward reference).

Use a weighted per-cue score with an **explicit weighting rule: each ACTIVE property (a channel/group the cue actually drives) contributes equally; inactive properties are excluded from that cue's denominator.** A cue is validated only if all active high-priority properties pass or are explicitly classified firmware-locked/unmeasurable. Aggregate success reports percent passing, percent unresolved, and percent higher-order failures separately; do not hide failures inside a single average.

**Method:**
1. Predict each captured real cue by composing the model.
2. Compare predicted vs measured dense-cue analysis and frame strips.
3. Bucket mismatches: firmware-locked, measurement gap, unsupported renderer/model field, or genuine higher-order interaction.
4. For confirmed higher-order failures, identify the active channel set and run the smallest targeted grid needed to characterize it.
5. Re-compose and re-validate until residual mismatches are explained or explicitly accepted.

**Deliverables:** complete `data/fixture_model.json` including `higher_order` and `validation`; `docs/FIXTURE_MODEL_FINAL.md`.

**Exit criteria:** every in-scope cue has pass/fail/unresolved status; all residual mismatches are explained; higher-order corrections exist only where real cue validation proves they are needed.

**Budget:** zero new captures for initial validation. Higher-order grids are conditional and must be approved with a count estimate before capture. If failures are widespread, the general-model premise is wrong and the project should rescope toward cue-family direct modeling.

---

## 6. Interaction matrix

| Relationship | Channels | Action | Phase |
|---|---|---|---|
| Gating | CH1 -> all, CH3 static/dynamic split, CH8 -> CH9, CH3+CH4 -> shape | confirm enable/disable | 2 |
| Compositional | CH5 x CH17, CH6/7 x CH15/16, CH12 x CH13 x CH14, CH8 x CH9, CH8 x CH18, **CH12 x CH15, CH15 x CH19** | derive combination rule | 3 |
| Independent | strobe x color, strobe x rotation, zoom x color, wave x color, rotation x color | spot-check orthogonality | 4 |
| Higher-order | real cue failures only | targeted grid after validation failure | 6 |

Rationale: the fixture is expected to be mostly compositional, but the assumption is tested against real cue captures before renderer tuning.

---

## 7. Combinatorial boundary

We will not attempt:
- full CH1-19 cross-product,
- all-pairs at fine resolution,
- speculative 3-/4-/5-way grids,
- dynamic macro internals,
- CH20-36 stacked pattern modeling,
- timing claims above analyzer/camera limits.

**Multi-channel assumption:** the model predicts full cue vectors by composing single-channel transfer functions plus measured pair/triple interaction rules, assuming higher-order effects are negligible. This assumption is tested in Phase 6. If Phase 6 shows broad higher-order failure, the program must rescope toward direct real cue-family modeling instead of continuing a general transfer-function model.

---

## 8. Verification standard

Every paper or measurement phase should run only non-capture verification unless the phase explicitly says it is a physical capture pass.

- `python3 -m json.tool calibration.json`
- `python3 -m json.tool data/soundswitch_cue_motion_coverage.json`
- `python3 -m json.tool data/fixture_model.json` if the file exists or is touched
- JSONL-validate any new `analysis_manifest.jsonl`
- `node --check static/renderer.js`
- `python3 -m py_compile` all touched/new `calib/*.py` scripts plus `calibration.py fixtures.py webserver.py` (and the Phase 5 adapter module once it exists)
- **Concrete no-change hash check (v2)** — before any physical capture phase:
  `shasum -a 256 static/renderer.js calibration.json fixtures.py > /tmp/vln_hash_before.txt`
  after the phase: rerun to `/tmp/vln_hash_after.txt`, then `diff` them. **Any diff is a STOP condition** — identify the source and restore before proceeding. (`fixtures.py` is included because a Phase 5 cross-check could inadvertently alter its decode contract = a silent renderer change.)
- No `static/renderer.js` behavior changes and no `calibration.json` render-value changes during measurement phases.
- **Post-Phase-5 (once `data/fixture_model.json` exists):** validate against `data/fixture_model_schema.json` (`python3 -m jsonschema -i data/fixture_model.json data/fixture_model_schema.json`); assert `schema_version==1`; spot-check no `evidence` array still holds the template placeholder `"capture/test/path"`.

---

## 9. Known facts to carry forward

- **Channel roles:** CH3 bank, CH4 program, CH5-19 modifiers.
- **Current decoder:** `fixtures.py` encodes CH3 static/dynamic split, CH4 static program every 5 values, CH8 color modes, CH9 color speed, CH10 scan, CH11 strobe, CH12-14 angle/speed, CH15-16 position/speed, CH17 size/speed, CH18 gradient, CH19 X/Y wave.
- **Color order:** CH8 fixed-7 order is white, red, yellow, green, cyan, blue, magenta.
- **Strobe:** CH11 has the strongest current timing evidence; coverage reports 50 reliable strobe-timing cues and 56 strobe cues with evidence.
- **Onsets:** CH12 spin about 144 with 128-143 deadband; CH17 zoom-pulse about 152; CH19 wave about 136. Treat these as starting evidence, not final dense breakpoints.
- **CH18 is NOT CH8-gated (v2):** 54% of CH18-active cues have CH8=0; 14 cues run CH18=120–255 at CH8=0. Do not encode CH8→CH18 as a gate.
- **CH10 base-dependence unknown (v2):** scan/line density is active on 24/37 cues of the most-used base and likely figure-topology-dependent; it is now a Phase 1.5 probe channel.
- **Quality gate:** use true `blank` plus motion confidence for timed motion; ignore `clipped`/`recapture_needed`.
- **Frequency floor:** dense analyzer fixed non-strobe period floor to 0.07s; old timed analyzer still has 0.35s and must be corrected or avoided.
- **Camera (updated 2026-06-06):** Continuity Camera does 60fps at 1280x720 nv12, but iOS low-light auto-FPS drops it to 30fps below ~20 luma — this is LIGHTING, not thermal (verified live: 60fps at luma 20/32/96/137; 30fps near-black). Hold the scene at ≥~20 luma super-dim to keep 60fps; disable iOS Auto-FPS. No cooling needed. 30fps remains sufficient for ≤15 Hz if a look can't be lit to ≥20 luma.
- **Layered Attribute Cue caveat:** SoundSwitch cue JSON has resolved CH1-19 values but no checked/authored-channel metadata. The model describes resolved-vector behavior, not per-cue authored-channel intent.
- **Corpus:** 184 real cues; 179 in static CH3<128 scope; 5 dynamic CH3>=128 deferred; 63 cues share previously sampled CH3 bases `{0,32,48,96}`.
- **Dense exact captures:** 118 exact 60fps cue captures exist and cover 126 cues including duplicate resolved vectors.
- **Corrected coverage:** `ready_static_color_strobe=78`, `ready_motion_mapping=66`, `motion_analysis_pending=35`, `defer=5`.
- **No model file yet:** `data/fixture_model.json` is a future deliverable, not a current runtime source.

---

## 10. For the final reviewer - challenge these

1. **Base-dependence assumption:** is the revised 5-channel / corpus-heavy base probe sufficient, or should CH10/CH18/CH13/CH14 be included before Phase 3?
2. **Phase 3 feasibility:** if base-dependent, which bases and grids should be reduced first to stay under a practical capture cap?
3. **Dual-exposure mechanism:** is CH1-based brightness bracketing safe after CH1 validation, or should camera exposure bracketing be required?
4. **Direction extraction robustness:** is centroid/PCA plus fallback visual review enough, or must the analyzer implement per-beam tracking before Phase 1 exit?
5. **Capture budget realism:** are the revised 4-7h Phase 1 and 6-10h base-invariant Phase 3 estimates still too optimistic for the real rig?
6. **Property curve representation:** is sampled piecewise interpolation sufficient, or should specific channels require parametric fits?
7. **Validation metric:** are the Phase 6 tolerances and weighted pass/fail criteria concrete enough?
8. **Higher-order risk:** should any real cue family be gridded up front instead of waiting for Phase 6 failure?
9. **Scope mistakes:** are any channels, interactions, exclusions, or known facts still wrong relative to the artifacts?

---

## 11. Change log

- v0 (DRAFT, 2026-06-05): initial program authored from session findings. Pending Codex review.
- v1 (Codex review, 2026-06-06): verified corpus/capture/coverage facts against repo artifacts; corrected coverage buckets; clarified that `data/fixture_model.json` does not exist or drive runtime yet; fixed the 60fps timing claim to distinguish Nyquist from current estimator floor; preserved the no-clipped-gate rule; strengthened Phase 1.5 base-dependence gate with corpus-heavy CH3/CH4 bases and CH19; quantified Phase 3 base-dependence multiplier and infeasibility threshold; revised dual-exposure method to avoid assuming CH1 is harmless; added signed-direction fallback requirements; added schema/provenance/versioning rules; added a concrete Phase 6 validation metric; corrected known-facts/caveats; added review responses in section 12.
- v2 (Claude final verdict, 2026-06-06; six-lens subagent fan-out): **§3.9 capture storage layout added** (phase→channel/group→test-state under `captures/fixture_model/`, master `manifest.jsonl`, per-test folder contents, naming conventions, evidence back-links). **Before-Phase-1 fixes:** sweep direction must use regression slope not first-vs-last (real bug in `dense_cue_breakpoints.py`); visual review formalized; CH1 sweep mandated first; §3.5 tightened (0.07 coeff at 60fps still caps 15 Hz — need ≤0.033); Phase 1/1.5 budgets corrected to measured 16.8 s/capture (~10–14 h / ~6.5 h); §0 stale-`next_actions` warning; Phase 1 exit now produces the geometry-precision artifact. **Before Phase 2:** CH18 corrected from gated to not-gated (54% of CH18 cues have CH8=0). **Phase 1.5:** probe expanded to 7 channels (added CH10, CH18); CH13/CH14 partial-coverage caveat. **Phase 3:** added CH12×CH15 and CH15×CH19 grids; coarse grids now the default; per-group approval gates; cap lowered to 3,500; ~17 h reality stated. **Phase 5:** formal JSON Schema required; structured gate predicates; CH8 multi-property representation; computable composition block; adapter must augment not replace `decode_36ch()`. **Phase 6:** geometry envelope tied to the Phase 1 artifact; equal-weight-per-active-property scoring. **Phase 4:** added CH11×CH15 spot-check. **§8:** concrete SHA-256 before/after+diff=STOP, `fixtures.py` added to hash check, post-Phase-5 schema validation. Four guardrails confirmed intact by all six lenses.

---

## 12. Review responses to section 10 challenges

1. **Base-dependence assumption:** The original 4 channels x 4 bases was too thin because it omitted CH19 and missed the most common real CH3=28/CH4=0 base. v1 requires at least CH8/CH12/CH15/CH17/CH19 across lab and corpus-heavy CH3/CH4 pairs. Confirmation still needed on whether CH10, CH18, CH13, and CH14 can be inferred from those representatives.

2. **Phase 3 feasibility:** Full base-dependent Phase 3 is not tractable. Base-invariant Phase 3 is about 3,584 dual-track captures; five-base multiplication is about 17,920 captures. v1 requires group-specific reduction to real cue bases and an explicit rescope above about 5,000 timed-equivalent captures.

3. **Dual-exposure mechanism:** CH1-based bracketing is not automatically valid because CH1 is itself a fixture channel. v1 requires CH1 validation first. If CH1 is not brightness-only, hold CH1 fixed and bracket camera exposure instead.

4. **Direction extraction robustness:** Centroid drift and PCA angle slope are necessary but not sufficient for symmetric rings, multi-beam fans, and wave deformations. v1 adds per-beam/feature tracking fallback or visual-review gating before signed direction can be considered resolved.

5. **Capture budget realism:** The original Phase 1 estimate was optimistic. v1 estimates Phase 1 at 4-7 rig hours and Phase 3 at 6-10 hours if base-invariant, with overnight risk if timed holds and overhead dominate.

6. **Property curve representation:** Piecewise sampled curves remain the default because they match the evidence workflow and discrete DMX bank structure. v1 requires explicit interpolation type per map and allows parametric fits only when validated against held-out samples.

7. **Validation metric:** The original spec did not define one. v1 adds property-specific tolerances for blanking, base look, color, strobe Hz/duty, motion type, direction, rate, and geometry envelope, plus aggregate pass/unresolved/fail reporting.

8. **Higher-order risk:** Compose-then-validate remains the right first principle, but v1 adds a failure condition: if Phase 6 shows widespread higher-order failures, stop and rescope toward direct cue-family modeling. No speculative high-order grids are added before evidence.

9. **Scope mistakes:** v1 keeps CH2, CH3>=128, CH20-36, and Laser 2 independent calibration out of scope. It corrects the known-facts section to current artifact counts and notes that `timed_motion_ch1_19.py` still has the old period floor.
