#!/usr/bin/env python3
"""
Capture-aware render grid harness.

Builds renderer state like static/app.js:
  composed fixture state + capture lookup metadata from the real capture index.

Usage examples:
  python3 calib/render_grid_capture.py /tmp/vln_phase1.html cue_001_off cue_002_green
  python3 calib/render_grid_capture.py /tmp/vln_phase1.html "manual|1=34,3=48,4=28,6=90,7=141,11=255,13=121,15=148"
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture_index_runtime import CaptureIndexRuntime  # noqa: E402
from fixture_model_adapter import compose_fixture_model, load_fixture_model, sanitize_model  # noqa: E402

CELL_W, CELL_H = 300, 190
INDEX_PATH = ROOT / "artifacts" / "renderer" / "renderer-capture-index-pr1" / "capture_index_v1.json"
CUES_PATH = ROOT / "data" / "soundswitch_laser_cues.json"
MODEL_PATH = ROOT / "data" / "fixture_model.json"
PHASE6_CUE_ROOT = ROOT / "captures" / "fixture_model" / "phase6_cue_validation" / "cue_relevant"


def js_json(data: Any) -> str:
    return json.dumps(data, allow_nan=False).replace("</", "<\\/")


def load_calibration_literal(root: Path) -> str:
    try:
        with (root / "calibration.json").open("r", encoding="utf-8") as fh:
            return js_json(json.load(fh))
    except (OSError, ValueError, TypeError):
        return "{}"


def parse_spec(spec: str) -> tuple[str, list[int]]:
    label, raw = (spec.split("|", 1) if "|" in spec else (spec, spec))
    channels = [0] * 36
    for kv in raw.split(","):
        kv = kv.strip()
        if not kv:
            continue
        if "=" not in kv:
            raise ValueError(f"Invalid channel assignment '{kv}' in '{spec}'")
        c_str, v_str = kv.split("=", 1)
        c = int(c_str.strip())
        v = int(v_str.strip())
        if c < 1 or c > 36:
            raise ValueError(f"Channel out of range in '{spec}': {c}")
        channels[c - 1] = max(0, min(255, v))
    return label.strip() or "unnamed", channels


def resolve_phase6_cue(name: str) -> tuple[str, list[int]]:
    folder = PHASE6_CUE_ROOT / name
    meta_path = folder / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Unknown cue folder '{name}' (missing {meta_path})")
    with meta_path.open("r", encoding="utf-8") as fh:
        meta = json.load(fh)
    ch1_19 = meta.get("ch1_19") or {}
    channels = [0] * 36
    for i in range(1, 20):
        channels[i - 1] = int(ch1_19.get(f"CH{i}", 0))
    return name, channels


def load_capture_geometry() -> dict[str, Any] | None:
    try:
        with INDEX_PATH.open("r", encoding="utf-8") as fh:
            index_data = json.load(fh)
        geometry = index_data.get("geometry")
        return geometry if isinstance(geometry, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def decode_case(
    channels_36: list[int],
    fixture_model_cache: dict[str, Any],
    runtime: CaptureIndexRuntime,
    capture_geometry: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    model = compose_fixture_model(channels_36, model=fixture_model_cache)
    composed = model.get("composed", {})
    lookup = runtime.lookup_exact_from_channels(channels_36)
    return [
        {
            **composed,
            "name": "Laser 1",
            "universe": 0,
            "__capture_lookup": lookup,
            "__provenance_label": lookup.get("provenance_label", "NO_VECTOR_MATCH"),
            "__model_status": model.get("fixture_model", {}).get("model_status", "unknown"),
            "__model_confidence": model.get("fixture_model", {}).get("confidence", "unknown"),
            "__capture_geometry": capture_geometry,
        }
    ]


def write_grid(out_path: Path, args: list[str]) -> tuple[int, int]:
    fixture_model_cache = sanitize_model(load_fixture_model(MODEL_PATH))
    runtime = CaptureIndexRuntime.from_paths(
        index_path=INDEX_PATH,
        cues_path=CUES_PATH,
        fixture_model_path=MODEL_PATH,
    )
    capture_geometry = load_capture_geometry()

    cols = int(os.environ.get("VLN_GRID_COLS", "3"))
    quarantine_ch19 = ROOT / "archive" / "experiments" / "quarantine" / "static" / "ch19_wave.js"
    quarantine_fan = ROOT / "archive" / "experiments" / "quarantine" / "static" / "fan_motion.js"
    renderer = ROOT / "static" / "renderer.js"
    cal = load_calibration_literal(ROOT)
    cases: list[tuple[str, list[dict[str, Any]]]] = []
    for raw in args:
        if re.match(r"^cue_\d+_", raw):
            label, channels = resolve_phase6_cue(raw)
        else:
            label, channels = parse_spec(raw)
        cases.append((label, decode_case(channels, fixture_model_cache, runtime, capture_geometry)))

    cells = "".join(
        f'<div class=cell><div class=lbl>{html_lib.escape(lbl)}</div><canvas id="c{i}"></canvas></div>'
        for i, (lbl, _) in enumerate(cases)
    )
    data = js_json([payload for _, payload in cases])
    geometry_literal = js_json(capture_geometry) if capture_geometry else "null"
    ch19_q = os.environ.get("VLN_QUARANTINE_CH19_WAVE", "")
    ch19_literal = js_json(ch19_q) if ch19_q else '""'
    fan_q = os.environ.get("VLN_QUARANTINE_FAN_MOTION", "")
    fan_literal = js_json(fan_q) if fan_q else '""'
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#000}}
.grid{{display:flex;flex-wrap:wrap;width:{CELL_W*cols}px}}
.cell{{width:{CELL_W}px;height:{CELL_H}px;position:relative}}
canvas{{width:{CELL_W}px;height:{CELL_H}px;display:block}}
.lbl{{position:absolute;top:0;left:3px;color:#ff0;font:11px monospace;z-index:2;text-shadow:0 0 2px #000}}
</style></head><body><div class="grid">{cells}</div>
<script>window.__VLN_CAL = {cal}; window.__VLN_CAPTURE_GEOMETRY = {geometry_literal}; window.__VLN_QUARANTINE_CH19_WAVE = {ch19_literal}; window.__VLN_QUARANTINE_FAN_MOTION = {fan_literal};</script>
<script src="file://{quarantine_ch19}"></script>
<script src="file://{quarantine_fan}"></script>
<script src="file://{renderer}"></script>
<script>
const DATA = {data};
const lasers = DATA.map((d, i) => {{
  const l = new LaserRenderer(document.getElementById('c' + i));
  if (window.__VLN_CAPTURE_GEOMETRY && l.setCaptureGeometry) {{
    l.setCaptureGeometry(window.__VLN_CAPTURE_GEOMETRY);
  }}
  l.update(d); return [l, d];
}});
setInterval(function(){{ for (const x of lasers) x[0].update(x[1]); }}, 30);
</script></body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    rows = (len(cases) + cols - 1) // cols
    return CELL_W * cols, CELL_H * rows


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: render_grid_capture.py out.html <cue_folder|label|spec> [more cases...]")
    out = Path(sys.argv[1])
    width, height = write_grid(out, sys.argv[2:])
    print(f"{out} {width} {height}")


if __name__ == "__main__":
    main()
