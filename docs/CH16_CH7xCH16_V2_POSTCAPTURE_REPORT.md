# CH16 & CH7xCH16 V2 Post-Capture Report

## Overview
- **Session Path**: `captures/recapture_CH16_CH7xCH16_distance_adjusted_2026_06_08_v2`
- **Expected Row Count**: 155
- **Actual Row Count**: 155

## Session Audit Results
- **Phase Breakdown**: 
  - `preflight_targeted`: 12
  - `phase1_single_channel`: 65
  - `phase3_composition`: 78
- **Blank Count**: 0
- **Clipped Count**: 0
- **Generic Clipped-Only Count**: 0
- **Geometry Clipped Low Count**: 0
- **Required Reference Status**: PASSED
- **CH16 Coverage Status**: PASSED (65 captures)
- **CH7xCH16 Coverage Status**: PASSED (78 captures)

## Processing Pipeline
- **Reprocess Result**: SUCCESS (155 captures reprocessed at 60fps)
- **Verify Result**: PASS (Analyzer is fully prepared)
- **Assembly Result**: PASS (Model successfully assembled with 16 channels, 81 banks, 260 base looks)
- **Validation/Test Results**: PASS (18/18 tests passed)

## Files Changed
- `data/fixture_model.before_CH16_CH7xCH16_v2.json` (New backup)
- `data/fixture_model.json` (Updated)
- `data/fixture_model_schema.json` (Updated)
- `docs/FIXTURE_MODEL_ASSEMBLY.md` (Updated)

## Remaining Warnings
- `fixtures.py` decode functions mismatch against the updated model for the following channels: CH8, CH10, CH11, CH12, CH13, CH14, CH15, CH16, CH17, CH19.

## Final Verdict
**PASS**
