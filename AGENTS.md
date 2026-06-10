# Agent Instructions for VirtualLaserNode

This repo uses agent-assisted development. Follow this file before making changes.

## Global Rules

- Do not modify `data/fixture_model.json` unless explicitly authorized.
- Do not modify capture data unless explicitly authorized.
- Do not convert the renderer to WebGL unless explicitly authorized.
- Do not do visual polish before MotionState correctness.
- Do not remove existing `second_pattern` rendering.
- Do not move fixture/aperture source origins.
- Do not claim exact digital-twin accuracy.
- Code evidence wins over docs.
- Keep each PR narrow.
- Every implementation PR must include an implementation report.
- Every implementation PR must include tests or smoke checks appropriate to scope.

## Primary Renderer Plan

Read this first for renderer work:

```text
docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md
```

Documentation map (historical vs active):

```text
docs/RENDERER_DOCS_INDEX.md
```

Status and branch tracking:

```text
docs/RENDERER_PR_STATUS.md
```

Supporting orchestration guide:

```text
docs/RENDERER_AGENT_ORCHESTRATION.md
```

Capture corpus policy (authority tiers, boundaries):

```text
docs/RENDERER_CAPTURE_BACKED_PLAN_V1.md
```

## Agent Roles

### Codex / implementation agent

Codex should implement only the currently requested PR scope.

It must:

1. inspect the relevant source files before coding,
2. stay inside the requested PR scope,
3. avoid unrelated refactors,
4. run tests and smoke checks,
5. produce an implementation report,
6. stop after the requested PR.

### Opus / review agent

Opus should review the actual diff, not the intention.

It must:

1. compare the diff against the requested PR scope,
2. cite file paths and line numbers where possible,
3. identify blockers separately from optional improvements,
4. reject scope creep,
5. avoid requesting future-PR features as current-PR blockers.

### Human / Brandon

The human should only be asked for:

1. final approval before merge,
2. visual judgment from screenshots/browser output,
3. physical-rig comparison when software cannot know the answer.

Do not ask Brandon to inspect every file or manually run every command unless blocked.

## Renderer PR Roadmap

**Active (2026-06-09):** see `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` (PR-G1–G4).

Historical (PR1–PR5, merged or complete):

1. `renderer-capture-index-pr1` — build-time capture index from manifest + per-capture analysis + analysis geometry.
2. `renderer-capture-lookup-pr2` — runtime lookup in webserver/adapter with provenance labels and diagnostics.
3. `renderer-measured-motion-pr3` — measured-parameter rendering with reduced MotionState fallback.
4. `renderer-diagnostics-pr4` — diagnostics expansion.
5. `renderer-visual-polish-pr5` — visual polish after diagnostics.
6. `renderer-physical-hardening-pr6` — **SUSPENDED** — physical calibration after PR-G + human validation.

Do not begin the next PR until the current PR is approved and merged.

## Standard Agent Loop

For each PR:

1. Create or verify a clean branch.
2. Implement only the current PR scope.
3. Inspect changed files for scope creep.
4. Run available tests.
5. Run renderer smoke harnesses where applicable.
6. Produce implementation report.
7. Get Opus review on actual diff.
8. Fix only blocking or approved minor review issues.
9. Repeat until approved.
10. Return a concise human checkpoint.

## Human Checkpoint Format

At the end of each PR, provide:

```text
PR checkpoint

PR:
Status:
Files changed:
Tests run:
Render smoke result:
Opus verdict:
Remaining approximations:
Human action needed:
```

Human action should be one of:

```text
approve merge
reject and fix listed issues
review screenshot/browser output
perform physical comparison
```

## Forbidden Scope Creep

Block or revert if any PR accidentally includes:

- fixture model mutation,
- capture data mutation,
- whole-renderer rewrite,
- WebGL conversion,
- removed diagnostics,
- moved fixture/aperture origins,
- broken `second_pattern`,
- visual polish before MotionState correctness,
- hidden decoded/composed fallback behavior,
- untested MotionState logic.
