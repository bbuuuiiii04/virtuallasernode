# Wall CH3 look atlas

This atlas isolates the first-pattern CH3 macro/group channel with CH4=0, CH5=90, CH6/7=128, CH8=20. Captures use iPhone Continuity Camera device 2. The real sheet crops the left projection as the master fixture ROI because both physical units receive the same DMX.

## Artifacts
- Real wall atlas: `/tmp/vln_wall_ch3_atlas_real.png`
- Virtual atlas: `/tmp/vln_wall_ch3_atlas_virtual_dynamiccolorfix.png`
- Comparison atlas: `/tmp/vln_wall_ch3_atlas_comparison_dynamiccolorfix.png`

## Discovered look families

| DMX range sampled | representative | family | behavior | evidence status | representative capture | priority |
|---|---:|---|---|---|---|---|
| 0-8 | 0 | circle/ring static | static wall figure | still sufficient for family; CH4 selection may vary shape | `calib/captures/wall_atlas_ch3_000.png` | medium |
| 16-40 | 32 | horizontal line static | static wall figure | still sufficient; useful as baseline and strobe/zoom test | `calib/captures/wall_atlas_ch3_032.png` | high |
| 48-56 | 48 | two-point / dual-dot static | static wall figure | still sufficient; low beam-count effect | `calib/captures/wall_atlas_ch3_048.png` | low-medium |
| 64-120 | 96 | dotted arc / compact swirl static-animation bank | selected static/animated-looking figure | still sample identifies family; CH4 selection likely important | `calib/captures/wall_atlas_ch3_096.png` | high |
| 128-136 | 128 | U-wave dynamic macro | motion-dependent macro | timed/burst evidence needed for loop; still identifies family | `calib/captures/wall_atlas_ch3_128.png` | high |
| 144-152 | 144 | three-star dynamic macro | motion-dependent macro | timed/burst evidence needed; high EDM/drop potential | `calib/captures/wall_atlas_ch3_144.png` | high |
| 160-168 | 160 | compact swirl dynamic macro | motion-dependent macro | timed/burst evidence needed | `calib/captures/wall_atlas_ch3_160.png` | medium-high |
| 176 | 176 | large star polygon dynamic macro | motion-dependent macro | timed/burst evidence needed; strong impact look | `calib/captures/wall_atlas_ch3_176.png` | high |
| 184-192, 208-216, 232-240, 255 | 216 | horizontal line dynamic variants | motion-dependent or macro-selected line | still identifies line family; timed evidence needed for whether it moves | `calib/captures/wall_atlas_ch3_216.png` | medium |
| 200 | 200 | low dotted-row dynamic macro | motion-dependent macro | still identifies impact row; timed evidence needed | `calib/captures/wall_atlas_ch3_200.png` | high |
| 224 | 224 | compact point/dot dynamic macro | motion-dependent macro | still identifies family; lower priority unless used in cues | `calib/captures/wall_atlas_ch3_224.png` | low-medium |
| 248 | 248 | late ring dynamic macro | motion-dependent macro | timed/burst evidence needed; possible build/drop accent | `calib/captures/wall_atlas_ch3_248.png` | medium-high |

## Per-sample observations

