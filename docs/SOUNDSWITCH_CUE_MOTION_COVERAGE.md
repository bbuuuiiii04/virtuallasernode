# SoundSwitch cue motion coverage

Corrected evidence bridge between extracted SoundSwitch Attribute Cue resolved DMX vectors and physical capture evidence.

Renderer behavior and calibration render values were not changed.

Important cue semantics: SoundSwitch Attribute Cues may be sparse/layered workflow cues. The current extracted JSON exposes resolved CH1-19 DMX values but not checked/authored-channel metadata, so this coverage describes resolved-vector behavior, not proof that each cue independently authors every channel.

## Dense Motion Analysis
- Capture root: `/tmp/vln_dense_cue_breakpoints_20260605_200426`
- Analysis manifest: `/tmp/vln_dense_cue_breakpoints_20260605_200426/analysis_manifest.jsonl`
- No new physical capture was run.
- Frequency floor changed from `0.35s` min lag to `0.07s` min lag for non-strobe periodic analysis.
- Strobe remains on crossing-count frequency estimation.
- Clipping is ignored for usability; true blanks and confidence gate drive classification.

## Corrected Buckets
- Before recommended_next_action: `{'ready_motion_mapping': 176, 'defer': 5, 'ready_static_validation': 3}`
- After recommended_next_action: `{'ready_static_color_strobe': 78, 'motion_analysis_pending': 35, 'ready_motion_mapping': 66, 'defer': 5}`
- Genuinely motion-ready: 66
- Static/colour/strobe-ready: 78
- Motion analysis pending: 35
- Deferred dynamic CH3 macros: 5

## Motion Capture Resolution
- Motion-family captures analyzed: 111
- Motion-family captures resolved to confidence-gated motion: 65
- Motion-family captures still pending/unresolved: 46

## Per-Channel Motion Summary

### CH12 z_rotation
- States with CH12 active: 22
- Resolved: 9

| value | cue | motion | direction | period_s | confidence | strobe_hz | status |
|---:|---|---|---|---:|---:|---:|---|
| 159 | INTRO TECHNO | static | unknown_from_numeric_analysis | 0.1333 | 0.5109 | 4.45 | pending |
| 196 | BREAKDOWN 1 | static | unknown_from_numeric_analysis | 0.2333 | 0.5056 | 3.8 | pending |
| 255 | BUILDUP TECHNO 1 | wave_deformation | wave_direction_requires_visual_review | 0.3333 | 0.7522 | 3.2 | resolved |
| 124 | PURPLE DAZZLED WAVES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.9382 | 0.55 | resolved |
| 159 | RAINBOW TALL RECTANGLES | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 0.0667 | 0.9844 | 1.0 | resolved |
| 130 | WHITE EMERGING RECTANGLES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.8383 | 0.15 | resolved |
| 196 | RED BOX SWAY DROP 149bpm | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | None | 0.1996 | 1.1 | pending |
| 238 | PROGRESSING FLOWERS BLUE | static | unknown_from_numeric_analysis | 0.1 | 0.6276 | 4.5 | pending |
| 255 | PROGRESSING FLOWERS RED WHITE | static | unknown_from_numeric_analysis | 0.2333 | 0.6578 | 8.1 | pending |
| 255 | LIGHTSPEED EFFECT (COOL!) | static | unknown_from_numeric_analysis | 0.2333 | 0.753 | 8.15 | pending |
| 255 | autoloop groove 4b | static | unknown_from_numeric_analysis | 0.0667 | 0.7847 | 1.2 | pending |
| 255 | autoloop groove 5a | static | unknown_from_numeric_analysis | 0.0667 | 0.7449 | 1.55 | pending |
| 255 | autoloop groove 5b | static | unknown_from_numeric_analysis | 0.9333 | 0.8839 | 1.15 | pending |
| 255 | autoloop groove 5c | static | unknown_from_numeric_analysis | 0.9667 | 0.8712 | 1.45 | pending |
| 172 | autoloop groove 7a | static | unknown_from_numeric_analysis | 0.0667 | 0.968 | 0.55 | pending |
| 255 | STATIC LASERS WHITE POSITIONAL 8 | strobe_gate | unknown_from_numeric_analysis | 0.1724 | 1.0 | 5.8 | resolved |
| 255 | LIGHTSPEED EFFECT (COOL!) | strobe_gate | unknown_from_numeric_analysis | 0.1852 | 1.0 | 5.4 | resolved |
| 255 | LIGHTSPEED EFFECT (COOL!) pos 2 copy | strobe_gate | unknown_from_numeric_analysis | 0.2222 | 1.0 | 4.5 | resolved |
| 255 | genuine spazz | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 0.4667 | 0.4469 | 6.4 | resolved |
| 255 | ACCENT LOOK 1 | color_chase | unknown_from_numeric_analysis | 0.4667 | 0.8034 | 6.05 | resolved |
| 255 | ACCENT LOOK 2 | static | unknown_from_numeric_analysis | 0.4667 | 0.4416 | 4.85 | pending |
| 255 | ACCENT LOOK 3 | static | unknown_from_numeric_analysis | 2.3667 | 0.5025 | 4.05 | pending |

