# ChatGPT review context

**Repo:** `bbuuiiii04/virtuallasernode`

## Branches

| Branch | Use |
|--------|-----|
| `review/plan-pr1-5-phase1` | **Primary review branch** — PR1–PR5 + Phase 1 + plan rev 3 |
| `main` | Corpus metadata only (`dc761b03`) — **not** current renderer policy |

## What `review/plan-pr1-5-phase1` contains

- PR1–PR5: capture index, lookup, measured overlay, diagnostics, visual polish
- **Phase 1 (PR-A/B/C):** provenance honesty, cue aliases, motion_type/color, CH1 binary fix
- **Plan rev 3:** `RENDERER_WALL_TO_AERIAL_PLAN_V1.md` — includes §18 Brandon decisions + G4 mandatory additions
- Forensic PR1–PR5 review + Phase 1 implementation report

## Explicitly excluded (local-only or superseded)

- Index regen / PR-D builder changes
- Quarantine modules (`static/quarantine/`, preview bar)
- Raw capture media (~37 GB, not in git)

## Prior review verdict (2026-06-09)

- **APPROVE** Phase 1 as honesty/motion-labeling foundation
- **BLOCK** claiming Phase 1 or PR1–PR5 is capture-driven geometry/motion
- **Next implementation:** PR-G1 atlas-first static shapes, then PR-G1b phase6 motion tracks

## Suggested read order

1. `docs/CHATGPT_REVIEW_CONTEXT.md` (this file)
2. `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` — especially §6 (PR-G1–G4), §9, §18
3. `artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md`
4. `artifacts/renderer/renderer-accuracy-phase1/implementation_report.md`
5. Code: `static/renderer.js`, `capture_index_runtime.py`, `webserver.py`
