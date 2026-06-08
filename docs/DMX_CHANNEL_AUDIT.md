# Full DMX channel wall audit

Master fixture wall-pattern audit using iPhone Continuity Camera device 2, no haze, fixed camera, left wall projection cropped as the master ROI. Channels 1-19 use the first-pattern baseline. Channels 20-36 use a second-pattern-active baseline because CH4>=1 is required to enable the second pattern block.

## Baselines
- `MASTER_VISIBLE_BASELINE`: `1=200,2=0,3=32,4=0,5=90,6=128,7=128,8=20,9=0,10=0,11=0`
  - Chosen because it turns output on, disables strobe/sound/random modes, selects a visible static CH3 line-family look, uses fixed cyan, centers position, and keeps motion neutral for safe wall projection.
- `SECOND_PATTERN_VISIBLE_BASELINE`: `1=200,2=0,3=32,4=10,5=90,6=128,7=128,8=20,9=0,10=0,11=0,20=32,21=10,22=90,23=128,24=128,25=20,26=0,27=0,28=0`
  - Chosen because CH4>=1 is required before CH20-36 can visibly affect the stacked second-pattern block.
- `COLOR_EFFECT_BASELINE`: `1=200,2=0,3=32,4=0,5=90,6=128,7=128,8=60,9=0,10=0,11=0`
  - Used for CH9 because color speed has no visible timing dependency unless CH8 is in an animated color/effect range.
- `GRADIENT_BASELINE`: `1=200,2=0,3=32,4=0,5=90,6=128,7=128,8=245,9=0,10=0,11=0,18=0`
  - Used for CH18 because gradient speed needs CH8 in the gradient/effect range.
- `SECOND_COLOR_EFFECT_BASELINE`: `1=200,2=0,3=32,4=10,5=90,6=128,7=128,8=20,9=0,10=0,11=0,20=32,21=10,22=90,23=128,24=128,25=60,26=0,27=0,28=0`
  - Used for CH26 because second color speed needs CH25 in an animated color/effect range.
- `SECOND_GRADIENT_BASELINE`: `1=200,2=0,3=32,4=10,5=90,6=128,7=128,8=20,9=0,10=0,11=0,20=32,21=10,22=90,23=128,24=128,25=245,26=0,27=0,28=0,35=0`
  - Used for CH35 because second gradient speed needs CH25 in the gradient/effect range.
- CH3 full look-family atlas evidence: `docs/WALL_CH3_LOOK_ATLAS.md`
- For every audited channel, `wall_audit_chXX_baseline.png` confirms visible output under the correct baseline before target values are tested.

## Channel Dependencies

- CH9 depends on CH8 being in a color-effect range; otherwise speed changes can look inactive.
- CH18 depends on CH8 gradient/effect modes.
- CH20-36 depend on CH4>=1 to enable second-pattern stacked output.
- CH26 depends on CH25 being in a color-effect range.
- CH35 depends on CH25 gradient/effect modes.
- CH11/CH28 strobe, CH12-CH17/CH29-CH34 motion/zoom speed, and CH19/CH36 wave channels require timed/burst capture for rate/phase; still frames only show sampled phase.
- CH2 auto/sound behavior can depend on ambient audio and is not deterministic show previz control.

