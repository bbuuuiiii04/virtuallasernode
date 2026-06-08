# Fixture Model Post-Capture Analysis Report

**Run:** CH1–19 fixture model physical capture, completed 2026-06-08 ~12:09 EDT (rc=0)
**Dataset:** 8,324 manifest rows across 6 phases, ~24 GB under `captures/fixture_model/`
**Model status:** `partial` — evidence indexed, no transfer functions fitted, no validation comparison run

---

## 1. Executive Summary

### Run Health: GOOD

The 11-hour capture run completed cleanly across all 6 phases with excellent operational stability:
- **FPS:** 98.5% of captures at 58–60 fps; only 4 captures below 55 fps (3 fps resets, all recovered)
- **Blanks:** 444 total (5.3%), concentrated in known blank-zone channels (CH6/CH7 position, CH15 movement)
- **Safety:** Final state `(all zero)`, clean shutdown
- **Evidence integrity:** All 12 sampled evidence folders contain complete artifacts (video, still, metadata, analysis)

### Three Critical Findings

> [!CAUTION]
> **Finding 1: Phase 5 is a ~15-line stub.** The "large offline analysis" the operator expected did not happen. `phase5()` writes a skeleton schema, sets `model_status = "partial"`, and exits. No transfer functions are fitted. No composition rules are derived. No cross-check against `fixtures.py` is performed. The model file is an evidence index, not a predictive model.

> [!CAUTION]
> **Finding 2: Phase 6 validation is a no-op.** `phase6_validate()` marks all 293 entries (118 dense + 175 new) as `unresolved`. No model-vs-measure comparison exists. The 175 Phase 6 captures are good raw data, but validation has not been attempted.

> [!WARNING]
> **Finding 3: The schema fails its own model.** `data/fixture_model_schema.json` requires an `interactions` key, but the model has `gates` and `higher_order` at the top level instead. The model would fail JSON Schema validation if `jsonschema` were installed.

### Dataset Verdict

The capture dataset is **good enough for model building**. Coverage is comprehensive, blank rates are explainable, and fps quality is excellent. The gap is entirely in offline analysis: the data exists but hasn't been processed into transfer functions, composition rules, or validation results.

---

## 2. Phase-by-Phase Capture Report

### Phase 0 — Methodology / Dense Citation

| Metric | Value |
|---|---|
| Dense root accessible? | **No** — `/tmp/vln_dense_cue_breakpoints_20260605_200426` is ephemeral and gone |
| Cited dense rows | 118 (from `data/fixture_model.json` provenance) |
| Phase 6 reference | `phase0_record_dense_root_absent` — uses the recorded count, not live re-validation |

Phase 0 ran `validate_existing_dense()`, which detected the absent `/tmp` root and fell back to the recorded provenance count of 118. This is honest but means Phase 6 cannot re-analyze those captures. The 118 dense captures would need recapturing or restoring from backup to enable full Phase 6 comparison.

---

### Phase 1 — Single-Channel Transfer Functions

| Metric | Value |
|---|---|
| Total captures | 2,515 |
| Blank captures | 171 (6.8%) |
| Channels swept | 17 (CH1 + CH3/CH4 atlas + CH5–CH19) |
| CH1 gate | CH1=0 → blank, CH1=220 → visible (binary on/off confirmed) |
| Step size | Every 4 values (0, 4, 8, ..., 252, 255) = 65 sweep values per channel |
| Dual-track | Both `geometry_motion` and `color` tracks for all non-CH1 channels |

**Per-channel blank rates:**

