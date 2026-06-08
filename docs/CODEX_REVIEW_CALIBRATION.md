# Codex review prompt — calibration.json extraction (data-driven renderer constants)

Run from `/Users/bbui/virtuallasernode`. This directory is **not currently a
Git repo**, so normal `git diff`/baseline review is unavailable unless you
create or are given a baseline copy. Use the current files as the review target.

Read-only review:
`codex exec --skip-git-repo-check -s read-only`

---

## What this change is

A **parity-preserving refactor**: the renderer's previously-hardcoded tunable
constants (movement rates, beam-fan geometry, beam look) and the decoder's
calibrated colour order + position blank window were lifted into a single
`calibration.json`, so the laser preview can be retuned **without editing code**
and hard-refreshing the browser. This is the first milestone of "Live
Calibration Mode" — deliberately scoped to the data-driven-constants extraction
only. No behaviour should change on a fresh checkout.

**User's #1 priority is MOVEMENT fidelity**, so the movement knobs
(`rates.*`, `geometry.{panGain,vShiftGain,inwardLean,spreadAngGain}`) are the
parameters that matter most to get right and keep faithful.

## Files changed / added

- `calibration.json` (NEW, package root) — single source of truth.
- `calibration.py` (NEW) — best-effort loader; `load_calibration()` + `get()`.
- `fixtures.py` — `SEVEN_COLORS`, `SEVEN_COLOR_NAMES`, and the `_position`
  blank window now sourced from `calibration.json` with the prior literals as
  fallback. Dual import (`from .calibration` / `from calibration`) so it works
  both as a package and as the top-level module the `calib/` harnesses import.
- `static/renderer.js` — `DELAY`/`FADE`/`BEAM`/`RATES` + inline geometry/zoom/
  dynamic/pattern-density/gradient magic numbers replaced with a `DEFAULTS`
  object + `CAL` (DEFAULTS overlaid with `window.__VLN_CAL` sync and/or a live
  `/calibration.json` fetch). `LaserRenderer.DEFAULTS` exposed for inspection.
- `webserver.py` — new `/calibration.json` route (served from package root,
  `Cache-Control: no-store`).