### CH15 horizontal_movement
- States with CH15 active: 81
- Resolved: 45

| value | cue | motion | direction | period_s | confidence | strobe_hz | status |
|---:|---|---|---|---:|---:|---:|---|
| 255 | GREEN | wave_deformation | wave_direction_requires_visual_review | None | 0.1597 | 1.2 | pending |
| 59 | INTRO TECHNO | static | unknown_from_numeric_analysis | 0.1333 | 0.5109 | 4.45 | pending |
| 59 | BREAKDOWN 1 | static | unknown_from_numeric_analysis | 0.2333 | 0.5056 | 3.8 | pending |
| 189 | BREAKDOWN 2 | horizontal_sweep | rightward | 0.1 | 0.5818 | 3.35 | resolved |
| 155 | BREAKDOWN CHILL 3 TURQOISE copy | horizontal_sweep | rightward | 1.2 | 0.5092 | 1.0 | resolved |
| 191 | BREAKDOWN TURQOISE reverse | horizontal_sweep | rightward | 0.9333 | 0.5081 | 1.05 | resolved |
| 176 | BREAKDOWN TURQOISE | pulse_zoom | contracting_at_end | 0.0667 | 0.7676 | 1.05 | resolved |
| 176 | BREAKDOWN CHILL 2 | pulse_zoom | contracting_at_end | 0.0667 | 0.8947 | 0.2 | resolved |
| 191 | BREAKDOWN CHILL | horizontal_sweep | rightward | 1.9 | 0.5171 | 1.25 | resolved |
| 176 | BREAKDOWN TURQOISE pointy | wave_deformation | wave_direction_requires_visual_review | 0.4333 | 0.5997 | 2.35 | resolved |
| 176 | BUILDUP SOFT | wave_deformation | wave_direction_requires_visual_review | 0.4333 | 0.6984 | 3.15 | resolved |
| 176 | BUILDUP 1 HEAVY | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.6704 | 2.55 | resolved |
| 83 | BUILDUP TECHNO 1 | wave_deformation | wave_direction_requires_visual_review | 0.3333 | 0.7522 | 3.2 | resolved |
| 176 | BUILDUP TURQOISE 2 | strobe_gate | unknown_from_numeric_analysis | 0.2041 | 1.0 | 4.9 | resolved |
| 176 | BUILDUP STROBE QUICK | strobe_gate | unknown_from_numeric_analysis | 0.2439 | 1.0 | 4.1 | resolved |
| 148 | BUILDUP STROBE LONG | pulse_zoom | contracting_at_end | 0.0667 | 0.8317 | 1.25 | resolved |
| 176 | BLUE AND WHITE SPERM | horizontal_sweep | rightward | None | 0.1911 | 0.45 | pending |
| 142 | WHITE AND YELLOW | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.6434 | 0.1 | resolved |
| 176 | GREEN SOLID SINEWAVES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.7629 | 0.35 | resolved |
| 179 | NEON SPINNING STRINGS | horizontal_sweep | leftward | 0.0667 | 0.903 | 0.2 | resolved |
| 142 | RED EMERGING LINES | static | unknown_from_numeric_analysis | 0.2 | 0.6134 | 2.75 | pending |
| 76 | PURPLE DAZZLED WAVES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.9382 | 0.55 | resolved |
| 176 | CYAN WAVE SLOW | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 0.0667 | 0.8098 | 0.25 | resolved |
| 143 | BLUE CIRCLE | static | unknown_from_numeric_analysis | 0.0667 | 0.6913 | 1.2 | pending |
| 129 | TALL WATER WAVES | horizontal_sweep | leftward | 0.0667 | 0.4248 | 3.5 | resolved |
| 175 | RAINBOW TALL RECTANGLES | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 0.0667 | 0.9844 | 1.0 | resolved |
| 169 | WHITE EMERGING RECTANGLES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.8383 | 0.15 | resolved |
| 191 | cyanwhite 128bpm strobe  | wave_deformation | wave_direction_requires_visual_review | 0.9333 | 0.826 | 1.05 | resolved |
| 223 | neon 134bpm wavey | horizontal_sweep | leftward | 2.6 | 0.2878 | 2.1 | pending |
| 255 | !! ZOOM 139 BPM !! | horizontal_sweep | rightward | 2.8 | 0.5269 | 1.8 | resolved |
| 186 | rainbow 139bpm outer pulse | horizontal_sweep | leftward | 0.0667 | 0.4421 | 2.1 | resolved |
| 143 | RED BOX SWAY DROP 149bpm | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | None | 0.1996 | 1.1 | pending |
| 76 | TRAP DROP 2 | wave_deformation | wave_direction_requires_visual_review | 0.5 | 0.7629 | 3.55 | resolved |
| 187 | WHITE LASER TAME | wave_deformation | wave_direction_requires_visual_review | 1.3333 | 0.3611 | 0.2 | resolved |
| 190 | BLUE LASER DROP | wave_deformation | wave_direction_requires_visual_review | 1.9667 | 0.2996 | 9.2 | pending |
| 17 | RAINBOW LASER static | color_chase | unknown_from_numeric_analysis | 0.7 | 0.8624 | 2.85 | resolved |
| 145 | WHEREUARE (low synth whir) | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.6207 | 3.25 | resolved |
| 145 | ACCENTED LASERS 2 | static | unknown_from_numeric_analysis | 4.2667 | 0.4527 | 4.0 | pending |
| 191 | autoloop groove 1b | horizontal_sweep | rightward | 0.9333 | 0.7206 | 1.6 | resolved |
| 182 | autoloop groove 2 | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 1.7333 | 0.3232 | 0.3 | pending |
| 152 | autoloop groove 3a | horizontal_sweep | rightward | 1.4333 | 0.6405 | 0.9 | resolved |
| 152 | autoloop groove 3b | pulse_zoom | expanding_at_end | 1.4333 | 0.8032 | 0.7 | resolved |
| 184 | autoloop groove 4 | pulse_zoom | expanding_at_end | 0.0667 | 0.8319 | 0.7 | resolved |
| 65 | autoloop groove 4b | static | unknown_from_numeric_analysis | 0.0667 | 0.7847 | 1.2 | pending |
| 79 | autoloop groove 5a | static | unknown_from_numeric_analysis | 0.0667 | 0.7449 | 1.55 | pending |
| 190 | autoloop groove 5b | static | unknown_from_numeric_analysis | 0.9333 | 0.8839 | 1.15 | pending |
| 159 | autoloop groove 5c | static | unknown_from_numeric_analysis | 0.9667 | 0.8712 | 1.45 | pending |
| 182 | autoloop groove 5d | static | unknown_from_numeric_analysis | 0.0667 | 0.8904 | 0.95 | pending |
| 182 | autoloop groove 6 | static | unknown_from_numeric_analysis | 0.0667 | 0.7285 | 0.7 | pending |
| 151 | autoloop groove 6b | static | unknown_from_numeric_analysis | 0.0667 | 0.9306 | 0.25 | pending |
| 148 | autoloop groove 7a | static | unknown_from_numeric_analysis | 0.0667 | 0.968 | 0.55 | pending |
| 176 | autoloop groove 7b | static | unknown_from_numeric_analysis | 0.0667 | 0.9013 | 1.55 | pending |
| 176 | AUTOLOOP GOOD 1 | static | unknown_from_numeric_analysis | 0.0667 | 0.9439 | 0.25 | pending |
| 148 | AUTOLOOP GOOD 1B | static | unknown_from_numeric_analysis | 0.0667 | 0.9319 | 0.5 | pending |
| 148 | autoloop groove 9 | static | unknown_from_numeric_analysis | 0.0667 | 0.9518 | 0.6 | pending |
| 191 | autoloop groove 9b | static | unknown_from_numeric_analysis | 0.0667 | 0.8242 | 1.05 | pending |
| 155 | autoloop groove 10 | static | unknown_from_numeric_analysis | 0.0667 | 0.8303 | 1.1 | pending |
| 176 | FLOWER BASE | static | unknown_from_numeric_analysis | 0.0667 | 0.9795 | 0.3 | pending |
| 20 | !! STROBE FAST 2 copy | static | unknown_from_numeric_analysis | 0.0667 | 0.831 | 0.05 | pending |
| 26 | STATIC LASERS WHITE POSITIONAL | static | unknown_from_numeric_analysis | 0.0667 | 0.859 | 1.25 | pending |
| 32 | STATIC LASERS WHITE POSITIONAL 2 | horizontal_sweep | leftward | 0.0667 | 0.8722 | 0.1 | resolved |
| 38 | STATIC LASERS WHITE POSITIONAL 2 copy | static | unknown_from_numeric_analysis | 0.0667 | 0.9401 | 0.85 | pending |
| 44 | STATIC LASERS WHITE POSITIONAL 2 copy copy | static | unknown_from_numeric_analysis | 0.0667 | 0.9637 | 0.15 | pending |
| 50 | STATIC LASERS WHITE POSITIONAL 2 copy copy | static | unknown_from_numeric_analysis | 0.0667 | 0.9408 | 0.45 | pending |
| 56 | STATIC LASERS WHITE POSITIONAL 2 copy copy copy | static | unknown_from_numeric_analysis | 0.0667 | 0.3847 | 0.05 | pending |
| 62 | STATIC LASERS WHITE POSITIONAL 2 copy | static | unknown_from_numeric_analysis | 0.0667 | 0.9644 | 0.25 | pending |
| 96 | LIGHTSPEED EFFECT (COOL!) | strobe_gate | unknown_from_numeric_analysis | 0.1852 | 1.0 | 5.4 | resolved |
| 46 | LIGHTSPEED EFFECT (COOL!) pos 2 copy | strobe_gate | unknown_from_numeric_analysis | 0.2222 | 1.0 | 4.5 | resolved |
| 96 | WHITE LASER LINE STATIC copy | horizontal_sweep | leftward | 0.7 | 0.5975 | 2.85 | resolved |
| 96 | POPULATED 1 copy | horizontal_sweep | leftward | 0.7 | 0.8804 | 2.8 | resolved |
| 96 | THICK RAINBOW | horizontal_sweep | rightward | 0.0667 | 0.5521 | 2.5 | resolved |
| 96 | THICK RAINBOW 3 | horizontal_sweep | rightward | 1.5667 | 0.8053 | 1.2 | resolved |
| 148 | ruby effect | horizontal_sweep | leftward | 2.1333 | 0.6325 | 0.7 | resolved |
| 123 | ruby effect 2 | static | unknown_from_numeric_analysis | 0.0667 | 0.89 | 0.1 | pending |
| 223 | ruby pos stable OUT | horizontal_sweep | rightward | 0.9667 | 0.8238 | 1.6 | resolved |
| 3 | ruby pos MOVE IN | static | unknown_from_numeric_analysis | 0.0667 | 0.854 | 0.15 | pending |
| 186 | 2stack wide to in | horizontal_sweep | rightward | 0.0667 | 0.3659 | 2.1 | resolved |
| 65 | rainbow 139bpm strobe copy copy | static | unknown_from_numeric_analysis | 0.0667 | 0.8482 | 0.05 | pending |
| 165 | rainbow 139bpm strobe copy copy copy | horizontal_sweep | rightward | 1.4 | 0.7203 | 1.5 | resolved |
| 165 | RAINBOW COVERAGE | horizontal_sweep | rightward | 0.3667 | 0.6556 | 3.95 | resolved |

