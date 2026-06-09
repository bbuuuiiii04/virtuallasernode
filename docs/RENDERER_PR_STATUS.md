# Renderer PR Status

This file tracks the active renderer PR so agents can continue work without asking Brandon to repeat context.

Primary orchestration guide:

```text
docs/RENDERER_AGENT_ORCHESTRATION.md
```

Primary implementation plan:

```text
docs/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md
```

## Current State

```text
active_pr: none
active_branch: none
base_branch: main
phase: ready_for_pr1
last_completed_step: orchestration_docs_created
next_recommended_command: Start renderer PR 1.
human_action_needed: none
```

## PR Roadmap Status

| PR | Branch | Status | Notes |
|---|---|---|---|
| PR 1 | renderer-motionstate-pr1 | not started | MotionState foundation and visibility gates |
| PR 2 | renderer-motion-fidelity-pr2 | blocked until PR 1 merged | Rotation, zoom, waves, dot mode, oscillator fidelity |
| PR 3 | renderer-diagnostics-pr3 | blocked until PR 2 merged | Debug View and operator confidence |
| PR 4 | renderer-visual-polish-pr4 | blocked until PR 3 merged | Visual polish after motion correctness |
| PR 5 | renderer-physical-calibration-pr5 | blocked until PR 4 merged | Physical comparison corrections |
| PR 6 | renderer-product-hardening-pr6 | blocked until PR 5 merged | Cleanup, docs, UX, performance |

## Active PR Checklist

No active PR yet.

When a PR starts, update this section with:

```text
PR:
Branch:
Base:
Status:
Codex implementation:
Tests:
Render smoke:
Opus review:
Blocking fixes:
Human checkpoint:
Merge state:
```

## Latest Decisions

- Use Codex as implementation agent.
- Use Opus as review/audit agent.
- Keep Brandon's workload minimal.
- Brandon should only provide short commands and final visual/physical judgment.
- Do not proceed to next PR without Brandon checkpoint approval and merge.

## Open Risks To Track

- Agents may expand scope beyond current PR.
- Agents may accidentally change fixture model or capture data.
- MotionState refactor may change visuals unintentionally.
- Source origins may move if `_drawFan()` is rewritten too aggressively.
- Existing `second_pattern` rendering may regress.
- Screenshot automation may be unavailable on some machines.

## Human Command Cheatsheet

```text
Start renderer PR 1.
Continue current renderer PR.
Send current renderer PR to Opus review.
Fix only Opus blocking issues.
Prepare human checkpoint.
Show renderer PR status.
Proceed to next renderer PR.
```