- `calib/render_test.py`, `calib/render_grid.py` — inject `window.__VLN_CAL`
  from `calibration.json` so headless verification honours live tuning (file://
  pages can't fetch).

## Verification already done (please re-run / confirm, don't trust blindly)

1. `node --check static/renderer.js` → OK.
2. `python3 -m py_compile calibration.py fixtures.py webserver.py calib/render_test.py calib/render_grid.py` → OK.
3. **JS↔JSON parity**: a Node script requiring `renderer.js` (with stubbed
   browser globals) deep-compares `LaserRenderer.DEFAULTS` against
   `calibration.json` for all 8 shared sections → **PARITY OK** (every key the
   JS reads equals the JSON; JSON's server-only keys `_doc`/`color.sevenColors`/
   `color.sevenColorNames`/`position` are intentionally not in the JS DEFAULTS).
4. **Decoder parity**: `SEVEN_COLORS == W,R,Y,G,C,B,M`, names match, blank
   window `50/254`; a cyan-band frame decodes `rgb=[0,255,255]`, a `CH6=40`
   frame decodes `blanked=True`.
5. Both harnesses emit HTML containing a valid, parseable injected
   `window.__VLN_CAL`.

## Known issues found by Codex review (treat as required fixes, not hypotheticals)

1. **`static/renderer.js` `deepMerge()` is prototype-pollutable.**
   `window.__VLN_CAL` and `/calibration.json` are merged with arbitrary keys.
   A JSON object containing `{"__proto__":{"polluted":true}}` mutates
   `Object.prototype` in the current implementation. Fix by rejecting
   `__proto__`, `prototype`, and `constructor`, and only recursively merging
   plain objects.
2. **Malformed-but-valid calibration JSON can still break consumers.**
   `calibration.py get()` assumes `calibration[section]` is a dict; for example
   `"color": []` raises `AttributeError` during decoder import/use. JS has the
   same class of risk if wrong types flow into numeric geometry/render fields and
   produce `NaN`. Add schema/type guards or a whitelist of known calibration
   paths with expected primitive/object types.
3. **Python decoder calibration is cached for the process lifetime.**
   Browser hard-refresh reloads renderer calibration, but decoder-owned values
   such as `color.sevenColors`, `color.sevenColorNames`, and
   `position.blankLow/blankHigh` do not update until the Python process restarts.
   Either document that server restart is required for decoder keys, or reload
   on file mtime changes.
4. **The file:// harnesses inject raw JSON directly into `<script>`.**
   Current `calibration.json` is safe, but a future string containing `</script>`
   would break the generated HTML. Parse and re-emit with `json.dumps(...)`, and
   escape `</` as `<\/`.

## What I could NOT verify (unknowns — please scrutinise)

- **Visual parity in a real browser / headless Chrome.** I did not render
  before-vs-after pixels (headless Chrome is flaky in this repo). Parity rests
  on (3): DEFAULTS == JSON, and the claim that every consumer now reads CAL.*
  with identical arithmetic. **Please audit that claim line-by-line** — confirm
  no constant changed value or changed the expression it sits in.
- Whether I missed any magic number that should have been extracted, or
  extracted one whose value silently drifted.

## Review focus — be adversarial

1. **Parity, exhaustively.** For every replaced constant in `renderer.js`,
   confirm `CAL.<path>` resolves to the same number AND the surrounding
   expression is unchanged. Pay special attention to:
   - `squashMax` used twice in one expression (`1 - Math.min(0.6, …*0.6)`) — both
     0.6s must map to `CAL.geometry.squashMax`.
   - `spinAngleMax: Math.PI` round-tripping through JSON (3.141592653589793).
   - `apGapFrac` (0.085) and `dynamic.count` (7) — the live file had drifted from
     an earlier state; confirm JSON/DEFAULTS match the CURRENT code, not the old.
   - size-response (`0.32 + (1-size/255)*0.45`), scan multipliers, and the
     `_beam` alpha stops were **left inline by design** — flag if any should be
     calibratable for the stated goal, but they are not parity risks.
2. **Loader robustness.** `calibration.py` swallows `OSError`/`ValueError` and
   caches `{}` for missing/unparseable files, but malformed valid JSON with the
   wrong shape is a known failure class. `renderer.js` `deepMerge` +
   `loadCalibration` catch fetch failure and keep DEFAULTS, but `deepMerge` is
   currently prototype-pollutable. Review the proposed fixes and confirm a
   missing, malformed, wrong-shaped, or hostile `calibration.json` cannot break
   the server, decoder, tests, or file:// harnesses.
3. **The dual import in `fixtures.py`** (`from .calibration` / `from calibration`).
   Confirm it resolves in: `python3 -m virtuallasernode`, the `calib/` harnesses
   (which `sys.path.insert(ROOT)` then `import fixtures`), and any test runner.
4. **The new web route.** `/calibration.json` reads a fixed package-root path
   (no user input) — confirm no traversal and that it 404s cleanly when absent.
5. **Live-edit semantics.** After editing `calibration.json`, browser geometry
   changes (`sourceYFrac`/`scaleFrac`) only apply on the next `_resize`. The
   constructor calls `loadCalibration().then(() => this._resize())`; confirm
   that re-resize is correct and that a stale first frame can't render with
   mixed old/new dims. Also account for Python-side decoder keys being cached
   until restart unless an mtime reload is added.
6. **Harness HTML injection.** `calib/render_test.py` and `calib/render_grid.py`
   inject `calibration.json` directly into a script block. Confirm the fix parses
   and re-serializes JSON safely, including escaping `</`.
7. Anything that would make this NOT a no-op on a fresh checkout.

## Out of scope (do not flag as missing)

Preset store / exact-DMX matching / playback recall, automated computer vision,
AI preset generation, fixing the known render bugs (core white-boost
desaturation — now `beam.coreWhiteBoost`, dial-down-able; CH8 1-3 "original"
colour), and exhaustive extraction of every shape-math constant. This milestone
is the constants extraction only.

## Output

1. Parity verdict: identical / drifted (list every drift with file:line).
2. Robustness/security findings (loader, deepMerge, route, harness injection).
3. Import-resolution findings.
4. Anything missed or mis-extracted.
5. Concrete diffs for any fix.