### CH16 vertical_movement
- States with CH16 active: 0
- Resolved: 0

| value | cue | motion | direction | period_s | confidence | strobe_hz | status |
|---:|---|---|---|---:|---:|---:|---|

### CH17 zoom
- States with CH17 active: 17
- Resolved: 10

| value | cue | motion | direction | period_s | confidence | strobe_hz | status |
|---:|---|---|---|---:|---:|---:|---|
| 73 | BREAKDOWN TURQOISE | pulse_zoom | contracting_at_end | 0.0667 | 0.7676 | 1.05 | resolved |
| 73 | BREAKDOWN CHILL 2 | pulse_zoom | contracting_at_end | 0.0667 | 0.8947 | 0.2 | resolved |
| 241 | BUILDUP STROBE LONG | pulse_zoom | contracting_at_end | 0.0667 | 0.8317 | 1.25 | resolved |
| 191 | WHITE TRIANGLE sparse | pulse_zoom | expanding_at_end | 0.7 | 0.5761 | 5.45 | resolved |
| 189 | !! ZOOM 124 BPM !! | pulse_zoom | expanding_at_end | 0.7 | 0.8897 | 1.45 | resolved |
| 191 | !! ZOOM 139 BPM !! | horizontal_sweep | rightward | 2.8 | 0.5269 | 1.8 | resolved |
| 69 | GREEN LASER STATIC 2 | color_chase | unknown_from_numeric_analysis | 0.2 | 0.8512 | 4.9 | resolved |
| 103 | GREEN LASER STATIC 2 smaller | pulse_zoom | expanding_at_end | 0.0667 | 0.9913 | 0.05 | resolved |
| 124 | GREEN LASER STATIC 2 smallerer | static | unknown_from_numeric_analysis | 0.1333 | 0.6633 | 2.2 | pending |
| 127 | GREEN LASER STATIC 2 smallerer than | static | unknown_from_numeric_analysis | 0.0667 | 0.989 | 0.1 | pending |
| 173 | PROGRESSING FLOWERS BLUE | static | unknown_from_numeric_analysis | 0.1 | 0.6276 | 4.5 | pending |
| 200 | autoloop groove 3b | pulse_zoom | expanding_at_end | 1.4333 | 0.8032 | 0.7 | resolved |
| 200 | autoloop groove 4 | pulse_zoom | expanding_at_end | 0.0667 | 0.8319 | 0.7 | resolved |
| 117 | AUTOLOOP GOOD 1 | static | unknown_from_numeric_analysis | 0.0667 | 0.9439 | 0.25 | pending |
| 241 | AUTOLOOP GOOD 1B | static | unknown_from_numeric_analysis | 0.0667 | 0.9319 | 0.5 | pending |
| 241 | autoloop groove 9 | static | unknown_from_numeric_analysis | 0.0667 | 0.9518 | 0.6 | pending |
| 1 | THICK RAINBOW 4 | static | unknown_from_numeric_analysis | 1.5667 | 0.7707 | 1.9 | pending |

