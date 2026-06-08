# Calibration results (observed from the real lasers)

Rig: Enttec Open via pyftdi, camera + haze, agent-driven sweep. White-balanced
to the CH8=0 white reference (camera renders white as blue in dark haze).

## CH8 / CH25 Colour — DONE 2026-06-05  ✅
Fixed 7-colour set (CH8 4-31, one colour per 4 values), order confirmed:

| CH8 band | colour |
|----------|--------|
| 0        | white (separate) |
| 1-3      | "original colour" (not yet swept; decoder currently → white) |
| 4-7      | white |
| 8-11     | red |
| 12-15    | yellow |
| 16-19    | green |
| 20-23    | cyan |
| 24-27    | blue |
| 28-31    | magenta |
| 32-255   | effect/animation modes (not yet swept) |

Applied to `fixtures.py` SEVEN_COLORS (was a wrong guess R,G,B,Y,C,M,W).
Frames: /tmp/calib/c_{0,6,10,14,18,22,26,30}.png + ch8_*.png.

## Still TODO (camera + haze ready)
- CH8 1-3 "original colour"; CH8 32-255 effect modes (+CH9 speed)
- CH6/CH7 horizontal/vertical position direction + blank bounds
- CH12/13/14 rotation axis mapping (which screen axis each moves)
- CH15/16 movement direction; CH17 zoom; CH10 scan; CH11 strobe
- CH3/CH4 pattern shapes (for renderer pattern library)

## Motion — DONE 2026-06-05  ✅ (clean X pattern CH3=16, dim, frozen poses)
| Channel | Observed on real lasers | Renderer status |
|---------|-------------------------|-----------------|
| CH12 rot Z | in-plane spin (roll), CW as value↑ | ✅ z→roll correct |
| CH13 rot X | tilt toward/away (pitch); subtle vertical foreshorten | ✅ x→pitch correct |
| CH14 rot Y | swing L/R (yaw); horizontal skew | ✅ y→yaw correct |
| CH6 H pos | translate: value↑ = screen-RIGHT; low extreme blanks; 128=centre | ❌ was folded into roll |
| CH7 V pos | translate: value↑ = screen-UP; low extreme blanks; 128=centre | ❌ posY translation ignored |
| CH15 H move | fine H translate (pos mode); speed mode auto-sweeps | ❌ was wired to yaw |
| CH16 V move | fine V translate (pos mode); speed mode auto-sweeps | ❌ was wired to pitch |
| CH17 zoom | value↑ = pattern bigger/wider | ✅ size direction correct |

KEY RENDERER FIX: position (CH6/7) + movement (CH15/16) must TRANSLATE the
pattern (right/up), NOT rotate it. Rotation comes only from CH12/13/14.
Direction CW/CCW + L/R signs are best-guess from single stills; user can flip.

## Remaining channels — DONE 2026-06-05
| Channel | Observed | Renderer status |
|---------|----------|-----------------|
| CH5 size | val↑ = pattern SMALLER (0=large) | ✅ spread matches |
| CH8 1-3 "original" | = the pattern's native colour (RED observed), NOT white | ✅ fixed -> red |
| CH8 32-239 effect | per-beam multicolour that flows/cycles over time | ✅ rainbow-cycle approximates |
| CH9 colour speed | drives the effect cycle rate | ok |
| CH10 scan | line/dot — indistinguishable in mid-air beams (dots only show on a surface) | minor |
| CH11 strobe | on/off flashing | ✅ gate correct |
| CH3 group | style/density: folder1-2(0-31)=sparse 2-beam X; folder3-4(32-63)=dense wide fans; anim(64+)=X-types | ❌ renderer IGNORES pattern |
| CH4 selection | pattern variation within a group (beam count/angle) | ❌ renderer IGNORES pattern |

ALL patterns are beam-fan arrangements (no gobo figures).
**OPEN GAP**: renderer draws ONE generic fan regardless of CH3/CH4 — changing
pattern in SoundSwitch does not change the preview. Proposed: map CH3 group ->
beam density + CH4 -> variation so the preview responds to pattern changes.
Not yet swept: CH18 gradient, CH19 X/Y wave (minor animated).

