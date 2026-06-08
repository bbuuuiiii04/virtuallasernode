#!/usr/bin/env python3
"""
Build wall calibration pass artifacts from captured master-fixture frames.

This keeps the capture order, DMX audit log, real contact sheet, virtual render
sheet, and aligned comparison sheet reproducible after the physical pass.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CAPDIR = ROOT / "calib" / "captures"
MANIFEST = CAPDIR / "manifest.jsonl"

ITEMS = [
    ("center", "wall_master_center_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=128,8=20"),
    ("left", "wall_master_left_cyan_dense", "1=200,3=32,4=10,5=90,6=64,7=128,8=20"),
    ("right", "wall_master_right_cyan_dense", "1=200,3=32,4=10,5=90,6=192,7=128,8=20"),
    ("up", "wall_master_up_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=200,8=20"),
    ("zoom", "wall_master_zoom_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=128,8=20,17=100"),
    ("spin", "wall_master_spin_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=128,8=20,12=150"),
    ("hsweep", "wall_master_hsweep_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=128,8=20,15=200"),
    ("vsweep", "wall_master_vsweep_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=128,8=20,16=200"),
    ("dynamic160", "wall_master_dynamic_160", "1=200,3=160,4=10,6=128,7=128"),
    ("ywave", "wall_master_ywave_cyan_dense", "1=200,3=32,4=10,5=90,6=128,7=128,8=20,19=200"),
]


def read_manifest() -> dict[str, dict]:
    entries = {}
    if not MANIFEST.exists():
        return entries
    for line in MANIFEST.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = entry.get("name")
        if name:
            entries[name] = entry
    return entries


def crop_roi(image: Image.Image, roi: tuple[float, float, float, float] | None) -> Image.Image:
    if not roi:
        return image
    x0, y0, x1, y1 = roi
    w, h = image.size
    return image.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))


def paste_scaled(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bw = x1 - x0
    bh = y1 - y0
    scale = min(bw / image.width, bh / image.height)
    nw = max(1, int(image.width * scale))
    nh = max(1, int(image.height * scale))
    resized = image.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, (x0 + (bw - nw) // 2, y0 + (bh - nh) // 2))


def make_contact_sheet(out: Path, roi: tuple[float, float, float, float] | None) -> Path:
    cell_w, cell_h, label_h = 300, 190, 24
    cols = 5
    rows = (len(ITEMS) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, name, _dmx) in enumerate(ITEMS):
        path = CAPDIR / f"{name}.png"
        if not path.exists():
            raise SystemExit(f"missing capture: {path}")
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle([x, y, x + cell_w, y + label_h], fill=(0, 0, 0))
        draw.text((x + 6, y + 6), label, fill=(255, 255, 0))
        im = crop_roi(Image.open(path).convert("RGB"), roi)
        paste_scaled(sheet, im, (x, y + label_h, x + cell_w, y + cell_h))
    sheet.save(out)
    return out


def make_dmx_log(out: Path) -> Path:
    entries = read_manifest()
    lines = [
        "# Wall master calibration DMX log",
        "",
        "Capture order matches the real/virtual comparison sheets.",
        "",
    ]
    for label, name, expected in ITEMS:
        entry = entries.get(name)
        lines.append(f"- {label}: `{name}.png`")
        lines.append(f"  - sent DMX: `{expected.replace(',', ' ')}`")
        if entry:
            dmx = entry.get("dmx", {})
            actual = " ".join(
                f"CH{ch}={value}"
                for ch, value in sorted((int(ch), value) for ch, value in dmx.items())
            )
            lines.append(f"  - logged DMX: `{actual}`")
            lines.append(f"  - note: {entry.get('note', '')}")
        else:
            lines.append("  - logged DMX: `MISSING manifest entry`")
        lines.append("")
    out.write_text("\n".join(lines))
    return out


def export_virtual(out: Path, size: str, single_fixture: str | None) -> Path:
    specs = [f"{label}|{dmx}" for label, _name, dmx in ITEMS]
    cmd = [sys.executable, str(ROOT / "calib" / "export_grid.py"), str(out), size] + specs
    env = os.environ.copy()
    if single_fixture:
        env["VLN_SINGLE_FIXTURE"] = single_fixture
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    return out


def make_comparison(real: Path, virtual: Path, out: Path) -> Path:
    real_im = Image.open(real).convert("RGB")
    virt_im = Image.open(virtual).convert("RGB")
    width = max(real_im.width, virt_im.width)
    label_h = 30
    canvas = Image.new("RGB", (width, label_h + real_im.height + label_h + virt_im.height), (14, 14, 14))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, width, label_h], fill=(0, 0, 0))
    draw.text((8, 8), "REAL WALL CAPTURE - master fixture", fill=(255, 255, 255))
    canvas.paste(real_im, ((width - real_im.width) // 2, label_h))
    y = label_h + real_im.height
    draw.rectangle([0, y, width, y + label_h], fill=(0, 0, 0))
    draw.text((8, y + 8), "VIRTUAL RENDER - same DMX values", fill=(255, 255, 255))
    canvas.paste(virt_im, ((width - virt_im.width) // 2, y + label_h))
    canvas.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", default="/tmp/vln_wall_master_real_contact_sheet.png")
    parser.add_argument("--virtual", default="/tmp/vln_wall_master_virtual_sheet.png")
    parser.add_argument("--comparison", default="/tmp/vln_wall_master_real_vs_virtual_comparison.png")
    parser.add_argument("--dmx-log", default=str(ROOT / "docs" / "CALIBRATION_WALL_MASTER_DMX_LOG.md"))
    parser.add_argument("--size", default="1500x380")
    parser.add_argument("--single-fixture", default="1")
    parser.add_argument("--roi", default="0,0,0.56,1",
                        help="fractional x0,y0,x1,y1 crop for the master projection; empty disables")
    args = parser.parse_args()

    roi = None
    if args.roi:
        parts = [float(x) for x in args.roi.split(",")]
        if len(parts) != 4:
            raise SystemExit("--roi must be x0,y0,x1,y1")
        roi = tuple(parts)  # type: ignore[assignment]
    real = make_contact_sheet(Path(args.real), roi)
    log = make_dmx_log(Path(args.dmx_log))
    virtual = export_virtual(Path(args.virtual), args.size, args.single_fixture)
    comparison = make_comparison(real, virtual, Path(args.comparison))
    print(real)
    print(virtual)
    print(comparison)
    print(log)


if __name__ == "__main__":
    main()