### CH19 wave
- States with CH19 active: 54
- Resolved: 36

| value | cue | motion | direction | period_s | confidence | strobe_hz | status |
|---:|---|---|---|---:|---:|---:|---|
| 88 | GREEN | wave_deformation | wave_direction_requires_visual_review | None | 0.1597 | 1.2 | pending |
| 136 | INTRO TECHNO | static | unknown_from_numeric_analysis | 0.1333 | 0.5109 | 4.45 | pending |
| 247 | BREAKDOWN 1 | static | unknown_from_numeric_analysis | 0.2333 | 0.5056 | 3.8 | pending |
| 121 | BREAKDOWN 2 | horizontal_sweep | rightward | 0.1 | 0.5818 | 3.35 | resolved |
| 121 | BREAKDOWN CHILL 3 TURQOISE copy | horizontal_sweep | rightward | 1.2 | 0.5092 | 1.0 | resolved |
| 121 | BREAKDOWN TURQOISE reverse | horizontal_sweep | rightward | 0.9333 | 0.5081 | 1.05 | resolved |
| 248 | BREAKDOWN TURQOISE | pulse_zoom | contracting_at_end | 0.0667 | 0.7676 | 1.05 | resolved |
| 74 | BREAKDOWN CHILL 2 | pulse_zoom | contracting_at_end | 0.0667 | 0.8947 | 0.2 | resolved |
| 121 | BREAKDOWN CHILL | horizontal_sweep | rightward | 1.9 | 0.5171 | 1.25 | resolved |
| 74 | BREAKDOWN TURQOISE pointy | wave_deformation | wave_direction_requires_visual_review | 0.4333 | 0.5997 | 2.35 | resolved |
| 79 | BUILDUP SOFT | wave_deformation | wave_direction_requires_visual_review | 0.4333 | 0.6984 | 3.15 | resolved |
| 74 | BUILDUP 1 HEAVY | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.6704 | 2.55 | resolved |
| 145 | BUILDUP TECHNO 1 | wave_deformation | wave_direction_requires_visual_review | 0.3333 | 0.7522 | 3.2 | resolved |
| 79 | BUILDUP TURQOISE 2 | strobe_gate | unknown_from_numeric_analysis | 0.2041 | 1.0 | 4.9 | resolved |
| 79 | BUILDUP STROBE QUICK | strobe_gate | unknown_from_numeric_analysis | 0.2439 | 1.0 | 4.1 | resolved |
| 72 | BUILDUP STROBE LONG | pulse_zoom | contracting_at_end | 0.0667 | 0.8317 | 1.25 | resolved |
| 88 | WHITE AND YELLOW | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.6434 | 0.1 | resolved |
| 86 | GREEN SOLID SINEWAVES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.7629 | 0.35 | resolved |
| 24 | NEON SPINNING STRINGS | horizontal_sweep | leftward | 0.0667 | 0.903 | 0.2 | resolved |
| 71 | RED EMERGING LINES | static | unknown_from_numeric_analysis | 0.2 | 0.6134 | 2.75 | pending |
| 7 | PURPLE DAZZLED WAVES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.9382 | 0.55 | resolved |
| 214 | TRAILING LINES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.9241 | 13.4 | resolved |
| 52 | BLUE CIRCLE | static | unknown_from_numeric_analysis | 0.0667 | 0.6913 | 1.2 | pending |
| 167 | TALL WATER WAVES | horizontal_sweep | leftward | 0.0667 | 0.4248 | 3.5 | resolved |
| 200 | RAINBOW TALL RECTANGLES | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 0.0667 | 0.9844 | 1.0 | resolved |
| 70 | WHITE EMERGING RECTANGLES | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.8383 | 0.15 | resolved |
| 121 | cyanwhite 128bpm strobe  | wave_deformation | wave_direction_requires_visual_review | 0.9333 | 0.826 | 1.05 | resolved |
| 217 | rainbow 139bpm strobe copy | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 0.0667 | 0.8048 | 6.65 | resolved |
| 7 | !! GRADIENT 140 bpm !! | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.7727 | 1.1 | resolved |
| 255 | RED BOX SWAY DROP 149bpm | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | None | 0.1996 | 1.1 | pending |
| 255 | TRAP DROP 2 | wave_deformation | wave_direction_requires_visual_review | 0.5 | 0.7629 | 3.55 | resolved |
| 111 | TURQOISE WAVEY DROP 128 bpm | wave_deformation | wave_direction_requires_visual_review | 0.1667 | 0.748 | 1.85 | resolved |
| 14 | WHITE LASER DROP | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.733 | 5.7 | resolved |
| 15 | WHITE LASER TAME | wave_deformation | wave_direction_requires_visual_review | 1.3333 | 0.3611 | 0.2 | resolved |
| 111 | RAINBOW LASER DROP 2 | wave_deformation | wave_direction_requires_visual_review | 0.9 | 0.7965 | 9.65 | resolved |
| 111 | BLUE LASER DROP | wave_deformation | wave_direction_requires_visual_review | 1.9667 | 0.2996 | 9.2 | pending |
| 255 | WHEREUARE (low synth whir) | wave_deformation | wave_direction_requires_visual_review | 0.0667 | 0.6207 | 3.25 | resolved |
| 210 | autoloop groove 2 | smooth_rotation | clockwise_or_counterclockwise_requires_visual_review | 1.7333 | 0.3232 | 0.3 | pending |
| 210 | autoloop groove 3a | horizontal_sweep | rightward | 1.4333 | 0.6405 | 0.9 | resolved |
| 210 | autoloop groove 5d | static | unknown_from_numeric_analysis | 0.0667 | 0.8904 | 0.95 | pending |
| 210 | autoloop groove 6 | static | unknown_from_numeric_analysis | 0.0667 | 0.7285 | 0.7 | pending |
| 210 | autoloop groove 6b | static | unknown_from_numeric_analysis | 0.0667 | 0.9306 | 0.25 | pending |
| 210 | autoloop groove 7a | static | unknown_from_numeric_analysis | 0.0667 | 0.968 | 0.55 | pending |
| 72 | AUTOLOOP GOOD 1B | static | unknown_from_numeric_analysis | 0.0667 | 0.9319 | 0.5 | pending |
| 72 | autoloop groove 9 | static | unknown_from_numeric_analysis | 0.0667 | 0.9518 | 0.6 | pending |
| 121 | autoloop groove 9b | static | unknown_from_numeric_analysis | 0.0667 | 0.8242 | 1.05 | pending |
| 121 | autoloop groove 10 | static | unknown_from_numeric_analysis | 0.0667 | 0.8303 | 1.1 | pending |
| 7 | autoloop groove 11 | static | unknown_from_numeric_analysis | 0.0667 | 0.9596 | 0.65 | pending |
| 111 | WHITE LASER LINE STATIC copy | horizontal_sweep | leftward | 0.7 | 0.5975 | 2.85 | resolved |
| 111 | POPULATED 1 | wave_deformation | wave_direction_requires_visual_review | 1.0667 | 0.6025 | 2.95 | resolved |
| 169 | THICK RAINBOW 4 | static | unknown_from_numeric_analysis | 1.5667 | 0.7707 | 1.9 | pending |
| 72 | rainbow 139bpm strobe copy copy copy | horizontal_sweep | rightward | 1.4 | 0.7203 | 1.5 | resolved |
| 79 | RAINBOW COVERAGE | horizontal_sweep | rightward | 0.3667 | 0.6556 | 3.95 | resolved |
| 107 | RAINBOW COVERAGE HYPER | horizontal_sweep | rightward | 0.3667 | 0.5163 | 4.2 | resolved |

