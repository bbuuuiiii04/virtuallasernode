# PR-G1 Visual Review Summary

**Brandon instruction:** Pass only if the yellow overlay roughly follows the actual bright laser drawing, not just the glow around it.

v6 uses typed stroke-vectorization with hysteresis support, skeleton graph tracing, and pixel-to-geometry fit scoring.

| shape_ref | lane | family/checkpoint | source path | shape_type | selected_vectorizer | visual_status | usable_as_shape_authority | reason | quality_flags | rejected_candidate_reasons | contact_sheet |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sh1_21b9e82ef84b930b` | v7_authority_record | circle/ring static | `phase1_5_base_dependence/base_CH3_000_CH4_195/CH08_color/CH08_000` | multi_geometry | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_21b9e82ef84b930b.png` |
| `sh1_41c84ad2ac1f458e` | v7_authority_record | two-point / dual-dot static | `phase1_5_base_dependence/base_CH3_048_CH4_000/CH08_color/CH08_000` | dot_anchor | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry |  |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_41c84ad2ac1f458e.png` |
| `sh1_adb58093da473f3e` | v7_authority_record | cue_002_green | `phase6_cue_validation/cue_relevant/cue_002_green` | dotted_arc_path | v7_shape_authority_record | pass | true | v7 authority record with vector render geometry | out_of_box_geometry |  | `artifacts/renderer/shape_authority_v2/contact_sheets/sh1_adb58093da473f3e.png` |

## Status counts

- pass: 3
- weak: 0
- fail: 0
- usable_as_shape_authority: 3

## Selected vectorizer counts

- v7_shape_authority_record: 3

## Shape type counts

- dot_anchor: 1
- dotted_arc_path: 1
- multi_geometry: 1

