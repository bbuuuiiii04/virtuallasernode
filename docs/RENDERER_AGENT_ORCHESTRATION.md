# Renderer Agent Orchestration Guide

This guide lets Brandon use short commands instead of repeatedly pasting full implementation and review prompts. Agents should read this file, `AGENTS.md`, and the active PR status file before renderer work.

Primary plan:

```text
docs/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md
```

Active status file:

```text
docs/RENDERER_PR_STATUS.md
```

## 0. Operating Model

The orchestration goal is minimum human workload with maximum guardrails.

Roles:

```text
Orchestrator = manages PR flow, scope, handoffs, tests, status, and checkpoints
Codex = implementation agent
Opus = independent review/audit agent
Brandon = final visual/physical approval only
```

The orchestrator must not treat Codex output as approved. Codex builds; Opus reviews; Brandon approves human checkpoints. Apparently even very smart robots need separation of powers, because otherwise they start grading their own homework with glitter pens.

## 1. How Brandon Should Use This

Brandon should only need short commands:

```text
Start renderer PR 1.
Continue current renderer PR.
Send current renderer PR to Opus review.
Fix only Opus blocking issues.
Prepare human checkpoint.
Proceed to next renderer PR.
Show renderer PR status.
```

Agents must infer the full process from this file and `docs/RENDERER_PR_STATUS.md`.

Do not ask Brandon to paste long prompts. If an agent needs detailed instructions, it must read this file and construct them.

## 2. Non-Negotiable Global Guardrails

Block or revert immediately if a PR accidentally includes:

- mutation of `data/fixture_model.json`
- mutation of capture data
- whole-renderer rewrite
- WebGL conversion
- removed existing `second_pattern` rendering
- moved fixture/aperture source origins
- hidden decoded/composed fallback behavior
- visual polish before MotionState correctness
- missing tests for new MotionState logic
- diagnostics removal
- broad unrelated refactors

No implementation PR may merge without:

```text
Codex implementation report
relevant tests/smoke checks
Opus review of the actual diff
human checkpoint approval
```

The orchestrator may prepare a merge recommendation, but Brandon decides final merge approval.

## 3. Required Repo State Tracking

Maintain this file during renderer work:

```text
docs/RENDERER_PR_STATUS.md
```

The status file should be updated at the end of each major step:

- branch created
- Codex implementation started
- Codex implementation finished
- tests/smoke run
- Opus review requested
- Opus review completed
- blocking fixes started
- blocking fixes completed
- human checkpoint prepared
- PR merged or abandoned

The status file prevents agent amnesia. Without it, every session becomes an archaeological dig through half-remembered chat messages, which is how civilization loses weekends.

## 4. Required Artifact Layout

Each PR should store or reference artifacts under:

```text
artifacts/renderer/<pr-name>/
```

Recommended contents:

```text
implementation_report.md
opus_review.md
smoke_cases.txt
render_grid_before.html
render_grid_after.html
screenshots/                 optional if screenshots were generated
manual_notes.md              optional human/physical comparison notes
```

If artifacts cannot be committed, the implementation report must still state where they were produced and what they showed.

## 5. Current Roadmap

### PR 1 — `renderer-motionstate-pr1`

Goal: MotionState foundation and visibility gates.

Scope:

- add `docs/RENDERER_MOTION_MODEL_V1.md`
- add browser-local MotionState builder
- add compatibility bridge from MotionState into current `_drawFan()` path
- preserve existing visuals as much as possible
- carry CH2 `control.sound_gated` into renderer layer/MotionState logic
- add debug sound gate override
- add CH1 power/dimmer visibility handling
- add CH6/CH7 `position.blanked` visibility handling
- add CH15/CH16 off/position/speed MotionState handling
- replace sine-threshold strobe gate with explicit square-wave MotionState gate
- add CH10 drawMode mapping:
  - `line-bright -> bright_line`
  - `line -> beam_line`
  - `dot -> dot`
- add `second_pattern` per-layer MotionState
- add MotionState debug output/panel or console inspection
- add warnings for CH15/CH16 approximate waveform
- add warning for CH19 approximate wave deformation
- add pure-JS MotionState tests
- add visual smoke check using `calib/render_test.py` or `calib/render_grid.py`

Acceptance:

- CH1=0 draws nothing and `killReason=power_off`
- CH6/CH7 center draws centered
- CH6 or CH7 outside blank window draws nothing and `killReason=position_blanked`
- CH2 `sound_gated` draws nothing unless debug override is enabled
- CH15 position mode is static, not oscillator
- CH15 speed mode oscillates and warns approximate/unverified
- CH16 position mode is static, not oscillator
- CH16 speed mode oscillates and warns approximate/unverified
- CH11 strobe uses square-wave gate
- CH10 dot gives `drawMode=dot`
- `second_pattern` active produces second layer MotionState
- `second_pattern` rendering is not broken
- CH19 active warns approximate/unverified
- no NaN/undefined MotionState fields
- existing source origins remain fixed
- existing visuals are preserved as much as possible

