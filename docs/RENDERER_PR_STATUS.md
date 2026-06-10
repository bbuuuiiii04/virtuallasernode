# Renderer PR Status

This file tracks the active renderer PR so agents can continue work without asking Brandon to repeat context.

**Documentation map:** `docs/RENDERER_DOCS_INDEX.md`

**Primary implementation plan:**

```text
docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md
```

**Orchestration guide:**

```text
docs/RENDERER_AGENT_ORCHESTRATION.md
```

## Current State

```text
active_plan: docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md (rev 4 — PR-G1 static-shape spec)
active_branch: renderer-accuracy-phase1
base_branch: renderer-capture-index-pr1
phase: wall_to_aerial_rebuild — PR-G1 spec ready; implementation not started
last_completed_step: repo_layout_refactor_committed_2026_06_10 + pr_g1_plan_cleanup
next_recommended_command: Implement PR-G1 (local shape_selection.json + shape_library_v1.json)
corpus: 8324+ captures LOCAL ONLY under captures/fixture_model/ (stills not on GitHub)
phase6: ~175 cue folders under phase6_cue_validation/cue_relevant/
human_action_needed: visual overlay yes/no after PR-G1 extraction harness
phase1_status: committed (PR-A/B/C) @ f5ad9212 — APPROVE as honesty foundation only
repo_refactor: committed @ 45c5734d — archive pre-corpus calib + doc reorganize
chatgpt_review_verdict: BLOCK capture-driven geometry claim until PR-G; APPROVE Phase 1
pr_d_status: REMOVED — fan-geometry-from-scalars never merged; use PR-G only
pr_f_status: SUSPENDED (was PR6 physical calibration)
review_branch: review/plan-pr1-5-phase1 (sync after push — not renderer policy on main)
```

## MODEL ROLES (effective 2026-06-09)

```text
Codex (gpt-5.3-codex)      = implementation agent for every renderer PR
Composer 2.5               = fallback only when Codex unavailable (historical)
gpt-5.5-high               = routine reviewer (PR-A, PR-B, PR-C, PR-G1, PR-G4, PR-E)
Opus (Claude 4.8)          = orchestrator + checkpoint reviewer
                             (PR-G1b motion tracks, PR-G2, PR-G3, final integration)
Brandon                    = final visual/physical approval
```

Mandate: DO NOT use SoundSwitch cue names/tags as trustworthy labels. Behavior is derived from capture analysis, not cue names.

## ACTIVE ROADMAP — Wall → Aerial (PR-G)

Corpus: **8,324+ local capture packages** (`captures/fixture_model/**`). Raw stills/videos/motion frames are **local-only** — GitHub has metadata/schema, not drawable media. Plan rev 4 defines PR-G1 dual-lane selection (CH3 families + phase6 cues).

```text
PR-G1   Static shape authority (local still.jpg → calibration-box polylines)  [gpt-5.5]
        Requires: shape_selection.json + shape_library_v1.json (both lanes)
PR-G1b  Motion shape tracks (motion_analysis_60fps → playback)   [OPUS checkpoint]
PR-G2   Wall playback + DMX residual (track-primary animation)     [OPUS checkpoint]
PR-G3   Rig projection + aerial beam draw (replace _drawFan)       [OPUS checkpoint]
PR-G4   Integration, diagnostics, capture-aware harness            [gpt-5.5]
PR-H1   Fast motion timing (track autocorr, 60fps)                  [gpt-5.5]
PR-H2   Modifier combo resolution (phase3 + residual)               [OPUS checkpoint]
PR-H3   Direction authority (track-derived + H2 overrides)          [gpt-5.5 + human H2]
PR-H4   Track compression + lazy load (sharded artifacts)           [gpt-5.5]
PR-E    Diagnostics completeness (after G4, extend for H-tier)        [gpt-5.5]
PR-F    Physical calibration (was PR6)                               [SUSPENDED until G+H + H1-H4]
```

## ACCURACY REBUILD — Phase 1 (PR-A/B/C) status

```text
PR-A provenance honesty     committed
PR-B cue aliases            committed
PR-C motion truth + color   committed
PR-D fan geometry/density   REMOVED — never merged; use PR-G1–G3
```

