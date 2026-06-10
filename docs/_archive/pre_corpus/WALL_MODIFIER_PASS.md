# Wall modifier pass

**Status:** Historical (2026-06-05) — modifier findings valid; evidence in `/tmp` + `calib/captures/wall_mod_*`  
**Last updated:** 2026-06-10

> **Agent rule:** Stills from this pass are pre-8k corpus. For PR-G use `captures/fixture_model/` vector lookup. See `calib/README.md`.

Limited modifier pass against representative wall look families. This is not an exhaustive combination sweep.

## Artifacts
- Real wall modifier sheet: `/tmp/vln_wall_modifier_real.png`
- Virtual modifier sheet: `/tmp/vln_wall_modifier_virtual_dynamiccolorfix.png`
- Comparison sheet: `/tmp/vln_wall_modifier_comparison_dynamiccolorfix.png`

## Observations

| case | representative family | logged DMX | still evidence | virtual mismatch | next action |
|---|---|---|---|---|---|
| line32_base | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=19543 bbox=[212, 434, 557, 511] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_red | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=8` | pixels=13163 bbox=[220, 444, 547, 502] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_flow | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=60 CH9=80` | pixels=15258 bbox=[220, 426, 557, 513] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_zoom | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | pixels=28141 bbox=[290, 48, 501, 579] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_panL | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=64 CH7=128 CH8=20` | pixels=62574 bbox=[439, 245, 715, 639] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_panR | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=192 CH7=128 CH8=20` | pixels=13804 bbox=[122, 420, 331, 525] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_spin | horizontal line static | `CH1=200 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH12=150` | pixels=19804 bbox=[227, 312, 543, 579] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| line32_strobe | horizontal line static | `CH1=220 CH3=32 CH5=90 CH6=128 CH7=128 CH8=20 CH11=150` | pixels=0 bbox= | still frame can catch on/off phase only | timed strobe duty/rate capture |
| swirl96_base | dotted arc / compact swirl static-animation | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=20247 bbox=[280, 405, 465, 577] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| swirl96_red | dotted arc / compact swirl static-animation | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=8` | pixels=6327 bbox=[284, 406, 447, 563] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| swirl96_zoom | dotted arc / compact swirl static-animation | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | pixels=17499 bbox=[302, 351, 471, 586] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| swirl96_spin | dotted arc / compact swirl static-animation | `CH1=200 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH12=150` | pixels=17218 bbox=[279, 389, 439, 577] | wall figure vs aerial fan model | use for preset family; avoid broad renderer tuning |
| swirl96_strobe | dotted arc / compact swirl static-animation | `CH1=220 CH3=96 CH5=90 CH6=128 CH7=128 CH8=20 CH11=150` | pixels=0 bbox= | still frame can catch on/off phase only | timed strobe duty/rate capture |
| dyn128_base | U-wave dynamic macro | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=23462 bbox=[224, 297, 559, 564] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |
| dyn128_red | U-wave dynamic macro | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=8` | pixels=13548 bbox=[228, 396, 547, 553] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |
| dyn128_zoom | U-wave dynamic macro | `CH1=200 CH3=128 CH5=90 CH6=128 CH7=128 CH8=20 CH17=100` | pixels=22507 bbox=[223, 287, 558, 563] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |
| dyn144_base | three-star dynamic macro | `CH1=200 CH3=144 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=30259 bbox=[168, 393, 715, 546] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |
| dyn144_strobe | three-star dynamic macro | `CH1=220 CH3=144 CH5=90 CH6=128 CH7=128 CH8=20 CH11=150` | pixels=0 bbox= | strobe still-frame phase only; shape remains generic aerial fan | timed strobe + dynamic burst capture |
| dyn176_base | large star polygon dynamic macro | `CH1=200 CH3=176 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=30957 bbox=[253, 336, 528, 607] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |
| dyn200_base | low dotted-row dynamic macro | `CH1=200 CH3=200 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=18808 bbox=[211, 438, 554, 509] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |
| dyn248_base | late ring dynamic macro | `CH1=200 CH3=248 CH5=90 CH6=128 CH7=128 CH8=20` | pixels=19138 bbox=[211, 437, 554, 509] | color now follows fixed CH8; shape remains generic aerial fan | timed/burst dynamic preset capture |

## Summary

- Static line and static swirl families respond to color, zoom, pan, spin, and strobe modifiers in ways visible on the wall.
- Dynamic macro families are distinct real looks, but still frames are insufficient to model motion loops.
- Dynamic fixed-color handling was corrected so CH8 fixed RGB values affect dynamic macros.
- Current virtual dynamic shape rendering remains the largest atlas mismatch: it uses one generic aerial fan shape for many visually different real macros.
- No haze/glow/bloom conclusions should be drawn from this pass.