### PR 2 — `renderer-motion-fidelity-pr2`

Goal: improve motion fidelity after MotionState exists.

Scope:

- CH12/13/14 rotation MotionState
- CH17 zoom size/speed/pulse MotionState
- CH19 wave phase/amplitude MotionState
- oscillator trace/debug output
- centralized waveform policy for CH15/CH16
- true CH10 dot rendering if PR 1 only exposed drawMode
- better strobe duty approximation if supported by model/calibration evidence

### PR 3 — `renderer-diagnostics-pr3`

Goal: make renderer trustable during show design.

Scope:

- clean Debug View separate from Show View
- per-layer MotionState panel
- aim crosshair overlay
- blanking boundary overlay
- strobe indicator
- sound gate indicator and override state
- second-pattern layer indicator
- approximation badges
- composed vs decoded fallback diagnostic
- model confidence diagnostic

### PR 4 — `renderer-visual-polish-pr4`

Goal: improve visual realism without changing motion semantics.

Scope:

- beam core/mid/halo tuning
- source glow
- trail fade
- haze wedge tuning
- brightness scaling
- dot appearance
- strobe visual sharpness
- room/camera view tuning
- fixture spacing tuning through calibration where possible

### PR 5 — `renderer-physical-calibration-pr5`

Goal: correct mismatches from real laser comparison.

Scope depends on physical comparison results:

- CH15/CH16 waveform correction
- CH19 wave coordinate-space correction
- dot mode correction
- strobe duty correction
- dynamic macro correction
- zoom response correction
- pattern density/spread correction
- color/gradient correction

### PR 6 — `renderer-product-hardening-pr6`

Goal: final cleanup.

Scope:

- performance cleanup
- docs cleanup
- UX cleanup
- remove dead code
- stabilize tests
- final operator workflow

## 6. Standard Agent Loop

For each PR:

1. Read `AGENTS.md`, this file, Rev 3 plan, and `docs/RENDERER_PR_STATUS.md`.
2. Verify clean repo state or report dirty state.
3. Create or verify the correct branch.
4. Update `docs/RENDERER_PR_STATUS.md`.
5. Give Codex the current PR scope from this file.
6. Let Codex implement only that scope.
7. Inspect changed files for scope creep.
8. Run relevant tests.
9. Run renderer smoke harnesses where applicable.
10. Produce or update implementation report.
11. Prepare Opus handoff packet.
12. Get Opus review of the actual diff.
13. Fix only blocking or approved minor Opus issues.
14. Rerun tests/smoke checks.
15. Update status file.
16. Prepare human checkpoint.
17. Stop.

The orchestrator should not automatically proceed to the next PR after a checkpoint. Brandon must approve.

## 7. Required Handoff Packet to Opus

When sending a PR to Opus, include:

```text
PR name:
Branch:
Base branch:
Plan section:
Files changed:
Diff summary:
Implementation report:
Tests run:
Smoke checks run:
Known approximations:
Explicit non-goals:
Questions for Opus:
```

Opus must review the actual diff, not just the report. If Opus cannot inspect the diff, the correct verdict is:

```text
BLOCK_MERGE
```

## 8. Required Implementation Report

Every implementation PR must produce an implementation report, preferably:

```text
artifacts/renderer/<pr-name>/implementation_report.md
```

Minimum sections:

```text
1. Scope implemented
2. Files changed
3. Design summary
4. How existing renderer behavior was preserved
5. Tests run
6. Renderer smoke checks
7. Known approximations
8. Deferred PR 2+ items
9. Risks / manual checks needed
```

For PR 1, the report must specifically explain:

```text
how MotionState is built
how MotionState bridges into _drawFan()
how CH2 sound_gated is carried into renderer state
how second_pattern layering is preserved
how source origins remain fixed
```

## 9. Test and Smoke Policy

Agents should run existing tests when available. If a command does not exist, the agent should report that and use the closest available smoke check.

Renderer smoke checks should prefer:

```text
calib/render_test.py
calib/render_grid.py
```

PR 1 minimum smoke cases:

```text
power off
center static
blank CH6
blank CH7
dot mode
strobe
CH15 position
CH15 speed
CH16 position
CH16 speed
CH19 wave x
CH19 wave y
second_pattern active
```

The visual baseline does not need perfect pixel matching. It must catch obvious regressions:

```text
source origins moved
second_pattern disappeared
blanked channels still render
sound_gated channels still render without override
CH10 dot destroys the fan unexpectedly
CH15/CH16 movement explodes geometry
strobe permanently dark or permanently open
```

If automated screenshots are unavailable, the orchestrator should request only a single human visual checkpoint, not repeated manual testing.

## 10. Short Command Behavior

### `Start renderer PR 1.`

Agent should:

1. read `AGENTS.md`, this file, Rev 3 plan, and status file;
2. create/verify branch `renderer-motionstate-pr1`;
3. update status file;
4. implement PR 1 only;
5. run tests/smoke checks;
6. produce implementation report;
7. prepare Opus review packet or request Opus review if available;
8. stop.

### `Continue current renderer PR.`

Agent should:

1. identify current branch and PR scope from status file;
2. continue only that scope;
3. run relevant tests/checks;
4. update status file;
5. produce concise status.

### `Send current renderer PR to Opus review.`

Agent should prepare an Opus review request using the current diff, implementation report, and current PR scope.

Opus must audit:

- scope compliance
- source-origin preservation
- second-pattern preservation
- MotionState architecture
- visibility gates
- diagnostics
- tests/smoke checks
- accidental fixture_model/capture changes
- whether implementation report matches code

### `Fix only Opus blocking issues.`

Agent should:

1. apply only blocking or explicitly required minor fixes;
2. avoid future-PR features;
3. rerun tests/smoke checks;
4. update implementation report;
5. update status file.

### `Prepare human checkpoint.`

Agent should return:

```text
PR checkpoint

PR:
Branch:
Status:
Files changed:
Tests run:
Render smoke result:
Opus verdict:
Remaining approximations:
Human action needed:
Exact approval options:
```

Human action should be one of:

```text
approve merge
reject and fix listed issues
review screenshot/browser output
perform physical comparison
```

### `Show renderer PR status.`

Agent should summarize `docs/RENDERER_PR_STATUS.md` and the current branch/diff.

### `Proceed to next renderer PR.`

Agent should only do this after the prior PR is approved and merged. It should identify the next PR from the roadmap and start that branch/scope.

## 11. Codex Implementation Prompt Template

When Codex is implementing, it should use this template internally:

```text
Implement the current renderer PR only.

Read:
- AGENTS.md
- docs/RENDERER_AGENT_ORCHESTRATION.md
- docs/RENDERER_PR_STATUS.md
- docs/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md
- relevant source files for this PR

Stay within the current PR scope.
Do not modify fixture_model.json.
Do not modify capture data.
Do not convert to WebGL.
Do not remove second_pattern rendering.
Do not move fixture/aperture origins.

After implementation:
- run tests
- run renderer smoke checks if relevant
- produce implementation report
- update status file
- stop
```

## 12. Opus Review Prompt Template

When Opus reviews, it should use this template internally:

```text
Review the actual current PR diff against:
- AGENTS.md
- docs/RENDERER_AGENT_ORCHESTRATION.md
- docs/RENDERER_PR_STATUS.md
- docs/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md
- implementation report
- smoke/test results

Return exactly one:
- APPROVE
- APPROVE_WITH_MINOR_FIXES
- REQUEST_CHANGES
- BLOCK_MERGE

Separate blockers from optional/future-PR improvements.
Do not request future-PR features as current blockers.
Cite file paths and line numbers where possible.
If implementation report conflicts with code, code wins.
```

## 13. Failure and Recovery Policy

If Codex expands scope:

```text
stop, revert unrelated changes, update status, continue only current PR scope
```

If tests fail:

```text
Codex gets one focused fix pass for test failures
if still failing, prepare human checkpoint with failure summary
```

If Opus blocks merge:

```text
Codex fixes only Opus blockers
optional/future items go to later PR notes
```

If renderer visuals obviously break:

```text
block merge
restore previous visual behavior unless the change was explicitly intended and documented
```

If branch state becomes confusing:

```text
stop
summarize current branch, diff, status file, and recommended recovery
```

## 14. Product Definition of Done

The renderer project is not done until:

```text
MotionState exists and is inspectable
visibility gates are respected
CH2 sound-gated cues do not lie
CH6/CH7 blanking works
strobe behavior is explicit
CH15/CH16 modes are not confused
second_pattern is rendered and diagnosed
show/debug separation exists
visual polish does not hide wrong motion
physical comparison notes exist for representative cues
```

## 15. Minimal Human Work Contract

Brandon should not be asked to paste full prompts repeatedly.

Brandon should only need to provide short commands and final visual/physical judgment.

If an agent needs a full prompt, it should read this file and construct the prompt itself. Making the human paste the same wall of text every 30 minutes is not workflow design. It is clerical punishment with syntax highlighting.
