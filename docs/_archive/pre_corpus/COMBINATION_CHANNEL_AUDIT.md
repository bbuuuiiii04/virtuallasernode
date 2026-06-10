# Combination-channel wall audit

**Status:** Historical audit (2026-06-05) — mismatch findings still valid; capture paths superseded  
**Last updated:** 2026-06-10

> **Agent rule:** The **`capture`** column below points at **`calib/captures/wall_combo_*.png`** — pre-corpus stills from **2026-06-05**.  
> **Do not use these PNGs for PR-G shape/motion authority.**  
> For implementation, resolve the **DMX state** column against `captures/fixture_model/manifest.jsonl` and read `still.jpg` + `motion_analysis_60fps/` from the matched `capture_path`.  
> See `calib/README.md`.

Master fixture wall-pattern combination audit using iPhone Continuity Camera device 2, no haze, fixed camera, and left projection as the master ROI.

No renderer behavior, haze/glow/bloom, Laser 2 override, or calibration numbers were changed in this audit.

## Artifacts (historical)

| Artifact | Status |
|----------|--------|
| `/tmp/vln_combo_audit_*.png` | Historical contact sheets (Jun 2026-05) |
| `calib/captures/wall_combo_*.png` | **Superseded** — pre-corpus; see 8k corpus |
| `captures/fixture_model/...` | **Authoritative** for PR-G (vector lookup → still + motion) |

## Scope
- Representative primary CH3 looks: ring/circle, horizontal line, dual-dot, dense dotted arc/swirl, U-wave dynamic, three-star dynamic, compact swirl dynamic, large star/polygon, dotted row/point macro.
- Modifiers tested: fixed color, zoom, position/size offset, spin, horizontal sweep, vertical sweep, strobe, wave, and stacked second-pattern states.
- No concrete SoundSwitch show preset file was found in this repo; `show_*` states below are curated SoundSwitch-style states from the observed fixture behavior, not imported cues.

## Tested Combinations

