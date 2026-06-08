#!/usr/bin/env python3
"""
Render MANY decoded frames in ONE HTML page (a grid of canvases), so a single
headless-Chrome launch produces a whole comparison sheet of the renderer output.
Far faster + more reliable than one Chrome per case for tuning iterations.

Usage:
  render_grid.py out.html "label|1=255,3=32,8=20" "label2|1=255,3=16,8=8" ...
Then screenshot with one Chrome:
  chrome --headless=new --screenshot=out.png --window-size=W,H file://out.html
"""
import html as html_lib
import sys, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fixtures import FIXTURES, decode_fixture

CELL_W, CELL_H = 300, 190


def js_json(data):
    """Serialize data for a script tag without allowing </script> breakouts."""
    return json.dumps(data, allow_nan=False).replace("</", "<\\/")


def load_calibration_literal(root):
    try:
        with open(os.path.join(root, "calibration.json")) as f:
            return js_json(json.load(f))
    except (OSError, ValueError, TypeError):
        return "{}"


def decode(spec):
    frame = [0] * 512
    for kv in spec.split(","):
        c, v = kv.split("=")
        frame[int(c) - 1] = int(v)
    fixtures = FIXTURES
    single = os.environ.get("VLN_SINGLE_FIXTURE")
    if single:
        idx = max(0, min(len(FIXTURES) - 1, int(single) - 1))
        fixtures = [FIXTURES[idx]]
    return [decode_fixture(frame, f) for f in fixtures]


def write_grid(out, args):
    cols = int(os.environ.get("VLN_GRID_COLS", "3"))
    cases = [(a.split("|", 1)[0], decode(a.split("|", 1)[1])) for a in args]
    renderer = os.path.join(ROOT, "static", "renderer.js")
    # Inject calibration.json so the headless grid honours live tuning (file://
    # pages can't fetch it). Empty {} -> renderer keeps its DEFAULTS.
    cal = load_calibration_literal(ROOT)
    cells = "".join(
        f'<div class=cell><div class=lbl>{html_lib.escape(lbl)}</div><canvas id="c{i}"></canvas></div>'
        for i, (lbl, _) in enumerate(cases))
    data = js_json([d for _, d in cases])
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#000}}
.grid{{display:flex;flex-wrap:wrap;width:{CELL_W*cols}px}}
.cell{{width:{CELL_W}px;height:{CELL_H}px;position:relative}}
canvas{{width:{CELL_W}px;height:{CELL_H}px;display:block}}
.lbl{{position:absolute;top:0;left:3px;color:#ff0;font:11px monospace;z-index:2;text-shadow:0 0 2px #000}}
</style></head><body><div class="grid">{cells}</div>
<script>window.__VLN_CAL = {cal};</script>
<script src="file://{renderer}"></script>
<script>
const DATA = {data};
const lasers = DATA.map((d, i) => {{
  const l = new LaserRenderer(document.getElementById('c' + i));
  l.update(d); return [l, d];
}});
setInterval(function(){{ for (const x of lasers) x[0].update(x[1]); }}, 30);
</script></body></html>"""
    with open(out, "w") as f:
        f.write(page)
    rows = (len(cases) + cols - 1) // cols
    return CELL_W * cols, CELL_H * rows


def main():
    out = sys.argv[1]
    width, height = write_grid(out, sys.argv[2:])
    print(f"{out} {width} {height}")


if __name__ == "__main__":
    main()
