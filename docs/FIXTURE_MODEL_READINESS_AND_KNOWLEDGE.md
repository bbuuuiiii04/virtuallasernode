# Fixture Model Readiness And Knowledge

This is the current source of truth for the final CH1-19 fixture-model capture run. It supersedes stale operational assumptions in older prompts and cross-references `docs/FIXTURE_MODEL_PROGRAM.md` for the original program narrative.

## Readiness Verdict

Software readiness: READY after the safe validation commands in this document pass. The current code has the resume-safe budget, missing-dense-root provenance handling, Phase 6 provenance labeling, Pro monitor detection, default-off frame strips, and cheap-but-safe fps probing in place.

Physical readiness: READY AFTER FINAL LIVE VALIDATION. A read-only AVFoundation device list on this machine currently shows `brandon Camera` as video device 0, plus `brandon Desk View Camera` and `Capture screen 0` as rejected non-wall sources. The final run must still validate a real fixture-facing test clip, non-desktop still, fps >=55, SoundSwitch quit, FTDI free, and Pro identity immediately before unattended capture.

Do not start the final run while SoundSwitch owns the DMX port. SoundSwitch may be useful for manual visual aiming, but the orchestrator preflight quits it and then owns the ENTTEC Pro port.

## Findings Register

HIGH-1 missing dense root: fixed in `calib/fixture_model_orchestrator.py:1237-1266`. `recorded_dense_rows()` cites `data/fixture_model.json` provenance, and `validate_existing_dense()` only falls back when the `/tmp` dense manifest is absent. If a manifest is present but wrong, it still errors.

HIGH-2 capture budget: fixed in `calib/fixture_model_orchestrator.py:44-45`, `calib/fixture_model_orchestrator.py:708-725`, and `calib/fixture_model_orchestrator.py:1415-1440`. The cap is 10000 captures taken this invocation, not cumulative manifest rows, so resume does not penalize already-recorded rows.

MEDIUM-1 Phase 6 dense coverage source: fixed in `calib/fixture_model_orchestrator.py:1350-1372`. When the dense analysis root is gone, Phase 6 reports `captured_exact_vectors_source = "phase0_record_dense_root_absent"` and keeps pass/fail unresolved instead of fabricating outcomes.

MEDIUM-2 monitor daemon detection: fixed in `calib/fixture_model_monitor.py:101-110`. The monitor counts both `dmx_open.py daemon` and `dmx_pro.py daemon`.

A1 frame-strip efficiency: fixed in `calib/fixture_model_orchestrator.py:57`, `calib/fixture_model_orchestrator.py:630-654`, `calib/fixture_model_orchestrator.py:990-1069`, and `calib/fixture_model_orchestrator.py:1446-1468`. `frame_strip.jpg` generation is now opt-in via `--frame-strips`; required `still.jpg`, desktop checks, frame stats, metadata, and analysis remain unchanged. The monitor creates its own latest-stills sheet from `still*.jpg` in `calib/fixture_model_monitor.py:59-93`.

A2 fps efficiency: fixed in `calib/fixture_model_orchestrator.py:366-405`. `ffprobe_fps()` now uses MP4 `nb_frames / duration` first and falls back to decoded `-count_frames` when the header count is absent or invalid. Tests cover 30fps, 60fps, and fallback behavior in `calib/test_fixture_model_readiness.py:165-205`.

A3 color-track reduction: OPEN QUESTION, no coverage reduction implemented. Current Phase 1 and Phase 1.5 still capture both `geometry_motion` and `color` tracks in `calib/fixture_model_orchestrator.py:856-887`. Recommendation: keep both tracks for the final run. The Phase 1.5 gate currently uses loop duration or motion-direction confidence without exposure-track-specific logic (`calib/fixture_model_orchestrator.py:1307-1323`), but the color analyzer and white-balance path still provide evidence for CH8/CH9/CH18 and possible color interactions (`calib/dense_cue_breakpoints.py:265-324`). With the manifest reset, there is no complete current dataset proving geometry-channel color captures are redundant.