| Channel | Captures | Blanks | Rate | Notes |
|---|---|---|---|---|
| CH1 | 2 | 1 | 50% | Expected: CH1=0 is blackout |
| CH3/CH4 atlas | 520 | 0 | 0% | 5 CH3 reps × 52 CH4 programs × 2 tracks |
| CH5 size | 132 | 4 | 3.0% | Minor blanks at extremes |
| CH6 horizontal | 130 | 28 | 21.5% | **Expected** — CH6 moves pattern out of frame |
| CH7 vertical | 130 | 74 | 56.9% | **Expected** — CH7 moves pattern out of frame |
| CH8–CH14 | 130 ea | 0 | 0% | Clean sweeps |
| CH15 movement | 142 | 23 | 16.2% | Some movement sweeps blank out of frame |
| CH16 movement | 136 | 41 | 30.1% | More blanks — vertical movement exceeds ROI |
| CH17–CH19 | 130 ea | 0 | 0% | Clean sweeps |

> [!NOTE]
> CH6/CH7/CH15/CH16 blanks are **expected fixture behavior** (pattern moves out of visible area), not capture failures. The orchestrator correctly distinguishes these via `blank_observation_reason = "ch6_ch7_out_of_bounds_closed_light"`.

**CH3/CH4 atlas completeness:** 5 CH3 bank reps × 52 CH4 programs × 2 tracks = **520 captures, 0 blanks**. This covers the spec's static bank atlas requirement.

**Transfer function quality:**
- All channels have evidence paths in `fixture_model.json` (no placeholder `capture/test/path` entries found)
- **BUT**: All channels show `banks=0, base_dependence=unknown, confidence=low` — `merge_phase_observations()` only indexed evidence paths, it did not fit transfer functions, extract breakpoints, or determine bank boundaries

**Geometry-precision exit artifact:** The spec requires a "centroid tolerance ±N px, area tolerance ±M%, angle tolerance ±P°" measurement from Phase 1. **This artifact does not exist.** Phase 6 geometry-envelope tolerances are therefore undefined.

---

### Phase 1.5 — Base-Dependence Gate

| Metric | Value |
|---|---|
| Total captures | 1,848 |
| Blank captures | 60 (3.2%) |
| Probe channels | 7 (CH8, CH10, CH12, CH15, CH17, CH18, CH19) |
| Bases probed | 6 |
| Probe values per channel/base | 22 values × 2 tracks = 44 captures |

**Gate verdict: ALL 7 probe channels are base-dependent**

| Channel | Verdict |
|---|---|
| CH8 (color) | `base_dependent` |
| CH10 (line) | `base_dependent` |
| CH12 (rotation Z) | `base_dependent` |
| CH15 (movement) | `base_dependent` |
| CH17 (zoom) | `base_dependent` |
| CH18 (gradient) | `base_dependent` |
| CH19 (wave) | `base_dependent` |

This triggered `phase3_scope = "reduce_to_varied_groups_and_real_cue_bases"`, meaning Phase 3 expanded most groups across all 6 bases. The exception is `translate_CH7xCH16` (CH7/CH16 not probed) which ran on 1 base only.

> [!WARNING]
> **Gate metric concern:** The gate compares `loop_duration_estimate` or `motion_direction_confidence` means across bases, with a >25% deviation threshold. This is a coarse proxy — a channel could have different *spatial* behavior across bases while having similar loop timing, or vice versa. The "all base-dependent" result is plausible but should be verified against actual behavioral analysis when transfer functions are fitted.

**CH15 blank pattern:** 10 blanks per base (23%) — consistent across all 6 bases, confirming the blanks are from movement values that push the pattern out of frame, not from base-specific issues.

---

### Phase 2 — Gating Dependencies

| Metric | Value |
|---|---|
| Total captures | 29 |
| Blank captures | 7 (24.1%) |
| Tests | CH1→all gate, CH3 static/dynamic split, CH8→CH9, CH8↔CH18 (not a gate), CH3/CH4→shape |

The 7 blanks include expected CH1=0 blackout tests. The spec called for 40–80 captures; the 29 actual captures cover the core gate tests. Notable:
- **CH8→CH9 gate:** Tested at CH8={0, 20, 60, 245} with CH9=128
- **CH8↔CH18 not-gate:** Explicitly tested as "not a gate" per v2 spec correction (54% of CH18 cues have CH8=0)
- **CH8→CH18 not in interactions:** No gate entries exist in the model (correct for the non-gate finding, but the model also has no compositional or interaction rules at all)

