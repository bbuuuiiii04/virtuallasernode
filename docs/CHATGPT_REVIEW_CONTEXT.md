# ChatGPT review context

**Repo:** `bbuuiiii04/virtuallasernode`  
**Plan:** `RENDERER_WALL_TO_AERIAL_PLAN_V1.md` **rev 4** (2026-06-10)

## Branches

| Branch | Use |
|--------|-----|
| `renderer-accuracy-phase1` | **Active implementation branch** — Phase 1 committed + repo refactor |
| `review/plan-pr1-5-phase1` | Review branch — sync from accuracy branch before external review |
| `main` | **Not** current renderer policy |

## What the active branch contains

- PR1–PR5 stack + **Phase 1 (PR-A/B/C) committed**
- **Plan rev 4:** PR-G1 static-shape spec — local corpus, calibration boxes, dual selection lanes
- Repo layout refactor (`45c5734d`) — pre-corpus calib archived

## PR-G1 policy (rev 4 — spec committed, not implemented)

- **Implementation spec:** `docs/PR_G1_STATIC_SHAPE_IMPLEMENTATION_SPEC.md`
- **Plan:** `RENDERER_WALL_TO_AERIAL_PLAN_V1.md` §5.2–5.3, §6.0
- **Not inputs:** `calib/captures/`, `/tmp` atlas PNGs, WALL_CH3 legacy still column
- **Normalization:** per-fixture calibration projection box from `analysis_geometry.json` (`image_left`, `image_right`)
- **Selection lanes:** A = CH3 families (atlas checklist); B = phase6 `cue_relevant` cues
- **Artifacts (future):** `shape_selection.json`, `shape_library_v1.json` + schema
- **Visible renderer:** `_drawFan()` may remain until PR-G3; PR-G1 is internal wall-space authority

## Explicitly excluded (local-only or superseded)

- Quarantine experiments → `archive/experiments/quarantine/`
- Raw capture media (~37 GB, **local only** — not in git)
- **Pre-corpus stills** → `archive/pre_corpus_2026-06-05/calib_captures/`
- Abandoned fan-geometry draft (never committed)

## Prior review verdict (2026-06-09)

- **APPROVE** Phase 1 as honesty/motion-labeling foundation
- **BLOCK** claiming Phase 1 or PR1–PR5 is capture-driven geometry/motion
- **Next implementation:** PR-G1 per plan §6.0 (local selection + shape library)

## Suggested read order

1. `docs/CHATGPT_REVIEW_CONTEXT.md` (this file)
2. `docs/PR_G1_STATIC_SHAPE_IMPLEMENTATION_SPEC.md` — PR-G1 coding contract
3. `docs/RENDERER_WALL_TO_AERIAL_PLAN_V1.md` — §5.2–5.3, §6.0 (PR-G1), §18
4. `docs/WALL_CH3_LOOK_ATLAS.md` — family checklist only
5. `artifacts/renderer/renderer-forensic-review-pr1-pr5/opus_capture_grounded_review.md`
6. `artifacts/renderer/pr-g1-plan-cleanup/implementation_report.md`