A4 laser-bloom/table-glare analyzer hardening: fixed in `calib/fixture_model_orchestrator.py:40-61`, `calib/fixture_model_orchestrator.py:545-807`, `calib/fixture_model_orchestrator.py:949-1003`, `calib/fixture_model_orchestrator.py:1435-1496`, and `calib/dense_cue_breakpoints.py:43-45`, `calib/dense_cue_breakpoints.py:69-127`, `calib/dense_cue_breakpoints.py:294-344`, `calib/dense_cue_breakpoints.py:585-652`. The old broad bright rule could classify laser-lit wall bloom as geometry, and the temporary blind bottom crop could silently truncate CH16/CH17. The analyzer now derives `captures/fixture_model/analysis_geometry.json` from a static reference frame, detects both aperture boxes, aligns them to `setup_geometry.json`, and sets the bottom ROI to the detected static-base box bottom plus a small boundary margin (`VLN_ANALYSIS_BOUNDARY_MARGIN_INCHES`, default 0.75 in), clamped only if a bottom glare band is detected. If the small boundary margin conflicts with the glare/baseboard band, it records `roi_boundary_glare_conflict`. `geometry_clipped_low` is surfaced in frame stats and dense analysis; CH16/CH17 captures with that flag are marked recapture-pending instead of accepted silently.

LOW-1 capture subprocess wall-clock timeout: deferred. `capture_video()` and frame extraction rely on subprocess completion (`calib/fixture_model_orchestrator.py:499-508`, `calib/fixture_model_orchestrator.py:580-584`). This is not changed in this pass.

LOW-2 stale debris: deferred. Helper folders such as `_camera_mark_check/` and `.DS_Store` are not model evidence and should not affect manifest-driven progress.

## Capture Program

The model is base look plus modifiers: CH3 selects the bank/folder, CH4 selects the program/look inside that bank, and CH5-19 modify the selected base. CH3 dynamic values >=128 are out of scope for this static-pattern run. The orchestrator's modeled channel names live in `CHANNEL_NAMES` at `calib/fixture_model_orchestrator.py:60-79`.

Core value generators:

- Sweep values: `range(0, 253, 4) + [255]`, 65 values (`calib/fixture_model_orchestrator.py:771-775`).
- CH3 static atlas reps: `[8, 24, 40, 56, 96]`, one representative for each static folder group (`calib/fixture_model_orchestrator.py:778-780`).
- CH4 atlas values: `range(2, 253, 5) + [255]`, 52 looks including the terminal 255 look (`calib/fixture_model_orchestrator.py:783-789`).
- Phase 1.5 probe values: 22 values (`calib/fixture_model_orchestrator.py:792-793`).
- Phase 1.5 bases: 6 current base labels in `BASES` (`calib/fixture_model_orchestrator.py:84-90`).

Exact generated counts from current code:

- Phase 1: 2472 captures. Derivation: CH1 binary gate 2 + CH3/CH4 atlas 5 * 52 * 2 tracks = 520 + 15 modifier channels * 65 sweep values * 2 tracks = 1950 (`calib/fixture_model_orchestrator.py:825-846`).
- Phase 1.5: 1848 captures. Derivation: 6 bases * 7 probe channels * 22 probe values * 2 tracks (`calib/fixture_model_orchestrator.py:849-856`).
- Phase 2: 29 captures. Derivation: CH1 enable spot checks, CH3 static/dynamic split, CH8/CH9 and CH8/CH18 gates, and CH3/CH4 shape checks (`calib/fixture_model_orchestrator.py:866-878`).
- Phase 3 default: 664 captures. Derivation: seven 8x8 pair grids = 448 plus one 6x6x6 orientation grid = 216. If probe channels are base-dependent, only affected groups expand across `BASES` (`calib/fixture_model_orchestrator.py:887-914`).
- Phase 4: 48 captures. Derivation: six independence pairs * eight grid values (`calib/fixture_model_orchestrator.py:917-924`).
- Phase 6: 175 captures from unique resolved cue vectors in `data/soundswitch_laser_cues.json` (`calib/fixture_model_orchestrator.py:927-944`).

Gate rules:

- CH1 is treated as binary: CH1=0 off, any nonzero on. The code captures only CH1 0 and `CH1_ON_VALUE` 220, then runs `ch1_binary_gate()` before continuing Phase 1 (`calib/fixture_model_orchestrator.py:82-83`, `calib/fixture_model_orchestrator.py:1100-1139`).
- CH6=128 and CH7=128 are the visibility baseline in `PRIMARY_BASE`; CH6/CH7 sweep blanks are expected fixture behavior, not capture failure (`calib/fixture_model_orchestrator.py:83`, `calib/fixture_model_orchestrator.py:953-956`).
- Phase 1.5 decides base dependence. It ignores legacy ambiguous, non-base-keyed orphan rows and applies the default rule: base-dependent if at least two of seven probe channels deviate more than 25 percent across bases (`calib/fixture_model_orchestrator.py:1276-1313`).
- Phase 3 uses the Phase 1.5 verdict to multiply only varied groups across bases (`calib/fixture_model_orchestrator.py:899-914`).
- Phase 6 keeps validation unresolved until measured model-vs-capture comparison exists; it does not fabricate pass/fail buckets (`calib/fixture_model_orchestrator.py:1350-1372`).

## DMX Architecture And Safety

The orchestrator talks to DMX through a subprocess CLI plus `/tmp/vln_calib_frame.bin` and `/tmp/vln_calib_frame.heartbeat`; backend selection is via `--dmx-backend` and `--dmx-port` (`calib/fixture_model_orchestrator.py:30-34`, `calib/fixture_model_orchestrator.py:1419-1421`).

Open backend: `calib/dmx_open.py` is the validated pyftdi bit-bang baseline. It was intentionally kept as the default backend so Pro support is opt-in.

Pro backend: `calib/dmx_pro.py` uses ENTTEC framed packets. Packet contract is label 6, length 513, payload `0x00` start code plus 512 channel bytes; channel N maps to byte index N-1 after the start code (`calib/dmx_pro.py:29-35`, `calib/dmx_pro.py:50-56`, `calib/dmx_pro.py:106-114`, `calib/dmx_pro.py:320-324`).

Pro identity and port resolution: the Open and Pro share USB VID/PID, so `--dmx-port /dev/cu.usbserial-EN396681` is the safest selector. If no explicit port is supplied for Pro and multiple FTDI ports exist, the code errors (`calib/fixture_model_orchestrator.py:213-226`). Pro identity is read-only label 3 and sends no DMX output (`calib/dmx_pro.py:160-187`).

Pro safety consequence: the Pro autonomously retransmits the last DMX frame. If the Pro daemon is hard-killed, the widget can leave lasers lit at the last frame. The daemon pushes zero on catchable SIGTERM/SIGINT/normal exit (`calib/dmx_pro.py:21-27`, `calib/dmx_pro.py:241-245`, `calib/dmx_pro.py:286-296`), and its watchdog sends/persists blackout when the orchestrator heartbeat goes stale (`calib/dmx_pro.py:46-57`, `calib/dmx_pro.py:269-284`). `kill -9` cannot be caught; the physical power switch or DMX-side kill is the only final failsafe. Never manually `kill -9` the Pro daemon.

The monitor's `safety_state` reads the frame file through `dmx_open.py show`, not the wire (`calib/fixture_model_monitor.py:42-44`). Treat it as frame-file state, not hardware readback.

## Camera Safety

The contaminated deleted run happened because a numeric AVFoundation index resolved to screen capture. The current guard is name-first and rejects `Capture screen` and `Desk View`, refusing to fall back to the numeric device (`calib/fixture_model_orchestrator.py:422-470`). `capture_video()` calls that guard before every clip (`calib/fixture_model_orchestrator.py:499-508`).

Every capture extracts a still, rejects desktop-like frames, computes ROI-cropped frame stats, and retries blanks up to three times unless the blank is expected CH1 off or CH6/CH7 out-of-bounds behavior. Nonblank low-ROI clipping is a separate quality signal: `geometry_clipped_low` is written into analysis, and CH16/CH17 captures with that flag become recapture-pending (`calib/fixture_model_orchestrator.py:949-1003`, `calib/fixture_model_orchestrator.py:1418-1496`).

White reference: Phase 1 captures or reuses `phase1_single_channel/_white_reference/CH08_000_white_reference.jpg`, and the analyzer white-balances against it through `VLN_WHITE_REFERENCE` (`calib/fixture_model_orchestrator.py:52-53`, `calib/fixture_model_orchestrator.py:534-565`, `calib/fixture_model_orchestrator.py:626-632`, `calib/dense_cue_breakpoints.py:303-324`).

