# Renderer Documentation Index

**Last updated:** 2026-06-10 (plan rev 4)

Single map of renderer-related docs: what to read first, what's active, what's historical, and what's evidence-only.

---

## Read this first (active)

| Doc | Role |
|---|---|
| **[RENDERER_WALL_TO_AERIAL_PLAN_V1.md](RENDERER_WALL_TO_AERIAL_PLAN_V1.md)** | **Primary implementation plan** — wall figure (captures) → rig projection → aerial beams |
| **[RENDERER_PR_STATUS.md](RENDERER_PR_STATUS.md)** | Branch, PR state, merge gates, next commands |
| **[RENDERER_AGENT_ORCHESTRATION.md](RENDERER_AGENT_ORCHESTRATION.md)** | Agent roles, review gates, forensic questions, workflow |
| **[AGENTS.md](../AGENTS.md)** | Repo-wide guardrails (global rules, forbidden scope creep) |
| **[../REPO_LAYOUT.md](../REPO_LAYOUT.md)** | **Repo map** — active vs archive vs corpus |
| **[../calib/README.md](../calib/README.md)** | Active calib scripts only |

---

## Present — active plans and policy

Plans and guides that govern **current and near-term** renderer work.

| Doc | Status | Notes |
|---|---|---|
| [RENDERER_WALL_TO_AERIAL_PLAN_V1.md](RENDERER_WALL_TO_AERIAL_PLAN_V1.md) | **Active primary (rev 4 — PR-G1 spec)** | G1–G4 core; §6.0 local corpus + calibration boxes; H1–H4 hardening |
| [RENDERER_PR_STATUS.md](RENDERER_PR_STATUS.md) | **Active** | Living status; update each PR checkpoint |
| [RENDERER_AGENT_ORCHESTRATION.md](RENDERER_AGENT_ORCHESTRATION.md) | **Active** | Orchestration + Opus forensic checklist |
| [RENDERER_ACCURACY_PLAN_V1.md](RENDERER_ACCURACY_PLAN_V1.md) | **Partially active** | PR-A/B/C/E policy still valid; **PR-D section superseded** by wall→aerial plan |
| [RENDERER_CAPTURE_BACKED_PLAN_V1.md](RENDERER_CAPTURE_BACKED_PLAN_V1.md) | **Policy reference** | Authority tiers, corpus boundaries; update "aerial renderer" wording — shape authority now wall-driven |

---

## Present — capture / rig evidence (read-only context)

Docs describing **measurement corpus and physical setup**. Not implementation plans; inform PR-G shape and projection.

**Evidence authority:** `captures/fixture_model/` (8k+ corpus, **local media only**). GitHub has metadata/schema — not reliable still/video access. Pre-corpus stills: `archive/pre_corpus_2026-06-05/calib_captures/` (historical).

| Doc | Use when |
|---|---|
| [FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md](FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md) | Rig geometry, capture program, renderer fidelity gap statement |
| [FIXTURE_MODEL_PROGRAM.md](FIXTURE_MODEL_PROGRAM.md) | CH1–19 semantics, honest ceiling (no firmware point lists) |
| [WALL_CH3_LOOK_ATLAS.md](WALL_CH3_LOOK_ATLAS.md) | **CH3 family checklist only** — which families PR-G1 must cover (not extraction evidence) |
| [CALIBRATION_RESULTS.md](CALIBRATION_RESULTS.md) | **Mixed** — decoder findings valid; pre-corpus PNG paths historical |
| [FIXTURE_36CH.md](FIXTURE_36CH.md) | Channel chart, ±25° scanner spec |
| [PHASE6_VALIDATION_REPORT.md](PHASE6_VALIDATION_REPORT.md) | Phase6 cue validation |

### Archived pre-corpus audits (`docs/_archive/pre_corpus/`)

| Doc | Notes |
|---|---|
| [_archive/pre_corpus/COMBINATION_CHANNEL_AUDIT.md](_archive/pre_corpus/COMBINATION_CHANNEL_AUDIT.md) | Combo mismatch ranking |
| [_archive/pre_corpus/DMX_CHANNEL_AUDIT.md](_archive/pre_corpus/DMX_CHANNEL_AUDIT.md) | Per-channel wall audit |
| [_archive/pre_corpus/TIMED_MOTION_CH1_19_CALIBRATION.md](_archive/pre_corpus/TIMED_MOTION_CH1_19_CALIBRATION.md) | Superseded by corpus motion clips |
| [_archive/pre_corpus/WALL_MODIFIER_PASS.md](_archive/pre_corpus/WALL_MODIFIER_PASS.md) | Modifier still pass |
| [_archive/pre_corpus/CALIBRATION.md](_archive/pre_corpus/CALIBRATION.md) | Early agent calibration phases |
| [_archive/pre_corpus/CALIBRATION_WALL_MASTER_DMX_LOG.md](_archive/pre_corpus/CALIBRATION_WALL_MASTER_DMX_LOG.md) | Wall master DMX log |
| [_archive/pre_corpus/CODEX_REVIEW_CALIBRATION.md](_archive/pre_corpus/CODEX_REVIEW_CALIBRATION.md) | Calibration review |

