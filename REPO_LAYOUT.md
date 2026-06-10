# Repository layout (agent map)

**Last updated:** 2026-06-10

## Start here

| Need | Path |
|------|------|
| Renderer implementation plan | `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` |
| PR status / next command | `docs/RENDERER_PR_STATUS.md` |
| Doc index (active vs archived) | `docs/RENDERER_DOCS_INDEX.md` |
| Agent guardrails | `AGENTS.md` |
| calib scripts (active only) | `calib/README.md` |

## Active code (renderer + capture)

```text
static/renderer.js, static/app.js    # browser renderer
webserver.py, fixture_model_adapter.py, capture_index_runtime.py
fixtures.py                            # DMX decode
tools/capture_index_builder.py         # build-time index
artifacts/renderer/renderer-capture-index-pr1/capture_index_v1.json
calib/render_grid_capture.py           # capture-aware smoke harness
captures/fixture_model/                # 8k corpus (metadata in git; media local)
data/fixture_model.json                # composed model (do not mutate without auth)
```

## Archive (do not use for PR-G)

```text
archive/pre_corpus_2026-06-05/         # old calib stills + legacy scripts
archive/experiments/                   # quarantine + PR-D experiments
docs/_archive/                         # historical markdown
```

## What is NOT bloat (keep)

- **`captures/fixture_model/`** (~37 GB local) — primary shape/motion evidence
- **`artifacts/renderer/renderer-capture-index-pr1/`** (~24 MB JSON) — runtime index
- **`calib/.venv/`** (gitignored) — local Python env; safe to delete and recreate

## Size cheatsheet (local)

| Path | ~Size | In git? |
|------|-------|---------|
| `captures/fixture_model/` media | 37 GB | no (jpg/mp4/motion frames) |
| `archive/pre_corpus_.../calib_captures/` | 206 MB | no |
| `calib/.venv/` | 160 MB | no |
| `artifacts/renderer/` | 25 MB | yes (mostly index JSON) |