## Important Contact Sheets
- CH01 Dimmer / laser on-off: `/tmp/vln_channel_audit/vln_channel_audit_ch01.png`
- CH04 First pattern select / second-pattern enable: `/tmp/vln_channel_audit/vln_channel_audit_ch04.png`
- CH05 First pattern size: `/tmp/vln_channel_audit/vln_channel_audit_ch05.png`
- CH06 First horizontal position: `/tmp/vln_channel_audit/vln_channel_audit_ch06.png`
- CH07 First vertical position: `/tmp/vln_channel_audit/vln_channel_audit_ch07.png`
- CH08 First color: `/tmp/vln_channel_audit/vln_channel_audit_ch08.png`
- CH09 First color speed: `/tmp/vln_channel_audit/vln_channel_audit_ch09.png`
- CH10 First line/dot scan: `/tmp/vln_channel_audit/vln_channel_audit_ch10.png`
- CH11 First strobe: `/tmp/vln_channel_audit/vln_channel_audit_ch11.png`
- CH12 First rotation Z: `/tmp/vln_channel_audit/vln_channel_audit_ch12.png`
- CH13 First rotation X: `/tmp/vln_channel_audit/vln_channel_audit_ch13.png`
- CH14 First rotation Y: `/tmp/vln_channel_audit/vln_channel_audit_ch14.png`
- CH15 First horizontal movement: `/tmp/vln_channel_audit/vln_channel_audit_ch15.png`
- CH16 First vertical movement: `/tmp/vln_channel_audit/vln_channel_audit_ch16.png`
- CH17 First zoom: `/tmp/vln_channel_audit/vln_channel_audit_ch17.png`
- CH18 First gradient: `/tmp/vln_channel_audit/vln_channel_audit_ch18.png`
- CH19 First X/Y wave: `/tmp/vln_channel_audit/vln_channel_audit_ch19.png`
- CH20 Second pattern group: `/tmp/vln_channel_audit/vln_channel_audit_ch20.png`
- CH21 Second pattern select: `/tmp/vln_channel_audit/vln_channel_audit_ch21.png`
- CH22 Second pattern size: `/tmp/vln_channel_audit/vln_channel_audit_ch22.png`
- CH23 Second horizontal position: `/tmp/vln_channel_audit/vln_channel_audit_ch23.png`
- CH24 Second vertical position: `/tmp/vln_channel_audit/vln_channel_audit_ch24.png`
- CH25 Second color: `/tmp/vln_channel_audit/vln_channel_audit_ch25.png`
- CH28 Second strobe: `/tmp/vln_channel_audit/vln_channel_audit_ch28.png`
- CH29 Second rotation Z: `/tmp/vln_channel_audit/vln_channel_audit_ch29.png`
- CH32 Second horizontal movement: `/tmp/vln_channel_audit/vln_channel_audit_ch32.png`
- CH33 Second vertical movement: `/tmp/vln_channel_audit/vln_channel_audit_ch33.png`
- CH34 Second zoom: `/tmp/vln_channel_audit/vln_channel_audit_ch34.png`
- CH36 Second X/Y wave: `/tmp/vln_channel_audit/vln_channel_audit_ch36.png`

## Channel Summary

