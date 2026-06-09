# CH16 & CH7×CH16 V2 — Opus Final Review

**Reviewer:** Claude Opus 4.6  
**Date:** 2026-06-08T22:14 EDT  
**Session:** `captures/recapture_CH16_CH7xCH16_distance_adjusted_2026_06_08_v2`

---

## 1. Physical Capture Status

| Item | Status |
|---|---|
| Physical capture complete | ✅ Yes — 155/155 rows |
| Camera/laser rig still needed | ❌ No — rig may be released |
| Capture data integrity | ✅ 0 missing videos, 0 missing metadata, 0 missing analysis, 0 zero-byte, 0 parse errors |

---

## 2. Gemini Report Trustworthiness

**Overall: TRUSTWORTHY with one inaccuracy.**

| Claim | Verified |
|---|---|
| Row count = 155 | ✅ Confirmed via `wc -l manifest.jsonl` |
| Phase breakdown (12/65/78) | ✅ Confirmed via audit script |
| Blank count = 0 | ✅ Confirmed |
| Clipped count = 0 | ✅ Confirmed |
| Geometry clipped low = 0 | ✅ Confirmed |
| Reprocess 155/155 at 60fps | ✅ Confirmed from task log output |
| Verify PASSED | ✅ Confirmed — re-ran independently |
| Assembly PASSED | ✅ Confirmed — model status = `measured` |
| 18/18 tests passed | ✅ Confirmed — re-ran both test scripts |
| `fixture_model_schema.json` was updated | ⚠️ **FALSE** — file is tracked, `git diff` shows no changes. Schema was *re-written* by the analyzer but content is identical to the committed version. Gemini's report incorrectly listed it as a changed file. |

---

## 3. Model Validation

### fixture_model.json

| Check | Result |
|---|---|
| Valid JSON, loads without error | ✅ |
| `model_status` = `measured` | ✅ |
| 16 channels present (CH1, CH5–CH19) | ✅ Same channel set as before |
| 260 base looks preserved | ✅ Unchanged |
| 4 gating rules | ✅ |
| 8 compositional rules | ✅ |
| 6 independence pairs | ✅ |
| No channels removed or corrupted | ✅ All 16 channels present with banks |

### Key Changes from Previous Model

| Channel | Old Bank 2 Behavior | New Bank 2 Behavior | Correct? |
|---|---|---|---|
| CH16 [128–255] | `color_animated` (CV misclassification) | `sweep` | ✅ Fix — this is a vertical movement speed range |
| CH12 [128–255] | `spin` | `deadband_static` | ✅ Refined — measured rotation speed behavior |
| CH13 [128–255] | `color_animated` | `deadband_static` | ✅ Fix |
| CH14 [1–127] | `color_animated` | `angle_pose` | ✅ Fix |
| CH14 [128–255] | `color_animated` | `deadband_static` | ✅ Fix |
| CH15 [1–127] | `sweep` | `position` | ✅ Refined classification |
| CH17 [1–127] | `zoom_pulse` | `size` | ✅ Refined classification |

### CH16 Coverage

- ✅ 65 clean sweep captures in `phase1_single_channel`
- ✅ Banks: `[0,0]=off`, `[1,127]=position`, `[128,255]=sweep`
- ✅ Previous `color_animated` misclassification is resolved

### CH7×CH16 Coverage

- ✅ 78 composition captures: 20 reference + 40 static + 18 temporal
- ✅ Composition rule: `interfere` (base_consistent=true, measured on 2 bases)
- ✅ Previous `insufficient_data` status is resolved
- ⚠️ `interfere` means the combined effect is non-linear — no simple add/multiply formula. This is a genuine physical characteristic of the fixture, not a data quality issue.

---

## 4. Decoder Mismatch Investigation

### Were the Stage 8b mismatches real?

**No. They were false positives caused by a comparison bug in `cross_check_fixtures()`.**

The cross-check function hardcodes `fixtures.py` breakpoints as `[0, 1, 128]` (including the implicit first bank start at 0), but the model's `breakpoints` field only lists *transition boundaries between banks* (e.g., `[1, 128]`), not the 0-start. The actual model bank ranges are:

```
bank 0: [0, 0]   → off
bank 1: [1, 127]  → position/angle/size
bank 2: [128, 255] → speed/sweep
```

This is **semantically identical** to what `fixtures.py` decodes:
- `v == 0` → off
- `v <= 127` → position/angle/size
- `v >= 128` → speed

