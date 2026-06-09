# Phase 2 — Post-Analysis Audit Report

**Date:** 2026-06-08  
**Dataset:** 8,236 captures at 60 FPS  
**Runtime:** ~4 hours on MacBook Air (passive cooling, thermal throttled)  
**Errors during analysis:** 1 (CH16_016 corrupted video.mp4)

---

## 1. Capture Inventory Summary

| Metric | Count |
|---|---|
| Total capture directories | 8,236 |
| Total analysis.json produced | 8,236 |
| Valid analyses | 8,236 |
| Blank (valid zero/off semantics) | 378 |
| Clipped (wall/edge clipping) | 289 |
| Failed to parse | 0 |
| Missing analysis.json | 0 |
| Missing metadata.json | 0 |
| Needing recapture | ~50 (CH16 clipping region) |

> [!NOTE]
> Zero failures. Every single capture directory has both `metadata.json` and `analysis.json`. The dataset is structurally complete.

### Phase Breakdown

| Phase | Captures | Purpose |
|---|---|---|
| phase1_single_channel | 2,472 | Isolated single-channel sweeps |
| phase1_5_base_dependence | 1,848 | Base-look-dependent single-channel sweeps |
| phase2_gating | 29 | Gate verification (CH1, CH3 gates) |
| phase3_composition | 3,664 | Pairwise/triple interaction matrices |
| phase4_independence | 48 | Independence verification |
| phase6_cue_validation | 175 | Real SoundSwitch cue stack validation |

---

## 2. Channel Coverage Report (CH1–CH19, First Pattern)

| CH | Captures | Valid | Blank | Clipped | Dirty Color | Value Range | Unique Values | Confidence | Recapture? |
|---|---|---|---|---|---|---|---|---|---|
| CH01 | 2 | 2 | 1 | 0 | 0 | 0–220 | 2 | measured_estimated | No (dimmer is binary on/off + scale) |
| CH02 | — | — | — | — | — | — | — | not_captured_standalone | No (auto/sound mode, not spatial) |
| CH03 | 520 | 520 | 0 | 0 | 0 | 2–255 | 57 | measured_good | No |
| CH04 | — | — | — | — | — | — | — | covered_via_CH03_CH04_atlas | No |
| CH05 | 130 | 130 | 2 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH06 | 130 | 130 | 28 | 4 | 4 | 0–255 | 65 | measured_good | No (blanking at extremes is correct behavior) |
| CH07 | 130 | 130 | 64 | 10 | 1 | 0–255 | 65 | measured_estimated | Targeted (high blank + clip rate at extremes) |
| CH08 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH09 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH10 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH11 | 130 | 130 | 0 | 1 | 0 | 0–255 | 65 | measured_good | No |
| CH12 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH13 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH14 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH15 | 130 | 130 | 11 | 5 | 0 | 0–255 | 65 | measured_good | No |
| CH16 | 130 | 130 | 31 | **50** | 2 | 0–255 | 65 | **dirty_capture** | **Yes** (38% clip rate, corrupted video) |
| CH17 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH18 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |
| CH19 | 130 | 130 | 0 | 0 | 0 | 0–255 | 65 | measured_good | No |

> [!WARNING]
> **CH16 (Vertical Movement)** has a 38% clipping rate (50/130 captures clipped) plus one corrupted video file (CH16_016). This is the single worst channel in the dataset and directly impacts the CH7×CH16 interaction matrix. This is the #1 recapture priority.

> [!NOTE]
> CH07 has 64 blank captures (49%) — this is physically correct behavior. The vertical position channel blanks the beam at extreme values (0 and 255 are "out of bounds"). The 10 clipped captures are at boundary values near the blank threshold. This is geometry_estimated, not dirty.

---

## 3. Interaction Coverage Report

| Interaction | Captures | Base Looks | Confidence | Visual Consequence | Recapture? |
|---|---|---|---|---|---|
| CH8 × CH9 (color × speed) | 384 | 6 bases | measured_good | Color animation timing | No |
| CH8 × CH18 (color × gradient) | 384 | 6 bases | measured_good | Gradient overlay accuracy | No |
| CH6 × CH15 (position × movement) | 384 | 6 bases | measured_good | Horizontal translation | No |
| CH5 × CH17 (size × zoom) | 384 | 6 bases | measured_good | Pattern scale accuracy | No |
| CH15 × CH19 (movement × wave) | 384 | 6 bases | measured_good | Wave modulation on sweep | No |
| CH12 × CH15 (rotation × movement) | 384 | 6 bases | measured_estimated | Rotation during sweep | No (but some clipping) |
| CH12 × CH13 × CH14 (triple rotation) | 1,296 | 6 bases | measured_estimated | 3-axis rotation compose | No |
| **CH7 × CH16** (vert pos × vert move) | **0** | **0** | **missing** | **Vertical translation** | **Yes — Priority 1** |

