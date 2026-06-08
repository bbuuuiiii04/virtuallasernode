#!/usr/bin/env python3
"""
Render-verify harness: decode a synthetic DMX frame with the REAL decoder
(fixtures.py), embed it in an HTML page that runs static/renderer.js, so a
headless-Chrome screenshot shows the actual VLN render for those channel values.
Lets us compare the on-screen render to the real-laser captures.

Usage:
  render_test.py out.html 1=255 3=32 8=20      # cyan dense fan
Then screenshot:
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
     --screenshot=out.png --window-size=900,600 --virtual-time-budget=1600 \
     --hide-scrollbars file://.../out.html
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fixtures import FIXTURES, decode_fixture

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#000;overflow:hidden}}
#stage{{width:900px;height:560px;display:block}}
</style></head><body>
<canvas id="stage"></canvas>
<script>window.__VLN_CAL = {cal};</script>
<script src="{renderer}"></script>
<script>
const DECODED = {decoded};
const laser = new LaserRenderer(document.getElementById('stage'));
laser.update(DECODED);
setInterval(function(){{ laser.update(DECODED); }}, 30);   // keep buffer fresh
</script></body></html>
"""


def js_json(data):
    """Serialize data for a script tag without allowing </script> breakouts."""
    return json.dumps(data, allow_nan=False).replace("</", "<\\/")


def load_calibration_literal(root):
    try:
        with open(os.path.join(root, "calibration.json")) as f:
            return js_json(json.load(f))
    except (OSError, ValueError, TypeError):
        return "{}"


def main():
    out = sys.argv[1]
    frame = [0] * 512
    for p in sys.argv[2:]:
        ch, val = p.split("=", 1)
        frame[int(ch) - 1] = int(val)
    decoded = [decode_fixture(frame, f) for f in FIXTURES]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    renderer = os.path.join(root, "static", "renderer.js")
    # Inject calibration.json so the headless render honours live tuning (the
    # file:// page can't fetch it). Empty {} -> renderer keeps its DEFAULTS.
    cal = load_calibration_literal(root)
    html = HTML.format(renderer="file://" + renderer, cal=cal,
                       decoded=js_json(decoded))
    with open(out, "w") as f:
        f.write(html)
    print(out)


if __name__ == "__main__":
    main()