| CH | Function | Expected behavior | Visible | Static shape | Motion | Color | Brightness/strobe | Position | Zoom/size | Auto/demo | SoundSwitch priority | Class | Timed needed | Evidence |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Dimmer / laser on-off | 0 off, 1-255 brightness | yes | no | no | no | yes | no | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch01.png` baseline_pixels=29579 value_pixels=143807,48272,47438,47526,43487 |
| 2 | Auto / sound active | 0-26 auto default, 27-127 auto speed, 128-255 sound sensitivity | yes | no | yes | no | yes | no | no | yes | skip | Skip/defer | no | `/tmp/vln_channel_audit/vln_channel_audit_ch02.png` baseline_pixels=53565 value_pixels=48289,51561,32747,9413,0,74316 |
| 3 | First pattern group / macro | static 0-127, dynamic 128-255 | yes | yes | no | no | no | no | no | no | high | Deep calibrate now | no | `/tmp/vln_wall_ch3_atlas_comparison_dynamiccolorfix.png` |
| 4 | First pattern select / second-pattern enable | static select; CH4>=1 enables second pattern | yes | yes | no | no | no | no | no | no | high | Deep calibrate now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch04.png` baseline_pixels=62089 value_pixels=59957,56865,56646,66920,38376,68865,47004 |
| 5 | First pattern size | pattern size | yes | yes | no | no | no | no | yes | no | high | Deep calibrate now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch05.png` baseline_pixels=40514 value_pixels=47014,43689,42206,64268,64037,0 |
| 6 | First horizontal position | 128 center, edges can blank | yes | no | no | no | no | yes | no | no | high | Deep calibrate now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch06.png` baseline_pixels=65677 value_pixels=0,120049,106449,38684,18955,0,0 |
| 7 | First vertical position | 128 center, edges can blank | yes | no | no | no | no | yes | no | no | high | Deep calibrate now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch07.png` baseline_pixels=74697 value_pixels=0,0,104662,64052,23590,0,0 |
| 8 | First color | fixed colors and color effects | yes | no | no | yes | no | no | no | no | high | Deep calibrate now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch08.png` baseline_pixels=66159 value_pixels=74736,6630,48074,15415,2545,5448,71932,123242... |
| 9 | First color speed | color effect speed/direction | yes | no | yes | yes | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch09.png` baseline_pixels=66100 value_pixels=64402,63159,57563,59324,53447,61213 |
| 10 | First line/dot scan | line/dot scan modes | yes | yes | no | no | yes | no | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch10.png` baseline_pixels=22009 value_pixels=20921,20123,20695,23379,14252,12379,20335 |
| 11 | First strobe | strobe speed | yes | no | yes | no | yes | no | no | no | high | Deep calibrate now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch11.png` baseline_pixels=19991 value_pixels=21135,0,361497,0,0,10931 |
| 12 | First rotation Z | angle 1-127, speed 128-255 | yes | no | yes | no | no | no | no | no | high | Deep calibrate now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch12.png` baseline_pixels=21720 value_pixels=22040,22268,32472,26314,24452,25066,24763,27471 |
| 13 | First rotation X | angle 1-127, speed 128-255 | yes | no | yes | no | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch13.png` baseline_pixels=22543 value_pixels=23562,22909,37733,33052,27086,23202,29156,34803 |
| 14 | First rotation Y | angle 1-127, speed 128-255 | yes | no | yes | no | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch14.png` baseline_pixels=26837 value_pixels=26427,27250,26521,26743,26269,26820,27069,26839 |
| 15 | First horizontal movement | position 1-127, speed 128-255 | yes | no | yes | no | no | yes | no | no | high | Deep calibrate now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch15.png` baseline_pixels=27886 value_pixels=30031,0,108571,55248,16022,0,65299,0... |
| 16 | First vertical movement | position 1-127, speed 128-255 | yes | no | yes | no | no | yes | no | no | high | Deep calibrate now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch16.png` baseline_pixels=58629 value_pixels=54592,0,105501,54639,0,0,69264,0... |
| 17 | First zoom | size 1-127, speed 128-255 | yes | yes | yes | no | no | no | yes | no | high | Deep calibrate now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch17.png` baseline_pixels=36458 value_pixels=36146,33630,39997,45892,33366,42780,26495,47728 |
| 18 | First gradient | gradient speed | yes | no | yes | yes | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch18.png` baseline_pixels=15401 value_pixels=15584,2543,10883,4248,9103 |
| 19 | First X/Y wave | 1-127 X-wave, 128-255 Y-wave | yes | yes | yes | no | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch19.png` baseline_pixels=26319 value_pixels=29741,33655,33373,38140,29438,54871,24072 |
| 20 | Second pattern group | static-only group | yes | yes | no | no | no | no | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch20.png` baseline_pixels=23518 value_pixels=30503,24867,33617,16223,20651,17289,30395 |
| 21 | Second pattern select | static pattern select | yes | yes | no | no | no | no | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch21.png` baseline_pixels=20566 value_pixels=22802,25863,21148,24396,41748,23883 |
| 22 | Second pattern size | second pattern size | yes | yes | no | no | no | no | yes | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch22.png` baseline_pixels=27716 value_pixels=27756,28163,29742,29023,45672,31893 |
| 23 | Second horizontal position | second pattern H position | yes | no | no | no | no | yes | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch23.png` baseline_pixels=35786 value_pixels=26279,38606,55331,28573,32641,25262,22934 |
| 24 | Second vertical position | second pattern V position | yes | no | no | no | no | yes | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch24.png` baseline_pixels=24248 value_pixels=18212,18896,22715,23288,31645,18336,18539 |
| 25 | Second color | second pattern color | yes | no | no | yes | no | no | no | no | medium | Light document now | no | `/tmp/vln_channel_audit/vln_channel_audit_ch25.png` baseline_pixels=20917 value_pixels=26081,17725,18068,6041,15380,9473,17849,24379... |
| 26 | Second color speed | second color effect speed | yes | no | yes | yes | no | no | no | no | low | Light document only | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch26.png` baseline_pixels=20621 value_pixels=25199,21634,33572,37340,39328,27876 |
| 27 | Second line/dot scan | second line/dot scan | yes | yes | no | no | yes | no | no | no | low | Light document only | no | `/tmp/vln_channel_audit/vln_channel_audit_ch27.png` baseline_pixels=25017 value_pixels=37465,40522,26179,64448,26379,22793,22668 |
| 28 | Second strobe | second strobe | yes | no | yes | no | yes | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch28.png` baseline_pixels=18518 value_pixels=19719,14825,15221,14443,14416,15131 |
| 29 | Second rotation Z | second Z rotation | yes | no | yes | no | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch29.png` baseline_pixels=22381 value_pixels=26690,37346,23138,25927,24494,28919 |
| 30 | Second rotation X | second X rotation | yes | no | yes | no | no | no | no | no | low | Light document only | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch30.png` baseline_pixels=25467 value_pixels=24539,25873,33037,29899,26807,31863 |
| 31 | Second rotation Y | second Y rotation | yes | no | yes | no | no | no | no | no | low | Light document only | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch31.png` baseline_pixels=24652 value_pixels=21028,23723,22719,24697,37909,33544 |
| 32 | Second horizontal movement | second H movement | yes | no | yes | no | no | yes | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch32.png` baseline_pixels=25774 value_pixels=33298,25659,31503,27369,24926,24430,45680 |
| 33 | Second vertical movement | second V movement | yes | no | yes | no | no | yes | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch33.png` baseline_pixels=31014 value_pixels=23418,18780,22700,18346,19619,19236,26496 |
| 34 | Second zoom | second zoom | yes | yes | yes | no | no | no | yes | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch34.png` baseline_pixels=22145 value_pixels=29276,21612,30259,31922,44234,34934,35380 |
| 35 | Second gradient | second gradient speed | yes | no | yes | yes | no | no | no | no | low | Light document only | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch35.png` baseline_pixels=8752 value_pixels=8886,12762,9586,10829,16186 |
| 36 | Second X/Y wave | second X/Y wave | yes | yes | yes | no | no | no | no | no | medium | Light document now | yes | `/tmp/vln_channel_audit/vln_channel_audit_ch36.png` baseline_pixels=16811 value_pixels=17097,20641,22497,29359,21864,20384,19650 |

## High-priority channels

- CH3 pattern/macro group: broad look-family selector; already atlas-swept.
- CH4 pattern select and second-pattern enable: changes selected figures and activates stacked output.
- CH5/CH17 size and zoom: strong wall geometry impact.
- CH6/CH7 position: strong pan/vertical offset and blanking behavior.
- CH8 color: direct fixed/effect color control.
- CH11 strobe: show-critical but still frames only catch phase.
- CH12/CH15/CH16 rotation and movement: show-critical, timed capture required.

## Timed/burst capture required

- CH9 color chase timing
- CH11 and CH28 strobe rate/duty
- CH12-CH16 first-pattern rotations/movement
- CH17 zoom speed bank
- CH18 gradient timing
- CH19 and CH36 wave deformation
- CH26/CH35 second-pattern color/gradient timing
- CH29-CH34 second-pattern rotation/movement/zoom speed banks
- CH3 dynamic macro motion loops

## Skip/defer

- CH2 auto/sound/demo behavior: not useful for deterministic SoundSwitch previz except to document as sound-gated/demo.
- Deep second-pattern tuning can wait until first-pattern preset families are stable; document it as stacked-output behavior for now.
- Haze/glow/bloom remains deferred.