## Combo-look validation — 2026-06-05  ✅
Drove 6 mixed looks + edge cases; all match the calibrated mappings:
- Colours dead-on across looks (cyan/red/green/magenta/white/flowing).
- Pattern density tracks CH3 group (dense fan vs sparse X).
- Position translate (CH6/7), rotation (CH12 angle+speed spin, CH14 yaw), zoom — all correct.
- CH15 speed = horizontal auto-sweep (translation); confirmed continuous.
- SECOND PATTERN (CH20-36, enabled CH4>=1) renders SIMULTANEOUSLY with the first,
  own colour+group (white X + red dense fan) — validates renderer _layers 2-pattern draw.
Renderer now also maps CH3/CH4 -> beam density (_patternShape) so pattern changes
show in the preview. Frames: /tmp/calib/L1-6.png, second_pat.png, sweep_spin/move.png.

## KEY behavioural finding — dynamic pattern groups  2026-06-05
CH3 >= 128 ("dynamic effect group") = SELF-ANIMATING pre-programmed look:
moves on its own AND cycles its own colours even with NO motion channels set and
CH8=0. Confirms manual note "dynamic effects group NOT applicable to CH5-CH19" —
i.e. for CH3>=128 the fixture IGNORES size/position/colour/rotation/movement and
plays its own animation. Static groups (CH3<=127) DO obey CH5-19.
RENDERER TODO: when pattern.kind=='dynamic', play a self-animating multicolour
look and ignore CH5-19 (currently applies them uniformly). Decoder already tags
kind='dynamic'. Frames: /tmp/calib/dyn_*.png. Mega stack: /tmp/calib/mega.png.

## Movement banks (CH15/CH16) — targeted deep-dive 2026-06-05
CH15 Horizontal movement:
  - Position bank 1-127: value 1 BLANKS; translates LEFT->RIGHT, centre ~64.
  - Speed bank 128-255: continuous horizontal SWEEP, monotonically faster.
CH16 Vertical movement:
  - Position bank 1-127: NARROWER usable window (~30-90); 1/96/127 blank;
    translates low->high within that window.
  - Speed bank 128-255: continuous vertical SWEEP; sweeps THROUGH the blank zone
    at the top extreme (pattern tilts out of view periodically).
