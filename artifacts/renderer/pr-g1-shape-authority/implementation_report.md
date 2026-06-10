# PR-G1 optional offline Gemini extractor prototype

## Summary

Handcrafted CV v6 reached its **stop line** (pass 0 / weak 11 / fail 8 / usable 0). v6 is **retained** as safety/fallback/converter infrastructure but is **not trusted** as completed shape authority.

This follow-up adds a **lean, optional, offline Gemini extractor prototype** without changing visible renderer behavior or wiring AI into authority by default.

## Handcrafted CV stop line (v6 retained)

| Status | Count |
|---|---:|
| pass | 0 |
| weak | 11 |
| fail | 8 |
| **usable_as_shape_authority** | **0** |

v6 CV remains in-repo for fallback, safety checks, and pixel→wall conversion patterns. No further handcrafted CV tuning is planned on real phase6 stills until AI or human review proves value.

## Gemini extractor prototype (optional/offline)

New tools (no runtime renderer changes):

| File | Role |
|---|---|
| `tools/ai_shape_extractor_adapter.py` | Provider-neutral interface; Gemini via `google-genai`; mock for tests |
| `tools/ai_shape_geometry_convert.py` | Validate AI JSON; crop px→wall norm (y flip); authority eligibility gate |
| `tools/ai_shape_extractor.py` | CLI prototype for PR-G1 selection targets only |

Artifacts (committed):

- `artifacts/renderer/pr-g1-ai-extraction/README.md`
- `artifacts/renderer/pr-g1-ai-extraction/ai_extraction.schema.json`
- `artifacts/renderer/pr-g1-ai-extraction/ai_extraction_prompt.md`
- `artifacts/renderer/pr-g1-ai-extraction/ai_extractions.example.json`

Generated outputs are **gitignored** (masks, contact sheets, full `ai_extractions.json`, API dumps). Never commit API keys.

### Smoke (mock, no API)

```bash
python3 tools/ai_shape_extractor.py --adapter mock --limit 1
python3 tools/ai_shape_extractor.py --adapter mock --limit 3
```

Live Gemini requires `--enable-gemini` and `GEMINI_API_KEY` (read from env only; never logged).

### Authority policy

- **Not wired by default.** Builder integration remains future/opt-in: `--prefer-ai-extraction`, `--require-ai-pass-for-authority`, `--ai-extractions-path`.
- Under require-AI mode: only valid `extracted` + high confidence may become authority; uncertain/failed/low-confidence/missing AI cannot; CV-only weak/fail cannot.
- Runtime continues respecting `bucket["shape_authority"]`.

## Explicit non-mutations

- **`captures/**` was not mutated.**
- **`data/fixture_model.json` was not mutated.**

## Visible geometry policy

Visible geometry remains **`DECODER_FALLBACK_DRAWFAN`** until PR-G3. No `_drawFan()` polish. No PR-G1b motion. No PR-G3 projection.

## Tests run

```bash
python3 -m pytest tests/test_ai_*.py -q
```

Covers: schema validity, example JSON, pixel→wall conversion, y-axis flip, uncertain/failed/low-confidence rejection, mock adapter without API key, CLI mock smoke, runtime `shape_authority` respect, gitignore paths for generated artifacts.

## Prior v6 patch context (retained)

Narrow patch after ChatGPT/Brandon review of geometry_kind repair. Focuses on scorer false negatives, stale validation bug, dense branch rejection, and dotted routing — without dashboards, PR-G1b, PR-G3, or visible renderer changes.

**Authority remains conservative:** only automated `pass` sets `usable_as_shape_authority=true`. Runtime continues respecting `bucket["shape_authority"]`.

### Fixes applied (v6)

1. Stale `poly`/`p` bug in `validate_geometry_candidate` (`tools/shape_geometry_kind.py`)
2. Scorer false-negative fix — fit target vs broad support (`tools/shape_stroke_vectorization.py`)
3. Centerline alignment score
4. Dense branch scribble rejection
5. Dotted routing correction

Key improvements from v6: branch scribble eliminated; diagonal baseline no longer hard-fail; still 0 automated pass.

See git history and v6 tests under `tests/test_shape*.py`, `tests/test_dense*.py`, `tests/test_dotted*.py` for full v6 patch detail.
