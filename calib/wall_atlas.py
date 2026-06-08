#!/usr/bin/env python3
"""
Capture and build a master-fixture wall projection atlas.

The atlas isolates CH3 first-pattern macro/group behavior by holding CH4=0
so the second pattern block is not enabled. It captures with caplog.py, keeps
DMX provenance in manifest.jsonl, crops the left wall projection as the master
fixture ROI, and exports matching single-fixture virtual sheets.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CAPDIR = ROOT / "calib" / "captures"
MANIFEST = CAPDIR / "manifest.jsonl"
DMX = ROOT / "calib" / "dmx_open.py"
CAPLOG = ROOT / "calib" / "caplog.py"
EXPORT_GRID = ROOT / "calib" / "export_grid.py"


def ch3_values(step: int) -> list[int]:
    vals = list(range(0, 256, step))
    if vals[-1] != 255:
        vals.append(255)
    return vals


def atlas_items(step: int) -> list[tuple[str, str, str]]:
    items = []
    for value in ch3_values(step):
        label = f"ch3_{value:03d}"
        name = f"wall_atlas_ch3_{value:03d}"
        dmx = f"1=200,3={value},4=0,5=90,6=128,7=128,8=20"
        items.append((label, name, dmx))
    return items


MODIFIER_ITEMS = [
    # Baseline static line family: useful for color, zoom, pan, spin, strobe.
    ("line32_base", "wall_mod_line32_base", "1=200,3=32,4=0,5=90,6=128,7=128,8=20"),
    ("line32_red", "wall_mod_line32_red", "1=200,3=32,4=0,5=90,6=128,7=128,8=8"),
    ("line32_flow", "wall_mod_line32_flow", "1=200,3=32,4=0,5=90,6=128,7=128,8=60,9=80"),
    ("line32_zoom", "wall_mod_line32_zoom", "1=200,3=32,4=0,5=90,6=128,7=128,8=20,17=100"),
    ("line32_panL", "wall_mod_line32_panL", "1=200,3=32,4=0,5=90,6=64,7=128,8=20"),
    ("line32_panR", "wall_mod_line32_panR", "1=200,3=32,4=0,5=90,6=192,7=128,8=20"),
    ("line32_spin", "wall_mod_line32_spin", "1=200,3=32,4=0,5=90,6=128,7=128,8=20,12=150"),
    ("line32_strobe", "wall_mod_line32_strobe", "1=220,3=32,4=0,5=90,6=128,7=128,8=20,11=150"),
    # Static animation/swirl family: color and movement modifiers still matter.
    ("swirl96_base", "wall_mod_swirl96_base", "1=200,3=96,4=0,5=90,6=128,7=128,8=20"),
    ("swirl96_red", "wall_mod_swirl96_red", "1=200,3=96,4=0,5=90,6=128,7=128,8=8"),
    ("swirl96_zoom", "wall_mod_swirl96_zoom", "1=200,3=96,4=0,5=90,6=128,7=128,8=20,17=100"),
    ("swirl96_spin", "wall_mod_swirl96_spin", "1=200,3=96,4=0,5=90,6=128,7=128,8=20,12=150"),
    ("swirl96_strobe", "wall_mod_swirl96_strobe", "1=220,3=96,4=0,5=90,6=128,7=128,8=20,11=150"),
    # Dynamic priority families: test whether common modifiers are ignored.
    ("dyn128_base", "wall_mod_dyn128_base", "1=200,3=128,4=0,5=90,6=128,7=128,8=20"),
    ("dyn128_red", "wall_mod_dyn128_red", "1=200,3=128,4=0,5=90,6=128,7=128,8=8"),
    ("dyn128_zoom", "wall_mod_dyn128_zoom", "1=200,3=128,4=0,5=90,6=128,7=128,8=20,17=100"),
    ("dyn144_base", "wall_mod_dyn144_base", "1=200,3=144,4=0,5=90,6=128,7=128,8=20"),
    ("dyn144_strobe", "wall_mod_dyn144_strobe", "1=220,3=144,4=0,5=90,6=128,7=128,8=20,11=150"),
    ("dyn176_base", "wall_mod_dyn176_base", "1=200,3=176,4=0,5=90,6=128,7=128,8=20"),
    ("dyn200_base", "wall_mod_dyn200_base", "1=200,3=200,4=0,5=90,6=128,7=128,8=20"),
    ("dyn248_base", "wall_mod_dyn248_base", "1=200,3=248,4=0,5=90,6=128,7=128,8=20"),
]


def run(cmd: list[str], **kwargs) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)


def capture_ch3(args: argparse.Namespace) -> None:
    for label, name, dmx in atlas_items(args.step):
        pairs = dmx.split(",")
        note = (
            f"wall CH3 atlas via iPhone Continuity Camera: {label}; "
            "CH4=0 first-pattern isolation; left projection is master ROI; no haze"
        )
        run([sys.executable, str(DMX), "base"], stdout=subprocess.DEVNULL)
        run([sys.executable, str(DMX), "set", *pairs], stdout=subprocess.DEVNULL)
        time.sleep(args.hold)
        run([sys.executable, str(CAPLOG), "--device", args.device, name, note])
    run([sys.executable, str(DMX), "blackout"])


def capture_modifiers(args: argparse.Namespace) -> None:
    for label, name, dmx in MODIFIER_ITEMS:
        pairs = dmx.split(",")
        note = (
            f"wall modifier pass via iPhone Continuity Camera: {label}; "
            "left projection is master ROI; no haze"
        )
        run([sys.executable, str(DMX), "base"], stdout=subprocess.DEVNULL)
        run([sys.executable, str(DMX), "set", *pairs], stdout=subprocess.DEVNULL)
        time.sleep(args.hold)
        run([sys.executable, str(CAPLOG), "--device", args.device, name, note])
    run([sys.executable, str(DMX), "blackout"])


def crop_roi(image: Image.Image, roi: tuple[float, float, float, float]) -> Image.Image:
    w, h = image.size
    x0, y0, x1, y1 = roi
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


def make_real_sheet(items: list[tuple[str, str, str]], out: Path, cols: int, roi: tuple[float, float, float, float]) -> Path:
    cell_w, cell_h, label_h = 240, 160, 22
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (16, 16, 16))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, name, _dmx) in enumerate(items):
        path = CAPDIR / f"{name}.png"
        if not path.exists():
            raise SystemExit(f"missing capture: {path}")
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle([x, y, x + cell_w, y + label_h], fill=(0, 0, 0))
        draw.text((x + 5, y + 6), label, fill=(255, 255, 0))
        im = crop_roi(Image.open(path).convert("RGB"), roi)
        paste_scaled(sheet, im, (x, y + label_h, x + cell_w, y + cell_h))
    sheet.save(out)
    return out


def export_virtual(items: list[tuple[str, str, str]], out: Path, cols: int) -> Path:
    specs = [f"{label}|{dmx}" for label, _name, dmx in items]
    env = os.environ.copy()
    env["VLN_SINGLE_FIXTURE"] = "1"
    size = f"{cols * 300}x{((len(items) + cols - 1) // cols) * 190}"
    run([sys.executable, str(EXPORT_GRID), str(out), size, *specs], env=env)
    return out


def make_comparison(real: Path, virtual: Path, out: Path) -> Path:
    real_im = Image.open(real).convert("RGB")
    virt_im = Image.open(virtual).convert("RGB")
    width = max(real_im.width, virt_im.width)
    label_h = 30
    canvas = Image.new("RGB", (width, label_h + real_im.height + label_h + virt_im.height), (14, 14, 14))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, width, label_h], fill=(0, 0, 0))
    draw.text((8, 8), "REAL WALL CH3 ATLAS - left projection master ROI", fill=(255, 255, 255))
    canvas.paste(real_im, ((width - real_im.width) // 2, label_h))
    y = label_h + real_im.height
    draw.rectangle([0, y, width, y + label_h], fill=(0, 0, 0))
    draw.text((8, y + 8), "VIRTUAL CH3 ATLAS - single fixture, same DMX", fill=(255, 255, 255))
    canvas.paste(virt_im, ((width - virt_im.width) // 2, y + label_h))
    canvas.save(out)
    return out


def latest_manifest_by_name() -> dict[str, dict]:
    by_name = {}
    if not MANIFEST.exists():
        return by_name
    for line in MANIFEST.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = entry.get("name")
        if name:
            by_name[name] = entry
    return by_name


def laser_metrics(path: Path, roi: tuple[float, float, float, float]) -> dict:
    im = crop_roi(Image.open(path).convert("RGB"), roi)
    pixels = im.load()
    coords = []
    red = cyan = blue = magenta = 0
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = pixels[x, y]
            is_cyan = g > 95 and b > 120 and r < 90
            is_red = r > 135 and g < 90 and b < 105
            is_blue = b > 130 and r < 95 and g < 130
            is_magenta = r > 130 and b > 100 and g < 100
            if is_cyan or is_red or is_blue or is_magenta:
                coords.append((x, y))
                red += int(is_red)
                cyan += int(is_cyan)
                blue += int(is_blue)
                magenta += int(is_magenta)
    if not coords:
        return {"pixels": 0}
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return {
        "pixels": len(coords),
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "center": [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)],
        "colors": {"red": red, "cyan": cyan, "blue": blue, "magenta": magenta},
    }


def ch3_family(value: int) -> tuple[str, str, str]:
    if value <= 15:
        return ("static line set 1", "static", "still sufficient for family; CH4 selection still matters")
    if value <= 31:
        return ("static line set 2", "static", "still sufficient for family; CH4 selection still matters")
    if value <= 47:
        return ("static line set 3 / dense", "static", "still sufficient for family; high EDM priority")
    if value <= 63:
        return ("static line set 4 / wide dense", "static", "still sufficient for family; high EDM priority")
    if value <= 127:
        return ("static animation bank", "static/selected animation", "still samples useful, CH4 selection important")
    if value <= 143:
        return ("dynamic line set 1", "motion-dependent", "timed/burst evidence needed")
    if value <= 159:
        return ("dynamic line set 2", "motion-dependent", "timed/burst evidence needed")
    if value <= 175:
        return ("dynamic animation bank", "motion-dependent", "timed/burst evidence needed; high EDM priority")
    return ("dynamic line set 3", "motion-dependent", "timed/burst evidence needed")


def write_report(
    items: list[tuple[str, str, str]],
    report: Path,
    real: Path,
    virtual: Path,
    comparison: Path,
    roi: tuple[float, float, float, float],
) -> Path:
    by_name = latest_manifest_by_name()
    rows = []
    groups: dict[str, list[int]] = {}
    for label, name, _dmx in items:
        value = int(label.rsplit("_", 1)[1])
        family, behavior, evidence = ch3_family(value)
        groups.setdefault(family, []).append(value)
        metrics = laser_metrics(CAPDIR / f"{name}.png", roi)
        rows.append((value, name, family, behavior, evidence, metrics, by_name.get(name, {})))

    lines = [
        "# Wall CH3 look atlas",
        "",
        "This atlas isolates the first-pattern CH3 macro/group channel with CH4=0, "
        "CH5=90, CH6/7=128, CH8=20. Captures use iPhone Continuity Camera device 2. "
        "The real sheet crops the left projection as the master fixture ROI because both physical units receive the same DMX.",
        "",
        "## Artifacts",
        f"- Real wall atlas: `{real}`",
        f"- Virtual atlas: `{virtual}`",
        f"- Comparison atlas: `{comparison}`",
        "",
        "## Discovered look families",
        "",
        "| DMX range sampled | representative | family | behavior | evidence status | representative capture | priority |",
        "|---|---:|---|---|---|---|---|",
    ]
    priority = {
        "static line set 3 / dense": "high",
        "static line set 4 / wide dense": "high",
        "dynamic animation bank": "high",
        "dynamic line set 3": "medium-high",
        "static animation bank": "medium",
        "dynamic line set 1": "medium",
        "dynamic line set 2": "medium",
        "static line set 1": "low-medium",
        "static line set 2": "low-medium",
    }
    for family, values in groups.items():
        rep = values[len(values) // 2]
        rep_name = f"wall_atlas_ch3_{rep:03d}"
        _family, behavior, evidence = ch3_family(rep)
        lines.append(
            f"| {min(values)}-{max(values)} step atlas | {rep} | {family} | {behavior} | "
            f"{evidence} | `calib/captures/{rep_name}.png` | {priority.get(family, 'medium')} |"
        )

    lines.extend([
        "",
        "## Per-sample observations",
        "",
        "| CH3 | family | logged DMX | laser pixels | bbox | center | dominant note |",
        "|---:|---|---|---:|---|---|---|",
    ])
    for value, name, family, _behavior, _evidence, metrics, entry in rows:
        dmx = entry.get("dmx", {})
        logged = " ".join(f"CH{k}={v}" for k, v in sorted((int(k), v) for k, v in dmx.items()))
        colors = metrics.get("colors", {})
        dominant = "none"
        if colors:
            dominant = max(colors, key=colors.get)
        lines.append(
            f"| {value} | {family} | `{logged}` | {metrics.get('pixels', 0)} | "
            f"`{metrics.get('bbox', '')}` | `{metrics.get('center', '')}` | {dominant} |"
        )

    lines.extend([
        "",
        "## Mismatch ranking by family",
        "",
        "1. Dynamic CH3>=128 families are motion-dependent; still frames capture a phase, not the loop.",
        "2. Wall projection vs aerial fan model remains the largest mismatch for all families.",
        "3. Static dense/wide families are the highest priority because they are common EDM beam looks.",
        "4. Static animation bank CH3=64-127 needs CH4 representative selection sweeps before detailed tuning.",
        "5. Sparse static line sets are lower priority unless they appear in actual SoundSwitch cues.",
        "",
        "## Deferred",
        "",
        "- Timed/burst capture for dynamic families, CH15/CH16 sweeps, CH12 spin rates, and CH19 waves.",
        "- Haze/glow/bloom tuning.",
        "- Laser 2 independent calibration.",
    ])
    report.write_text("\n".join(lines) + "\n")
    return report


def write_modifier_report(
    items: list[tuple[str, str, str]],
    report: Path,
    real: Path,
    virtual: Path,
    comparison: Path,
    roi: tuple[float, float, float, float],
) -> Path:
    by_name = latest_manifest_by_name()
    lines = [
        "# Wall modifier pass",
        "",
        "Limited modifier pass against representative wall look families. This is not an exhaustive combination sweep.",
        "",
        "## Artifacts",
        f"- Real wall modifier sheet: `{real}`",
        f"- Virtual modifier sheet: `{virtual}`",
        f"- Comparison sheet: `{comparison}`",
        "",
        "## Observations",
        "",
        "| case | representative family | logged DMX | still evidence | virtual mismatch | next action |",
        "|---|---|---|---|---|---|",
    ]
    family_for = {
        "line32": "horizontal line static",
        "swirl96": "dotted arc / compact swirl static-animation",
        "dyn128": "U-wave dynamic macro",
        "dyn144": "three-star dynamic macro",
        "dyn176": "large star polygon dynamic macro",
        "dyn200": "low dotted-row dynamic macro",
        "dyn248": "late ring dynamic macro",
    }
    for label, name, _dmx in items:
        entry = by_name.get(name, {})
        dmx = entry.get("dmx", {})
        logged = " ".join(f"CH{k}={v}" for k, v in sorted((int(k), v) for k, v in dmx.items()))
        key = label.split("_", 1)[0]
        metrics = laser_metrics(CAPDIR / f"{name}.png", roi)
        still = f"pixels={metrics.get('pixels', 0)} bbox={metrics.get('bbox', '')}"
        if "dyn" in key:
            mismatch = "renderer collapses dynamic macro to generic red fan"
            action = "timed/burst dynamic preset capture"
        elif "strobe" in label:
            mismatch = "still frame can catch on/off phase only"
            action = "timed strobe duty/rate capture"
        else:
            mismatch = "wall figure vs aerial fan model"
            action = "use for preset family; avoid broad renderer tuning"
        lines.append(
            f"| {label} | {family_for.get(key, key)} | `{logged}` | {still} | {mismatch} | {action} |"
        )
    lines.extend([
        "",
        "## Summary",
        "",
        "- Static line and static swirl families respond to color, zoom, pan, spin, and strobe modifiers in ways visible on the wall.",
        "- Dynamic macro families are distinct real looks, but still frames are insufficient to model motion loops.",
        "- Current virtual dynamic rendering is the largest atlas mismatch: it uses one generic red/pink fan for many visually different real macros.",
        "- No haze/glow/bloom conclusions should be drawn from this pass.",
    ])
    report.write_text("\n".join(lines) + "\n")
    return report


def build(args: argparse.Namespace) -> None:
    items = atlas_items(args.step)
    roi_parts = [float(x) for x in args.roi.split(",")]
    if len(roi_parts) != 4:
        raise SystemExit("--roi must be x0,y0,x1,y1")
    roi = tuple(roi_parts)  # type: ignore[assignment]
    real = make_real_sheet(items, Path(args.real), args.cols, roi)
    virtual = export_virtual(items, Path(args.virtual), args.cols)
    comparison = make_comparison(real, virtual, Path(args.comparison))
    report = write_report(items, Path(args.report), real, virtual, comparison, roi)
    print(real)
    print(virtual)
    print(comparison)
    print(report)


def build_modifiers(args: argparse.Namespace) -> None:
    roi_parts = [float(x) for x in args.roi.split(",")]
    if len(roi_parts) != 4:
        raise SystemExit("--roi must be x0,y0,x1,y1")
    roi = tuple(roi_parts)  # type: ignore[assignment]
    real = make_real_sheet(MODIFIER_ITEMS, Path(args.real), args.cols, roi)
    virtual = export_virtual(MODIFIER_ITEMS, Path(args.virtual), args.cols)
    comparison = make_comparison(real, virtual, Path(args.comparison))
    report = write_modifier_report(MODIFIER_ITEMS, Path(args.report), real, virtual, comparison, roi)
    print(real)
    print(virtual)
    print(comparison)
    print(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture-ch3")
    cap.add_argument("--step", type=int, default=8)
    cap.add_argument("--device", default="2")
    cap.add_argument("--hold", type=float, default=2.0)
    cap.set_defaults(func=capture_ch3)

    modcap = sub.add_parser("capture-modifiers")
    modcap.add_argument("--device", default="2")
    modcap.add_argument("--hold", type=float, default=2.0)
    modcap.set_defaults(func=capture_modifiers)

    b = sub.add_parser("build")
    b.add_argument("--step", type=int, default=8)
    b.add_argument("--cols", type=int, default=8)
    b.add_argument("--roi", default="0,0,0.56,1")
    b.add_argument("--real", default="/tmp/vln_wall_ch3_atlas_real.png")
    b.add_argument("--virtual", default="/tmp/vln_wall_ch3_atlas_virtual.png")
    b.add_argument("--comparison", default="/tmp/vln_wall_ch3_atlas_comparison.png")
    b.add_argument("--report", default=str(ROOT / "docs" / "WALL_CH3_LOOK_ATLAS.md"))
    b.set_defaults(func=build)

    mb = sub.add_parser("build-modifiers")
    mb.add_argument("--cols", type=int, default=7)
    mb.add_argument("--roi", default="0,0,0.56,1")
    mb.add_argument("--real", default="/tmp/vln_wall_modifier_real.png")
    mb.add_argument("--virtual", default="/tmp/vln_wall_modifier_virtual.png")
    mb.add_argument("--comparison", default="/tmp/vln_wall_modifier_comparison.png")
    mb.add_argument("--report", default=str(ROOT / "docs" / "WALL_MODIFIER_PASS.md"))
    mb.set_defaults(func=build_modifiers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
