# Renderer Documentation Index

**Last updated:** 2026-06-09

Single map of renderer-related docs: what to read first, what's active, what's historical, and what's evidence-only.

---

## Read this first (active)

| Doc | Role |
|---|---|
| **[RENDERER_WALL_TO_AERIAL_PLAN_V1.md](RENDERER_WALL_TO_AERIAL_PLAN_V1.md)** | **Primary implementation plan** — wall figure (captures) → rig projection → aerial beams |
| **[RENDERER_PR_STATUS.md](RENDERER_PR_STATUS.md)** | Branch, PR state, merge gates, next commands |
| **[RENDERER_AGENT_ORCHESTRATION.md](RENDERER_AGENT_ORCHESTRATION.md)** | Agent roles, review gates, forensic questions, workflow |
| **[AGENTS.md](../AGENTS.md)** | Repo-wide guardrails (global rules, forbidden scope creep) |

---

## Present — active plans and policy

Plans and guides that govern **current and near-term** renderer work.

| Doc | Status | Notes |
|---|---|---|
| [RENDERER_WALL_TO_AERIAL_PLAN_V1.md](RENDERER_WALL_TO_AERIAL_PLAN_V1.md) | **Active primary (rev 2 + §14 PR-H)** | G1–G4 core; H1–H4 hardening (timing, combos, direction, lazy load) |
| [RENDERER_PR_STATUS.md](RENDERER_PR_STATUS.md) | **Active** | Living status; update each PR checkpoint |
| [RENDERER_AGENT_ORCHESTRATION.md](RENDERER_AGENT_ORCHESTRATION.md) | **Active** | Orchestration + Opus forensic checklist |
| [RENDERER_ACCURACY_PLAN_V1.md](RENDERER_ACCURACY_PLAN_V1.md) | **Partially active** | PR-A/B/C/E policy still valid; **PR-D section superseded** by wall→aerial plan |
| [RENDERER_CAPTURE_BACKED_PLAN_V1.md](RENDERER_CAPTURE_BACKED_PLAN_V1.md) | **Policy reference** | Authority tiers, corpus boundaries; update "aerial renderer" wording — shape authority now wall-driven |

---

## Present — capture / rig evidence (read-only context)

Docs describing **measurement corpus and physical setup**. Not implementation plans; inform PR-G shape and projection.

| Doc | Use when |
|---|---|
| [FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md](FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md) | Rig geometry, capture program, renderer fidelity gap statement |
| [FIXTURE_MODEL_PROGRAM.md](FIXTURE_MODEL_PROGRAM.md) | CH1–19 semantics, honest ceiling (no firmware point lists) |
| [WALL_CH3_LOOK_ATLAS.md](WALL_CH3_LOOK_ATLAS.md) | Look-family matrix — PR-G1/G3 smoke acceptance |
| [WALL_MODIFIER_PASS.md](WALL_MODIFIER_PASS.md) | Modifier behavior on wall stills |
| [COMBINATION_CHANNEL_AUDIT.md](COMBINATION_CHANNEL_AUDIT.md) | Combo looks vs aerial fan mismatch ranking |
| [DMX_CHANNEL_AUDIT.md](DMX_CHANNEL_AUDIT.md) | Per-channel wall projection audit |
| [TIMED_MOTION_CH1_19_CALIBRATION.md](TIMED_MOTION_CH1_19_CALIBRATION.md) | Timed/burst motion evidence |
| [CALIBRATION_RESULTS.md](CALIBRATION_RESULTS.md) | Wall vs virtual comparison; pan/zoom sign fixes |
| [CALIBRATION.md](CALIBRATION.md) | Agent-driven calibration phases |
| [FIXTURE_36CH.md](FIXTURE_36CH.md) | Channel chart, ±25° scanner spec |

---

## Historical — superseded plans

Kept for audit trail. **Do not implement from these without cross-checking the active plan.**

