# Timed motion calibration CH1-19

Evidence-only timed/burst pass for one master fixture using wall projection, no haze, iPhone Continuity Camera device 2, and deterministic first-pattern CH3 bases only.

No renderer behavior, calibration.json values, CH20-36 channels, or second-pattern behavior were changed or used in this pass. CH4 is included only as the first-pattern program selector inside deterministic CH3 banks.

Important scope note: this is a broad timed-motion scaffold, not a dense breakpoint atlas. The fixture manual and live observations show that CH3 through CH19 can contain fine internal value ranges and sub-looks. Treat these captures as representative timing/interaction evidence; do not treat unsampled values as calibrated.

## Artifacts
- Motion capture root: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855`
- Organized capture bundles: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/captures`
- Manifest/log: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/manifest.jsonl`
- Analysis manifest: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/analysis_manifest.jsonl`
- Master contact sheet: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/timed_motion_ch1_19_master.png`
- CH4 first-pattern bank selection: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch04_pattern_select.png`
- CH11 strobe: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch11_strobe.png`
- CH12 spin: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch12_spin.png`
- CH15 horizontal sweep: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch15_hsweep.png`
- CH16 vertical sweep: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch16_vsweep.png`
- CH17 zoom: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch17_zoom.png`
- CH18 gradient: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch18_gradient.png`
- CH19 wave: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch19_wave.png`
- CH8 color timing: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch08_color.png`
- CH5/CH6/CH7 position offset: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch05_06_07_position.png`
- CH13 rotation X sanity: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch13_rot_x.png`
- CH14 rotation Y sanity: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/ch14_rot_y.png`
- CH1-19 deterministic combinations: `/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855/contact_sheets/combos_ch1_19.png`

## Baselines
- `ring`: CH1=200 CH2=0 CH3=0 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0
- `line`: CH1=200 CH2=0 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0
- `dual`: CH1=200 CH2=0 CH3=48 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0
- `arc`: CH1=200 CH2=0 CH3=96 CH4=20 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0
- `line_ch4_60` and `arc_ch4_60`: alternate CH4 bank representatives used to check that motion behavior is not unique to one CH4-selected figure.

## Captured States

| test_id | group | baseline | changed CH | duration | motion | loop | strobe Hz | quality | renderer support | priority |
|---|---|---|---|---:|---|---:|---:|---|---|---|
| `ctrl_static_ring` | controls | ring | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ctrl_static_line` | controls | line | `none` | 5.0 | static | 1.833 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ctrl_static_dual` | controls | dual | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ctrl_static_arc` | controls | arc | `none` | 5.0 | smooth rotation | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ctrl_blackout` | controls | line | `CH1=0` | 5.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | medium |
| `ctrl_no_strobe_line` | controls | line | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ctrl_no_spin_line` | controls | line | `none` | 5.0 | static | 0.833 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ctrl_no_sweep_wave_line` | controls | line | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch04_pattern_select_ring_ch04_000` | ch04_pattern_select | ring | `CH4=0` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_001` | ch04_pattern_select | ring | `CH4=1` | 5.0 | static | 2.25 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_005` | ch04_pattern_select | ring | `CH4=5` | 5.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_010` | ch04_pattern_select | ring | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_020` | ch04_pattern_select | ring | `CH4=20` | 5.0 | smooth rotation | 0.833 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_060` | ch04_pattern_select | ring | `CH4=60` | 5.0 | static | 1.667 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_100` | ch04_pattern_select | ring | `CH4=100` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_ring_ch04_130` | ch04_pattern_select | ring | `CH4=130` | 5.0 | smooth rotation | 0.75 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_000` | ch04_pattern_select | line | `CH4=0` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_001` | ch04_pattern_select | line | `CH4=1` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_005` | ch04_pattern_select | line | `CH4=5` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_010` | ch04_pattern_select | line | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_020` | ch04_pattern_select | line | `CH4=20` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_060` | ch04_pattern_select | line | `CH4=60` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_100` | ch04_pattern_select | line | `CH4=100` | 5.0 | static | 0.917 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_line_ch04_130` | ch04_pattern_select | line | `CH4=130` | 5.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_000` | ch04_pattern_select | dual | `CH4=0` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_001` | ch04_pattern_select | dual | `CH4=1` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_005` | ch04_pattern_select | dual | `CH4=5` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_010` | ch04_pattern_select | dual | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_020` | ch04_pattern_select | dual | `CH4=20` | 5.0 | static | 0.833 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_060` | ch04_pattern_select | dual | `CH4=60` | 5.0 | static | 0.917 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_100` | ch04_pattern_select | dual | `CH4=100` | 5.0 | smooth rotation | 0.833 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_dual_ch04_130` | ch04_pattern_select | dual | `CH4=130` | 5.0 | brightness pulse | 0.5 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch04_pattern_select_arc_ch04_000` | ch04_pattern_select | arc | `CH4=0` | 5.0 | smooth rotation | 1.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_001` | ch04_pattern_select | arc | `CH4=1` | 5.0 | smooth rotation | 1.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_005` | ch04_pattern_select | arc | `CH4=5` | 5.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_010` | ch04_pattern_select | arc | `CH4=10` | 5.0 | smooth rotation | 0.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_020` | ch04_pattern_select | arc | `none` | 5.0 | static | 1.167 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_060` | ch04_pattern_select | arc | `CH4=60` | 5.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_100` | ch04_pattern_select | arc | `CH4=100` | 5.0 | static | 0.667 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch04_pattern_select_arc_ch04_130` | ch04_pattern_select | arc | `CH4=130` | 5.0 | smooth rotation | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_000` | ch11_strobe | line | `none` | 8.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_001` | ch11_strobe | line | `CH11=1` | 8.0 | strobe gate | 2.833 | 0.312 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_016` | ch11_strobe | line | `CH11=16` | 8.0 | strobe gate | 2.5 | 0.375 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_032` | ch11_strobe | line | `CH11=32` | 8.0 | strobe gate | 2.167 | 0.438 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_048` | ch11_strobe | line | `CH11=48` | 8.0 | strobe gate | 1.833 | 0.5 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_064` | ch11_strobe | line | `CH11=64` | 8.0 | strobe gate | 1.417 | 0.688 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_096` | ch11_strobe | line | `CH11=96` | 8.0 | strobe gate | 0.833 | 1.188 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_128` | ch11_strobe | line | `CH11=128` | 8.0 | strobe gate | 0.583 | 1.75 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_160` | ch11_strobe | line | `CH11=160` | 8.0 | strobe gate | 0.417 | 2.312 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_192` | ch11_strobe | line | `CH11=192` | 8.0 | strobe gate | 0.833 | 3.5 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_224` | ch11_strobe | line | `CH11=224` | 8.0 | strobe gate | 1.0 | 4.25 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_line_ch11_255` | ch11_strobe | line | `CH11=255` | 8.0 | strobe gate | 1.5 | 2.375 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_ring_ch11_128` | ch11_strobe | ring | `CH11=128` | 8.0 | strobe gate | 0.583 | 1.75 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_ring_ch11_200` | ch11_strobe | ring | `CH11=200` | 8.0 | strobe gate | 0.583 | 3.5 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_dual_ch11_128` | ch11_strobe | dual | `CH11=128` | 8.0 | strobe gate | 0.583 | 1.75 | nonblank, clipped, not overexposed | partially supported | high |
| `ch11_strobe_arc_ch11_128` | ch11_strobe | arc | `CH11=128` | 8.0 | strobe gate | 0.583 | 1.688 | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_000` | ch12_spin | line | `none` | 6.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_001` | ch12_spin | line | `CH12=1` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_032` | ch12_spin | line | `CH12=32` | 6.0 | static | 0.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_064` | ch12_spin | line | `CH12=64` | 6.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_096` | ch12_spin | line | `CH12=96` | 6.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_127` | ch12_spin | line | `CH12=127` | 6.0 | static | 2.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_128` | ch12_spin | line | `CH12=128` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_136` | ch12_spin | line | `CH12=136` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_144` | ch12_spin | line | `CH12=144` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_152` | ch12_spin | line | `CH12=152` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_160` | ch12_spin | line | `CH12=160` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_176` | ch12_spin | line | `CH12=176` | 8.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch12_spin_line_ch12_192` | ch12_spin | line | `CH12=192` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_208` | ch12_spin | line | `CH12=208` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_224` | ch12_spin | line | `CH12=224` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_240` | ch12_spin | line | `CH12=240` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch12_255` | ch12_spin | line | `CH12=255` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_ring_ch12_150` | ch12_spin | ring | `CH12=150` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_ring_ch12_220` | ch12_spin | ring | `CH12=220` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_dual_ch12_150` | ch12_spin | dual | `CH12=150` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_arc_ch12_150` | ch12_spin | arc | `CH12=150` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_arc_ch12_220` | ch12_spin | arc | `CH12=220` | 8.0 | smooth rotation | 0.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_line_ch4_60_ch12_150` | ch12_spin | line_ch4_60 | `CH12=150` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch12_spin_arc_ch4_60_ch12_150` | ch12_spin | arc_ch4_60 | `CH12=150` | 8.0 | brightness pulse | None | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch13_rot_x_line_ch13_000` | ch13_rot_x | line | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_001` | ch13_rot_x | line | `CH13=1` | 5.0 | static | 0.833 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_032` | ch13_rot_x | line | `CH13=32` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_064` | ch13_rot_x | line | `CH13=64` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_096` | ch13_rot_x | line | `CH13=96` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_127` | ch13_rot_x | line | `CH13=127` | 5.0 | static | 0.417 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_128` | ch13_rot_x | line | `CH13=128` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_160` | ch13_rot_x | line | `CH13=160` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_192` | ch13_rot_x | line | `CH13=192` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_224` | ch13_rot_x | line | `CH13=224` | 6.0 | smooth rotation | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch13_rot_x_line_ch13_255` | ch13_rot_x | line | `CH13=255` | 6.0 | static | 2.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_000` | ch14_rot_y | line | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_001` | ch14_rot_y | line | `CH14=1` | 5.0 | static | 2.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_032` | ch14_rot_y | line | `CH14=32` | 5.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_064` | ch14_rot_y | line | `CH14=64` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_096` | ch14_rot_y | line | `CH14=96` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_127` | ch14_rot_y | line | `CH14=127` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_128` | ch14_rot_y | line | `CH14=128` | 6.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_160` | ch14_rot_y | line | `CH14=160` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_192` | ch14_rot_y | line | `CH14=192` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_224` | ch14_rot_y | line | `CH14=224` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch14_rot_y_line_ch14_255` | ch14_rot_y | line | `CH14=255` | 6.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch15_hsweep_line_ch15_000` | ch15_hsweep | line | `none` | 5.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch15_hsweep_line_ch15_001` | ch15_hsweep | line | `CH15=1` | 5.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch15_hsweep_line_ch15_032` | ch15_hsweep | line | `CH15=32` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_064` | ch15_hsweep | line | `CH15=64` | 5.0 | static | 0.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_096` | ch15_hsweep | line | `CH15=96` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_127` | ch15_hsweep | line | `CH15=127` | 5.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch15_hsweep_line_ch15_128` | ch15_hsweep | line | `CH15=128` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_136` | ch15_hsweep | line | `CH15=136` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_144` | ch15_hsweep | line | `CH15=144` | 10.0 | horizontal sweep | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_152` | ch15_hsweep | line | `CH15=152` | 10.0 | smooth rotation | 1.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_160` | ch15_hsweep | line | `CH15=160` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_176` | ch15_hsweep | line | `CH15=176` | 10.0 | smooth rotation | 4.25 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_192` | ch15_hsweep | line | `CH15=192` | 10.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch15_hsweep_line_ch15_208` | ch15_hsweep | line | `CH15=208` | 10.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch15_hsweep_line_ch15_224` | ch15_hsweep | line | `CH15=224` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_240` | ch15_hsweep | line | `CH15=240` | 10.0 | smooth rotation | 2.083 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch15_255` | ch15_hsweep | line | `CH15=255` | 10.0 | smooth rotation | 0.417 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_ring_ch15_200` | ch15_hsweep | ring | `CH15=200` | 10.0 | unknown/needs recapture | 0.333 | None | blank, clipped, not overexposed | unknown/needs evidence | high |
| `ch15_hsweep_dual_ch15_200` | ch15_hsweep | dual | `CH15=200` | 10.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch15_hsweep_arc_ch15_200` | ch15_hsweep | arc | `CH15=200` | 10.0 | smooth rotation | 0.833 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_line_ch4_60_ch15_200` | ch15_hsweep | line_ch4_60 | `CH15=200` | 10.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch15_hsweep_arc_ch4_60_ch15_200` | ch15_hsweep | arc_ch4_60 | `CH15=200` | 10.0 | smooth rotation | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_000` | ch16_vsweep | line | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_001` | ch16_vsweep | line | `CH16=1` | 5.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch16_vsweep_line_ch16_032` | ch16_vsweep | line | `CH16=32` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_064` | ch16_vsweep | line | `CH16=64` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_096` | ch16_vsweep | line | `CH16=96` | 5.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch16_vsweep_line_ch16_127` | ch16_vsweep | line | `CH16=127` | 5.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch16_vsweep_line_ch16_128` | ch16_vsweep | line | `CH16=128` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_136` | ch16_vsweep | line | `CH16=136` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_144` | ch16_vsweep | line | `CH16=144` | 10.0 | vertical sweep | 4.25 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_152` | ch16_vsweep | line | `CH16=152` | 10.0 | smooth rotation | 2.833 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_160` | ch16_vsweep | line | `CH16=160` | 10.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_176` | ch16_vsweep | line | `CH16=176` | 10.0 | smooth rotation | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_192` | ch16_vsweep | line | `CH16=192` | 10.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch16_vsweep_line_ch16_208` | ch16_vsweep | line | `CH16=208` | 10.0 | brightness pulse | 4.25 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch16_vsweep_line_ch16_224` | ch16_vsweep | line | `CH16=224` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_240` | ch16_vsweep | line | `CH16=240` | 10.0 | vertical sweep | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_line_ch16_255` | ch16_vsweep | line | `CH16=255` | 10.0 | vertical sweep | 0.917 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_ring_ch16_200` | ch16_vsweep | ring | `CH16=200` | 10.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch16_vsweep_dual_ch16_200` | ch16_vsweep | dual | `CH16=200` | 10.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `ch16_vsweep_arc_ch16_200` | ch16_vsweep | arc | `CH16=200` | 10.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch16_vsweep_line_ch4_60_ch16_200` | ch16_vsweep | line_ch4_60 | `CH16=200` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch16_vsweep_arc_ch4_60_ch16_200` | ch16_vsweep | arc_ch4_60 | `CH16=200` | 10.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_000` | ch17_zoom | line | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_001` | ch17_zoom | line | `CH17=1` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_032` | ch17_zoom | line | `CH17=32` | 5.0 | static | 1.0 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_064` | ch17_zoom | line | `CH17=64` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_096` | ch17_zoom | line | `CH17=96` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_127` | ch17_zoom | line | `CH17=127` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_128` | ch17_zoom | line | `CH17=128` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_136` | ch17_zoom | line | `CH17=136` | 10.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_144` | ch17_zoom | line | `CH17=144` | 10.0 | static | 1.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_152` | ch17_zoom | line | `CH17=152` | 10.0 | pulse zoom | 0.917 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch17_zoom_line_ch17_160` | ch17_zoom | line | `CH17=160` | 10.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_176` | ch17_zoom | line | `CH17=176` | 10.0 | smooth rotation | 1.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_192` | ch17_zoom | line | `CH17=192` | 10.0 | pulse zoom | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch17_zoom_line_ch17_208` | ch17_zoom | line | `CH17=208` | 10.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_line_ch17_224` | ch17_zoom | line | `CH17=224` | 10.0 | pulse zoom | None | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch17_zoom_line_ch17_240` | ch17_zoom | line | `CH17=240` | 10.0 | pulse zoom | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch17_zoom_line_ch17_255` | ch17_zoom | line | `CH17=255` | 10.0 | pulse zoom | 1.083 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch17_zoom_ring_ch17_080` | ch17_zoom | ring | `CH17=80` | 8.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_ring_ch17_200` | ch17_zoom | ring | `CH17=200` | 8.0 | pulse zoom | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `ch17_zoom_dual_ch17_080` | ch17_zoom | dual | `CH17=80` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch17_zoom_arc_ch17_080` | ch17_zoom | arc | `CH17=80` | 8.0 | smooth rotation | 2.0 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch19_wave_line_ch19_000` | ch19_wave | line | `none` | 10.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_001` | ch19_wave | line | `CH19=1` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_032` | ch19_wave | line | `CH19=32` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_064` | ch19_wave | line | `CH19=64` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_096` | ch19_wave | line | `CH19=96` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_127` | ch19_wave | line | `CH19=127` | 10.0 | smooth rotation | 0.5 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_128` | ch19_wave | line | `CH19=128` | 10.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_136` | ch19_wave | line | `CH19=136` | 10.0 | wave/deformation | 2.083 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch19_wave_line_ch19_144` | ch19_wave | line | `CH19=144` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_152` | ch19_wave | line | `CH19=152` | 10.0 | horizontal sweep | 2.167 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_160` | ch19_wave | line | `CH19=160` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_176` | ch19_wave | line | `CH19=176` | 10.0 | wave/deformation | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch19_wave_line_ch19_192` | ch19_wave | line | `CH19=192` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_208` | ch19_wave | line | `CH19=208` | 10.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_line_ch19_224` | ch19_wave | line | `CH19=224` | 10.0 | wave/deformation | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch19_wave_line_ch19_240` | ch19_wave | line | `CH19=240` | 10.0 | wave/deformation | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch19_wave_line_ch19_255` | ch19_wave | line | `CH19=255` | 10.0 | smooth rotation | 1.917 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_ring_ch19_200` | ch19_wave | ring | `CH19=200` | 10.0 | wave/deformation | 2.167 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch19_wave_dual_ch19_200` | ch19_wave | dual | `CH19=200` | 10.0 | horizontal sweep | 2.167 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch19_wave_arc_ch19_200` | ch19_wave | arc | `CH19=200` | 10.0 | smooth rotation | 2.25 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch08_line_white_or_first_000` | ch08_color | line | `CH8=0` | 8.0 | color chase | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch08_line_red_008` | ch08_color | line | `CH8=8` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch08_line_yellow_or_green_014` | ch08_color | line | `CH8=14` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch08_line_cyan_020` | ch08_color | line | `none` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch08_line_magenta_028` | ch08_color | line | `CH8=28` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch08_line_color_effect_060` | ch08_color | line | `CH8=60` | 8.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch08_line_gradient_effect_245` | ch08_color | line | `CH8=245` | 8.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch09_line_effect_speed_000` | ch08_color | line | `CH8=60` | 8.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_001` | ch08_color | line | `CH8=60 CH9=1` | 8.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_004` | ch08_color | line | `CH8=60 CH9=4` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_016` | ch08_color | line | `CH8=60 CH9=16` | 8.0 | static | 0.417 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_032` | ch08_color | line | `CH8=60 CH9=32` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_064` | ch08_color | line | `CH8=60 CH9=64` | 8.0 | static | 1.75 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_096` | ch08_color | line | `CH8=60 CH9=96` | 8.0 | static | 0.833 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_127` | ch08_color | line | `CH8=60 CH9=127` | 8.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_128` | ch08_color | line | `CH8=60 CH9=128` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_144` | ch08_color | line | `CH8=60 CH9=144` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_160` | ch08_color | line | `CH8=60 CH9=160` | 8.0 | static | 0.417 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_192` | ch08_color | line | `CH8=60 CH9=192` | 8.0 | static | 1.833 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_224` | ch08_color | line | `CH8=60 CH9=224` | 8.0 | static | 0.917 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch09_line_effect_speed_255` | ch08_color | line | `CH8=60 CH9=255` | 8.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch08_color_ring_ch08_060_ch09_128` | ch08_color | ring | `CH8=60 CH9=128` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch08_color_arc_ch08_060_ch09_128` | ch08_color | arc | `CH8=60 CH9=128` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch18_line_gradient_speed_000` | ch18_gradient | line | `CH8=245` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch18_line_gradient_speed_001` | ch18_gradient | line | `CH8=245 CH18=1` | 8.0 | color chase | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch18_line_gradient_speed_016` | ch18_gradient | line | `CH8=245 CH18=16` | 8.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_032` | ch18_gradient | line | `CH8=245 CH18=32` | 8.0 | brightness pulse | 0.833 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_064` | ch18_gradient | line | `CH8=245 CH18=64` | 8.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_096` | ch18_gradient | line | `CH8=245 CH18=96` | 8.0 | brightness pulse | 3.0 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_128` | ch18_gradient | line | `CH8=245 CH18=128` | 8.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_160` | ch18_gradient | line | `CH8=245 CH18=160` | 8.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_192` | ch18_gradient | line | `CH8=245 CH18=192` | 8.0 | brightness pulse | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_224` | ch18_gradient | line | `CH8=245 CH18=224` | 8.0 | brightness pulse | 3.0 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch18_line_gradient_speed_255` | ch18_gradient | line | `CH8=245 CH18=255` | 8.0 | brightness pulse | 0.75 | None | nonblank, clipped, not overexposed | limited/needs preset | medium |
| `ch05_06_07_position_line_ch05_040` | ch05_06_07_position | line | `CH5=40` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch05_090` | ch05_06_07_position | line | `none` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch05_170` | ch05_06_07_position | line | `CH5=170` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch06_064` | ch05_06_07_position | line | `CH6=64` | 5.0 | static | 0.5 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch06_128` | ch05_06_07_position | line | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch06_192` | ch05_06_07_position | line | `CH6=192` | 5.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch07_064` | ch05_06_07_position | line | `CH7=64` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch07_128` | ch05_06_07_position | line | `none` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_line_ch07_192` | ch05_06_07_position | line | `CH7=192` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | high |
| `ch05_06_07_position_ring_ch06_064` | ch05_06_07_position | ring | `CH6=64` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch05_06_07_position_ring_ch07_192` | ch05_06_07_position | ring | `CH7=192` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch05_06_07_position_dual_ch06_192` | ch05_06_07_position | dual | `CH6=192` | 5.0 | static | None | None | nonblank, clipped, not overexposed | partially supported | medium |
| `ch05_06_07_position_dual_ch07_064` | ch05_06_07_position | dual | `CH7=64` | 5.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | medium |
| `combo_line_spin` | combos_ch1_19 | line | `CH12=150` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_line_hsweep` | combos_ch1_19 | line | `CH15=200` | 8.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `combo_line_vsweep` | combos_ch1_19 | line | `CH16=200` | 8.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `combo_line_strobe` | combos_ch1_19 | line | `CH1=220 CH11=150` | 8.0 | strobe gate | 0.5 | 2.0 | nonblank, clipped, not overexposed | partially supported | high |
| `combo_line_zoom` | combos_ch1_19 | line | `CH17=80` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_line_wave` | combos_ch1_19 | line | `CH19=200` | 8.0 | wave/deformation | 0.333 | None | nonblank, clipped, not overexposed | limited/needs preset | high |
| `combo_line_color_chase` | combos_ch1_19 | line | `CH8=60 CH9=128` | 8.0 | static | 1.667 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_ring_spin` | combos_ch1_19 | ring | `CH12=150` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_ring_hsweep` | combos_ch1_19 | ring | `CH15=200` | 8.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `combo_dual_spin` | combos_ch1_19 | dual | `CH12=150` | 8.0 | smooth rotation | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_dual_hsweep` | combos_ch1_19 | dual | `CH15=200` | 8.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `combo_arc_spin` | combos_ch1_19 | arc | `CH12=150` | 8.0 | smooth rotation | 1.0 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_arc_hsweep` | combos_ch1_19 | arc | `CH15=200` | 8.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |
| `combo_line_ch4_60_spin` | combos_ch1_19 | line_ch4_60 | `CH12=150` | 8.0 | static | 0.333 | None | nonblank, clipped, not overexposed | partially supported | high |
| `combo_line_ch4_60_hsweep` | combos_ch1_19 | line_ch4_60 | `CH15=200` | 8.0 | unknown/needs recapture | 0.333 | None | blank, not clipped, not overexposed | unknown/needs evidence | high |