| label | family | DMX state | visual behavior / purpose | classification | mismatch type | still enough | legacy capture (pre-corpus) | metrics |
|---|---|---|---|---|---|---|---|---|
| ring_cyan | ring/circle | `CH1=200 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs macro-shape preset | shape | yes | `calib/captures/wall_combo_ring_cyan.png` | pixels=106151 bbox=[152, 48, 715, 719] dominant=blue |
| ring_red | ring/circle | `CH1=200 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | static wall-shape calibration ready | color | yes | `calib/captures/wall_combo_ring_red.png` | pixels=18572 bbox=[164, 302, 515, 719] dominant=red |
| ring_zoom | ring/circle | `CH1=200 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | static wall-shape calibration ready | zoom/shape | yes | `calib/captures/wall_combo_ring_zoom.png` | pixels=124964 bbox=[192, 5, 715, 719] dominant=blue |
| ring_offset | ring/circle | `CH1=200 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | static wall-shape calibration ready | position/zoom/shape | yes | `calib/captures/wall_combo_ring_offset.png` | pixels=37330 bbox=[284, 358, 715, 719] dominant=blue |
| line_cyan | horizontal line | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | static wall-shape calibration ready | motion | yes | `calib/captures/wall_combo_line_cyan.png` | pixels=31665 bbox=[156, 281, 535, 719] dominant=blue |
| line_red | horizontal line | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | static wall-shape calibration ready | color | yes | `calib/captures/wall_combo_line_red.png` | pixels=25112 bbox=[158, 400, 531, 719] dominant=red |
| line_zoom | horizontal line | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | static wall-shape calibration ready | zoom/shape | yes | `calib/captures/wall_combo_line_zoom.png` | pixels=32466 bbox=[258, 281, 479, 719] dominant=blue |
| line_offset | horizontal line | `CH1=200 CH3=32 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | static wall-shape calibration ready | position/zoom/shape | yes | `calib/captures/wall_combo_line_offset.png` | pixels=56969 bbox=[282, 174, 715, 719] dominant=blue |
| dual_cyan | dual-dot | `CH1=200 CH3=48 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs macro-shape preset | shape | yes | `calib/captures/wall_combo_dual_cyan.png` | pixels=9515 bbox=[154, 281, 715, 719] dominant=cyan |
| dual_red | dual-dot | `CH1=200 CH3=48 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | static wall-shape calibration ready | color | yes | `calib/captures/wall_combo_dual_red.png` | pixels=4329 bbox=[162, 409, 521, 719] dominant=red |
| dual_zoom | dual-dot | `CH1=200 CH3=48 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | static wall-shape calibration ready | zoom/shape | yes | `calib/captures/wall_combo_dual_zoom.png` | pixels=19046 bbox=[274, 281, 459, 719] dominant=blue |
| dual_offset | dual-dot | `CH1=200 CH3=48 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | static wall-shape calibration ready | position/zoom/shape | yes | `calib/captures/wall_combo_dual_offset.png` | pixels=5210 bbox=[278, 176, 357, 719] dominant=cyan |
| arc_cyan | dense dotted arc/swirl | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs macro-shape preset | shape | yes | `calib/captures/wall_combo_arc_cyan.png` | pixels=21601 bbox=[216, 338, 433, 719] dominant=blue |
| arc_red | dense dotted arc/swirl | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | static wall-shape calibration ready | color | yes | `calib/captures/wall_combo_arc_red.png` | pixels=19261 bbox=[273, 329, 463, 719] dominant=red |
| arc_zoom | dense dotted arc/swirl | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | static wall-shape calibration ready | zoom/shape | yes | `calib/captures/wall_combo_arc_zoom.png` | pixels=21000 bbox=[287, 265, 461, 719] dominant=blue |
| arc_offset | dense dotted arc/swirl | `CH1=200 CH3=96 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | static wall-shape calibration ready | position/zoom/shape | yes | `calib/captures/wall_combo_arc_offset.png` | pixels=27196 bbox=[348, 464, 715, 719] dominant=blue |
| uwave_cyan | U-wave dynamic | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs timed/burst motion capture | motion | no - timed/burst needed | `calib/captures/wall_combo_uwave_cyan.png` | pixels=32942 bbox=[162, 225, 531, 719] dominant=blue |
| uwave_red | U-wave dynamic | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | needs color behavior calibration | color/shape | no - timed/burst needed | `calib/captures/wall_combo_uwave_red.png` | pixels=25195 bbox=[158, 356, 527, 719] dominant=red |
| uwave_zoom | U-wave dynamic | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | needs timed/burst motion capture | zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_uwave_zoom.png` | pixels=37194 bbox=[154, 287, 715, 719] dominant=blue |
| uwave_offset | U-wave dynamic | `CH1=200 CH3=128 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | needs timed/burst motion capture | position/zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_uwave_offset.png` | pixels=0 bbox=[] dominant= |
| star3_cyan | three-star dynamic | `CH1=200 CH3=144 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs timed/burst motion capture | motion | no - timed/burst needed | `calib/captures/wall_combo_star3_cyan.png` | pixels=88070 bbox=[96, 280, 715, 719] dominant=blue |
| star3_red | three-star dynamic | `CH1=200 CH3=144 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | needs color behavior calibration | color/shape | no - timed/burst needed | `calib/captures/wall_combo_star3_red.png` | pixels=26098 bbox=[121, 350, 715, 719] dominant=red |
| star3_zoom | three-star dynamic | `CH1=200 CH3=144 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | needs timed/burst motion capture | zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_star3_zoom.png` | pixels=50784 bbox=[78, 303, 715, 719] dominant=blue |
| star3_offset | three-star dynamic | `CH1=200 CH3=144 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | needs timed/burst motion capture | position/zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_star3_offset.png` | pixels=35129 bbox=[310, 396, 715, 719] dominant=blue |
| swirl_cyan | compact swirl dynamic | `CH1=200 CH3=160 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs timed/burst motion capture | motion | no - timed/burst needed | `calib/captures/wall_combo_swirl_cyan.png` | pixels=23446 bbox=[233, 330, 441, 719] dominant=blue |
| swirl_red | compact swirl dynamic | `CH1=200 CH3=160 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | needs color behavior calibration | color/shape | no - timed/burst needed | `calib/captures/wall_combo_swirl_red.png` | pixels=22310 bbox=[268, 329, 471, 719] dominant=red |
| swirl_zoom | compact swirl dynamic | `CH1=200 CH3=160 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | needs timed/burst motion capture | zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_swirl_zoom.png` | pixels=27852 bbox=[267, 266, 489, 719] dominant=blue |
| swirl_offset | compact swirl dynamic | `CH1=200 CH3=160 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | needs timed/burst motion capture | position/zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_swirl_offset.png` | pixels=58367 bbox=[340, 416, 715, 719] dominant=blue |
| poly_cyan | large star/polygon | `CH1=200 CH3=176 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs macro-shape preset | shape | no - timed/burst needed | `calib/captures/wall_combo_poly_cyan.png` | pixels=40578 bbox=[188, 304, 521, 719] dominant=blue |
| poly_red | large star/polygon | `CH1=200 CH3=176 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | needs color behavior calibration | color/shape | no - timed/burst needed | `calib/captures/wall_combo_poly_red.png` | pixels=30953 bbox=[202, 320, 509, 719] dominant=red |
| poly_zoom | large star/polygon | `CH1=200 CH3=176 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | needs timed/burst motion capture | zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_poly_zoom.png` | pixels=40851 bbox=[214, 321, 493, 719] dominant=blue |
| poly_offset | large star/polygon | `CH1=200 CH3=176 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | needs timed/burst motion capture | position/zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_poly_offset.png` | pixels=42678 bbox=[316, 395, 715, 719] dominant=blue |
| row_cyan | dotted row/point macro | `CH1=200 CH3=200 CH5=90 CH6=128 CH7=128 CH8=20` | representative cyan base look | needs macro-shape preset | shape | no - timed/burst needed | `calib/captures/wall_combo_row_cyan.png` | pixels=43443 bbox=[178, 269, 515, 719] dominant=blue |
| row_red | dotted row/point macro | `CH1=200 CH3=200 CH5=90 CH6=128 CH7=128 CH8=8` | same look with fixed red color | needs color behavior calibration | color/shape | no - timed/burst needed | `calib/captures/wall_combo_row_red.png` | pixels=14986 bbox=[154, 621, 509, 678] dominant=red |
| row_zoom | dotted row/point macro | `CH1=200 CH3=200 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | zoom/size interaction | needs timed/burst motion capture | zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_row_zoom.png` | pixels=46557 bbox=[157, 302, 715, 719] dominant=blue |
| row_offset | dotted row/point macro | `CH1=200 CH3=200 CH5=70 CH6=96 CH7=160 CH8=20` | position and size interaction | needs timed/burst motion capture | position/zoom/shape | no - timed/burst needed | `calib/captures/wall_combo_row_offset.png` | pixels=122727 bbox=[272, 266, 715, 719] dominant=blue |
| line_spin | motion/show modifier | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH12=150` | spin speed/pose interaction | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_line_spin.png` | pixels=50306 bbox=[165, 317, 715, 719] dominant=blue |
| line_hsweep | motion/show modifier | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH15=200` | horizontal sweep interaction | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_line_hsweep.png` | pixels=0 bbox=[] dominant= |
| line_vsweep | motion/show modifier | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH16=200` | vertical sweep interaction | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_line_vsweep.png` | pixels=0 bbox=[] dominant= |
| line_strobe | motion/show modifier | `CH1=220 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH11=150` | strobe interaction | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_line_strobe.png` | pixels=325647 bbox=[98, 4, 715, 719] dominant=blue |
| arc_spin | motion/show modifier | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH12=150` | spin on dense dotted arc | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_arc_spin.png` | pixels=26179 bbox=[214, 355, 448, 719] dominant=blue |
| arc_hsweep | motion/show modifier | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH15=200` | horizontal sweep on dotted arc | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_arc_hsweep.png` | pixels=0 bbox=[] dominant= |
| arc_vsweep | motion/show modifier | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH16=200` | vertical sweep on dotted arc | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_arc_vsweep.png` | pixels=0 bbox=[] dominant= |
| arc_wave | motion/show modifier | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH19=200` | wave deformation on dotted arc | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_arc_wave.png` | pixels=28028 bbox=[266, 323, 479, 719] dominant=blue |
| dyn160_spin | motion/show modifier | `CH1=200 CH3=160 CH5=90 CH6=128 CH7=128 CH8=20 CH12=150` | dynamic macro plus spin channel | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_dyn160_spin.png` | pixels=26983 bbox=[269, 384, 485, 719] dominant=blue |
| dyn176_strobe | motion/show modifier | `CH1=220 CH3=176 CH5=90 CH6=128 CH7=128 CH8=20 CH11=150` | dynamic macro plus strobe | needs timed/burst motion capture | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_dyn176_strobe.png` | pixels=333569 bbox=[134, 3, 715, 719] dominant=blue |
| stack_line_arc | stacked output | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=10 CH22=90 CH23=128 CH24=128 CH25=8` | primary cyan line plus red second pattern | needs stacked-pattern support | stacked pattern | yes | `calib/captures/wall_combo_stack_line_arc.png` | pixels=50830 bbox=[162, 282, 715, 719] dominant=blue |
| stack_ring_line | stacked output | `CH1=200 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=60 CH22=90 CH23=128 CH24=128 CH25=28` | cyan ring plus magenta second line selection | needs stacked-pattern support | stacked pattern | yes | `calib/captures/wall_combo_stack_ring_line.png` | pixels=69023 bbox=[148, 281, 715, 719] dominant=blue |
| stack_arc_dot | stacked output | `CH1=200 CH3=96 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=64 CH21=20 CH22=70 CH23=128 CH24=128 CH25=20` | dotted arc plus smaller second pattern | needs stacked-pattern support | stacked pattern | yes | `calib/captures/wall_combo_stack_arc_dot.png` | pixels=21812 bbox=[224, 296, 409, 719] dominant=blue |
| stack_dyn_static | stacked output | `CH1=200 CH3=160 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=10 CH22=90 CH23=128 CH24=128 CH25=8` | dynamic primary plus static second pattern | needs timed/burst motion capture | stacked pattern/motion | no - timed/burst needed | `calib/captures/wall_combo_stack_dyn_static.png` | pixels=25909 bbox=[250, 350, 466, 719] dominant=blue |
| stack_offset | stacked output | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=96 CH7=160 CH8=20 CH20=32 CH21=10 CH22=90 CH23=192 CH24=64 CH25=8` | opposed primary/second positions | needs stacked-pattern support | stacked pattern | yes | `calib/captures/wall_combo_stack_offset.png` | pixels=17119 bbox=[147, 174, 715, 719] dominant=blue |
| stack_second_spin | stacked output | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=10 CH22=90 CH23=128 CH24=128 CH25=20 CH29=150` | second-pattern rotation speed | needs timed/burst motion capture | stacked pattern/motion | no - timed/burst needed | `calib/captures/wall_combo_stack_second_spin.png` | pixels=44430 bbox=[163, 351, 715, 719] dominant=blue |
| stack_second_sweep | stacked output | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=10 CH22=90 CH23=128 CH24=128 CH25=20 CH32=200` | second-pattern horizontal sweep | needs timed/burst motion capture | stacked pattern/motion | no - timed/burst needed | `calib/captures/wall_combo_stack_second_sweep.png` | pixels=33228 bbox=[158, 281, 715, 719] dominant=blue |
| stack_second_zoom | stacked output | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=10 CH22=210 CH23=128 CH24=128 CH25=20 CH34=100` | second-pattern size/zoom interaction | needs timed/burst motion capture | stacked pattern/motion | no - timed/burst needed | `calib/captures/wall_combo_stack_second_zoom.png` | pixels=43035 bbox=[158, 281, 527, 719] dominant=blue |
| show_build_cyan_wide | curated SoundSwitch-style state | `CH1=200 CH3=32 CH4=10 CH5=70 CH6=128 CH7=128 CH8=20 CH17=80` | build-up wide cyan fan | static wall-shape calibration ready | shape/stacked pattern | yes | `calib/captures/wall_combo_show_build_cyan_wide.png` | pixels=41534 bbox=[248, 281, 497, 719] dominant=blue |
| show_drop_magenta_spin | curated SoundSwitch-style state | `CH1=200 CH3=96 CH4=10 CH5=90 CH6=128 CH7=128 CH8=28 CH12=150` | drop-impact magenta spin | used in SoundSwitch show, high priority | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_show_drop_magenta_spin.png` | pixels=31102 bbox=[264, 284, 715, 719] dominant=blue |
| show_drop_red_strobe | curated SoundSwitch-style state | `CH1=230 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=8 CH11=150` | drop-impact red strobe | used in SoundSwitch show, high priority | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_show_drop_red_strobe.png` | pixels=27703 bbox=[176, 382, 543, 719] dominant=red |
| show_sweep_cyan | curated SoundSwitch-style state | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH15=200` | cyan horizontal sweep | used in SoundSwitch show, high priority | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_show_sweep_cyan.png` | pixels=0 bbox=[] dominant= |
| show_dynamic_pink | curated SoundSwitch-style state | `CH1=200 CH3=160 CH4=10 CH5=90 CH6=128 CH7=128 CH8=8` | dynamic pink/red compact swirl | used in SoundSwitch show, high priority | motion/strobe/shape | no - timed/burst needed | `calib/captures/wall_combo_show_dynamic_pink.png` | pixels=17910 bbox=[250, 346, 425, 719] dominant=red |
| show_stack_contrast | curated SoundSwitch-style state | `CH1=200 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH20=32 CH21=10 CH23=192 CH25=8` | cyan primary plus red offset second layer | static wall-shape calibration ready | shape/stacked pattern | yes | `calib/captures/wall_combo_show_stack_contrast.png` | pixels=28048 bbox=[159, 282, 531, 719] dominant=blue |

## Discovered Interaction Patterns

- Static CH3 families keep responding to CH8 fixed colours, CH17 zoom, and CH5/CH6/CH7 wall geometry modifiers.
- Dynamic CH3 families identify distinct macro shapes in still frames, but their loop timing, colour phase, and whether modifier channels are ignored or blended need timed evidence.
- CH11 strobe can only be sampled as an on/off still phase; rate and duty need burst capture.
- CH12, CH15, and CH16 produce show-important motion states, but still frames only identify the visual family and sampled phase.
- CH4-enabled stacked states add a second projected pattern block; this is a separate renderer capability concern from simple first-pattern geometry.
- Second-pattern motion channels matter only after CH4 enables stacked output.

## Mismatch Ranking

1. Renderer model mismatch: the physical wall evidence is mostly closed projected figures, dots, rows, waves, and small shape clusters; the current virtual render is still an aerial beam-fan model from two apertures.
2. Macro-shape mismatch: CH3 representative looks need calibrated shape presets before fine geometry tuning will be meaningful.
3. Stacked-output mismatch: CH4 plus CH20-36 produces a second pattern block that needs explicit support independent of first-pattern geometry.
4. Motion-phase ambiguity: CH12, CH15, CH16, dynamic CH3 macros, strobe, and second-pattern motion channels cannot be tuned from single still frames.
5. Position/blanking mismatch: CH5/CH6/CH7 and sweep channels can move sampled frames partially or fully out of the master ROI; zero-pixel stills are sampled phase evidence, not proof of no output.
6. Zoom mismatch: CH17 and CH34 visibly alter wall scale, but the current virtual fan zoom does not map cleanly to wall-projected figure scale.
7. Dynamic color mismatch: fixed CH8 red/cyan states are identifiable, but dynamic/chase timing and color phase still need timed capture.

## Channels And Combinations That Matter Most

- First-pattern show looks: CH3 + CH8 + CH5/CH6/CH7 + CH17.
- First-pattern motion looks: CH3 + CH12/CH15/CH16, plus CH11 for strobe.
- Dynamic/drop looks: CH3 values 128-255 with CH8 fixed/effect color and optional CH12/CH11.
- Stacked looks: CH4 enabled with CH20/CH21/CH22/CH23/CH24/CH25, then CH29/CH32/CH34 only when second-pattern motion/size is needed.
- Low-value/defer in this pass: auto/sound/demo behavior, haze/glow/bloom, and exhaustive second-pattern tuning.

## High-priority SoundSwitch-style States

- `line_cyan`: `1=200 2=0 3=32 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0` - representative cyan base look
- `line_red`: `1=200 2=0 3=32 4=0 5=90 6=128 7=128 8=8 9=0 10=0 11=0` - same look with fixed red color
- `arc_cyan`: `1=200 2=0 3=96 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0` - representative cyan base look
- `swirl_cyan`: `1=200 2=0 3=160 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0` - representative cyan base look
- `swirl_red`: `1=200 2=0 3=160 4=0 5=90 6=128 7=128 8=8 9=0 10=0 11=0` - same look with fixed red color
- `poly_cyan`: `1=200 2=0 3=176 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0` - representative cyan base look
- `poly_red`: `1=200 2=0 3=176 4=0 5=90 6=128 7=128 8=8 9=0 10=0 11=0` - same look with fixed red color
- `row_cyan`: `1=200 2=0 3=200 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0` - representative cyan base look
- `line_spin`: `1=200 2=0 3=32 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 12=150` - spin speed/pose interaction
- `line_hsweep`: `1=200 2=0 3=32 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 15=200` - horizontal sweep interaction
- `line_vsweep`: `1=200 2=0 3=32 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 16=200` - vertical sweep interaction
- `line_strobe`: `1=220 2=0 3=32 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=150` - strobe interaction
- `arc_spin`: `1=200 2=0 3=96 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 12=150` - spin on dense dotted arc
- `arc_hsweep`: `1=200 2=0 3=96 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 15=200` - horizontal sweep on dotted arc
- `arc_vsweep`: `1=200 2=0 3=96 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 16=200` - vertical sweep on dotted arc
- `arc_wave`: `1=200 2=0 3=96 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 19=200` - wave deformation on dotted arc
- `dyn160_spin`: `1=200 2=0 3=160 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=0 12=150` - dynamic macro plus spin channel
- `dyn176_strobe`: `1=220 2=0 3=176 4=0 5=90 6=128 7=128 8=20 9=0 10=0 11=150` - dynamic macro plus strobe
- `stack_line_arc`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=8 26=0 27=0 28=0` - primary cyan line plus red second pattern
- `stack_ring_line`: `1=200 2=0 3=0 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=60 22=90 23=128 24=128 25=28 26=0 27=0 28=0` - cyan ring plus magenta second line selection
- `stack_arc_dot`: `1=200 2=0 3=96 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=64 21=20 22=70 23=128 24=128 25=20 26=0 27=0 28=0` - dotted arc plus smaller second pattern
- `stack_dyn_static`: `1=200 2=0 3=160 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=8 26=0 27=0 28=0` - dynamic primary plus static second pattern
- `stack_offset`: `1=200 2=0 3=32 4=10 5=90 6=96 7=160 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=192 24=64 25=8 26=0 27=0 28=0` - opposed primary/second positions
- `stack_second_spin`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=20 26=0 27=0 28=0 29=150` - second-pattern rotation speed
- `stack_second_sweep`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=20 26=0 27=0 28=0 32=200` - second-pattern horizontal sweep
- `stack_second_zoom`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=210 23=128 24=128 25=20 26=0 27=0 28=0 34=100` - second-pattern size/zoom interaction
- `show_build_cyan_wide`: `1=200 2=0 3=32 4=10 5=70 6=128 7=128 8=20 9=0 10=0 11=0 17=80` - build-up wide cyan fan
- `show_drop_magenta_spin`: `1=200 2=0 3=96 4=10 5=90 6=128 7=128 8=28 9=0 10=0 11=0 12=150` - drop-impact magenta spin
- `show_drop_red_strobe`: `1=230 2=0 3=32 4=10 5=90 6=128 7=128 8=8 9=0 10=0 11=150` - drop-impact red strobe
- `show_sweep_cyan`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 15=200` - cyan horizontal sweep
- `show_dynamic_pink`: `1=200 2=0 3=160 4=10 5=90 6=128 7=128 8=8 9=0 10=0 11=0` - dynamic pink/red compact swirl
- `show_stack_contrast`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 23=192 25=8` - cyan primary plus red offset second layer

## Timed/Burst Capture Required

- `uwave_cyan`: representative cyan base look (motion)
- `uwave_red`: same look with fixed red color (color/shape)
- `uwave_zoom`: zoom/size interaction (zoom/shape)
- `uwave_offset`: position and size interaction (position/zoom/shape)
- `star3_cyan`: representative cyan base look (motion)
- `star3_red`: same look with fixed red color (color/shape)
- `star3_zoom`: zoom/size interaction (zoom/shape)
- `star3_offset`: position and size interaction (position/zoom/shape)
- `swirl_cyan`: representative cyan base look (motion)
- `swirl_red`: same look with fixed red color (color/shape)
- `swirl_zoom`: zoom/size interaction (zoom/shape)
- `swirl_offset`: position and size interaction (position/zoom/shape)
- `poly_cyan`: representative cyan base look (shape)
- `poly_red`: same look with fixed red color (color/shape)
- `poly_zoom`: zoom/size interaction (zoom/shape)
- `poly_offset`: position and size interaction (position/zoom/shape)
- `row_cyan`: representative cyan base look (shape)
- `row_red`: same look with fixed red color (color/shape)
- `row_zoom`: zoom/size interaction (zoom/shape)
- `row_offset`: position and size interaction (position/zoom/shape)
- `line_spin`: spin speed/pose interaction (motion/strobe/shape)
- `line_hsweep`: horizontal sweep interaction (motion/strobe/shape)
- `line_vsweep`: vertical sweep interaction (motion/strobe/shape)
- `line_strobe`: strobe interaction (motion/strobe/shape)
- `arc_spin`: spin on dense dotted arc (motion/strobe/shape)
- `arc_hsweep`: horizontal sweep on dotted arc (motion/strobe/shape)
- `arc_vsweep`: vertical sweep on dotted arc (motion/strobe/shape)
- `arc_wave`: wave deformation on dotted arc (motion/strobe/shape)
- `dyn160_spin`: dynamic macro plus spin channel (motion/strobe/shape)
- `dyn176_strobe`: dynamic macro plus strobe (motion/strobe/shape)
- `stack_dyn_static`: dynamic primary plus static second pattern (stacked pattern/motion)
- `stack_second_spin`: second-pattern rotation speed (stacked pattern/motion)
- `stack_second_sweep`: second-pattern horizontal sweep (stacked pattern/motion)
- `stack_second_zoom`: second-pattern size/zoom interaction (stacked pattern/motion)
- `show_drop_magenta_spin`: drop-impact magenta spin (motion/strobe/shape)
- `show_drop_red_strobe`: drop-impact red strobe (motion/strobe/shape)
- `show_sweep_cyan`: cyan horizontal sweep (motion/strobe/shape)
- `show_dynamic_pink`: dynamic pink/red compact swirl (motion/strobe/shape)

## Stacked-output States

- `stack_line_arc`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=8 26=0 27=0 28=0` - primary cyan line plus red second pattern
- `stack_ring_line`: `1=200 2=0 3=0 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=60 22=90 23=128 24=128 25=28 26=0 27=0 28=0` - cyan ring plus magenta second line selection
- `stack_arc_dot`: `1=200 2=0 3=96 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=64 21=20 22=70 23=128 24=128 25=20 26=0 27=0 28=0` - dotted arc plus smaller second pattern
- `stack_dyn_static`: `1=200 2=0 3=160 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=8 26=0 27=0 28=0` - dynamic primary plus static second pattern
- `stack_offset`: `1=200 2=0 3=32 4=10 5=90 6=96 7=160 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=192 24=64 25=8 26=0 27=0 28=0` - opposed primary/second positions
- `stack_second_spin`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=20 26=0 27=0 28=0 29=150` - second-pattern rotation speed
- `stack_second_sweep`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=90 23=128 24=128 25=20 26=0 27=0 28=0 32=200` - second-pattern horizontal sweep
- `stack_second_zoom`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 22=210 23=128 24=128 25=20 26=0 27=0 28=0 34=100` - second-pattern size/zoom interaction
- `show_stack_contrast`: `1=200 2=0 3=32 4=10 5=90 6=128 7=128 8=20 9=0 10=0 11=0 20=32 21=10 23=192 25=8` - cyan primary plus red offset second layer

## Recommended Next Step

Do a timed/burst motion pass for a small subset instead of changing renderer constants from stills:

1. `line_spin`, `line_hsweep`, `line_vsweep`, and `line_strobe` for first-pattern motion/strobe timing.
2. `dyn160_spin` and `show_dynamic_pink` for dynamic macro loop and colour phase behavior.
3. `stack_second_spin` and `stack_second_sweep` for CH4-enabled stacked-output motion.

After timed evidence exists, implement calibrated preset families for the highest-priority show-style states rather than adding broad renderer art changes.
