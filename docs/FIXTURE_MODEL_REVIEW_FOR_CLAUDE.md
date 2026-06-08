# Claude Final Review Prompt - Fixture Model Measurement Program

You are the final reviewer for the VirtualLaserNode CH1-19 fixture-model measurement program. This is a paper review only. Do not run physical capture, drive DMX, open the laser, or touch FTDI/laser hardware.

Review target:
- `/Users/bbui/virtuallasernode/docs/FIXTURE_MODEL_PROGRAM.md`

Ground your verdict in these artifacts:
- `/Users/bbui/virtuallasernode/data/soundswitch_laser_cues.json`
- `/Users/bbui/virtuallasernode/data/soundswitch_cue_motion_coverage.json`
- `/tmp/vln_dense_cue_breakpoints_20260605_200426/manifest.jsonl`
- `/tmp/vln_dense_cue_breakpoints_20260605_200426/analysis_manifest.jsonl`
- `/Users/bbui/virtuallasernode/calib/dense_cue_breakpoints.py`
- `/Users/bbui/virtuallasernode/calib/timed_motion_ch1_19.py`
- `/Users/bbui/virtuallasernode/fixtures.py`
- `/Users/bbui/virtuallasernode/calibration.json`
- `/Users/bbui/virtuallasernode/static/renderer.js`

Verified baseline facts from the Codex revision:
- `soundswitch_laser_cues.json`: 184 cues; all have resolved CH1-19 values; 5 cues have CH3 >= 128 dynamic macros.
- `soundswitch_cue_motion_coverage.json`: corrected buckets are `ready_static_color_strobe=78`, `ready_motion_mapping=66`, `motion_analysis_pending=35`, `defer=5`.
- Dense capture root: `/tmp/vln_dense_cue_breakpoints_20260605_200426`.
- Dense manifest rows: 118 exact 60fps cue captures.
- Dense analysis manifest rows: 118; analysis values are nested under `analysis`; all 118 are nonblank and clipped, so clipped must stay ignored.
- Dense analysis characterized 69 captures total; of 111 motion-family captures, 65 resolved and 46 remained pending.
- `calib/dense_cue_breakpoints.py` uses a `0.07s` non-strobe period floor.
- `calib/timed_motion_ch1_19.py` still uses the old `0.35s` floor.
- `data/fixture_model.json` does not exist yet and is not a runtime input.
- `static/renderer.js` and `calibration.json` render values were not changed by the Codex paper review.

Hard guardrails to enforce:
1. Do not reintroduce a clipped/recapture_needed quality gate.
2. Do not weaken or remove the Phase 1.5 base-dependence gate.
3. Do not claim measurability beyond the Nyquist/analyzer/firmware ceiling.
4. Do not let Phase 3 or Phase 6 budgets become infeasible without explicitly flagging and reducing scope.

## What changed overall

Codex revised `FIXTURE_MODEL_PROGRAM.md` from draft to v1:
- Section 0 now includes verified artifact facts, corrected coverage buckets, and the current absence of `data/fixture_model.json`.
- Section 2 now treats `fixture_model.json` as a future deliverable, not something the renderer/decoder already consumes; it adds provenance, model status, interpolation type, evidence paths, base looks, and validation fields.
- Section 3 now requires signed direction extraction with per-beam/feature fallback where PCA is ambiguous; dual evidence tracks with CH1 validation before CH1 brightness bracketing; full-frame/wide ROI preflight; blank+loop_confidence motion gate; analyzer parity between dense and timed scripts.
- Section 3.5 now distinguishes the 0.07s dense analyzer fix from the old 0.35s timed analyzer, and no longer overclaims 60fps re-analysis unless a two-frame 60fps lag is enabled.
- Phase 1 now models CH3+CH4 together instead of treating CH3 alone as the base atlas, and corrects current evidence counts.
- Phase 1.5 is strengthened to include CH19 and corpus-heavy CH3/CH4 bases, especially CH3=28/CH4=0 and common CH3=0 high-CH4 programs.
- Phase 3 now quantifies the base-dependence multiplier: about 3,584 dual-track captures if base-invariant versus about 17,920 if multiplied across five bases, which is infeasible.
- Phase 6 now has concrete property-specific validation metrics for blanking, base look, color, strobe, motion type, direction, rate, and geometry envelope.
- Section 9 known facts are corrected to current artifact state: 184 cues, 179 static-scope cues, 5 dynamic deferred, 118 exact captures, 126 covered including duplicate vectors, corrected coverage buckets.
- Section 11 has the v1 changelog.
- Section 12 answers the nine review challenges.