ROI and bloom handling: `ANALYSIS_ROI_TOP_FRAC = 0.18` still excludes the top shelf/molding, but the bottom bound is no longer a blind 0.86 crop. Geometry is derived from the preflight-only boundary-box look (`GEOMETRY_REFERENCE_BASE`, CH3=0/CH4~62/CH5=0/CH6=128/CH7=128/CH17=0), not the `PRIMARY_BASE` line/capture baseline, which remains CH5=90 for sweeps. CH5=0 is used because it is the largest static pattern size and should match the pencil-tick physical boundary; CH17 stays explicitly 0 for this static max-envelope reference and is not an additional dynamic/extreme reference. `derive_analysis_geometry()` detects the two aperture boxes, uses `setup_geometry.json` box height to compute px/inch scale, adds `ANALYSIS_BOUNDARY_MARGIN_INCHES = 0.75`, and writes `captures/fixture_model/analysis_geometry.json`; frame stats and dense analysis consume that artifact when present and scale it for extracted analysis frames (`calib/fixture_model_orchestrator.py:727-843`, `calib/dense_cue_breakpoints.py:69-115`). Existing raw captures do not need physical recapture solely because of this fix, but existing manifest analysis is stale after preflight regenerates `analysis_geometry.json`; reanalyze all existing rows before Phase 5/model build so every row uses the same CH5=0 geometry provenance. If the small boundary margin overlaps a detected bottom glare/baseboard band, the artifact records `roi_boundary_glare_conflict`; the code does not silently prefer either boundary headroom or glare exclusion.

FPS recovery: after each clip, `ffprobe_fps()` measures delivered fps. If it is below 55, the code kills `ContinuityCaptureAgent`, takes throwaway warmup clips, retries up to three times, and tags fps30 if it cannot recover (`calib/fixture_model_orchestrator.py:511-524`, `calib/fixture_model_orchestrator.py:1003-1045`). Low fps can often be solved by that Continuity restarter, but preflight still requires recovery to >=55 before unattended capture.

Current read-only device list, captured during this pass: `brandon Camera`, `OBS Virtual Camera`, `FaceTime HD Camera`, `brandon Desk View Camera`, and `Capture screen 0`. The final command should use `--camera-name "brandon Camera"` for this local setup unless the operator intentionally renames or reconnects the camera and revalidates the exact device name.

## Dense Dataset Situation

The legacy dense capture root was `/tmp/vln_dense_cue_breakpoints_20260605_200426`, which was ephemeral and is now gone. The durable cited record is `data/fixture_model.json` provenance `phase0_validated_existing_dense_rows = 118`, read by `recorded_dense_rows()` (`calib/fixture_model_orchestrator.py:43`, `calib/fixture_model_orchestrator.py:1237-1244`).

When the raw dense root is absent, Phase 0 and Phase 6 cite that prior validation count with explicit provenance. They do not rerun analysis and do not fabricate pass/fail details (`calib/fixture_model_orchestrator.py:1247-1266`, `calib/fixture_model_orchestrator.py:1350-1372`). To restore live re-validation, the 118 raw dense clips must be recaptured or restored.

## Data Layout And Resume

Capture root is `captures/fixture_model/`; manifest is `captures/fixture_model/manifest.jsonl`; checkpoint is `captures/fixture_model/checkpoint.json`; analysis geometry is `captures/fixture_model/analysis_geometry.json`; model is `data/fixture_model.json`; schema is generated in Phase 5 at `data/fixture_model_schema.json` (`calib/fixture_model_orchestrator.py:36-43`, `calib/fixture_model_orchestrator.py:727-843`).

Each capture folder currently stores `video.mp4` or `video_color.mp4`, `still.jpg` or `still_color.jpg`, `metadata.json`, and `analysis.json`. `frame_strip.jpg` exists only when `--frame-strips` is passed (`calib/fixture_model_orchestrator.py:959-1039`).

Manifest rows include metadata plus a compact `analysis` summary and `folder` path, then checkpoint records last capture and totals (`calib/fixture_model_orchestrator.py:1023-1058`). JSON writes are atomic via temp file plus replace (`calib/fixture_model_orchestrator.py:133-141`).

