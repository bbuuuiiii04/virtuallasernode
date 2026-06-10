# calib/ — active scripts only

**Last updated:** 2026-06-10

Pre-corpus audit scripts and `calib/captures/` were moved to **`archive/pre_corpus_2026-06-05/`**.  
Historical audit markdown moved to **`docs/_archive/pre_corpus/`**.

**Shape/motion authority:** `captures/fixture_model/` (8k corpus). See `REPO_LAYOUT.md`.

---

## Active scripts

### 8k capture pipeline

| Script | Role |
|--------|------|
| `fixture_model_orchestrator.py` | Capture orchestration |
| `fixture_model_analyzer.py` | Per-capture `analysis.json` |
| `fixture_model_validator.py` | Validation |
| `fixture_model_monitor.py` | Monitor |
| `reprocess_60fps.py` | Re-analysis |
| `targeted_recapture.py` | Gap fills |
| `dense_cue_breakpoints.py` | Motion analysis helpers |
| `migrate_manifest_tags.py` | Manifest maintenance |
| `run_supervisor.sh`, `capture_stop_mute_watcher.sh` | Ops |

### DMX + utilities

| Script | Role |
|--------|------|
| `dmx_open.py`, `dmx_pro.py` | DMX I/O |
| `export_grid.py`, `shoot.sh` | Headless Chrome grids |
| `soundswitch_cue_coverage.py` | Cue coverage analysis |
| `fixture_model_progress.py` | Progress reporting |

### Renderer harness

| Script | Role |
|--------|------|
| `render_grid_capture.py` | **Primary** — capture lookup + composed state |
| `render_grid.py` | Decoder-only grid |
| `render_test.py` | Single-frame smoke |

### Tests

| Script | Role |
|--------|------|
| `test_dmx_pro.py`, `test_fixture_model_readiness.py` | calib tests |

---

## Archived (do not import from active code)

```text
archive/pre_corpus_2026-06-05/scripts/   caplog, channel_audit, wall_atlas, …
archive/pre_corpus_2026-06-05/calib_captures/   681 PNG stills
```

---

## PR-G lookup recipe

1. Search `captures/fixture_model/manifest.jsonl` for vector match.
2. Read `still.jpg` + `motion_analysis_60fps/` from `capture_path`.
3. Use `docs/WALL_CH3_LOOK_ATLAS.md` for atlas-family smoke paths.