## Per-lens dossiers

### Lens 1 - Measurement Validity

What Codex changed:
- Added signed direction requirements: centroid drift, PCA angle slope, area slope, and per-beam/feature fallback.
- Clarified that PCA-only is not sufficient for symmetric rings, multi-beam fans, or wave deformation.
- Replaced simple CH1 dual-exposure with dual evidence tracks and a CH1-validation precondition.
- Preserved the blank+loop_confidence gate for timed motion and explicitly ignored clipped/recapture_needed.
- Corrected the frequency ceiling: 30fps analysis supports about 15 Hz; 60fps re-analysis only approaches 30 Hz if the estimator allows a two-frame 60fps lag.

Rationale:
- The dense footage analysis currently has magnitude evidence but direction fields often remain provisional.
- All 118 dense analyzed captures are clipped, so clipped cannot be a meaningful wall-capture invalidation signal.
- `dense_cue_breakpoints.py` has the 0.07s fix; `timed_motion_ch1_19.py` does not.

Residual concerns:
- The spec does not fully define the per-beam/feature tracking algorithm.
- The 60fps re-analysis path is a requirement, not an implemented verified path.
- CH1-based brightness bracketing may still distort measurement if CH1 is not linear brightness-only.

Questions for the measurement-validity subagent:
1. Is the signed-direction requirement strong enough to produce reliable direction transfer functions?
2. Should Phase 1 be blocked until per-beam tracking exists, or is visual review acceptable for ambiguous cases?
3. Is the dual evidence-track method safe if CH1 validation passes, or should camera exposure bracketing be mandatory?
4. Is the 15 Hz / conditional 30 Hz timing language now technically correct?

### Lens 2 - Feasibility and Budget

What Codex changed:
- Phase 1 estimate revised to about 2,300 base dual-track captures plus 500-800 densification captures, roughly 4-7 rig hours with batching.
- Phase 1.5 revised to about 1,000 captures, or about 1,200 if both common CH3=0 high-CH4 programs remain separate.
- Phase 3 estimate revised to about 3,584 dual-track captures if base-invariant, roughly 6-10 hours plus overhead.
- Phase 3 all-bases multiplication is flagged as about 17,920 captures and infeasible.
- Added a rescope trigger around 5,000 timed-equivalent captures.

Rationale:
- Capture count alone was misleading because many states require 5-8s timed clips.
- Base-dependence is the dominant multiplier.
- The real cue corpus is concentrated in a few CH3/CH4 bases, so reductions should follow corpus use.

Residual concerns:
- Wall-clock estimates still depend heavily on hold duration, camera startup, DMX settle time, and failed recaptures.
- Phase 3 may still be too expensive if several groups vary by base.
- Phase 6 higher-order grids are intentionally unbounded until failures are known.

Questions for the feasibility subagent:
1. Are the revised wall-clock estimates credible for the actual rig workflow?
2. Should the capture cap be lower than 5,000 timed-equivalent captures?
3. If Phase 1.5 shows base dependence, which grids should be reduced first?
4. Should Phase 3 be split into separate approval gates per interaction group?

### Lens 3 - Model Soundness

What Codex changed:
- Made CH3+CH4 the base identity throughout the spec.
- Strengthened the base-dependence probe with CH19 and corpus-heavy bases.
- Kept the composition approach but made Phase 6 explicitly validate and correct it.
- Added a concrete Phase 6 metric with property-specific tolerances and unresolved/fail buckets.
- Added a stop condition if Phase 6 shows widespread higher-order failure.

Rationale:
- The fixture behavior is plausibly compositional, but channel combinations can create unique movements.
- Real SoundSwitch cues are the correct validation distribution.
- Brute-forcing full CH1-19 combinations is impossible.

Residual concerns:
- The base-dependence probe may still miss CH10 scan, CH18 gradient, or X/Y rotation base-dependence.
- The validation metric may need numeric tolerance tuning after Phase 1 establishes measurement noise.
- Higher-order risk may be highest in cue families that combine CH15, CH19, CH12/13, CH17, and color/gradient channels.

