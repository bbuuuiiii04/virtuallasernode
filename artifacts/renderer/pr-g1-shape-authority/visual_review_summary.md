# PR-G1 Visual Review Summary

**Brandon instruction:** Pass only if the yellow overlay roughly follows the actual bright laser drawing, not just the glow around it.

v6 uses typed stroke-vectorization with hysteresis support, skeleton graph tracing, and pixel-to-geometry fit scoring.

| shape_ref | lane | family/checkpoint | source path | shape_type | selected_vectorizer | visual_status | usable_as_shape_authority | reason | quality_flags | rejected_candidate_reasons | contact_sheet |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sh1_21b9e82ef84b930b` | v7_authority_record | circle/ring static | `phase1_5_base_dependence/base_CH3_000_CH4_195/CH08_color/CH08_000` | multi_geometry | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_21b9e82ef84b930b.png` |
| `sh1_e9743d87837d24ad` | v7_authority_record | horizontal line static | `phase1_single_channel/CH01_master_dimmer/CH01_220` | multi_geometry | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_e9743d87837d24ad.png` |
| `sh1_41c84ad2ac1f458e` | v7_authority_record | two-point / dual-dot static | `phase1_5_base_dependence/base_CH3_048_CH4_000/CH08_color/CH08_000` | dot_anchor | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_41c84ad2ac1f458e.png` |
| `sh1_2e3da0a4330792c3` | v7_authority_record | U-wave dynamic macro | `phase6_cue_validation/cue_relevant/cue_024_neon_wandering_lines` | multi_geometry | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_2e3da0a4330792c3.png` |
| `sh1_adb58093da473f3e` | v7_authority_record | cue_002_green | `phase6_cue_validation/cue_relevant/cue_002_green` | dotted_arc_path | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry | out_of_box_geometry |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_adb58093da473f3e.png` |
| `sh1_2bae89cc023a3c52` | v7_authority_record | cue_006_breakdown_chill_3_turqoise_copy | `phase6_cue_validation/cue_relevant/cue_006_breakdown_chill_3_turqoise_copy` | dot_anchor | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_2bae89cc023a3c52.png` |
| `sh1_d9c0e1383b952508` | v7_authority_record | cue_007_breakdown_turqoise_reverse | `phase6_cue_validation/cue_relevant/cue_007_breakdown_turqoise_reverse` | dot_anchor | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_d9c0e1383b952508.png` |
| `sh1_14928e116b6d46fb` | v7_authority_record | cue_009_breakdown_chill_2 | `phase6_cue_validation/cue_relevant/cue_009_breakdown_chill_2` | dotted_arc_path | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_14928e116b6d46fb.png` |
| `sh1_5f0125b19c4208c0` | v7_authority_record | cue_011_breakdown_turqoise_pointy | `phase6_cue_validation/cue_relevant/cue_011_breakdown_turqoise_pointy` | dotted_arc_path | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_5f0125b19c4208c0.png` |
| `sh1_83b4671ca39044d5` | v7_authority_record | cue_012_buildup_soft | `phase6_cue_validation/cue_relevant/cue_012_buildup_soft` | multi_geometry | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry | out_of_box_geometry |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_83b4671ca39044d5.png` |

## Status counts

- pass: 10
- weak: 0
- fail: 0
- usable_as_shape_authority: 10

## Selected vectorizer counts

- v7_shape_authority_record: 10

## Shape type counts

- multi_geometry: 4
- dot_anchor: 3
- dotted_arc_path: 3

