#!/usr/bin/env python3
"""
Generate a render_grid HTML page and export it to PNG with headless Chrome.

Use Chrome's wall-clock --timeout instead of --virtual-time-budget. The renderer
has a continuous requestAnimationFrame loop, and virtual time can wait forever on
that kind of page. A short wall-clock timeout gives the page enough time to draw
and then exits reliably.
"""
import os
import subprocess
import sys
import tempfile
import shutil

import render_grid

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    if len(sys.argv) < 4:
        raise SystemExit(
            "usage: export_grid.py OUT.png WIDTHxHEIGHT label|CH=VAL[,CH=VAL...] ..."
        )
    out = os.path.abspath(sys.argv[1])
    size = sys.argv[2]
    width = int(size.split("x", 1)[0])
    os.environ["VLN_GRID_COLS"] = str(max(1, width // render_grid.CELL_W))
    td = tempfile.mkdtemp(prefix="vln_export_grid_")
    html = os.path.join(td, "grid.html")
    profile = os.path.join(td, "chrome-profile")
    render_grid.write_grid(html, sys.argv[3:])

    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--no-first-run",
        "--hide-scrollbars",
        "--user-data-dir=" + profile,
        "--timeout=3000",
        "--screenshot=" + out,
        "--window-size=" + size,
        "file://" + html,
    ]
    try:
        try:
            subprocess.run(cmd, check=True, timeout=10, start_new_session=True)
        except subprocess.TimeoutExpired as exc:
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(out)
                return
            raise SystemExit(f"Chrome export timed out before writing {out}") from exc
        except subprocess.CalledProcessError as exc:
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(out)
                return
            raise
        print(out)
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    main()
