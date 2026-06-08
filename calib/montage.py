#!/usr/bin/env python3
"""
Tile several calibration captures into one labeled image, so the agent can read
a whole channel-sweep (e.g. CH12 rotation at 0/40/80/127) in a single view and
compare poses side by side. Horizontal strip, each panel captioned.

Usage:
  montage.py out.png "CH6=40"=/tmp/calib/p6_40.png "CH6=128"=/tmp/calib/p6_128.png ...
"""
import sys
from PIL import Image, ImageDraw

THUMB_W = 360


def main():
    out = sys.argv[1]
    items = [(a.rsplit("=", 1)[0], a.rsplit("=", 1)[1]) for a in sys.argv[2:]]
    thumbs = []
    for label, path in items:
        im = Image.open(path).convert("RGB")
        h = max(1, int(im.height * THUMB_W / im.width))
        im = im.resize((THUMB_W, h))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, THUMB_W, 20], fill=(0, 0, 0))
        d.text((5, 4), label, fill=(255, 255, 0))
        thumbs.append(im)
    if not thumbs:
        sys.exit("no inputs")
    H = max(t.height for t in thumbs)
    W = sum(t.width for t in thumbs)
    canvas = Image.new("RGB", (W, H), (20, 20, 20))
    x = 0
    for t in thumbs:
        canvas.paste(t, (x, 0))
        x += t.width
    canvas.save(out)
    print(out)


if __name__ == "__main__":
    main()