> [!NOTE]
> CH8↔CH18 gating was **NOT** tested — it was correctly classified as "not a gate" per the v2 spec revision. This is intentional.

---

### Phase 3 — Compositional Grids

| Metric | Value |
|---|---|
| Total rows | 3,709 |
| Blank captures | 205 (5.5%) |
| Recapture pending | 250 (6.7%) |
| fps30 | 4 |
| Expected (computed) | 3,664 |
| Extra rows | 45 (blank retries creating duplicate manifest entries) |
| Grid resolution | `grid_values(8)` → 8 evenly-spaced values (0, 36, 73, 109, 146, 182, 219, 255) |

**Groups completed (all on 6 bases unless noted):**

| Group | Captures | Blanks | Bases | Notes |
|---|---|---|---|---|
| colour_CH8xCH9 | 64×6=384 | Low | 6 | |
| colour_CH8xCH18 | 64×6=384 + extras | Low | 6 | 2-4 extra rows per some bases |
| translate_CH6xCH15 | 64×6=384 + extras | **High** | 6 | 9-17 extra rows from blank retries |
| translate_CH7xCH16 | 64×1=64 | High | **1** | CH7/CH16 not in probe set |
| scale_CH5xCH17 | 64×6=384 | Low | 6 | |
| rotation_move_CH12xCH15 | 64×6=384 | Low | 6 | |
| move_wave_CH15xCH19 | 64×6=384 | Low | 6 | |
| orientation_CH12xCH13xCH14 | 216×6=1296 | Low | 6 | 6×6×6 triple grid |

**Blank hotspots — CH6=0 translate combos:**

| CH6 Value | Captures | Blanks | Rate |
|---|---|---|---|
| CH6=0 | 64 | 36 | **56.2%** |
| CH6=255 | 56 | 30 | **53.6%** |
| CH6=128 | 64 | 27 | **42.2%** |
| CH6=36 | 51 | 9 | 17.6% |
| CH6=109 | 48 | 0 | 0% |

The CH6=0 and CH6=255 blanks are expected — these extreme horizontal positions move the pattern entirely out of frame. The CH6=128 blanks are surprising (128 should be centered) and likely reflect combinations where CH15 movement sweeps the pattern off-screen during the 8-second clip.