VERDICT: each movement channel = ONE clean translate/sweep behaviour per axis.
No wave/shift sub-banks (the wrong 34CH manual's sub-ranges do NOT apply to 36CH).
CH16 vertical range is narrower than CH15 horizontal.
Fixes applied this session: CH6/7 blank window [55,254]; CH2 sound_gated; CH10
scan density/brightness in renderer. Position stills logged to calib/captures/.

## CH19 waves deep-dive 2026-06-05
1-127 = X-wave, 128-255 = Y-wave. Both distort straight beams into animated
undulating/rippling beams; amplitude+speed grow with value within each bank.
Axis distinction (X vs Y) hard to read from this camera angle (both = beam ripple).
NOTE: renderer does NOT yet implement wave distortion (minor gap).

## Look library (combinatorial, logged) — building 2026-06-05
- Pattern x colour matrix: CH3 {16,0,32,48,64} x CH8 {white,red,yellow,green,cyan,
  blue,magenta,flowing} = 40 static looks (calib/captures/look_p*_c*.png).
- + moving + second-pattern stacks (below).

## Live calibration pass — 2026-06-05 15:11–15:14
Captured a focused evidence set for the current renderer calibration:
- `calib_center_cyan_dense`: CH3=32 CH4=10 CH5=90 CH8=20 centered cyan dense reference.
- `calib_left_cyan_dense` / `calib_right_cyan_dense`: CH6=64/192 horizontal position.
- `calib_up_cyan_dense`: CH7=200, which nearly blanks/dims the look from this angle.
- `calib_zoom_cyan_dense`: CH17=100 zoom/spread.
- `calib_spin_cyan_dense`: CH12=150 Z rotation speed.
- `calib_hsweep_cyan_dense` / `calib_vsweep_cyan_dense`: CH15/16=200 sweep stills, captured near blank/out-of-view phase.
- `calib_dynamic_160`: CH3=160 dynamic self-animation, observed red/pink-dominant.
- `calib_ywave_cyan_dense`: CH19=200 Y-wave ripple, visibly bends beams.

First virtual comparison showed the preview was too dense/bright and CH6 pan was
too aggressive for the real cyan dense fan. Applied `calibration.json` pass:
reduced folder3/folder4 beam counts and spread, reduced `panGain`, moved source
lower in the frame, and reduced beam/source glow plus white boost. Remaining
renderer gaps from this pass: dynamic groups need more fixture-specific colour
families than the current rainbow self-animation, and CH19 wave amplitude/rate
should become calibration knobs if wave looks matter in show design.

Follow-up pass:
- Fixed reliable virtual grid export by adding `calib/export_grid.py`, using
  Chrome `--timeout=3000` instead of virtual time. The renderer runs continuous
  `requestAnimationFrame`, so `--virtual-time-budget` can hang.
- Added `VLN_GRID_COLS` support to `calib/render_grid.py` so virtual sheets can
  match the 5-column real capture sheet.
- Produced aligned comparison sheet:
  `/tmp/vln_real_vs_virtual_calib_sheet_dynamic_spinfix.png`
  Order: center, left, right, up, zoom, spin, hsweep, vsweep, dynamic, ywave.
- Mismatch ranking from the aligned sheet:
  1. Dynamic colour: real CH3=160 is red/pink-dominant; previous virtual was
     yellow/green rainbow. Added dynamic colour calibration knobs and set
     `dynamic.colorBase=235`, `dynamic.colorSpread=4`, `dynamic.colorRate=2`.
  2. Spin: real CH12=150 has a stronger crossed/rotated pose than virtual.
     Increased `rates.spinRps` from 0.18 to 0.28 as the single motion tweak.
  3. Static fan geometry: still too clean/symmetric versus camera/haze, but now
     close enough for the current constants-only pass.
  4. Horizontal/vertical sweep: still-frame phase makes current evidence weak;
     leave untouched until we capture short bursts or local motion summaries.
  5. Wave: visible but stylized; leave for a future CH19-specific pass.

## Master wall-pattern pass — 2026-06-05 17:00
Captured a clean no-haze wall pass using the iPhone Continuity Camera
(`avfoundation` device `2`, logged in the manifest). Both physical projectors
receive the same DMX, so the artifact builder crops the left wall projection as
the master fixture ROI and exports a single-fixture virtual sheet.

Artifacts:
- Real master wall contact sheet:
  `/tmp/vln_wall_master_real_contact_sheet.png`
- Single-fixture virtual render sheet:
  `/tmp/vln_wall_master_virtual_sheet.png`
- Aligned real-vs-virtual comparison:
  `/tmp/vln_wall_master_real_vs_virtual_comparison.png`
- Sent/logged DMX audit:
  `docs/CALIBRATION_WALL_MASTER_DMX_LOG.md`

Important capture note: the first attempted wall pass used FaceTime camera
device `0` and captured the wrong view. Those files were overwritten by the
iPhone Continuity Camera pass; current `wall_master_*` manifest entries include
`camera.device=2`.

Mismatch ranking from the wall comparison:
1. Source position/model mismatch: real evidence is a wall projection with the
   wall-hit line/dots visible; the renderer remains an aerial beam-fan view.
   Do not tune source height/orientation from this pass alone.
2. Fan/spread width mismatch: center cyan dense has roughly the right beam/dot
   count, but the virtual aerial fan reads much wider than the wall projection.
   This is partly projection-model mismatch; avoid broad spread changes here.
3. Horizontal offset mismatch: wall ROI shows CH6=64 shifts the master pattern
   right and CH6=192 shifts it left. Current virtual pan is the opposite for the
   master wall projection.
4. Vertical offset mismatch: CH7=200 blanks or moves out of the cropped master
   ROI; current virtual `up` also blanks, so no vertical change from this still.
5. Beam count mismatch: center cyan dense is close enough for this pass; keep
   `patternShape.folder3.n=8`.
6. Zoom mismatch: CH17=100 makes the real wall pattern much narrower; current
   virtual zoom makes it wider. This is a strong wall-specific calibration
   signal.
7. Spin/motion mismatch: CH12=150 produces a diagonal/rotated wall pose, but one
   still frame cannot validate spin rate. Preserve `rates.spinRps=0.28`.
8. Dynamic colour mismatch: CH3=160 remains red/pink-dominant in both real and
   virtual. Shape differs, but dynamic macro shape needs separate preset work.
9. Wave mismatch: CH19=200 shows a changed wall-line pose; still-frame phase is
   ambiguous. Defer wave tuning to timed/burst evidence.

Small calibration changes justified by this wall pass:
- Flip `geometry.panGain` sign so CH6 movement matches the master wall
  projection direction.
- Make active CH17 size-mode zoom shrink the virtual fan instead of widen it for
  the tested mid value.

Applied changes:
- `geometry.panGain`: `0.32` -> `-0.32`
- `zoom.min`: `0.55` -> `0.28`
- `zoom.range`: `0.9` -> `0.32`

Post-change artifacts:
- Updated virtual sheet:
  `/tmp/vln_wall_master_virtual_sheet_panzoomfix.png`
- Updated comparison:
  `/tmp/vln_wall_master_real_vs_virtual_comparison_panzoomfix.png`

What improved:
- CH6 pan direction now follows the master wall projection evidence instead of
  the earlier haze-perspective assumption.
- CH17=100 virtual zoom now narrows materially, matching the wall capture
  direction.

Still wrong / deferred:
- The renderer is an aerial beam-fan renderer, not a wall-projection renderer;
  source orientation and wall-hit geometry will remain visibly different until
  a dedicated wall preview/projection mode exists.
- CH15 horizontal sweep, CH16 vertical sweep, and CH19 wave are not tunable from
  these stills because their captured phase is blank or ambiguous. Capture
  timed bursts before changing those.
- CH12 spin speed was not changed; the wall still only gives one sampled pose,
  not a reliable rate.
- Laser 2 should reuse this master calibration for now. It should only get a
  per-fixture override if future evidence shows different brightness, colour
  balance, spread, mirror direction, aperture offset, or motion phase.

## Comprehensive wall CH3 look atlas — 2026-06-05 17:10–17:16
Captured a broader wall-pattern atlas for the master fixture ROI using iPhone
Continuity Camera device `2`, no haze, CH4=0 first-pattern isolation, CH5=90,
CH6/7=128, and CH8=20. Swept CH3 every 8 values plus 255.

Artifacts:
- Real wall CH3 atlas:
  `/tmp/vln_wall_ch3_atlas_real.png`
- Virtual CH3 atlas after dynamic-colour fix:
  `/tmp/vln_wall_ch3_atlas_virtual_dynamiccolorfix.png`
- Real-vs-virtual CH3 atlas comparison:
  `/tmp/vln_wall_ch3_atlas_comparison_dynamiccolorfix.png`
- Atlas report:
  `docs/WALL_CH3_LOOK_ATLAS.md`
- Modifier real sheet:
  `/tmp/vln_wall_modifier_real.png`
- Modifier virtual sheet after dynamic-colour fix:
  `/tmp/vln_wall_modifier_virtual_dynamiccolorfix.png`
- Modifier comparison:
  `/tmp/vln_wall_modifier_comparison_dynamiccolorfix.png`
- Modifier report:
  `docs/WALL_MODIFIER_PASS.md`

Observed CH3 look families:
- 0-8: circle/ring static.
- 16-40: horizontal line static.
- 48-56: two-point / dual-dot static.
- 64-120: dotted arc / compact swirl static-animation bank.
- 128-136: U-wave dynamic macro.
- 144-152: three-star dynamic macro.
- 160-168: compact swirl dynamic macro.
- 176: large star polygon dynamic macro.
- 184-192, 208-216, 232-240, 255: horizontal line dynamic variants.
- 200: low dotted-row dynamic macro.
- 224: compact point/dot dynamic macro.
- 248: late ring dynamic macro.

Limited modifier pass:
- Static line (`CH3=32`) and static swirl (`CH3=96`) respond visibly to colour,
  zoom, pan, spin, and strobe. Strobe stills can capture only an on/off phase.
- Dynamic macro representatives (`CH3=128/144/176/200/248`) are distinct real
  wall figures. Still frames identify families but do not model loop timing.

Renderer change from this pass:
- `static/renderer.js` dynamic colour selection now respects fixed CH8 RGB
  colours before falling back to the calibrated dynamic self-colour cycle. This
  fixes CH3 dynamic macros with CH8 fixed colours rendering as one forced
  red/pink family.

No `calibration.json` numeric changes were made in this atlas pass. The major
remaining mismatch is renderer capability: real dynamic macros are distinct
wall figures, while the virtual renderer still draws a generic aerial fan shape.
Next useful work is timed/burst capture and preset-family rendering for dynamic
macros, not haze/glow tuning.

## Full DMX channel wall audit — 2026-06-05 17:33–17:40
Ran a channel-by-channel wall projection audit for the master fixture using
iPhone Continuity Camera device `2`, no haze, fixed camera, and the left wall
projection as the master ROI. This pass was evidence gathering only: no
renderer behavior, haze/glow/bloom, Laser 2 override, or `calibration.json`
numbers were changed.

Artifacts:
- Full channel audit report:
  `docs/DMX_CHANNEL_AUDIT.md`
- Overview contact sheet:
  `/tmp/vln_channel_audit_overview.png`
- Per-channel contact sheets:
  `/tmp/vln_channel_audit/vln_channel_audit_chXX.png`

Baseline policy used:
- `MASTER_VISIBLE_BASELINE`: `1=200,2=0,3=32,4=0,5=90,6=128,7=128,8=20,9=0,10=0,11=0`
- `SECOND_PATTERN_VISIBLE_BASELINE`: same first-pattern visible state plus
  `4=10,20=32,21=10,22=90,23=128,24=128,25=20,26=0,27=0,28=0`
- `COLOR_EFFECT_BASELINE` / `GRADIENT_BASELINE` and second-pattern equivalents
  were used for speed channels that otherwise appear inactive without the
  required colour/effect mode.

Every audited channel was reset to the appropriate visible baseline before its
own sweep, and a `wall_audit_chXX_baseline.png` frame was captured first. This
prevents false negatives from blacked-out output, wrong mode, disabled colour
effects, or CH4 not enabling the second-pattern channel block.

Channel dependency findings:
- CH9 depends on CH8 being in a colour-effect range.
- CH18 depends on CH8 being in a gradient/effect range.
- CH20-36 depend on CH4>=1 before the second-pattern block is visible.
- CH26 depends on CH25 being in a second-pattern colour-effect range.
- CH35 depends on CH25 being in a second-pattern gradient/effect range.
- CH2 is auto/sound/demo behavior and is not useful for deterministic
  SoundSwitch previz except as a documented skip/defer channel.

High-priority channels for first-pattern previz:
- CH3 pattern/macro family: already atlas-swept; still the main look selector.
- CH4 pattern select / second-pattern enable: changes figures and stacked output.
- CH5 and CH17 size/zoom: strong wall-geometry impact.
- CH6 and CH7 position: strong pan/vertical offset plus blanking at extremes.
- CH8 colour: direct fixed/effect colour control.
- CH11 strobe: show-critical, needs timed capture for real rate/duty.
- CH12, CH15, and CH16: show-critical spin/movement controls, need timed capture.

Timed/burst capture required before tuning:
- CH3 dynamic macro loops.
- CH9 colour chase timing.
- CH11 and CH28 strobe rate/duty.
- CH12-CH16 first-pattern rotations/movement.
- CH17 zoom speed bank.
- CH18 gradient timing.
- CH19 and CH36 wave deformation.
- CH26/CH35 second-pattern colour/gradient timing.
- CH29-CH34 second-pattern rotation/movement/zoom speed banks.

Audit conclusion:
- We are no longer guessing which channels matter. The useful deterministic
  show-previz surface is CH3-19 for the primary pattern plus CH20-36 only when
  CH4 enables stacked second-pattern output.
- Deep calibration should stay focused on first-pattern macro/colour/geometry
  and timed motion first. Second-pattern channels can reuse documented behavior
  until stacked-output looks are needed in actual SoundSwitch cues.
- Laser 2 can continue to reuse the master calibration with mirrored placement
  unless future evidence shows different brightness, colour balance, spread,
  mirror direction, aperture offset, or motion phase.

<!-- TIMED_MOTION_CH1_19_START -->
## Timed Motion CH1-19 Pass

- Report: `/Users/bbui/virtuallasernode/docs/TIMED_MOTION_CH1_19_CALIBRATION.md`
- Motion capture root: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855`
- Master contact sheet: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/timed_motion_ch1_19_master.png`
- Automated quality-flag count: 249
- Scope: CH1-19 only, CH4 included as first-pattern selector, CH20-36 omitted, deterministic CH3 bases only.
- Key result: representative motion timing evidence now exists for CH4-selected first-pattern banks, CH11 strobe, CH12/13/14 rotation sanity, CH15/CH16 movement, CH17 zoom, CH18 gradient timing, CH19 wave, CH8/CH9 color timing, CH5/6/7 position, and deterministic CH1-19 combinations.
- Limitation: CH3-CH19 all need dense breakpoint discovery before renderer tuning; this pass should not be read as complete value-by-value calibration.
<!-- TIMED_MOTION_CH1_19_END -->
