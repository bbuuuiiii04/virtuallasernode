# Renderer Agent Orchestration Guide

This guide lets Brandon use short commands instead of repeatedly pasting full implementation and review prompts. Agents should read this file and `AGENTS.md` before renderer work.

Primary plan:

```text
docs/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md
```

## How Brandon Should Use This

Brandon only needs to say one of these short commands:

```text
Start renderer PR 1.
Continue current renderer PR.
Send current renderer PR to Opus review.
Fix only Opus blocking issues.
Prepare human checkpoint.
Proceed to next renderer PR.
```

Agents must infer the full process from this file.

## Current Roadmap

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

## Short Command Behavior

### `Start renderer PR 1.`

Agent should:

1. read `AGENTS.md`, this file, and Rev 3 plan;
2. create/verify branch `renderer-motionstate-pr1`;
3. implement PR 1 only;
4. run tests/smoke checks;
5. produce implementation report;
6. stop and request Opus review or run Opus review if available.

### `Continue current renderer PR.`

Agent should:

1. identify current branch and PR scope;
2. continue only that scope;
3. run relevant tests/checks;
4. produce concise status.

### `Send current renderer PR to Opus review.`

Agent should prepare an Opus review request using the current diff and current PR scope.

Opus must audit:

- scope compliance
- source-origin preservation
- second-pattern preservation
- MotionState architecture
- visibility gates
- diagnostics
- tests/smoke checks
- accidental fixture_model/capture changes

### `Fix only Opus blocking issues.`

Agent should:

1. apply only blocking or explicitly required minor fixes;
2. avoid future-PR features;
3. rerun tests/smoke checks;
4. update implementation report.

### `Prepare human checkpoint.`

Agent should return:

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

### `Proceed to next renderer PR.`

Agent should only do this after the prior PR is merged. It should identify the next PR from the roadmap and start that branch/scope.

## Codex Implementation Prompt Template

When Codex is implementing, it should use this template internally:

```text
Implement the current renderer PR only.

Read:
- AGENTS.md
- docs/RENDERER_AGENT_ORCHESTRATION.md
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
- stop
```

## Opus Review Prompt Template

When Opus reviews, it should use this template internally:

```text
Review the actual current PR diff against:
- AGENTS.md
- docs/RENDERER_AGENT_ORCHESTRATION.md
- docs/RENDERER_MOTION_FIRST_REVIEW_PLAN_REV3.md

Return exactly one:
- APPROVE
- APPROVE_WITH_MINOR_FIXES
- REQUEST_CHANGES
- BLOCK_MERGE

Separate blockers from optional/future-PR improvements.
Do not request future-PR features as current blockers.
Cite file paths and line numbers where possible.
```

## Minimal Human Work Contract

Brandon should not be asked to paste full prompts repeatedly.

Brandon should only need to provide short commands and final visual/physical judgment.

If an agent needs a full prompt, it should read this file and construct the prompt itself. Because making the human paste the same wall of text every 30 minutes is not workflow design, it is clerical punishment with syntax highlighting.
