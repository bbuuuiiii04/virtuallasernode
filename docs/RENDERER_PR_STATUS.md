# Renderer PR Status

This file tracks the active renderer PR so agents can continue work without asking Brandon to repeat context.

Primary orchestration guide:

```text
docs/RENDERER_AGENT_ORCHESTRATION.md
```

Primary implementation plan:

```text
docs/RENDERER_CAPTURE_BACKED_PLAN_V1.md
```

## Current State

```text
active_pr: renderer-capture-lookup-pr2
active_branch: renderer-capture-index-pr1
base_branch: main
phase: pr2_implemented_tests_passed_review_gate_satisfied
last_completed_step: pr2_review_completed
next_recommended_command: Continue to renderer PR 3 implementation.
human_action_needed: none
```

## PR Roadmap Status

| PR | Branch | Status | Notes |
|---|---|---|---|
| PR 1 | renderer-capture-index-pr1 | implementation complete, tests passed, review gate satisfied | Build-time capture index generator from manifest + per-capture analysis + analysis geometry; no renderer/webserver changes |
| PR 2 | renderer-capture-lookup-pr2 | implementation complete, tests passed, review gate satisfied | Load index in webserver/adapter; exact vector + cue lookup; provenance labels and diagnostics |
| PR 3 | renderer-measured-motion-pr3 | ready to start | Consume measured parameters with reduced MotionState fallback layer |
| PR 4 | renderer-diagnostics-pr4 | blocked until PR 3 merged | Diagnostics expansion |
| PR 5 | renderer-visual-polish-pr5 | blocked until PR 4 merged | Visual polish |
| PR 6 | renderer-physical-hardening-pr6 | blocked until PR 5 merged | Physical calibration / hardening |

## Active PR Checklist

```text
PR: renderer-capture-lookup-pr2
Branch: renderer-capture-index-pr1
Base: main
Status: implementation complete, tests passed, review gate satisfied
Codex implementation: completed
Tests: targeted PR1+PR2 tests passed (test_capture_index_builder + test_capture_index_runtime)
Render smoke: not applicable (no renderer drawing semantics changed in PR2)
Opus review: completed (no blockers)
Blocking fixes: completed
Human checkpoint: not prepared yet
Merge state: not merged
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