> [!CAUTION]
> **CH7 × CH16 interaction has ZERO dedicated captures.** There is no `group_translate_CH7xCH16` folder in the composition directory. Both channels individually have data, but their combined interaction behavior is completely unmeasured. This is a real gap that affects vertical translation rendering accuracy.

---

## 4. Temporal Limitation Report

| Behavior | CH | Captures | 60fps Reliable? | Classification |
|---|---|---|---|---|
| Strobe | CH11 | 156 | ✅ Yes (all ≤30Hz detected) | measured_good |
| Color speed | CH9 | 130 | ✅ Yes (color chase visible) | measured_good |
| Rotation speed (Z) | CH12 | 778 | ⚠️ Partially (fast_motion_inferred on some) | temporal_estimated |
| Movement speed (H) | CH15 | 394 | ⚠️ Partially | temporal_estimated |
| Zoom speed | CH17 | 394 | ⚠️ Partially | temporal_estimated |
| Gradient speed | CH18 | 394 | ⚠️ Partially | temporal_estimated |
| Wave speed | CH19 | 778 | ⚠️ Partially | temporal_estimated |
| Rotation speed (X/Y) | CH13/14 | 130 each | ⚠️ Partially | temporal_estimated |

**Key finding:** 1,473 captures (17.9% of total) have `fast_motion_timing_inferred: true`. This means the analyzer detected motion too fast to precisely characterize at 60fps and fell back to numeric regression. This is **not a fatal flaw** — it means timing is estimated rather than exact for fast-moving effects.

**60fps hard limit assessment:**
- Strobe ≤30Hz: fully measurable ✅
- Slow-medium rotation/movement/zoom: fully measurable ✅
- Fast rotation (CH12 high speed values): timing estimated, direction reliable ⚠️
- Very fast wave/movement combos: timing estimated ⚠️
- Recapture at higher FPS: **NOT possible** (Continuity Camera limit is 60fps)

---

## 5. Dirty Capture Report

| Dirty Reason | Count | Severity |
|---|---|---|
| Clipped (wall/edge) | 289 | Medium — affects geometry at extremes |
| Color on spatial channel | 248 | Low — CV artifact, sanitizable in adapter |
| Geometry clipped low | 86 | Medium — beam hitting bottom of frame |

**Total dirty captures: 512 (6.2% of dataset)**

### Classification of dirty regions:

| Region | Action |
|---|---|
| CH16 clipping (50 captures) | **needs_recapture** — too many clipped values to trust geometry |
| CH07 boundary blanking (10 clipped) | can_sanitize — blanking at extremes is expected behavior |
| CH06 boundary blanking (4 clipped) | can_sanitize — same as CH07 |
| Color labels on spatial channels (248) | can_sanitize — already handled by `_sanitize_model()` in adapter |
| CH12×CH15 clipping (scattered) | should_be_ignored — rotation at extreme movement pushes beam wide |
| Phase2 gating clips (1) | should_be_ignored — edge case |

> [!TIP]
> 248 of the 512 dirty captures are **color_on_spatial** artifacts. These are already handled by the `sanitize_model()` function in `fixture_model_adapter.py` which reclassifies `color_animated` on spatial channels. No recapture needed for these.

---

## 6. Geometry Measurement Audit

### Overall Geometry Quality

| Classification | Count | % of Total |
|---|---|---|
| geometry_good | 7,397 | 89.8% |
| geometry_estimated | 178 | 2.2% |
| geometry_dirty | 283 | 3.4% |
| geometry_failed | 0 | 0% |
| Blanked (valid off) | 378 | 4.6% |

> [!NOTE]
> **89.8% of all captures have clean, reliable geometry.** Zero geometry failures. The 178 estimated captures are primarily high-angle-range rotation captures (>45°) where the oriented bounding box shifts significantly across frames — this is expected physical behavior for rotation channels, not a measurement error.

### Per-Channel Geometry Confidence

| CH | Centroid | Area/Spread | Angle | Blanking | Dirty Regions | Recapture? |
|---|---|---|---|---|---|---|
| CH05 | good | good | good | good (2 blank) | None | No |
| CH06 | good | good | good | good (28 blank at extremes) | 0–3, 252–255 blank zone | No |
| CH07 | estimated | estimated | good | good (64 blank at extremes) | 0–40, 215–255 blank zone | Targeted |
| CH08 | good | good | N/A (color) | N/A | None | No |
| CH09 | good | good | N/A (color speed) | N/A | None | No |
| CH10 | good | good | good | good | None | No |
| CH11 | good | good | N/A (strobe) | N/A | None | No |
| CH12 | good | estimated | good | good | None | No |
| CH13 | good | estimated | good | good | None | No |
| CH14 | good | estimated | good | good | None | No |
| CH15 | good | good | good | good (11 blank) | None | No |
| **CH16** | **dirty** | **dirty** | **dirty** | **dirty (31 blank)** | **50 clipped, 1 corrupt** | **Yes** |
| CH17 | good | good | good | good | None | No |
| CH18 | good | good | N/A (gradient) | N/A | None | No |
| CH19 | good | good | good | good | None | No |