## Pending Cues

| cue | family | reason |
|---|---|---|
| GREEN | `horizontal_line_static+ch4_program_255_255+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| INTRO TECHNO | `horizontal_line_static+ch4_program_135_139+zrot+xrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| BREAKDOWN 1 | `horizontal_line_static+ch4_program_135_139+zrot+xrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| BLUE AND WHITE SPERM | `horizontal_line_static+ch4_program_000_004+xmove+gradient` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| RED EMERGING LINES | `horizontal_line_static+ch4_program_000_004+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| BLUE CIRCLE | `horizontal_line_static+ch4_program_000_004+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| neon 134bpm wavey | `ring_circle_static+ch4_program_195_199+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| RED BOX SWAY DROP 149bpm | `ch3_unsampled_bin_040_047+ch4_program_120_124+zrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| BLUE LASER DROP | `horizontal_line_static+ch4_program_000_004+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| ACCENTED LASERS 2 | `ring_circle_static+ch4_program_225_229+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| PROGRESSING FLOWERS BLUE | `ring_circle_static+ch4_program_185_189+zrot+zoom` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| PROGRESSING FLOWERS RED WHITE | `dual_dot_static+ch4_program_100_104+zrot` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| LIGHTSPEED EFFECT (COOL!) | `dual_dot_static+ch4_program_100_104+zrot` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 2 | `ch3_unsampled_bin_040_047+ch4_program_000_004+xrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 4b | `ch3_unsampled_bin_040_047+ch4_program_000_004+zrot+yrot+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 5a | `ch3_unsampled_bin_040_047+ch4_program_000_004+zrot+yrot+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 5b | `ch3_unsampled_bin_040_047+ch4_program_000_004+zrot+yrot+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 5c | `ch3_unsampled_bin_040_047+ch4_program_000_004+zrot+yrot+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 5d | `ch3_unsampled_bin_040_047+ch4_program_120_124+xrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 6 | `ch3_unsampled_bin_040_047+ch4_program_120_124+xrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 6b | `ch3_unsampled_bin_040_047+ch4_program_000_004+xrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 7a | `ring_circle_static+ch4_program_055_059+zrot+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 7b | `horizontal_line_static+ch4_program_000_004+xmove+gradient` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| AUTOLOOP GOOD 1 | `horizontal_line_static+ch4_program_000_004+xmove+zoom+gradient` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| AUTOLOOP GOOD 1B | `horizontal_line_static+ch4_program_045_049+xmove+zoom+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 9 | `horizontal_line_static+ch4_program_045_049+xrot+xmove+zoom+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 9b | `ring_circle_static+ch4_program_200_204+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 10 | `ring_circle_static+ch4_program_200_204+xmove+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 11 | `horizontal_line_static+ch4_program_000_004+gradient+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| autoloop groove 14b | `ch3_unsampled_bin_040_047+ch4_program_000_004+zrot+yrot+xmove` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| FLOWER BASE | `horizontal_line_static+ch4_program_000_004+xmove+gradient` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| THICK RAINBOW 4 | `ring_circle_static+ch4_program_000_004+zoom+wave` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| ACCENT LOOK 1 | `horizontal_line_static+ch4_program_195_199+zrot` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| ACCENT LOOK 2 | `horizontal_line_static+ch4_program_090_094+zrot` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |
| ACCENT LOOK 3 | `horizontal_line_static+ch4_program_145_149+zrot` | exact vector filmed at 60fps, but motion_type/period did not pass confidence gate |

## Exact Next Recommendation
Use `ready_static_color_strobe` cues for static, colour, gradient, position, and strobe preset mapping. Use `ready_motion_mapping` only for cues whose dense analysis has `motion_characterized=true`. Do not tune unresolved spin/sweep/zoom/wave families until they either pass this analysis gate or are visually reviewed from frame strips for direction and period.