**Valid count reconciliation:**
- 3,709 total − 205 blank = 3,504 non-blank
- 3,504 non-blank − 45 duplicate retry rows = **3,459 usable** (matches the prompt's "3,459 valid" figure)
- The "3,664 planned valid" figure = 3,664 expected captures, of which 205 were blank → 94.4% non-blank rate

---

### Phase 4 — Independence Spot-Checks

| Metric | Value |
|---|---|
| Total captures | 48 |
| Blank captures | 0 (0%) |
| Pairs tested | 6 |
| Values per pair | 8 diagonal combinations |

**All 6 pairs:**

| Pair | Captures | Blanks | Rationale |
|---|---|---|---|
| CH11×CH8 (strobe×color) | 8 | 0 | Orthogonality of strobe and color mode |
| CH11×CH12 (strobe×rotation) | 8 | 0 | Strobe doesn't affect rotation |
| CH11×CH15 (strobe×movement) | 8 | 0 | **Critical:** does strobe gate position updates? |
| CH12×CH8 (rotation×color) | 8 | 0 | |
| CH17×CH8 (zoom×color) | 8 | 0 | |
| CH19×CH8 (wave×color) | 8 | 0 | |

Zero blanks across all pairs is a strong signal. However, **no actual pass/fail analysis has been performed** — the independence verdict (whether each channel's effect is unchanged by the other) requires comparing the 8 diagonal captures against single-channel baselines. This analysis hasn't been done in `merge_phase_observations()` and isn't part of Phase 5's stub implementation.

---

### Phase 6 — Cue Validation Captures

| Metric | Value |
|---|---|
| Total captures | 175 |
| Blank captures | 1 (0.6%) |
| fps30 | 0 |
| fps range | 57.8–60.0 |
| Recapture pending | 7 |

**175 unique resolved cue vectors captured**, derived from `data/soundswitch_laser_cues.json`. fps quality is excellent (all ≥57.8). The 1 blank capture is likely the CH1=0 "off" cue.

> [!IMPORTANT]
> **Validation has NOT run.** `phase6_validate()` marks all 293 entries (118 dense + 175 new) as `unresolved` with `pass=0, firmware_locked=0, higher_order=0`. No model-vs-measure comparison was attempted because:
> 1. No predictive composition function exists
> 2. The dense root is absent (captures in ephemeral `/tmp`)
> 3. `phase6_validate()` is designed to be a placeholder until model assembly is complete

---

## 3. Offline Analysis Gap Analysis — Phase 5 & Phase 6

### Phase 5: Spec vs Implementation

```diff
  SPEC (docs/FIXTURE_MODEL_PROGRAM.md §Phase 5)          IMPLEMENTATION (phase5() — 18 lines)
  ────────────────────────────────────────────────          ──────────────────────────────────────
- Merge Phases 1–4 into fixture_model.json                → merge_phase_observations() indexes evidence
  (transfer functions, gates, composition rules)             paths only — no fitting, no rule extraction
  
- Formal JSON Schema (draft-07) with enums,              → Writes skeleton with 9 required top-level
  required fields, testable structure                        keys; channels = {type: object} (no depth)
  
- Composition adapter predicting resolved                 → fixture_model_adapter.py exists but wraps
  CH1-19 for any in-scope vector                            decode_36ch() + evaluates gating predicates
                                                             (model has 0 gates → always empty)
  
- Cross-check fixtures.py decode vs model                 → Not attempted
  banks/breakpoints
  
- FIXTURE_MODEL_ASSEMBLY.md                               → Does not exist
- Deterministic prediction with confidence flags          → Not implemented
```

### What `merge_phase_observations()` Actually Does

Called after each capture phase, it reads the manifest and for each row:
1. Creates a channel entry in the model if it doesn't exist (with `banks=[], base_dependence=unknown, confidence=low`)
2. Appends the capture folder path to the channel's `evidence[]` array

**This is evidence indexing, not model assembly.** The result is 18 channels, each with hundreds of evidence paths, but zero banks, zero transfer functions, zero breakpoints, and all confidence=low.

### Answers to Required Questions

**Q1: What assembly happened incrementally via `merge_phase_observations()` vs what should happen in Phase 5?**

`merge_phase_observations()` built an evidence index only: channel entries with folder paths. Phase 5 should have:
- Analyzed the evidence to extract per-channel transfer functions (banks, breakpoints, property curves)
- Populated `base_dependence` from Phase 1.5 verdicts (they exist in `method.base_dependence_gate` but aren't propagated to channels)
- Populated `interactions.gating` from Phase 2 data
- Populated `interactions.compositional` from Phase 3 grids
- Populated `interactions.independent` from Phase 4 spot-checks
- Cross-checked against `fixtures.py` decode
- Written `docs/FIXTURE_MODEL_ASSEMBLY.md`

**Q2: Is `data/fixture_model.json` a predictive model or evidence indexing?**

**Evidence indexing only.** The model contains:
- 18 channels, all with `banks=[], confidence=low`
- 0 gating rules, 0 compositional rules, 0 independent pairs, 0 higher-order entries
- 0 base_looks entries
- Phase summaries with capture statistics
- Base dependence gate verdicts (in `method`, not propagated to channels)

**Q3: Does `data/fixture_model_schema.json` validate the model?**

**No — it would FAIL.** The schema requires `interactions` (with `gating`, `compositional`, `independent`, `higher_order`), but the model has `gates` and `higher_order` at the top level instead of under `interactions`. Additionally, the model has no `interactions` key at all. `jsonschema` is not installed in either the system Python or the calib venv, so this failure was never caught.

**Q4: What does `fixture_model_adapter.py` actually compose?**

It wraps `decode_36ch()` and evaluates gating predicates from `model.interactions.gating[]`. Since the model has 0 gating rules, `gate_flags` is always empty. The adapter **cannot predict cue behavior** — it only adds empty metadata to the existing decoder output. It does not:
- Apply transfer functions
- Evaluate composition rules
- Produce confidence or unsupported-field flags (beyond the static `model_not_fully_measured`)

**Q5: Is `docs/FIXTURE_MODEL_ASSEMBLY.md` missing? What else is absent?**

Missing deliverables:
| Deliverable | Status |
|---|---|
| `docs/FIXTURE_MODEL_ASSEMBLY.md` | **Missing** |
| `docs/FIXTURE_MODEL_FINAL.md` | **Missing** |
| Fitted transfer functions in model | **Missing** |
| Populated `interactions.*` in model | **Missing** |
| Schema depth (enum validation, map shapes) | **Missing** — skeleton only |
| Deterministic prediction function | **Missing** |
| `fixtures.py` cross-check | **Missing** |
| Geometry-precision exit artifact from Phase 1 | **Missing** |

**Q6: Were manifest rows reanalyzed for CH5=0 geometry provenance?**

**No reanalysis was performed**, but per-folder `analysis.json` files show `analysis_roi_source = "analysis_geometry"` consistently, meaning all captures used the same `analysis_geometry.json` derived from the preflight CH5=0 boundary-box reference. The geometry reference is consistent across all 8,324 captures. The manifest compact analysis summaries don't store this field (showing `unknown`), but the full per-folder analysis confirms consistent provenance.

**Q7: Effort estimate — what offline work remains for spec-compliant Phase 5?**

| Work Item | Effort Estimate |
|---|---|
| Transfer function fitting (18 channels × analyze evidence) | 2–4 days |
| Populate interactions from Phase 2/3/4 data | 1–2 days |
| Composition adapter with prediction capability | 1–2 days |
| JSON Schema with full depth validation | 0.5 day |
| `fixtures.py` cross-check and gap report | 0.5 day |
| Geometry-precision artifact from Phase 1 stills | 0.5 day |
| Documentation (ASSEMBLY.md) | 0.5 day |
| **Total** | **~5–10 days of focused offline work** |

### Phase 6 Validation: Spec vs Implementation

```diff
  SPEC                                                    IMPLEMENTATION
  ────                                                    ──────────────
- Predict each cue from composed model                   → No prediction exists
- Compare predicted vs measured                          → Marks all as unresolved
- Bucket: pass / unresolved / firmware-locked /          → unresolved = dense_count + new_count
  higher-order                                              (all 293 in unresolved bucket)
- Targeted higher-order grids for failures               → Not attempted
```

**Q1: Can validation run now offline?**
Yes, in principle. The 175 Phase 6 captures have full analysis.json files. However:
- The 118 dense captures are **gone** (ephemeral `/tmp`) — only the count survives as provenance
- A composition/prediction function doesn't exist yet
- Transfer functions haven't been fitted

**Q2: What code exists for prediction?**
- `fixture_model_adapter.py`: Gate evaluation only (0 gates populated)
- `calib/dense_cue_breakpoints.py`: Motion analysis, not prediction
- `calib/soundswitch_cue_coverage.py`: Coverage reporting, not prediction
- **Missing:** Transfer function interpolation, composition rule evaluation, predicted-vs-measured comparison

**Q3: Preliminary pass/fail estimate?**
Cannot estimate without fitted transfer functions. The data is there but hasn't been reduced.

**Q4: Which cue families likely fail composition first?**
- **Strobe × movement** (CH11 × CH15): 40+ cues combine strobe with movement; if strobe gates position updates, the translate composition model fails
- **CH6=0 translate combos:** 56% blank rate at CH6=0 means limited evidence for extreme-position composition
- **Multi-modifier stacks:** Cues using 5+ active channels simultaneously (strobe + movement + rotation + zoom + wave) are the hardest for a pairwise composition model

---

## 4. Cross-Cutting Analysis

### 4.1 Data Quality Dashboard

| Metric | Value | Verdict |
|---|---|---|
| Total captures | 8,324 | ✅ |
| Blank captures | 444 (5.3%) | ✅ Mostly expected position blanks |
| fps < 55 | 4 (0.05%) | ✅ Excellent |
| fps < 30 | 3 (0.04%) | ✅ 3 fps resets, all recovered |
| Recapture pending | 257 (3.1%) | ⚠️ 250 in Phase 3, 7 in Phase 6 |
| FPS distribution | 98.5% in 58-60 range | ✅ |
| Blank retries | 671 | ✅ System handled gracefully |
| fps resets | 3 (all recovered) | ✅ |
| Corrupt JPEGs | 0 found in samples | ✅ |
| Evidence folder completeness | 12/12 sampled OK | ✅ |

### 4.2 Geometry / ROI Consistency

- **`analysis_geometry.json`** was derived from the preflight CH5=0 boundary-box reference
- **No `roi_boundary_glare_conflict`** — the boundary margin and glare band don't conflict
- All per-folder analysis.json files show `analysis_roi_source = "analysis_geometry"` — **consistent provenance**
- The CH5=0 reference (largest static pattern) vs CH5=90 capture baseline difference is handled correctly: geometry is from CH5=0, sweeps use CH5=90 via `PRIMARY_BASE`
- **No reanalysis needed** — all rows were analyzed with the same geometry from the start of this run

### 4.3 Model Auditability

12 sampled evidence folders (2 per phase) all contain complete artifacts:

| Phase | Sample | Status |
|---|---|---|
| Phase 1 | CH03_096_CH04_097 | ✅ Complete |
| Phase 1 | CH03_008_CH04_252 | ✅ Complete |
| Phase 1.5 | CH19_x_y_wave/CH19_120 (base 041) | ✅ Complete |
| Phase 1.5 | CH18_gradient/CH18_160_c (base 028) | ✅ Complete |
| Phase 2 | CH01_220_CH12_200 | ✅ Complete |
| Phase 2 | CH01_000_CH11_200 | ✅ Complete |
| Phase 3 | orientation (base 195) | ✅ Complete |
| Phase 3 | colour_CH8xCH18 (base 032) | ✅ Complete |
| Phase 4 | CH11_109_CH15_146 | ✅ Complete |
| Phase 4 | CH11_255_CH15_000 | ✅ Complete |
| Phase 6 | cue_146 lightspeed | ✅ Complete |
| Phase 6 | cue_023 green sinewaves | ✅ Complete |

Each folder has: `video.mp4` or `video_color.mp4`, `still.jpg` or `still_color.jpg`, `metadata.json`, `analysis.json`.

### 4.4 Coverage Gaps

| Gap | Impact | Action |
|---|---|---|
| translate_CH7xCH16 on 1 base only | Moderate — CH7/CH16 weren't probed | Consider adding 5 more bases if base-dependent |
| 250 Phase 3 recapture-pending rows | Low — mostly CH6 extreme position blanks | Expected behavior, not recapture needed |
| CH15 blanks (23% of Phase 1.5 probes) | Low — movement extremes | Known blank zone |
| 118 dense captures gone (/tmp) | **High** — Phase 6 comparison needs them | Recapture or restore from backup |
| No Phase 5 analysis performed | **Critical** — model is evidence-only | Offline work needed |

### 4.5 Risks for Renderer Integration

| Safe to consume now | Requires caution | Would be fabricated |
|---|---|---|
| `decode_36ch()` output (unchanged) | Channel evidence paths (exist, but unanalyzed) | Transfer functions (none fitted) |
| Phase 1.5 base-dependence verdicts | Base-look atlas (captured, but `base_looks={}`) | Composition rules (none derived) |
| Blank-zone channel lists (CH6/CH7 extremes) | Phase 2 gate observations (raw, unprocessed) | Validation pass/fail (all unresolved) |
| `analysis_geometry.json` ROI | Phase 4 independence (captured, uncompared) | Confidence values (all `low`) |

---

## 5. Prioritized Recommendations

### Priority 1: Offline Phase 5 Assembly (Critical Path)

> [!IMPORTANT]
> This is the single most important next step. Without it, the capture data has no model value.

1. **Fit transfer functions** for all 18 channels from Phase 1 evidence — extract banks, breakpoints, property curves, signed directions from the per-folder `analysis.json` files
2. **Propagate Phase 1.5 verdicts** from `method.base_dependence_gate` into per-channel `base_dependence`
3. **Extract gating rules** from Phase 2 captures into `interactions.gating`
4. **Derive composition rules** from Phase 3 grid data into `interactions.compositional`
5. **Confirm independence** from Phase 4 diagonal captures into `interactions.independent`
6. **Fix schema structure** — move `gates`/`higher_order` under `interactions`, add enum validation for `behavior`/`interpolation`/`confidence`/`direction`
7. **Build the geometry-precision artifact** from Phase 1 static/control captures

### Priority 2: Fix Schema Mismatch (Quick Win)

The model has `gates` and `higher_order` at the top level but the schema expects them under `interactions`. Install `jsonschema` in the calib venv and fix the structural mismatch before any model build step.

### Priority 3: Offline Phase 6 Validation (After Phase 5)

Once transfer functions and composition rules exist:
1. Implement the prediction function in `fixture_model_adapter.py`
2. Compare predicted vs measured for all 175 Phase 6 captures
3. Bucket results into pass/unresolved/firmware-locked/higher-order
4. Consider recapturing the 118 dense cues if Phase 6 comparison needs them

### Priority 4: Targeted Recaptures (Only If Needed)

- **250 Phase 3 recapture-pending rows:** Most are CH6 extreme position blanks — these are expected blank zones, not capture failures. Verify whether the usable data at non-extreme positions is sufficient for composition rule fitting before recapturing.
- **translate_CH7xCH16 multi-base:** Consider adding bases if analysis shows CH7/CH16 are base-dependent despite not being in the probe set.
- **7 Phase 6 recapture-pending:** Investigate these specific cues before recapture.

### Priority 5: Documentation

Write `docs/FIXTURE_MODEL_ASSEMBLY.md` and `docs/FIXTURE_MODEL_FINAL.md` as the offline analysis progresses.

---

## 6. Open Questions for the Operator

1. **Phase 5 implementation scope:** Should the offline analysis be implemented as new functions in `fixture_model_orchestrator.py`, as a separate analysis script, or as modifications to existing modules? The spec says Phase 5 should "finalize the model and define the composition function" — this is substantial engineering, not just running a script.

2. **Dense capture recovery:** The 118 dense captures from `/tmp` are gone. Should they be recaptured (adding ~33 min to a new run), or is the 175-capture Phase 6 set sufficient for validation?

3. **Base-dependence all-7 result:** All 7 probe channels were classified as base-dependent using a coarse metric (loop timing deviation). Should this be re-examined with more nuanced behavioral comparison before accepting the full 6-base Phase 3 expansion?

4. **Schema vs model structural mismatch:** The model has `gates`/`higher_order` at top level; the schema expects `interactions`. Should the model be restructured, or should the schema be relaxed? (Recommendation: restructure the model to match the spec's `interactions` layout.)

5. **Renderer consumption path:** The spec says Phase 5 should "define how renderer/export tooling will consume the model." Should this design be done before or after the offline analysis?

6. **Recapture authorization:** If specific recaptures are needed (e.g., dense set re-run, CH7/CH16 multi-base), should those be queued now or deferred until after Phase 5 analysis identifies actual gaps?

---

*Report generated 2026-06-08. Based on read-only analysis of manifest.jsonl, model artifacts, orchestrator code, and sampled evidence folders. No source files were modified.*