Resume is folder-dedup plus session-relative budget. `completed_capture_folders()` ignores superseded legacy Phase 1.5 rows and rows with recapture-pending analysis, and `run_capture_phase()` filters pending cases before asserting the budget (`calib/fixture_model_orchestrator.py:728-769`, `calib/fixture_model_orchestrator.py:1062-1097`).

## Geometry Reference

`captures/fixture_model/setup_geometry.json` is still reference data for later coordinate analysis, but the analyzer now reads its aperture-box measurements during `analysis_geometry.json` derivation to convert detected box height into px/inch scale. Runtime capture/dense analysis then reads `analysis_geometry.json`, not the raw setup measurements directly. The setup geometry remains approximate unless marked exact; detection from the reference still is the primary source for box pixels.

Measurements currently recorded:

- Camera view: bottom visible wall width 9 ft 9 in, top visible wall width 11 ft, left/right visible wall height 5 ft 11 in, with left/right defined as image-left/image-right in the camera frame (`captures/fixture_model/setup_geometry.json:4-14`).
- Image-left aperture box: 3 ft 9 in wide, 3 ft 4 in high, bottom at 24.5 in, top at 5 ft 5 in; approximate user measured (`captures/fixture_model/setup_geometry.json:22-39`).
- Image-right aperture box: 4 ft 6 in to 4 ft 8 in wide, 3 ft 4 in to 3 ft 5 in high, bottom at 24.5 in, top at 5 ft 5 in; approximate/range user measured (`captures/fixture_model/setup_geometry.json:40-57`).
- Gap between boxes: 8.5 in approximate (`captures/fixture_model/setup_geometry.json:58-61`).
- Fixed references: outlet-to-box offsets approximate; bottom of white shelf 5 ft exact, distance between bottom outlets 6 ft 5 in exact, distance from outlets to white shelf 5 ft 1 in exact (`captures/fixture_model/setup_geometry.json:62-83`).
- Fixture setup: fixture-to-wall about 6 ft 1 in, camera-to-wall about 7 ft 5 in, fixture spacing 30.5 in center-to-center, fixtures parallel, one fixture used because both are identical (`captures/fixture_model/setup_geometry.json:85-94`).
- Physical fixture: laser output hole center spacing about 5 in, housing 9.6 x 6.4 x 3 in exact, aperture opening about 2 x 1.5 in (`captures/fixture_model/setup_geometry.json:95-110`).

Vendor-confirmed scanner specs are 15 kpps and +/-25 degrees; treat these as scanner-physics constraints for later renderer/coordinate work, not as built-in pattern files (`docs/FIXTURE_36CH.md:1-4`).

## Renderer Fidelity Gap

`static/renderer.js` is an aerial/beam-in-air visualizer, not a wall-pattern scan model. It models color, brightness, aim, movement, rotation, size/zoom, strobe, fan density, and beam glow (`static/renderer.js:1-5`, `static/renderer.js:269-347`, `static/renderer.js:427-480`).

It does not currently simulate a 15 kpps point budget, point-order flicker, corner softness, blanking timing, exact built-in pattern point lists, or coordinate-to-wall scaling from a +/-25 degree cone. The empirical capture run supplies look evidence; photoreal scanner physics is complementary future work and must not be mixed into this measurement run.

## Fixture CH1-19 Semantics

See `docs/FIXTURE_36CH.md:13-34` for the chart. Current capture semantics are:

- CH1: binary on/off for measurement. CH1=0 off; CH1>0 on. Do not use CH1 as a dimmer or exposure track.
- CH2: auto/sound, out of scope.
- CH3: pattern group. Static modeled range is <128; static bank reps are 8, 24, 40, 56, and 96. Dynamic >=128 is out of scope.
- CH4: pattern select. Static looks are sampled mid-bin every 5 values, plus 255 as a terminal look.
- CH5: pattern size.
- CH6/CH7: horizontal/vertical coarse position. 128/128 is required to keep patterns visible except during the CH6/CH7 sweeps.
- CH8: color and color macros; CH9 affects color-speed ranges.
- CH10: line/dot scan density.
- CH11: strobe.
- CH12/CH13/CH14: Z/X/Y rotation, angle below 128 and speed above 127.
- CH15/CH16: horizontal/vertical movement, position below 128 and speed above 127.
- CH17: zoom size/speed.
- CH18: gradient speed; not assumed CH8-gated.
- CH19: X wave at 1-127 and Y wave at 128-255.

