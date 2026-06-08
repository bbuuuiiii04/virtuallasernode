# Phase 6: Dense Validation Report

This report compares the predicted state from `fixture_model_adapter.py` against the actual physical measurements of 175 real SoundSwitch cues.

**Total Cues Evaluated**: 175
- ✅ **PASS**: 20
- ❌ **FAIL (Gating)**: 1
- ❌ **FAIL (Composition)**: 0
- ⚠️ **HIGHER ORDER REQUIRED**: 154

## Failed Gating
These cues have a mismatch between predicted power state and actual physical visibility.

- `phase6_cue_validation__cue_relevant__cue_088_green_laser_static_2_smallest`: Predicted Power=True, Actual Power=False

## Higher Order Required
These cues passed gating, but have 4+ active modifier channels simultaneously. Our current additive/multiplicative adapter rules may not fully capture their complex non-linear geometry.

- `phase6_cue_validation__cue_relevant__cue_001_off`: 5 active modifiers
- `phase6_cue_validation__cue_relevant__cue_002_green`: 8 active modifiers
- `phase6_cue_validation__cue_relevant__cue_003_intro_techno`: 9 active modifiers
- `phase6_cue_validation__cue_relevant__cue_004_breakdown_1`: 9 active modifiers
- `phase6_cue_validation__cue_relevant__cue_005_breakdown_2`: 8 active modifiers
- `phase6_cue_validation__cue_relevant__cue_006_breakdown_chill_3_turqoise_copy`: 7 active modifiers
- `phase6_cue_validation__cue_relevant__cue_007_breakdown_turqoise_reverse`: 7 active modifiers
- `phase6_cue_validation__cue_relevant__cue_008_breakdown_turqoise`: 7 active modifiers
- `phase6_cue_validation__cue_relevant__cue_009_breakdown_chill_2`: 6 active modifiers
- `phase6_cue_validation__cue_relevant__cue_010_breakdown_chill`: 7 active modifiers
- *(...and 144 more)*