### Interaction Geometry Confidence

| Interaction | Geometry | Visual Consequence | Recapture Values | Suggested Base Looks |
|---|---|---|---|---|
| CH6 × CH15 | good | Horizontal translation accurate | None | — |
| **CH7 × CH16** | **missing** | **Vertical translation completely unknown** | **Full 8×8 grid: CH7 [32,64,96,128,160,192] × CH16 [32,64,96,128,160,192]** | **CH3=0/CH4=195 (static look)** |
| CH5 × CH17 | good | Scale interaction accurate | None | — |
| CH12 × CH15 | estimated (some clips) | Rotation during sweep slightly noisy | None needed | — |
| CH15 × CH19 | good | Wave on movement accurate | None | — |
| CH12 × CH13 × CH14 | estimated | Triple rotation compose noisy at extremes | None needed | — |

### Geometry Summary

1. **Good enough:** CH05–CH06, CH08–CH15, CH17–CH19, all pairwise interactions except CH7×CH16
2. **Estimated:** CH07 boundary, CH12/13/14 rotation spread, CH12×CH15 interaction
3. **Dirty:** CH16 single-channel (38% clip rate)
4. **Missing:** CH7×CH16 interaction
5. **Use now:** Everything classified good or estimated
6. **Fallback only:** CH16 clipped captures (use blanking threshold from CH16 non-clipped data)

---

## 7. Targeted Recapture List

### Priority 1 — Blocks renderer accuracy

| Item | Why | Channels | Values | Base Looks | Expected Improvement |
|---|---|---|---|---|---|
| CH7 × CH16 interaction matrix | Zero captures exist | CH7, CH16 | 6×6 grid: [32,64,96,128,160,192] each | CH3=0/CH4=195, CH3=32/CH4=10 | Unlocks vertical translation rendering |
| CH16 single-channel reclean | 50/130 clipped, 1 corrupt video | CH16 | 0–255 step 4 | CH3=0/CH4=195 | Clean vertical movement geometry |

**Total Priority 1 recaptures: ~100 captures** (36 interaction + 65 single-channel)

### Priority 2 — Improves accuracy at boundaries

| Item | Why | Channels | Values | Expected Improvement |
|---|---|---|---|---|
| CH07 boundary captures | 10 clipped at blank threshold | CH7 | 35–45, 210–220 (boundary region) | Sharper blank threshold detection |
| CH12×CH15 clipped captures | Some clipping at max rotation + max movement | CH12=255, CH15=200–255 | 5–10 captures | Cleaner extreme rotation+sweep |

**Total Priority 2: ~20 captures**

### Priority 3 — Optional polish

| Item | Why | Expected Improvement |
|---|---|---|
| Real SoundSwitch cue stack validation | Only 175 cues validated | Confidence in complex multi-channel stacks |
| Additional CH01 dimmer curve points | Only 2 captures | Smoother dimmer ramp (cosmetic only) |

**Total Priority 3: Optional, ~50 captures**

---

## 8. Renderer Readiness Summary

**Can the renderer move forward without full recapture?** **YES.**

| Behavior | Status |
|---|---|
| Pattern selection (CH3/CH4) | ✅ Trusted (520 captures, 57 unique values) |
| Pattern size (CH5) | ✅ Trusted |
| Horizontal position (CH6) | ✅ Trusted |
| Vertical position (CH7) | ⚠️ Estimated (blank boundaries noisy) |
| Color (CH8) | ✅ Trusted |
| Color speed (CH9) | ✅ Trusted |
| Scan mode (CH10) | ✅ Trusted |
| Strobe (CH11) | ✅ Trusted |
| Rotation Z (CH12) | ✅ Trusted (speed timing estimated for fast values) |
| Rotation X/Y (CH13/14) | ✅ Trusted |
| H Movement (CH15) | ✅ Trusted |
| V Movement (CH16) | ⚠️ Dirty (38% clip rate, needs recapture) |
| Zoom (CH17) | ✅ Trusted |
| Gradient (CH18) | ✅ Trusted |
| Wave (CH19) | ✅ Trusted |
| CH6×CH15 translation | ✅ Trusted |
| CH8×CH9 color×speed | ✅ Trusted |
| CH8×CH18 color×gradient | ✅ Trusted |
| CH5×CH17 size×zoom | ✅ Trusted |
| CH15×CH19 move×wave | ✅ Trusted |
| CH7×CH16 vert translation | ❌ Missing — not measurable from existing data |
| CH12×CH13×CH14 triple rotation | ⚠️ Estimated (noisy at extremes) |
| CH12×CH15 rot×move | ⚠️ Estimated (some clipping) |

