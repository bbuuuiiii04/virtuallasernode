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
active_plan: docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md (rev 3 — PR-G wall → aerial)
active_branch: renderer-accuracy-phase1
base_branch: renderer-capture-index-pr1
phase: wall_to_aerial_rebuild
last_completed_step: phase1_committed_2026_06_09 + chatgpt_review_verdict
next_recommended_command: Implement PR-G1 (atlas-first static shapes from stills)
corpus: 8324 captures (still+video+motion frames each); phase6=175 cue folders; dense /tmp absent
human_action_needed: visual checkpoint after PR-G3
phase1_status: committed (PR-A/B/C) — APPROVE merge as honesty foundation only
chatgpt_review_verdict: BLOCK PR-G merge claim; APPROVE Phase 1; start G1 atlas-first
pr_d_status: SUPERSEDED — do not merge; salvage geometry SSE wiring in PR-G3
pr_f_status: SUSPENDED (was PR6 physical calibration)
review_branch: review/plan-pr1-5-phase1 (GitHub — PR1-5 + Phase 1 + docs)
```

## MODEL ROLES (effective 2026-06-09)

```text
Codex (gpt-5.3-codex)      = implementation agent for every renderer PR
Composer 2.5               = fallback only when Codex unavailable (historical: PR-D)
gpt-5.5-high               = routine reviewer (PR-A, PR-B, PR-C, PR-G1, PR-G4, PR-E)
Opus (Claude 4.8)          = orchestrator + checkpoint reviewer
                             (PR-G1b motion tracks, PR-G2, PR-G3, final integration)
Brandon                    = final visual/physical approval
```

Mandate: DO NOT use SoundSwitch cue names/tags as trustworthy labels. Behavior is derived from capture analysis, not cue names.

## ACTIVE ROADMAP — Wall → Aerial (PR-G)

Corpus: **8,324 stills + 8,324 motion clips** per capture folder. Plan rev 2 wires both — not scalars-only.

```text
PR-G1   Static shape authority (still.jpg → wall polylines)        [gpt-5.5]
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
PR-D fan geometry/density   SUPERSEDED — see RENDERER_WALL_TO_AERIAL_PLAN_V1.md §8
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
| PR-A/B/C | renderer-accuracy-phase1 | **implemented, uncommitted** | Provenance + motion + color |
| PR-D | renderer-accuracy-phase1 | **SUPERSEDED — do not merge** | Salvage SSE geometry in PR-G3 |
| PR-G1–G4 | TBD | **not started** | G1 stills + G1b motion tracks → G2 playback → G3 projection |
| PR-H1–H4 | TBD | **not started** | Timing, combos, direction, track storage — after G4 (see plan §14) |

## Active PR Checklist — Phase 1 (PR-A/B/C)

```text
PR: renderer-accuracy-phase1 (PR-A + PR-B + PR-C)
Branch: renderer-accuracy-phase1
Base: renderer-capture-index-pr1
Status: implemented (uncommitted)
Tests: node tests/test_renderer_motionstate.js; pytest capture_index + fixtures_decode
Render smoke: calib/render_grid_capture.py
Merge state: not merged — ready to land independently of PR-G
Next: merge Phase 1, then branch PR-G1 from result
```

## PR-D Checklist — SUPERSEDED

```text
PR: PR-D — capture-driven fan geometry + density
Status: SUPERSEDED by RENDERER_WALL_TO_AERIAL_PLAN_V1.md
Opus review: CANCELLED — review PR-G2/G3 instead
Action: do not merge; cherry-pick analysis_geometry SSE wiring into PR-G3
Report: artifacts/renderer/renderer-accuracy-pr-d/implementation_report.md (historical)
```

## Latest Decisions (2026-06-09)

- **Primary plan rev 2:** 8,324 stills + 8,324 motion clips (video + motion_analysis_60fps) — dual authority; scalars-only index is insufficient.
- PR-D fan spread/count/density is deprecated; not merge-ready and not the path forward.
- PR-A/B/C (provenance, aliases, motion type, color) remain required foundation.
- PR-E runs after PR-G4, not before.
- Doc index: `docs/RENDERER_DOCS_INDEX.md` categorizes historical vs present docs.

## Open Risks To Track

- Shape extraction quality on macros and low-contrast stills.
- Projection math without full homography — label error honestly.
- PR-H blocked until PR-G4 exit (timing, combos, direction, lazy load — plan §14).
- PR-D unmerged code on branch may confuse agents — treat as salvage-only.
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