Phase 1 remains valid and should land before or alongside PR-G1; it does not depend on fan geometry.

## POLICY — Capture-grounded review

Forensic review (PR1–PR5 era):

```text
artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md
```

Verdict: BLOCK_MERGE for "capture-backed geometry" claim. PR-G addresses root cause (shape authority + projection).

Checkpoint PRs require committed review at `artifacts/renderer/<pr-name>/opus_review.md`.

## PR Roadmap Status (historical + active)

| PR | Branch | Status | Notes |
|---|---|---|---|
| PR 1 | renderer-capture-index-pr1 | complete | Capture index builder |
| PR 2 | renderer-capture-lookup-pr2 | complete | Runtime lookup + diagnostics |
| PR 3 | renderer-measured-motion-pr3 | complete | Measured motion overlay on fan |
| PR 4 | renderer-diagnostics-pr4 | complete | Diagnostics expansion |
| PR 5 | renderer-visual-polish-pr5 | complete | Visual polish |
| PR 6 / PR-F | renderer-physical-hardening-pr6 | **SUSPENDED** | After PR-G + H1–H4 |
| PR-A/B/C | renderer-accuracy-phase1 | **committed** @ f5ad9212 | Provenance + motion + color |
| PR-G1–G4 | TBD | **not started** | Spec rev 4 ready; G1 = local stills + calibration boxes |
| PR-H1–H4 | TBD | **not started** | Timing, combos, direction, track storage — after G4 (see plan §14) |

## Active PR Checklist — Phase 1 (PR-A/B/C)

```text
PR: renderer-accuracy-phase1 (PR-A + PR-B + PR-C)
Branch: renderer-accuracy-phase1
Base: renderer-capture-index-pr1
Status: committed (f5ad9212)
Tests: node tests/test_renderer_motionstate.js; pytest capture_index + fixtures_decode
Render smoke: calib/render_grid_capture.py
Next: PR-G1 — local shape_selection + shape_library (see plan §6.0)
```

## PR-G1 Checklist — spec ready, not implemented

```text
PR: PR-G1 — static shape authority (local stills)
Status: spec only (plan rev 4); no shape_library_builder.py yet
Inputs: captures/fixture_model/** still.jpg (LOCAL); analysis_geometry.json boxes
Lanes: A = CH3 families (WALL_CH3 checklist); B = phase6 cue_relevant
Outputs: shape_selection.json, shape_library_v1.json + schema
Visible renderer: _drawFan may remain until PR-G3; internal shape_ref in diagnostics
Not evidence: calib/captures/, /tmp atlas PNGs, WALL_CH3 legacy still column
Report: artifacts/renderer/pr-g1-plan-cleanup/implementation_report.md
```

## Latest Decisions (2026-06-10)

- **Primary plan rev 4:** PR-G1 uses **local** `captures/fixture_model/**` stills; normalization in **per-fixture calibration projection boxes** from `analysis_geometry.json`.
- **WALL_CH3_LOOK_ATLAS.md** is a **family checklist only** — not extraction evidence.
- **Dual selection lanes:** CH3 family coverage (alphabet) + phase6 cue captures (SoundSwitch words).
- **Topology labels** are diagnostic (`line`, `two_clusters`, …); Brandon validates overlays visually (yes/no).
- Fan-geometry-from-scalars path removed; no unmerged draft on branch.
- PR-A/B/C committed; PR-G1 implementation not started.
- Doc index: `docs/RENDERER_DOCS_INDEX.md` categorizes historical vs present docs.

## Open Risks To Track

- Shape extraction quality on macros and low-contrast stills.
- Projection math without full homography — label error honestly.
- PR-H blocked until PR-G4 exit (timing, combos, direction, lazy load — plan §14).
- Composer quarantine experiments — default off (`COMPOSER_QUARANTINE_LEDGER.md`).
- `second_pattern` regression during `_drawFan` replacement.
- Do not mutate fixture_model or capture data during PR-G.

## Human Command Cheatsheet

```text
Start PR-G1.
Continue current renderer PR.
Show renderer PR status.
Send PR-G2/G3 to Opus review.
Prepare human checkpoint.
Show renderer docs index.
```