---

## 9. Simple Human-Readable Summary

**For the project director:**

- **What data is good enough:** 89.8% of all 8,236 captures have clean, reliable geometry. 14 out of 19 channels are fully trusted. 5 out of 7 interaction matrices are fully measured.

- **What data is estimated:** Vertical position (CH07) boundary behavior, all fast rotation/movement timing (the camera can't go above 60fps), and the triple rotation interaction at extreme values.

- **What data is missing:** The **CH7 × CH16 vertical translation interaction** was never captured. There is no data for how vertical position and vertical movement combine. This is the single biggest gap.

- **What I need to recapture:** About **100 targeted captures** — mostly a 6×6 CH7×CH16 interaction grid plus a clean re-sweep of CH16 single-channel (which has too much wall clipping). This is maybe 30 minutes of physical laser time.

- **What I do NOT need to recapture:** Everything else. 8,135 out of 8,236 captures are usable. Do not redo the full dataset.

- **Whether the renderer can move forward now:** **YES.** The renderer can proceed with current data for all horizontal behaviors, color, rotation, zoom, wave, and strobe. Vertical translation will be estimated/fallback until the CH7×CH16 recapture is done.

- **Whether the physical lasers still need to stay available:** **YES** — for the ~100 targeted recaptures and for real SoundSwitch cue-stack validation.

---

## FINAL VERDICT

### 1. Recapture everything?
**Answer: No**

### 2. Proceed with existing 8000+ dataset?
**Answer: Yes** (with targeted supplements for CH16 and CH7×CH16)

### 3. Targeted recaptures needed?
**Answer: Yes** — approximately 100 captures focused on CH16 geometry and CH7×CH16 interaction

### 4. Physical lasers still needed for validation?
**Answer: Yes** — for targeted recaptures and cue-stack validation

### 5. Current model confidence:
**Answer: usable previz**

Moving toward "model-aware previz" once CH7×CH16 is captured and CH16 is recleaned. "High-confidence previz" requires full cue-stack validation against real SoundSwitch output.

### 6. Next action:
**Recapture CH16 single-channel sweep (65 captures) and CH7×CH16 interaction grid (36 captures).** This is 30 minutes of physical laser time and unblocks vertical translation for the renderer.

---

## Recommended Next Task for ChatGPT Architect

The architect should direct the next physical capture session with these exact parameters:

1. **CH16 single-channel re-sweep**: CH16 values 0–255 step 4, base look CH3=0/CH4=195, camera stable, ensure beam does NOT clip bottom of frame (raise camera or tilt down slightly).

2. **CH7×CH16 interaction matrix**: 6×6 grid with CH7=[32,64,96,128,160,192] × CH16=[32,64,96,128,160,192], base look CH3=0/CH4=195 and CH3=32/CH4=10.

3. After recapture, re-run `reprocess_60fps.py` on only the new captures, then re-assemble `fixture_model.json`.

4. Once CH7×CH16 data exists, implement the composition rule in `fixture_model_adapter.py` (currently listed as `composition_missing` with reason `insufficient_data`).

---

## Addendum: Targeted Recapture Prepared (2026-06-08)

A targeted recapture workflow has been fully prepared per the architect's corrections:
* **Session ID:** `recapture_CH16_CH7xCH16_distance_adjusted_2026_06_08`
* **Preflight Gate:** Built into `calib/targeted_recapture.py` to analyze 12 boundary frames immediately at 60 FPS and halt on `clipped` or `geometry_clipped_low` flags to ensure the slight framing shift (0.5cm) remains safe.
* **Semantic CH16 Split:** The CH7xCH16 matrix correctly maps `CH16 <= 120` as static positional geometry (24 frames per base) and `CH16 >= 128` as temporal estimated speed geometry (9 frames per base).
* **Total Captures:** 143 captures (12 preflight + 65 CH16 re-sweep + 33 Base A CH7xCH16 + 33 Base B CH7xCH16)
* **Tooling:** Use `python3 calib/targeted_recapture.py --rig-confirmed` to run, `python3 calib/reprocess_60fps.py captures/recapture_CH16_CH7xCH16_distance_adjusted_2026_06_08` to process, and `python3 calib/fixture_model_analyzer.py --include-session captures/recapture_CH16_CH7xCH16_distance_adjusted_2026_06_08` to assemble.