| CH3 | family | logged DMX | laser pixels | bbox | center | dominant note |
|---:|---|---|---:|---|---|---|
| 0 | static line set 1 | `CH1=200 CH5=90 CH6=128 CH7=128 CH8=20` | 35231 | `[227, 327, 555, 626]` | `[402.0, 474.4]` | blue |
| 8 | static line set 1 | `CH1=200 CH3=8 CH5=90 CH6=128 CH7=128 CH8=20` | 34383 | `[227, 328, 554, 628]` | `[403.1, 476.7]` | blue |
| 16 | static line set 2 | `CH1=200 CH3=16 CH5=90 CH6=128 CH7=128 CH8=20` | 19868 | `[213, 434, 555, 511]` | `[395.3, 472.0]` | blue |
| 24 | static line set 2 | `CH1=200 CH3=24 CH5=90 CH6=128 CH7=128 CH8=20` | 19346 | `[212, 432, 555, 510]` | `[395.5, 472.0]` | blue |
| 32 | static line set 3 / dense | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20` | 19484 | `[216, 434, 557, 513]` | `[399.1, 472.4]` | blue |
| 40 | static line set 3 / dense | `CH1=200 CH3=40 CH5=90 CH6=128 CH7=128 CH8=20` | 19385 | `[215, 430, 557, 513]` | `[399.4, 472.2]` | blue |
| 48 | static line set 4 / wide dense | `CH1=200 CH3=48 CH5=90 CH6=128 CH7=128 CH8=20` | 6056 | `[213, 245, 561, 527]` | `[415.1, 473.2]` | cyan |
| 56 | static line set 4 / wide dense | `CH1=200 CH3=56 CH5=90 CH6=128 CH7=128 CH8=20` | 6436 | `[212, 245, 562, 529]` | `[417.1, 473.1]` | cyan |
| 64 | static animation bank | `CH1=200 CH3=64 CH5=90 CH6=128 CH7=128 CH8=20` | 18869 | `[278, 412, 459, 577]` | `[357.6, 492.4]` | blue |
| 72 | static animation bank | `CH1=200 CH3=72 CH5=90 CH6=128 CH7=128 CH8=20` | 16945 | `[278, 402, 465, 552]` | `[358.1, 466.5]` | blue |
| 80 | static animation bank | `CH1=200 CH3=80 CH5=90 CH6=128 CH7=128 CH8=20` | 18453 | `[278, 411, 457, 576]` | `[357.2, 491.7]` | blue |
| 88 | static animation bank | `CH1=200 CH3=88 CH5=90 CH6=128 CH7=128 CH8=20` | 18312 | `[280, 406, 463, 575]` | `[362.3, 481.8]` | blue |
| 96 | static animation bank | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20` | 17542 | `[280, 408, 459, 574]` | `[362.0, 483.6]` | blue |
| 104 | static animation bank | `CH1=200 CH3=104 CH5=90 CH6=128 CH7=128 CH8=20` | 17427 | `[279, 407, 463, 576]` | `[360.3, 484.3]` | blue |
| 112 | static animation bank | `CH1=200 CH3=112 CH5=90 CH6=128 CH7=128 CH8=20` | 17432 | `[280, 408, 461, 575]` | `[360.6, 484.2]` | blue |
| 120 | static animation bank | `CH1=200 CH3=120 CH5=90 CH6=128 CH7=128 CH8=20` | 16907 | `[282, 396, 461, 551]` | `[362.5, 472.1]` | blue |
| 128 | dynamic line set 1 | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=20` | 23401 | `[224, 300, 559, 563]` | `[404.2, 470.9]` | blue |
| 136 | dynamic line set 1 | `CH1=200 CH3=136 CH5=90 CH6=128 CH7=128 CH8=20` | 22336 | `[224, 300, 559, 562]` | `[403.4, 470.5]` | blue |
| 144 | dynamic line set 2 | `CH1=200 CH3=144 CH5=90 CH6=128 CH7=128 CH8=20` | 19820 | `[165, 416, 715, 531]` | `[414.5, 472.0]` | blue |
| 152 | dynamic line set 2 | `CH1=200 CH3=152 CH5=90 CH6=128 CH7=128 CH8=20` | 21347 | `[162, 409, 715, 542]` | `[450.6, 470.1]` | blue |
| 160 | dynamic animation bank | `CH1=200 CH3=160 CH5=90 CH6=128 CH7=128 CH8=20` | 18914 | `[283, 402, 465, 578]` | `[373.1, 483.7]` | blue |
| 168 | dynamic animation bank | `CH1=200 CH3=168 CH5=90 CH6=128 CH7=128 CH8=20` | 18348 | `[280, 408, 461, 574]` | `[362.1, 482.1]` | blue |
| 176 | dynamic line set 3 | `CH1=200 CH3=176 CH5=90 CH6=128 CH7=128 CH8=20` | 31297 | `[252, 336, 527, 607]` | `[397.4, 468.7]` | blue |
| 184 | dynamic line set 3 | `CH1=200 CH3=184 CH5=90 CH6=128 CH7=128 CH8=20` | 19200 | `[213, 435, 554, 509]` | `[394.5, 472.5]` | blue |
| 192 | dynamic line set 3 | `CH1=200 CH3=192 CH5=90 CH6=128 CH7=128 CH8=20` | 19320 | `[212, 435, 554, 509]` | `[394.2, 472.1]` | blue |
| 200 | dynamic line set 3 | `CH1=200 CH3=200 CH5=90 CH6=128 CH7=128 CH8=20` | 22438 | `[184, 609, 543, 715]` | `[369.6, 659.5]` | blue |
| 208 | dynamic line set 3 | `CH1=200 CH3=208 CH5=90 CH6=128 CH7=128 CH8=20` | 19173 | `[211, 434, 553, 509]` | `[395.1, 472.8]` | blue |
| 216 | dynamic line set 3 | `CH1=200 CH3=216 CH5=90 CH6=128 CH7=128 CH8=20` | 19186 | `[212, 436, 554, 510]` | `[395.8, 472.9]` | blue |
| 224 | dynamic line set 3 | `CH1=200 CH3=224 CH5=90 CH6=128 CH7=128 CH8=20` | 10462 | `[334, 400, 454, 542]` | `[393.6, 474.2]` | blue |
| 232 | dynamic line set 3 | `CH1=200 CH3=232 CH5=90 CH6=128 CH7=128 CH8=20` | 19413 | `[211, 434, 554, 510]` | `[394.9, 472.4]` | blue |
| 240 | dynamic line set 3 | `CH1=200 CH3=240 CH5=90 CH6=128 CH7=128 CH8=20` | 19413 | `[213, 434, 555, 509]` | `[394.5, 472.5]` | blue |
| 248 | dynamic line set 3 | `CH1=200 CH3=248 CH5=90 CH6=128 CH7=128 CH8=20` | 33691 | `[279, 374, 501, 583]` | `[389.2, 477.4]` | blue |
| 255 | dynamic line set 3 | `CH1=200 CH3=255 CH5=90 CH6=128 CH7=128 CH8=20` | 19919 | `[212, 434, 555, 510]` | `[394.8, 472.5]` | blue |

## Mismatch ranking by family

1. Dynamic CH3>=128 families are the worst shape mismatch: the physical laser produces distinct wall figures (U-wave, stars, swirl, polygon, dotted row, ring), while the virtual renderer still uses a generic aerial fan shape for most dynamic macros.
2. Wall projection vs aerial fan model remains a global mismatch; wall figures cannot be fully matched by tuning aerial beam constants alone.
3. Static animation bank CH3=64-120 is visually distinct as dotted arc/swirl figures, while the virtual output remains a generic beam fan.
4. Static line/ring/two-dot families CH3=0-56 are identifiable from still frames, but the virtual output mostly changes beam density rather than wall figure shape.
5. Dynamic fixed-color handling is now improved: CH8 fixed colors are respected for dynamic macros, but timed/burst evidence is still required for macro motion loops.

## Deferred

- Timed/burst capture for dynamic families, CH15/CH16 sweeps, CH12 spin rates, and CH19 waves.
- Haze/glow/bloom tuning.
- Laser 2 independent calibration.
