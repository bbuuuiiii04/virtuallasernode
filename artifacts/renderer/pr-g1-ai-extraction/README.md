# PR-G1 optional offline Gemini shape extraction

Handcrafted CV v6 remains the in-repo safety/fallback/converter path. This folder holds an **optional, offline** Gemini extractor prototype. It does **not** change visible renderer output and is **not** wired into shape authority by default.

## Policy

- Generated Gemini outputs (masks, contact sheets, full `ai_extractions.json`, API dumps) stay **local** and are **gitignored**.
- Only adapter/converter code, schema, prompt, tiny example JSON, README, and tests are committed.
- Runtime continues respecting `bucket["shape_authority"]` from the capture index.
- Visible geometry remains `DECODER_FALLBACK_DRAWFAN` until PR-G3.
- Do **not** mutate `captures/**` or `data/fixture_model.json`.

## Requirements

```bash
pip install Pillow jsonschema
# For live Gemini runs only:
pip install google-genai
export GEMINI_API_KEY=...   # never commit or log this value
export GEMINI_MODEL=gemini-2.5-flash   # optional; default is image-capable gemini-2.5-flash
```

## Smoke (mock adapter, no API key, 1–3 captures)

```bash
python3 tools/ai_shape_extractor.py --adapter mock --limit 1
python3 tools/ai_shape_extractor.py --adapter mock --limit 3
```

Outputs land under ignored paths:

- `artifacts/renderer/pr-g1-ai-extraction/generated/ai_extractions.json`
- `artifacts/renderer/pr-g1-ai-extraction/contact_sheets/*.png`

## Live Gemini (opt-in)

```bash
export GEMINI_API_KEY=...
python3 tools/ai_shape_extractor.py --enable-gemini --adapter gemini --limit 1
```

Fails closed when `GEMINI_API_KEY` is missing. No API calls unless `--enable-gemini` is set.

## Builder integration (future, opt-in only)

If integrated into `shape_library_builder.py`, flags must remain opt-in:

- `--prefer-ai-extraction`
- `--require-ai-pass-for-authority`
- `--ai-extractions-path PATH`

Under `--require-ai-pass-for-authority`:

- Valid `extracted` + high confidence may become authority.
- `uncertain` / `failed` / low confidence / missing AI output cannot become authority.
- CV-only weak/fail cannot become authority.

## Files

| File | Purpose |
|---|---|
| `ai_extraction.schema.json` | JSON schema for one extraction entry |
| `ai_extraction_prompt.md` | Gemini prompt (pixel-space geometry, JSON only) |
| `ai_extractions.example.json` | Tiny committed example (not bulk corpus output) |

## Tools

| Tool | Role |
|---|---|
| `tools/ai_shape_extractor_adapter.py` | Provider-neutral adapter + Gemini + mock |
| `tools/ai_shape_geometry_convert.py` | Validate + pixel→wall conversion + shape entry |
| `tools/ai_shape_extractor.py` | CLI prototype for PR-G1 selection targets |
