# PR-G1 plan cleanup — implementation report

**Date:** 2026-06-10  
**Scope:** Documentation/spec only — no PR-G1 code, no capture mutation  
**Branch:** `renderer-accuracy-phase1`

## Summary

Updated active renderer plan and status docs so PR-G1 static shape authority is unambiguous before implementation. Plan bumped to **rev 4** in `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md`.

## Corrections encoded

| Topic | Policy |
|---|---|
| Historical `calib/captures/` | **Not** PR-G1 evidence — archived under `archive/pre_corpus_*/` |
| `WALL_CH3_LOOK_ATLAS.md` | **Look-family checklist only** — not extraction evidence; `/tmp` and legacy PNG paths are historical |
| PR-G1 inputs | Local `captures/fixture_model/**` stills (`still.jpg` / `still_color.jpg`) + sidecar JSON |
| GitHub vs local | Raw stills/videos/motion frames are **local-only**; GitHub = code/docs/schema/tests |
| Selection lanes | **A:** CH3 family coverage; **B:** phase6 `cue_relevant` SoundSwitch cues — both required |
| Normalization frame | **Per-fixture calibration projection box** from `analysis_geometry.json` (`image_left`, `image_right`) |
| Coordinate space | x/y ∈ [-1, +1] inside fixture box; y up (flip pixel y); never normalize to shape-own bbox |
| Topology labels | Diagnostic only: `line`, `two_clusters`, `closed_loop`, `multi_cluster`, `complex_shape`, `unknown` |
| Brandon validation | Side-by-side still + overlay; yes/no only — no geometry vocabulary required |
| Required artifacts | `shape_selection.json`, `shape_library_v1.json`, `shape_library_v1.schema.json` |
| Visible renderer | `_drawFan()` may remain until PR-G3; PR-G1 is internal wall-space authority only |

## Files changed

- `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` — rev 4; §5.2–5.3, §6.0 PR-G1 spec
- `docs/RENDERER_PR_STATUS.md` — Phase 1 committed; rev 4; PR-G1 checklist
- `docs/WALL_CH3_LOOK_ATLAS.md` — checklist-only banner
- `docs/RENDERER_DOCS_INDEX.md` — rev 4, local corpus note, PR-G1 artifacts
- `docs/CHATGPT_REVIEW_CONTEXT.md` — branch/plan alignment

## Not done (intentional)

- No `tools/shape_library_builder.py`
- No `shape_selection.json` or `shape_library_v1.json` generated
- No changes under `captures/**`
- No changes to `data/fixture_model.json`
- No PR-D revival or `_drawFan()` polish

## Tests

N/A — documentation-only change.

## Agent checkpoint

PR-G1 implementation may proceed when Brandon approves plan rev 4 wording. First coding step: local selector → `shape_selection.json` (both lanes) → shape extraction → `shape_library_v1.json`.