The same applies to CH8: the model merges `[0,3]` into one `color_animated` bank, while `fixtures.py` distinguishes `0=white` from `1-3=original`. This is a granularity difference, not a conflict — `fixtures.py` has *finer* resolution than the model, which is correct and desirable for the renderer.

**Conclusion: `fixtures.py` decoders are already correct. No patch needed.**

### What was actually patched

`fixture_model_adapter.py` had **genuinely stale metadata and routing logic**:

1. **`ch7x16` coverage** was hardcoded to `"insufficient_data"` — now dynamically derived from the model's actual composition rules → resolves to `"measured_interfere"`
2. **`unsupported` list** included `"ch7x16_missing"` — removed since CH7×CH16 data now exists
3. **Composition routing** matched on specific rule names (`"multiply"`, `"add"`, `"override_by_CH18"`) that no longer match the model's actual rules (all are now `"interfere"` or `"insufficient_reference_rows"`). Refactored to be model-driven:
   - `interfere` and `insufficient_reference_rows` rules → acknowledged as `_passthrough` (decoder outputs are correct as-is)
   - CH7×CH16 → explicitly tagged as `_measured_not_correctable`
   - Orientation triple → `_handled_by_decoder`
   - Gradient override → still applied at compose time for `interfere` rule

---

## 5. Validation Results After Patch

| Script | Result |
|---|---|
| `python3 tools/validate_model_adapter.py` | ✅ All 5 cases passed |
| `python3 calib/test_fixture_model_readiness.py` | ✅ 18/18 passed |
| Import smoke test (`fixtures`, `fixture_model_adapter`) | ✅ Pass |
| Load `fixture_model.json` | ✅ Pass |
| CH16 position decode (val=64) | ✅ `{mode: position, val: 64}` |
| CH16 speed decode (val=200) | ✅ `{mode: speed, val: 73}` |
| CH7×CH16 composition routing | ✅ Routed to `composition_supported`, not `composition_missing` |
| Gradient override (CH8×CH18) | ✅ Still applied correctly |
| `composition_missing` list | ✅ Empty (all rules now routed) |
| JSON serialization | ✅ Pass |

---

## 6. Files Changed

### Modified (tracked)
| File | Change |
|---|---|
| `data/fixture_model.json` | Reassembled with new CH16 sweep + CH7×CH16 composition data (+2258/−3138 lines) |
| `docs/FIXTURE_MODEL_ASSEMBLY.md` | Regenerated assembly report (+14/−16 lines) |
| `fixture_model_adapter.py` | Updated stale composition routing and coverage metadata (+41/−35 lines) |

### New (untracked)
| File | Purpose |
|---|---|
| `data/fixture_model.before_CH16_CH7xCH16_v2.json` | Pre-recapture model backup |
| `docs/CH16_CH7xCH16_V2_POSTCAPTURE_REPORT.md` | Gemini's post-capture report |
| `docs/CH16_CH7xCH16_V2_OPUS_REVIEW.md` | This review |

### NOT changed (confirmed)
- `data/fixture_model_schema.json` — content identical, no diff
- `fixtures.py` — decoders are already correct
- `captures/` — data untouched

---

## 7. Remaining Risks

| Risk | Severity | Notes |
|---|---|---|
| `cross_check_fixtures()` false positive bug | Low | The comparison logic in the analyzer includes 0 in fixtures.py breakpoints but the model omits it. Cosmetic only — does not affect model or decoder correctness. |
| CH7×CH16 `interfere` is not runtime-correctable | Low | This is a genuine non-linear interaction. The decoder already outputs independent CH7 position + CH16 movement values, which is the best the renderer can do without a lookup table. |
| 118 dense captures still missing (ephemeral /tmp loss) | Medium | Pre-existing issue, not introduced by this recapture. Tracked in `unsupported` list. |
| CH6×CH15 has `insufficient_reference_rows` | Low | Pre-existing. Not affected by this recapture. |

---

## 8. Final Verdict

### **PASS** — safe to review and commit.

- Physical capture is complete and verified (155/155 rows, all quality checks green)
- Model updated correctly with measured CH16 and CH7×CH16 data
- No existing channels were corrupted or removed
- Adapter updated to reflect new model reality
- All validation tests pass (23/23 total across both suites + 6 smoke tests)
- `fixtures.py` decoders are correct and require no changes
- Gemini's report was accurate except for one minor inconsistency (schema file)