## Skipped Or Deferred

- CH2 auto/sound/demo: Skipped: non-deterministic and not useful for deterministic SoundSwitch previz.
- CH4 stacked/second-pattern behavior: CH4 was included only as the first-pattern bank selector for deterministic CH3 ranges; CH20-36 second-pattern controls remained omitted.
- CH10 line/dot scan: Documented from still channel audit; not motion-timed here because it is a static scan/shape modifier.
- CH18 gradient speed: Included with CH8 in the gradient range; deeper gradient-program mapping can be refined after this pass.
- CH3 >=128 dynamic macros: Skipped by scope to avoid macro-loop confusion; deterministic CH3 values 0, 32, 48, and 96 were used.

## Recapture Needed

- `ctrl_static_ring`: blank=False clipped=True overexposed=False
- `ctrl_static_line`: blank=False clipped=True overexposed=False
- `ctrl_static_dual`: blank=False clipped=True overexposed=False
- `ctrl_static_arc`: blank=False clipped=True overexposed=False
- `ctrl_blackout`: blank=True clipped=False overexposed=False
- `ctrl_no_strobe_line`: blank=False clipped=True overexposed=False
- `ctrl_no_spin_line`: blank=False clipped=True overexposed=False
- `ctrl_no_sweep_wave_line`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_000`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_001`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_005`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_010`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_020`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_060`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_100`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_ring_ch04_130`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_000`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_001`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_005`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_010`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_020`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_060`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_100`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_line_ch04_130`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_000`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_001`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_005`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_010`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_020`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_060`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_100`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_dual_ch04_130`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_000`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_001`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_005`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_010`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_020`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_060`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_100`: blank=False clipped=True overexposed=False
- `ch04_pattern_select_arc_ch04_130`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_000`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_001`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_016`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_032`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_048`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_064`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_096`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_128`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_160`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_192`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_224`: blank=False clipped=True overexposed=False
- `ch11_strobe_line_ch11_255`: blank=False clipped=True overexposed=False
- `ch11_strobe_ring_ch11_128`: blank=False clipped=True overexposed=False
- `ch11_strobe_ring_ch11_200`: blank=False clipped=True overexposed=False
- `ch11_strobe_dual_ch11_128`: blank=False clipped=True overexposed=False
- `ch11_strobe_arc_ch11_128`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_000`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_001`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_032`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_064`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_096`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_127`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_128`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_136`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_144`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_152`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_160`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_176`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_192`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_208`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_224`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_240`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch12_255`: blank=False clipped=True overexposed=False
- `ch12_spin_ring_ch12_150`: blank=False clipped=True overexposed=False
- `ch12_spin_ring_ch12_220`: blank=False clipped=True overexposed=False
- `ch12_spin_dual_ch12_150`: blank=False clipped=True overexposed=False
- `ch12_spin_arc_ch12_150`: blank=False clipped=True overexposed=False
- `ch12_spin_arc_ch12_220`: blank=False clipped=True overexposed=False
- `ch12_spin_line_ch4_60_ch12_150`: blank=False clipped=True overexposed=False
- `ch12_spin_arc_ch4_60_ch12_150`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_000`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_001`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_032`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_064`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_096`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_127`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_128`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_160`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_192`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_224`: blank=False clipped=True overexposed=False
- `ch13_rot_x_line_ch13_255`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_000`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_001`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_032`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_064`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_096`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_127`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_128`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_160`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_192`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_224`: blank=False clipped=True overexposed=False
- `ch14_rot_y_line_ch14_255`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_000`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_001`: blank=True clipped=False overexposed=False
- `ch15_hsweep_line_ch15_032`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_064`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_096`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_127`: blank=True clipped=False overexposed=False
- `ch15_hsweep_line_ch15_128`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_136`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_144`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_152`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_160`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_176`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_192`: blank=True clipped=False overexposed=False
- `ch15_hsweep_line_ch15_208`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_224`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_240`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch15_255`: blank=False clipped=True overexposed=False
- `ch15_hsweep_ring_ch15_200`: blank=True clipped=True overexposed=False
- `ch15_hsweep_dual_ch15_200`: blank=False clipped=True overexposed=False
- `ch15_hsweep_arc_ch15_200`: blank=False clipped=True overexposed=False
- `ch15_hsweep_line_ch4_60_ch15_200`: blank=False clipped=True overexposed=False
- `ch15_hsweep_arc_ch4_60_ch15_200`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_000`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_001`: blank=True clipped=False overexposed=False
- `ch16_vsweep_line_ch16_032`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_064`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_096`: blank=True clipped=False overexposed=False
- `ch16_vsweep_line_ch16_127`: blank=True clipped=False overexposed=False
- `ch16_vsweep_line_ch16_128`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_136`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_144`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_152`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_160`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_176`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_192`: blank=True clipped=False overexposed=False
- `ch16_vsweep_line_ch16_208`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_224`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_240`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch16_255`: blank=False clipped=True overexposed=False
- `ch16_vsweep_ring_ch16_200`: blank=True clipped=False overexposed=False
- `ch16_vsweep_dual_ch16_200`: blank=True clipped=False overexposed=False
- `ch16_vsweep_arc_ch16_200`: blank=False clipped=True overexposed=False
- `ch16_vsweep_line_ch4_60_ch16_200`: blank=False clipped=True overexposed=False
- `ch16_vsweep_arc_ch4_60_ch16_200`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_000`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_001`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_032`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_064`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_096`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_127`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_128`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_136`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_144`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_152`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_160`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_176`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_192`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_208`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_224`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_240`: blank=False clipped=True overexposed=False
- `ch17_zoom_line_ch17_255`: blank=False clipped=True overexposed=False
- `ch17_zoom_ring_ch17_080`: blank=False clipped=True overexposed=False
- `ch17_zoom_ring_ch17_200`: blank=False clipped=True overexposed=False
- `ch17_zoom_dual_ch17_080`: blank=False clipped=True overexposed=False
- `ch17_zoom_arc_ch17_080`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_000`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_001`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_032`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_064`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_096`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_127`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_128`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_136`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_144`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_152`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_160`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_176`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_192`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_208`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_224`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_240`: blank=False clipped=True overexposed=False
- `ch19_wave_line_ch19_255`: blank=False clipped=True overexposed=False
- `ch19_wave_ring_ch19_200`: blank=False clipped=True overexposed=False
- `ch19_wave_dual_ch19_200`: blank=False clipped=True overexposed=False
- `ch19_wave_arc_ch19_200`: blank=False clipped=True overexposed=False
- `ch08_line_white_or_first_000`: blank=False clipped=True overexposed=False
- `ch08_line_red_008`: blank=False clipped=True overexposed=False
- `ch08_line_yellow_or_green_014`: blank=False clipped=True overexposed=False
- `ch08_line_cyan_020`: blank=False clipped=True overexposed=False
- `ch08_line_magenta_028`: blank=False clipped=True overexposed=False
- `ch08_line_color_effect_060`: blank=False clipped=True overexposed=False
- `ch08_line_gradient_effect_245`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_000`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_001`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_004`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_016`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_032`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_064`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_096`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_127`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_128`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_144`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_160`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_192`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_224`: blank=False clipped=True overexposed=False
- `ch09_line_effect_speed_255`: blank=False clipped=True overexposed=False
- `ch08_color_ring_ch08_060_ch09_128`: blank=False clipped=True overexposed=False
- `ch08_color_arc_ch08_060_ch09_128`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_000`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_001`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_016`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_032`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_064`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_096`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_128`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_160`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_192`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_224`: blank=False clipped=True overexposed=False
- `ch18_line_gradient_speed_255`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch05_040`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch05_090`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch05_170`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch06_064`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch06_128`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch06_192`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch07_064`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch07_128`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_line_ch07_192`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_ring_ch06_064`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_ring_ch07_192`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_dual_ch06_192`: blank=False clipped=True overexposed=False
- `ch05_06_07_position_dual_ch07_064`: blank=False clipped=True overexposed=False
- `combo_line_spin`: blank=False clipped=True overexposed=False
- `combo_line_hsweep`: blank=True clipped=False overexposed=False
- `combo_line_vsweep`: blank=True clipped=False overexposed=False
- `combo_line_strobe`: blank=False clipped=True overexposed=False
- `combo_line_zoom`: blank=False clipped=True overexposed=False
- `combo_line_wave`: blank=False clipped=True overexposed=False
- `combo_line_color_chase`: blank=False clipped=True overexposed=False
- `combo_ring_spin`: blank=False clipped=True overexposed=False
- `combo_ring_hsweep`: blank=True clipped=False overexposed=False
- `combo_dual_spin`: blank=False clipped=True overexposed=False
- `combo_dual_hsweep`: blank=True clipped=False overexposed=False
- `combo_arc_spin`: blank=False clipped=True overexposed=False
- `combo_arc_hsweep`: blank=True clipped=False overexposed=False
- `combo_line_ch4_60_spin`: blank=False clipped=True overexposed=False
- `combo_line_ch4_60_hsweep`: blank=True clipped=False overexposed=False

## Recommended Motion Preset Table

| preset | source evidence | renderer need | priority |
|---|---|---|---|
| static wall figure | controls + CH5/6/7/17 static states | calibrated wall-projection shape preset per deterministic CH3 family | high |
| strobe gate | CH11 strobe states | timed brightness gate with frequency/duty controls | high |
| smooth/stepped spin | CH12 plus CH13/CH14 sanity states | rotation axis/rate/direction preset per channel/value band | high |
| CH4-selected static figures | CH4 pattern-select states | first-pattern shape preset key should include CH3 range plus CH4 selector | high |
| horizontal sweep | CH15 states | pan/sweep loop with range, clip, bounce/reset behavior | high |
| vertical sweep | CH16 states | vertical sweep loop with offset/range and clip behavior | high |
| zoom/pulse zoom | CH17 states | static size plus possible pulse/speed bank behavior | high |
| wave/deformation | CH19 states | deformation preset separate from whole-pattern movement | medium |
| color chase | CH8/CH9 states | fixed-color map plus color-cycle timing/order | medium |
| gradient timing | CH18 states with CH8 gradient range | gradient speed preset/color flow timing | medium |

## Exact Next Implementation Step

Implement dense breakpoint discovery for CH3-CH19 before tuning renderer behavior. Use CH3+CH4 as the base-look key, sweep each modifier channel finely under valid visible baselines, group adjacent values that produce the same visual behavior, then timed-capture only the representative ranges and high-value combinations. After that, implement a non-rendering calibration data layer keyed by CH3 deterministic range plus CH4 first-pattern selector, then attach CH5-CH19 modifier presets and explicit combo overrides where layered behavior fails.
