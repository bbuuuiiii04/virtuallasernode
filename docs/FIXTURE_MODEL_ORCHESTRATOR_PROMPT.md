# Fixture Model Orchestrator Prompt

> Superseded operational prompt. Do not paste this file for the final run without reconciling it against `docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md`, which is the current runbook and contains the final command. This file is retained as historical context for the v2 program prompt.

---

Build and run a sequential orchestrator that executes the CH1-19 Fixture Model Program end to end, including physical captures, on the local rig. Current source of truth: `docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md`, with program background in `docs/FIXTURE_MODEL_PROGRAM.md`.

## Authorization & preflight (once, before any laser output)
- Require an explicit `--rig-confirmed` flag to enable DMX output; without it, run code/dry-run only.
- Preflight asserts: SoundSwitch quit; `lsof` shows the selected ENTTEC port free; ENTTEC Pro identity passes for the explicit `--dmx-port`; ffmpeg resolves the fixture camera by name, rejects Desk View/screen capture, and records a 60fps test frame; blackout round-trips to the frame file. Abort if any fail.
- Capture one wide full-frame reference and confirm it contains the full CH15/CH16 travel and max CH17 growth (§3.3) before trusting any `blank`.
- **Camera framerate (lighting, not thermal):** disable iOS **Settings → Camera → Record Video → Auto FPS** (low-light) on the iPhone. Then capture one test clip **at the intended super-dim operating point** (room dark enough to see beams, but scene metering **≥~20 mean luma**) and confirm it reads **≥55fps** via `ffprobe nb_frames/duration`. The limiter is light, not heat — there is nothing to cool or wait out.

## Orchestration (resumable; `--resume-from PHASE`; checkpoint after each phase)
Run in order, merging results into `data/fixture_model.json` after each phase and appending to `captures/fixture_model/manifest.jsonl` (§3.9 layout):
1. **Phase 0** (no rig): cite the recorded 118-row dense validation if the ephemeral `/tmp` dense root is absent; do not fabricate fresh dense analysis.
2. **Phase 1** (capture): CH1 binary gate FIRST (CH1=0 off, CH1>0 on), then CH3/CH4 atlas and CH1-19 single-channel sweeps, both tracks. The geometry/motion track must hold >=~20 luma for 60fps; the colour track may be dimmer/30fps. Analyze -> merge transfer functions + the geometry-precision exit artifact.
3. **Phase 1.5** (capture): 7-channel probe (CH8/CH10/CH12/CH15/CH17/CH18/CH19) × the corpus+lab bases. Then apply the coded base-dependence rule (default: ≥2 of 7 probe channels deviate >25% across bases → base-dependent) and auto-scope Phase 3.
4. **Phase 2** (capture): gating tests (CH1→all, CH3 split, CH8→CH9; CH8↔CH18 as NOT-gated per v2; CH3+CH4→shape).
5. **Phase 3** (capture): compositional grids at the size the gate chose - coarse default, per-group order (colour -> translate -> scale -> CH12xCH15 + CH15xCH19 -> orientation), each group's verdict derived before the next; enforce the current resume-safe new-capture cap from the orchestrator.
6. **Phase 4** (capture): independence spot-checks incl. CH11×CH15.
7. **Phase 5** (no rig): formal `data/fixture_model_schema.json`, composition adapter as a NEW module augmenting (never replacing) `decode_36ch()`.
8. **Phase 6** (no new capture): validate the composed model against the 118 existing + all new cue-relevant captures; bucket pass/unresolved/firmware-locked/higher-order; run targeted higher-order grids only if real cues fail (capture, gated by the cap).

## Capture-loop robustness (every physical capture)
- Quit-SoundSwitch precondition held for the whole run.
- Per state: blackout → set DMX → settle → record → verify **not blank** (retry up to 3×); on persistent blank, log `recapture_pending` and continue (never synthesize).
- After each clip, `ffprobe` actual delivered fps. If **<55fps**, use the orchestrator's ContinuityCaptureAgent reset/warmup path and retry; if it cannot recover, tag fps30 and continue according to current code. Never silently accept an unexplained <55fps clip; never insert cooldown pauses.
- On FTDI hang / ffmpeg failure / any exception: **send blackout, stop daemon, halt, and write a resume checkpoint.**
- Between phases and at end: blackout + frame-file all-zero verify + physical dark check. For the ENTTEC Pro, never hard-kill the daemon because the widget retransmits the last frame until it receives a new one.

## Guardrails (hard)
- No `static/renderer.js` / `calibration.json` render-value / `decode_36ch()` contract changes — SHA-256 before/after `renderer.js calibration.json fixtures.py`, diff must be empty.
- Never reuse the `0.35s` floor; never gate on `clipped`; never fabricate or assume the base-dependence verdict.
- Honor the current orchestrator cap (`--max-new-captures`, default 10000 captures taken this invocation); if a phase would exceed it, halt and report for rescope.

## Verification & deliverables
- `py_compile` new modules + `json.tool` the model/coverage/schema + `node --check renderer.js` + hash-diff attestation.
- Per-phase report: captures taken, blanks/retries, low-fps relight events, analysis summary, model-merge diff, and (Phase 1.5) the gate verdict + resulting Phase 3 scope.
- Final: completed `data/fixture_model.json` + `data/fixture_model_schema.json`, validation results, safety state, and any `recapture_pending` / `lowfps_30_ok` / camera-bracketing flags left for human follow-up.

## Success condition
Phases run in sequence with captures; the base-dependence gate auto-scopes Phase 3; the model is assembled and validated against real cues; no guardrail violated; no fabricated data; the rig ends blacked out.