Static outlines can look like a chasing/gradient segment on camera even when the real-life laser image is static. Treat manual/chart static-vs-moving intent as a prior and let the analyzer distinguish actual translation/rotation/wave motion from scan/rolling-shutter aliasing (`captures/fixture_model/setup_geometry.json:117-121`).

## Final Run Procedure

Run from `/Users/bbui/virtuallasernode`. Confirm the fixture is aimed safely, physical power kill is reachable, camera is framed on the wall, and SoundSwitch is quit before the command.

Recommended command for the current local setup:

```bash
caffeinate -dimsu calib/.venv/bin/python calib/fixture_model_orchestrator.py \
  --rig-confirmed \
  --dmx-backend pro \
  --dmx-port /dev/cu.usbserial-EN396681 \
  --camera-name "brandon Camera" \
  --camera-size 1280x720 \
  --resume-from 1 \
  --max-new-captures 10000
```

Do not pass `--frame-strips` for the final run unless debugging contact sheets; leaving it off saves substantial ffmpeg work per capture. If the exact camera name changes, stop and re-list AVFoundation devices, then use the exact fixture-facing camera name. Never use `Desk View`, `Capture screen`, or a numeric fallback. Do not move/angle the camera only to hide the table reflection; the derived `analysis_geometry.json` ROI and static-reference mask preflight are intended to preserve the measured framing while surfacing any boundary-vs-glare conflict explicitly.

Preflight behavior:

- Quits SoundSwitch and aborts if it remains running (`calib/fixture_model_orchestrator.py:199-206`, `calib/fixture_model_orchestrator.py:1171-1182`).
- Resolves and probes the selected Pro port (`calib/fixture_model_orchestrator.py:1179-1187`).
- Resolves camera by name and rejects non-wall devices (`calib/fixture_model_orchestrator.py:1193-1196`).
- Starts the daemon, blackouts, sets the `PRIMARY_BASE` "line" look with CH5=90, records a 1-second clip, verifies fps >=55, extracts a still, rejects desktop capture. It then projects the preflight-only boundary-box look `GEOMETRY_REFERENCE_BASE` (CH3=0, CH4~62, CH5=0, CH6/CH7=128, CH17=0) on a separate clip and derives/writes `analysis_geometry.json` and runs the mask sanity check from that box still, because CH5=0 is the largest static pattern size and `PRIMARY_BASE` traces lines (not boxes). Then it writes the checkpoint and blackouts/stops the daemon (`calib/fixture_model_orchestrator.py`).

Monitoring:

```bash
calib/.venv/bin/python calib/fixture_model_monitor.py --interval 600 --latest 8
```

The monitor reports progress bars, fps min/max/<55, run stats, process counts, safety frame-file state, and a contact sheet from the latest stills (`calib/fixture_model_monitor.py:69-115`; `calib/fixture_model_progress.py:69-93`).

Pause/resume:

- Prefer Ctrl-C/SIGTERM to the orchestrator. Its signal/exception path blackouts and checkpoints (`calib/fixture_model_orchestrator.py:1400-1412`, `calib/fixture_model_orchestrator.py:1086-1096`).
- Do not hard-kill the Pro daemon. If a process must be stopped, use catchable termination and verify dark output physically.
- Resume with the same command. The manifest folder-dedup and session-relative budget skip completed captures.

Physical validation checklist before unattended run:

1. SoundSwitch quit; `lsof /dev/cu.usbserial-EN396681` shows the port free.
2. `calib/.venv/bin/python calib/dmx_pro.py blackout --port /dev/cu.usbserial-EN396681 --require-hardware` succeeds while fixture is aimed safely.
3. Supervised non-zero Pro fire test has already been performed for this unit; repeat only if cabling/backend changed, with power kill in reach and immediate blackout afterward.
4. `ffmpeg -f avfoundation -list_devices true -i ""` lists the fixture camera by exact name; current expected local name is `brandon Camera`.
5. A real preflight clip through the orchestrator must show fixture wall, not desktop/Desk View, delivered fps >=55, and adaptive analysis-mask sanity must pass.
6. White reference is captured/reused at the start of Phase 1.
7. Confirm CH6=128 and CH7=128 baseline is preserved outside their own sweeps.