---

## Historical — superseded plans (`docs/_archive/historical_renderer/`)

Kept for audit trail. **Do not implement from these.**

| Doc | Superseded by |
|---|---|
| [_archive/historical_renderer/RENDERER_PLAN.md](_archive/historical_renderer/RENDERER_PLAN.md) | RENDERER_WALL_TO_AERIAL_PLAN_V1.md |
| [_archive/historical_renderer/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md](_archive/historical_renderer/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md) | RENDERER_WALL_TO_AERIAL_PLAN_V1.md |
| [_archive/historical_renderer/RENDERER_REVIEW.md](_archive/historical_renderer/RENDERER_REVIEW.md) | Forensic review artifact |
| [PLANNING.md](PLANNING.md) §Renderer | RENDERER_WALL_TO_AERIAL_PLAN_V1.md |

**PR-D (fan geometry):** superseded — reports in `archive/experiments/pr_d/` (local).

---

## Historical — completed PR era (PR1–PR5)

Merged or completed work from the capture-backed **metadata + fan overlay** era.

| Doc / artifact | Era | Notes |
|---|---|---|
| [RENDERER_CAPTURE_BACKED_PLAN_V1.md](RENDERER_CAPTURE_BACKED_PLAN_V1.md) | PR1–PR6 roadmap | Index + lookup + motion overlay roadmap |
| [RENDERER_REVIEW.md](RENDERER_REVIEW.md) | Early review | Pre-forensic review notes |
| `artifacts/renderer/renderer-capture-index-pr1/` | PR1 | Capture index build |
| `artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md` | Forensic | **BLOCK_MERGE** for "capture-backed" geometry claim |
| `artifacts/renderer/renderer-accuracy-phase1/` | PR-A/B/C | Phase 1 implementation report |
| `artifacts/renderer/pr-g1-plan-cleanup/` | PR-G1 spec | Plan rev 4 cleanup report (docs only) |
| `artifacts/renderer/pr-g1-shape-authority/` | PR-G1 | Future: `shape_selection.json` (local dual-lane picks) |
| `artifacts/renderer/shape_library_v1.json` | PR-G1 | Future: wall-normalized static shapes + schema |

---

## Historical — reviews and one-off audits

| Doc | Notes |
|---|---|
| [CODEX_REVIEW_CALIBRATION.md](_archive/pre_corpus/CODEX_REVIEW_CALIBRATION.md) | Calibration code review |
| [PHASE2_AUDIT.md](PHASE2_AUDIT.md) | Capture phase 2 audit |
| [FIXTURE_MODEL_POST_CAPTURE_ANALYSIS.md](FIXTURE_MODEL_POST_CAPTURE_ANALYSIS.md) | Post-capture corpus stats |

---

## Archive / experiments (non-production, local)

| Path | Notes |
|---|---|
| [../archive/README.md](../archive/README.md) | Pre-corpus stills + legacy scripts + quarantine |
| `archive/experiments/quarantine/` | Superseded CH19/fan motion experiments |
| `archive/experiments/pr_d/` | Superseded PR-D reports |

---

## Document lifecycle rules

1. **One active primary plan:** `RENDERER_WALL_TO_AERIAL_PLAN_V1.md`. New architectural direction supersedes via new `_V2` doc + index update — do not silently fork plans.
2. **Status lives in** `RENDERER_PR_STATUS.md` only — plans describe intent, not merge state.
3. **Historical docs** live under `docs/_archive/`; this index assigns category.
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
  → captures/fixture_model/ (LOCAL media — not on GitHub)
  → WALL_CH3_LOOK_ATLAS.md (family checklist only)

Why did we build a fan?
  → docs/_archive/historical_renderer/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md
  → opus_capture_grounded_review.md (forensic verdict)

Tuning calibration.json for fan spread?
  → STOP — PR-F suspended; fix shape/projection first (PR-G)
```