Questions for the model-soundness subagent:
1. Is the revised base-dependence probe sufficient, or should CH10/CH18/CH13/CH14 be added?
2. Is compose-singles-plus-selected-grids sound for this fixture, given the real cue distribution?
3. Are the Phase 6 validation tolerances concrete enough to decide pass/fail?
4. Are there specific higher-order combinations that should be gridded before Phase 6?

### Lens 4 - Schema and Data Engineering

What Codex changed:
- Clarified that `data/fixture_model.json` is new and not currently consumed.
- Added `schema_version`, `model_version`, `model_status`, `provenance`, `base_looks`, interpolation metadata, evidence paths, confidence, validation fields, and resolved-vector caveat.
- Required explicit interpolation type per map and explicit evidence for every bank/rule.
- Required Phase 5 to define a composition adapter and a consumption plan for `fixtures.py`/renderer/export tooling.

Rationale:
- The original draft implied runtime consumption that does not exist.
- Without provenance/evidence and map interpolation semantics, the model would not be auditable.
- SoundSwitch Attribute Cues can be layered/sparse at authoring time, but current JSON only contains resolved vectors.

Residual concerns:
- The schema remains illustrative, not a strict JSON Schema.
- Runtime migration from `fixtures.py`/`calibration.json` to `fixture_model.json` is not fully specified.
- Versioning and backward compatibility rules need enforcement once code starts consuming the file.

Questions for the schema subagent:
1. Should the deliverable include a formal JSON Schema in Phase 5?
2. Are `banks`, `maps`, `interactions`, `composition`, and `higher_order` fields sufficient and unambiguous?
3. How should `fixtures.py` consume the model without breaking current renderer behavior?
4. Should resolved-vector cue coverage and authored-channel metadata be represented separately?

### Lens 5 - Scope and Consistency

What Codex changed:
- Cross-checked known facts against real files and corrected corpus/coverage stats.
- Kept CH2, CH3>=128, CH20-36, and Laser 2 independent calibration out of scope.
- Corrected the dense analysis caveat: analysis values are nested under `analysis`, not top-level fields.
- Corrected the statement about validation inheriting the layered cue caveat from Phase 5 to the actual Phase 6 validation context.

Rationale:
- The measurement program must not relitigate settled exclusions.
- Current coverage is no longer the older 50/126/5 state.
- CH3 and CH4 must not be separated incorrectly.

Residual concerns:
- Some current `soundswitch_cue_motion_coverage.json` top-level statistics still preserve older before/after sections; reviewers must use current per-cue buckets and corrected reclassification.
- The phrase "complete CH1-19" can still be misread as dynamic macros included, even though CH3>=128 is excluded.

Questions for the scope subagent:
1. Are all section 9 known facts supported by artifacts?
2. Does any language still imply CH3-only base selection instead of CH3+CH4?
3. Are the exclusions correct and tight enough?
4. Does the spec overstate "complete" despite excluding dynamic macros and firmware-locked geometry?

### Lens 6 - Safety and Verification

What Codex changed:
- Repeated that measurement phases must not change `static/renderer.js` behavior or `calibration.json` render values.
- Added hash recording for renderer/calibration during measurement-only passes.
- Kept SoundSwitch quit / FTDI precondition and DMX blackout safety.
- Made paper-review verification separate from physical capture.

Rationale:
- The current task is paper review only.
- Previous physical passes had FTDI contention risk and required all-zero blackout at the end.
- Measurement data should not silently tune renderer output.

Residual concerns:
- The spec does not prescribe a single command to verify live DMX all-zero; it says "if tooling supports it."
- Once `fixture_model.json` exists, verification should include formal schema validation, not just `json.tool`.

Questions for the safety subagent:
1. Are the physical safety steps complete enough for future capture phases?
2. Should a mandatory DMX readback/all-zero command be specified now?
3. Is the verification set sufficient for a measurement-only pass?
4. Are the renderer/calibration no-change rules enforceable enough?

## Contested or uncertain items

Please adjudicate these explicitly:
1. YES/NO: Phase 1.5 can proceed with the revised 5-channel representative probe, without adding CH10/CH18/CH13/CH14.
2. A/B: Use CH1 brightness bracketing after CH1 validation, or require camera exposure bracketing for dual evidence tracks.
3. YES/NO: Phase 1 exit may allow `requires_visual_review` direction on ambiguous patterns, or must block until per-beam tracking resolves them.
4. YES/NO: A 5,000 timed-equivalent capture cap is high enough for Phase 3 before mandatory rescope.
5. A/B: Keep the general transfer-function model as the main program, or pivot earlier to direct cue-family modeling if Phase 1.5 shows broad base dependence.
6. YES/NO: The Phase 6 validation metric is concrete enough to use as the final pass/fail standard.
7. YES/NO: The current schema sketch is enough for measurement execution, or Phase 5 must first create formal JSON Schema.

