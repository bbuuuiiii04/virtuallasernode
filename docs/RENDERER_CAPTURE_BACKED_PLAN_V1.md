# Renderer Capture-Backed Plan V1

**Date:** 2026-06-09  
**Status:** Active primary renderer plan

## Purpose

Make the capture-backed architecture the active renderer authority model after the 2026-06-09 capture corpus audit. This plan is documentation-only guidance for roadmap and governance. It does not implement runtime changes by itself.

## Renderer Authority Order

1. **EXACT_CAPTURE**  
   Exact CH1-19 vector match from a generated capture index. Handles geometry/color exposure-track pairs, latest-timestamp dedup of duplicate test_ids, and quality gates `usable_evidence` / `geometry_clipped_low` / `recapture_pending`.

2. **CAPTURE_INDEX_INTERPOLATED**  
   Single-channel nearest-measured interpolation within a measured bank, honoring fixture_model interpolation/breakpoints, never across blank zones.

3. **MEASURED_FIXTURE_MODEL**  
   `data/fixture_model.json` base looks + gated transfer maps + composition rules.

4. **MEASURED_MOTION_ANALYSIS**  
   Measured `motion_type`, `direction+confidence`, `loop_duration_estimate`, `strobe_frequency_hz`, `duty_cycle`, extents.

5. **FALLBACK_MOTIONSTATE**  
   Simulated oscillator math, always labeled.

6. **MANUAL_DECODER**  
   `decode_36ch` channel assumptions.

## Boundaries (Verbatim)

- corpus covers CH1-19 first pattern only
- CH20-36 second_pattern and CH2 remain decoder-driven with warnings
- committed corpus is numeric (raw media is local-only), so capture-backed means measured parameters driving the existing procedural aerial renderer
- x_range/y_range and model maps are camera pixels, converted via analysis_geometry.json px_per_inch = 10.5185
- wall-space conversion is approximate (no homography, <=~5% error)
- manifest inline analysis is stale - per-capture analysis.json is the analysis authority
- phase6 adapter validation passed only 20/175 real cues, which is why EXACT_CAPTURE outranks model composition

## PR Roadmap (Active)

### PR1 — `renderer-capture-index-pr1`

Build-time index generator from `manifest.jsonl` + per-capture `analysis.json` + `analysis_geometry.json`; no renderer/webserver changes.

### PR2 — `renderer-capture-lookup-pr2`

Load index in webserver/adapter, exact vector + cue lookup, provenance labels in SSE payload, diagnostics.

### PR3 — `renderer-measured-motion-pr3`

Renderer consumes measured parameters; reduced MotionState core - visibility gates, square strobe, CH2 sound gate, CH10 drawMode - retained as the labeled fallback layer.

### PR4-PR6

Diagnostics expansion, visual polish, physical calibration/hardening (in that order).

## Preserved Guardrails

Copied from the existing orchestration guide:

- no `fixture_model.json` mutation
- no capture data mutation
- no WebGL
- no removed second_pattern rendering
- no moved fixture/aperture origins
- no visual polish before motion correctness
- no hidden fallback behavior
- tests required
- no exact-digital-twin claims