| Doc | Superseded by | Why historical |
|---|---|---|
| [RENDERER_PLAN.md](RENDERER_PLAN.md) | PR-G2 (transform) + PR-G3 (projection) | Original Step 6 polyline-on-canvas plan; partially reused but never shipped as primary path |
| [RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md](RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md) | PR-G3 | Pivoted to "preserve `_drawFan()`"; explicitly rejected wall-projection thinking |
| [PLANNING.md](PLANNING.md) §Renderer | RENDERER_WALL_TO_AERIAL_PLAN_V1 | North-star MVP; v3 "photograph patterns" never wired to renderer |

**Accuracy plan PR-D (fan geometry):** documented in [RENDERER_ACCURACY_PLAN_V1.md](RENDERER_ACCURACY_PLAN_V1.md) §PR-D but **superseded** — see [RENDERER_WALL_TO_AERIAL_PLAN_V1.md](RENDERER_WALL_TO_AERIAL_PLAN_V1.md) §7. Implementation report only: `artifacts/renderer/renderer-accuracy-pr-d/`.

---

## Historical — completed PR era (PR1–PR5)

Merged or completed work from the capture-backed **metadata + fan overlay** era.

| Doc / artifact | Era | Notes |
|---|---|---|
| [RENDERER_CAPTURE_BACKED_PLAN_V1.md](RENDERER_CAPTURE_BACKED_PLAN_V1.md) | PR1–PR6 roadmap | Index + lookup + motion overlay roadmap |
| [RENDERER_REVIEW.md](RENDERER_REVIEW.md) | Early review | Pre-forensic review notes |
| `artifacts/renderer/renderer-capture-index-pr1/` | PR1 | Capture index build |
| `artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md` | Forensic | **BLOCK_MERGE** for "capture-backed" geometry claim |
| `artifacts/renderer/renderer-accuracy-phase1/` | PR-A/B/C | Phase 1 implementation report (uncommitted) |
| `artifacts/renderer/renderer-accuracy-pr-d/` | PR-D | Composer implementation — **do not merge** |

---

## Historical — reviews and one-off audits

| Doc | Notes |
|---|---|
| [RENDERER_REVIEW.md](RENDERER_REVIEW.md) | General renderer review |
| [CODEX_REVIEW_CALIBRATION.md](CODEX_REVIEW_CALIBRATION.md) | Calibration code review |
| [PHASE2_AUDIT.md](PHASE2_AUDIT.md) | Capture phase 2 audit |
| [FIXTURE_MODEL_POST_CAPTURE_ANALYSIS.md](FIXTURE_MODEL_POST_CAPTURE_ANALYSIS.md) | Post-capture corpus stats |

---

## Quarantine / experiments (non-production)

| Artifact | Notes |
|---|---|
| [../artifacts/renderer/COMPOSER_QUARANTINE_LEDGER.md](../artifacts/renderer/COMPOSER_QUARANTINE_LEDGER.md) | CH19 wave, fan motion experiments — default off |
| `static/quarantine/ch19_wave.js` | Opt-in only |
| `static/quarantine/fan_motion.js` | Opt-in only |

---

## Document lifecycle rules

1. **One active primary plan:** `RENDERER_WALL_TO_AERIAL_PLAN_V1.md`. New architectural direction supersedes via new `_V2` doc + index update — do not silently fork plans.
2. **Status lives in** `RENDERER_PR_STATUS.md` only — plans describe intent, not merge state.
3. **Historical docs stay in place** (no moves) to preserve links; this index assigns category.
4. **Evidence docs** (`captures/`, fixture model program) are read-only for renderer agents.
5. **Every implementation PR** adds `artifacts/renderer/<pr-name>/implementation_report.md`; checkpoint PRs add `opus_review.md`.

---

## Quick decision tree

```text
Implementing renderer code?
  → RENDERER_WALL_TO_AERIAL_PLAN_V1.md
  → RENDERER_PR_STATUS.md (current branch/PR)
  → AGENTS.md (guardrails)

Reviewing a PR?
  → RENDERER_AGENT_ORCHESTRATION.md §12 forensic questions
  → Diff vs active plan scope

Understanding capture corpus?
  → FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md
  → WALL_CH3_LOOK_ATLAS.md

Why did we build a fan?
  → RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md (historical)
  → opus_capture_grounded_review.md (forensic verdict)

Tuning calibration.json for fan spread?
  → STOP — PR-F suspended; fix shape/projection first (PR-G)
```