## Section 10 challenge responses from Codex

1. Base-dependence: original probe was too thin; v1 uses CH8/CH12/CH15/CH17/CH19 and real CH3/CH4 bases. Confirm whether to add CH10/CH18/CH13/CH14.
2. Phase 3 feasibility: full base-dependent Phase 3 is infeasible. Reduce by affected group and real cue bases; rescope above about 5,000 timed-equivalent captures.
3. Dual exposure: CH1 bracketing is safe only if CH1 is validated brightness-only. Otherwise use camera exposure bracketing.
4. Direction extraction: centroid/PCA is not enough for every shape. Per-beam/feature fallback or visual review is required.
5. Capture budget: Phase 1 is 4-7 hours; base-invariant Phase 3 is 6-10 hours; base-dependent Phase 3 can become infeasible.
6. Property curves: piecewise sampled curves are the default; parametric fits are allowed only when validated.
7. Validation metric: v1 now defines tolerances by property and requires pass/unresolved/fail reporting.
8. Higher-order risk: compose-then-validate remains acceptable, but widespread Phase 6 failure triggers rescope.
9. Scope: v1 keeps CH2, CH3>=128, CH20-36, and Laser 2 independent calibration out of scope and corrects known facts to current artifacts.

## Feasibility verdict with numbers

Codex tractability call:
- Phase 1: about 2,300 base dual-track captures + 500-800 densification captures; estimated 4-7 hours, possibly overnight if timed holds dominate.
- Phase 1.5: about 1,000 captures, or about 1,200 if both common CH3=0 high-CH4 programs are kept; estimated 1.5-3 hours.
- Phase 2: about 40-80 captures; estimated 10-30 minutes.
- Phase 3 if base-invariant: about 3,584 dual-track captures; estimated 6-10 hours plus overhead.
- Phase 3 if multiplied across five bases: about 17,920 captures; not tractable without reduction.
- Phase 4: about 80-160 captures; estimated 20-60 minutes.
- Phase 6: zero new captures for initial validation; targeted higher-order grids only if failures demand them.

Verdict: tractable only if Phase 1.5 proves most modifier behavior is base-invariant or if Phase 3 is reduced to the corpus-heavy bases/groups that vary. Full per-base general modeling is not tractable on this rig.

## Guardrail attestation

Codex attests the v1 spec preserves the hard guardrails:
1. Clipped/recapture_needed gate was not reintroduced; clipped is explicitly ignored for valid wall evidence.
2. Phase 1.5 base-dependence gate was strengthened, not weakened.
3. Timing measurability is limited to about 15 Hz at 30fps analysis and conditional near-30 Hz only if 60fps re-analysis permits a two-frame lag; no firmware-ceiling overclaim remains.
4. Phase 3/6 infeasibility is explicitly flagged, with reduction/rescope rules.

## Explicit decisions needed from final verdict

1. Approve or revise the Phase 1.5 probe channel/base set.
2. Decide CH1 bracketing vs camera exposure bracketing for dual evidence tracks.
3. Decide whether per-beam tracking is mandatory before Phase 1 execution.
4. Approve or lower the Phase 3 capture cap and reduction strategy.
5. Approve the Phase 6 validation metric or specify exact tolerance changes.
6. Decide whether formal JSON Schema is required before measurement begins.
7. Decide whether any higher-order cue family should be gridded before Phase 6 validation.

## Requested final-review output

Return:
- Findings first, ordered by severity with file/section references.
- Per-lens verdict: blocker / major / minor / clear.
- Answers to the seven explicit decisions above.
- A final feasibility verdict: proceed, proceed with changes, or do not proceed.
- Any exact edits you recommend to `FIXTURE_MODEL_PROGRAM.md`.

Pointer for diffing:
- Revised spec: `/Users/bbui/virtuallasernode/docs/FIXTURE_MODEL_PROGRAM.md`
- Changelog: section 11, `v1 (Codex review, 2026-06-06)`
- Review responses: section 12
