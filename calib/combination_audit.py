#!/usr/bin/env python3
"""
Combination-channel wall audit for the master laser fixture.

This is an evidence pass: drive practical multi-channel DMX states, capture the
real wall projection through caplog.py, then build real/virtual comparison
artifacts and a markdown report. It intentionally does not tune renderer
constants or calibration.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CAPDIR = ROOT / "calib" / "captures"
MANIFEST = CAPDIR / "manifest.jsonl"
DMX = ROOT / "calib" / "dmx_open.py"
CAPLOG = ROOT / "calib" / "caplog.py"
EXPORT_GRID = ROOT / "calib" / "export_grid.py"

MASTER_BASE = {
    1: 200, 2: 0, 3: 32, 4: 0, 5: 90, 6: 128, 7: 128, 8: 20,
    9: 0, 10: 0, 11: 0,
}


@dataclass(frozen=True)
class Combo:
    label: str
    name: str
    dmx: dict[int, int]
    family: str
    purpose: str
    classification: str
    mismatch: str
    timed: bool
    show_like: bool = False


def state(updates: dict[int, int] | None = None) -> dict[int, int]:
    frame = dict(MASTER_BASE)
    if updates:
        frame.update(updates)
    return frame


def stacked(updates: dict[int, int] | None = None) -> dict[int, int]:
    frame = state({
        4: 10,
        20: 32,
        21: 10,
        22: 90,
        23: 128,
        24: 128,
        25: 20,
        26: 0,
        27: 0,
        28: 0,
    })
    if updates:
        frame.update(updates)
    return frame


def channels(updates: dict[str, int]) -> dict[int, int]:
    return {int(k): v for k, v in updates.items()}


REPRESENTATIVE_LOOKS = [
    ("ring", 0, "ring/circle", "needs macro-shape preset"),
    ("line", 32, "horizontal line", "static wall-shape calibration ready"),
    ("dual", 48, "dual-dot", "needs macro-shape preset"),
    ("arc", 96, "dense dotted arc/swirl", "needs macro-shape preset"),
    ("uwave", 128, "U-wave dynamic", "needs timed/burst motion capture"),
    ("star3", 144, "three-star dynamic", "needs timed/burst motion capture"),
    ("swirl", 160, "compact swirl dynamic", "needs timed/burst motion capture"),
    ("poly", 176, "large star/polygon", "needs macro-shape preset"),
    ("row", 200, "dotted row/point macro", "needs macro-shape preset"),
]


def build_cases() -> list[Combo]:
    cases: list[Combo] = []

    for short, ch3, family, cls in REPRESENTATIVE_LOOKS:
        dynamic = ch3 >= 128
        cases.append(Combo(
            f"{short}_cyan", f"wall_combo_{short}_cyan",
            state({3: ch3, 8: 20}), family,
            "representative cyan base look", cls,
            "shape" if "macro-shape" in cls else "motion", dynamic,
            show_like=ch3 in {32, 96, 160, 176, 200},
        ))
        cases.append(Combo(
            f"{short}_red", f"wall_combo_{short}_red",
            state({3: ch3, 8: 8}), family,
            "same look with fixed red color", "needs color behavior calibration" if dynamic else "static wall-shape calibration ready",
            "color/shape" if dynamic else "color", dynamic,
            show_like=ch3 in {32, 160, 176},
        ))
        cases.append(Combo(
            f"{short}_zoom", f"wall_combo_{short}_zoom",
            state({3: ch3, 8: 20, 17: 100}), family,
            "zoom/size interaction", "needs timed/burst motion capture" if dynamic else "static wall-shape calibration ready",
            "zoom/shape", dynamic,
        ))
        cases.append(Combo(
            f"{short}_offset", f"wall_combo_{short}_offset",
            state({3: ch3, 8: 20, 5: 70, 6: 96, 7: 160}), family,
            "position and size interaction", "needs timed/burst motion capture" if dynamic else "static wall-shape calibration ready",
            "position/zoom/shape", dynamic,
        ))

    motion_common = [
        ("line_spin", 32, {"12": 150}, "spin speed/pose interaction"),
        ("line_hsweep", 32, {"15": 200}, "horizontal sweep interaction"),
        ("line_vsweep", 32, {"16": 200}, "vertical sweep interaction"),
        ("line_strobe", 32, {"1": 220, "11": 150}, "strobe interaction"),
        ("arc_spin", 96, {"12": 150}, "spin on dense dotted arc"),
        ("arc_hsweep", 96, {"15": 200}, "horizontal sweep on dotted arc"),
        ("arc_vsweep", 96, {"16": 200}, "vertical sweep on dotted arc"),
        ("arc_wave", 96, {"19": 200}, "wave deformation on dotted arc"),
        ("dyn160_spin", 160, {"12": 150}, "dynamic macro plus spin channel"),
        ("dyn176_strobe", 176, {"1": 220, "11": 150}, "dynamic macro plus strobe"),
    ]
    for label, ch3, updates, purpose in motion_common:
        cases.append(Combo(
            label, f"wall_combo_{label}", state({3: ch3, 8: 20, **channels(updates)}),
            "motion/show modifier", purpose, "needs timed/burst motion capture",
            "motion/strobe/shape", True, show_like=True,
        ))

    stacked_cases = [
        ("stack_line_arc", {"3": 32, "8": 20, "20": 32, "21": 10, "25": 8}, "primary cyan line plus red second pattern"),
        ("stack_ring_line", {"3": 0, "8": 20, "20": 32, "21": 60, "25": 28}, "cyan ring plus magenta second line selection"),
        ("stack_arc_dot", {"3": 96, "8": 20, "20": 64, "21": 20, "22": 70, "25": 20}, "dotted arc plus smaller second pattern"),
        ("stack_dyn_static", {"3": 160, "8": 20, "20": 32, "21": 10, "25": 8}, "dynamic primary plus static second pattern"),
        ("stack_offset", {"3": 32, "8": 20, "6": 96, "7": 160, "20": 32, "21": 10, "23": 192, "24": 64, "25": 8}, "opposed primary/second positions"),
        ("stack_second_spin", {"3": 32, "8": 20, "20": 32, "21": 10, "25": 20, "29": 150}, "second-pattern rotation speed"),
        ("stack_second_sweep", {"3": 32, "8": 20, "20": 32, "21": 10, "25": 20, "32": 200}, "second-pattern horizontal sweep"),
        ("stack_second_zoom", {"3": 32, "8": 20, "20": 32, "21": 10, "22": 210, "25": 20, "34": 100}, "second-pattern size/zoom interaction"),
    ]
    for label, updates, purpose in stacked_cases:
        timed = any(k in updates for k in {"29", "32", "33", "34"}) or updates.get("3", 0) >= 128
        cases.append(Combo(
            label, f"wall_combo_{label}",
            stacked(channels(updates)),
            "stacked output", purpose,
            "needs stacked-pattern support" if not timed else "needs timed/burst motion capture",
            "stacked pattern/motion" if timed else "stacked pattern",
            timed, show_like=True,
        ))

    show_states = [
        ("show_build_cyan_wide", {"3": 32, "4": 10, "5": 70, "6": 128, "7": 128, "8": 20, "17": 80}, "build-up wide cyan fan"),
        ("show_drop_magenta_spin", {"3": 96, "4": 10, "5": 90, "8": 28, "12": 150}, "drop-impact magenta spin"),
        ("show_drop_red_strobe", {"1": 230, "3": 32, "4": 10, "5": 90, "8": 8, "11": 150}, "drop-impact red strobe"),
        ("show_sweep_cyan", {"3": 32, "4": 10, "5": 90, "8": 20, "15": 200}, "cyan horizontal sweep"),
        ("show_dynamic_pink", {"3": 160, "4": 10, "8": 8}, "dynamic pink/red compact swirl"),
        ("show_stack_contrast", {"3": 32, "4": 10, "8": 20, "20": 32, "21": 10, "25": 8, "23": 192}, "cyan primary plus red offset second layer"),
    ]
    for label, updates, purpose in show_states:
        timed = any(k in updates for k in {"11", "12", "15", "16"}) or updates.get("3", 0) >= 128
        cls = "used in SoundSwitch show, high priority" if timed else "static wall-shape calibration ready"
        cases.append(Combo(
            label, f"wall_combo_{label}",
            state(channels(updates)),
            "curated SoundSwitch-style state", purpose, cls,
            "motion/strobe/shape" if timed else "shape/stacked pattern",
            timed, show_like=True,
        ))

    return cases


def dmx_spec(frame: dict[int, int]) -> str:
    return ",".join(f"{ch}={frame[ch]}" for ch in sorted(frame))


def run(cmd: list[str], **kwargs) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)


def capture(args: argparse.Namespace) -> None:
    cases = build_cases()
    selected = {x.strip() for x in args.labels.split(",") if x.strip()}
    if selected:
        cases = [c for c in cases if c.label in selected]
    for idx, case in enumerate(cases, 1):
        note = (
            f"wall combination audit {idx}/{len(cases)}: {case.label}; "
            f"{case.purpose}; classification={case.classification}; "
            "iPhone Continuity Camera; left projection master ROI; no haze"
        )
        run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
        run([sys.executable, str(DMX), "set", *dmx_spec(case.dmx).split(",")], stdout=subprocess.DEVNULL)
        time.sleep(args.hold)
        cap_cmd = [sys.executable, str(CAPLOG)]
        if args.screen:
            cap_cmd.append("--screen")
        else:
            cap_cmd.extend(["--device", args.device])
        cap_cmd.extend([case.name, note])
        run(cap_cmd)
    run([sys.executable, str(DMX), "blackout"])


def crop_roi(image: Image.Image, roi: tuple[float, float, float, float]) -> Image.Image:
    w, h = image.size
    x0, y0, x1, y1 = roi
    return image.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))


def paste_scaled(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    scale = min(bw / image.width, bh / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    canvas.paste(resized, (x0 + (bw - resized.width) // 2, y0 + (bh - resized.height) // 2))


def make_real_sheet(cases: list[Combo], out: Path, cols: int, roi: tuple[float, float, float, float]) -> Path:
    cell_w, cell_h, label_h = 260, 170, 24
    rows = (len(cases) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (16, 16, 16))
    draw = ImageDraw.Draw(sheet)
    for idx, case in enumerate(cases):
        path = CAPDIR / f"{case.name}.png"
        if not path.exists():
            raise SystemExit(f"missing capture: {path}")
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle([x, y, x + cell_w, y + label_h], fill=(0, 0, 0))
        draw.text((x + 5, y + 7), case.label, fill=(255, 255, 0))
        im = crop_roi(Image.open(path).convert("RGB"), roi)
        paste_scaled(sheet, im, (x, y + label_h, x + cell_w, y + cell_h))
    sheet.save(out)
    return out


def export_virtual(cases: list[Combo], out: Path, cols: int) -> Path:
    specs = [f"{case.label}|{dmx_spec(case.dmx)}" for case in cases]
    env = os.environ.copy()
    env["VLN_SINGLE_FIXTURE"] = "1"
    width = cols * 300
    rows = (len(cases) + cols - 1) // cols
    height = rows * 190
    run([sys.executable, str(EXPORT_GRID), str(out), f"{width}x{height}", *specs], env=env)
    return out


def make_comparison(real: Path, virtual: Path, out: Path) -> Path:
    real_im = Image.open(real).convert("RGB")
    virt_im = Image.open(virtual).convert("RGB")
    width = max(real_im.width, virt_im.width)
    label_h = 30
    canvas = Image.new("RGB", (width, label_h + real_im.height + label_h + virt_im.height), (14, 14, 14))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, width, label_h], fill=(0, 0, 0))
    draw.text((8, 8), "REAL WALL COMBINATION AUDIT - master ROI", fill=(255, 255, 255))
    canvas.paste(real_im, ((width - real_im.width) // 2, label_h))
    y = label_h + real_im.height
    draw.rectangle([0, y, width, y + label_h], fill=(0, 0, 0))
    draw.text((8, y + 8), "VIRTUAL COMBINATION AUDIT - same DMX, current renderer", fill=(255, 255, 255))
    canvas.paste(virt_im, ((width - virt_im.width) // 2, y + label_h))
    canvas.save(out)
    return out


def latest_manifest_by_name() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not MANIFEST.exists():
        return out
    for line in MANIFEST.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = entry.get("name")
        if name:
            out[name] = entry
    return out


def metrics(name: str, roi: tuple[float, float, float, float]) -> dict:
    path = CAPDIR / f"{name}.png"
    if not path.exists():
        return {"pixels": 0}
    im = crop_roi(Image.open(path).convert("RGB"), roi)
    pix = im.load()
    coords = []
    colors = {"red": 0, "cyan": 0, "blue": 0, "magenta": 0, "white": 0}
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = pix[x, y]
            tests = {
                "red": r > 135 and g < 100 and b < 115,
                "cyan": g > 95 and b > 120 and r < 100,
                "blue": b > 130 and r < 105 and g < 140,
                "magenta": r > 130 and b > 100 and g < 110,
                "white": r > 150 and g > 150 and b > 150,
            }
            if any(tests.values()):
                coords.append((x, y))
                for key, hit in tests.items():
                    colors[key] += int(hit)
    if not coords:
        return {"pixels": 0}
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return {
        "pixels": len(coords),
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "center": [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)],
        "dominant": max(colors, key=colors.get),
    }


def write_report(
    cases: list[Combo],
    report: Path,
    real: Path,
    virtual: Path,
    comparison: Path,
    roi: tuple[float, float, float, float],
) -> Path:
    manifest = latest_manifest_by_name()
    lines = [
        "# Combination-channel wall audit",
        "",
        "Master fixture wall-pattern combination audit using iPhone Continuity Camera device 2, no haze, fixed camera, and left projection as the master ROI.",
        "",
        "No renderer behavior, haze/glow/bloom, Laser 2 override, or calibration numbers were changed in this audit.",
        "",
        "## Artifacts",
        f"- Combination contact sheet: `{real}`",
        f"- Virtual render sheet: `{virtual}`",
        f"- Real-vs-virtual comparison sheet: `{comparison}`",
        "",
        "## Scope",
        "- Representative primary CH3 looks: ring/circle, horizontal line, dual-dot, dense dotted arc/swirl, U-wave dynamic, three-star dynamic, compact swirl dynamic, large star/polygon, dotted row/point macro.",
        "- Modifiers tested: fixed color, zoom, position/size offset, spin, horizontal sweep, vertical sweep, strobe, wave, and stacked second-pattern states.",
        "- No concrete SoundSwitch show preset file was found in this repo; `show_*` states below are curated SoundSwitch-style states from the observed fixture behavior, not imported cues.",
        "",
        "## Tested Combinations",
        "",
        "| label | family | DMX state | visual behavior / purpose | classification | mismatch type | still enough | capture | metrics |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for case in cases:
        entry = manifest.get(case.name, {})
        logged = entry.get("dmx") or {str(k): v for k, v in case.dmx.items()}
        logged_spec = " ".join(f"CH{int(k)}={v}" for k, v in sorted(logged.items(), key=lambda kv: int(kv[0])))
        m = metrics(case.name, roi)
        still = "no - timed/burst needed" if case.timed else "yes"
        lines.append(
            f"| {case.label} | {case.family} | `{logged_spec}` | {case.purpose} | "
            f"{case.classification} | {case.mismatch} | {still} | "
            f"`calib/captures/{case.name}.png` | pixels={m.get('pixels', 0)} bbox={m.get('bbox', [])} dominant={m.get('dominant', '')} |"
        )

    high = [c for c in cases if c.show_like or c.classification.startswith("used in SoundSwitch")]
    timed = [c for c in cases if c.timed]
    stacked_cases = [c for c in cases if "stack" in c.label or "stacked" in c.family]
    lines.extend([
        "",
        "## Discovered Interaction Patterns",
        "",
        "- Static CH3 families keep responding to CH8 fixed colours, CH17 zoom, and CH5/CH6/CH7 wall geometry modifiers.",
        "- Dynamic CH3 families identify distinct macro shapes in still frames, but their loop timing, colour phase, and whether modifier channels are ignored or blended need timed evidence.",
        "- CH11 strobe can only be sampled as an on/off still phase; rate and duty need burst capture.",
        "- CH12, CH15, and CH16 produce show-important motion states, but still frames only identify the visual family and sampled phase.",
        "- CH4-enabled stacked states add a second projected pattern block; this is a separate renderer capability concern from simple first-pattern geometry.",
        "- Second-pattern motion channels matter only after CH4 enables stacked output.",
        "",
        "## Mismatch Ranking",
        "",
        "1. Renderer model mismatch: the physical wall evidence is mostly closed projected figures, dots, rows, waves, and small shape clusters; the current virtual render is still an aerial beam-fan model from two apertures.",
        "2. Macro-shape mismatch: CH3 representative looks need calibrated shape presets before fine geometry tuning will be meaningful.",
        "3. Stacked-output mismatch: CH4 plus CH20-36 produces a second pattern block that needs explicit support independent of first-pattern geometry.",
        "4. Motion-phase ambiguity: CH12, CH15, CH16, dynamic CH3 macros, strobe, and second-pattern motion channels cannot be tuned from single still frames.",
        "5. Position/blanking mismatch: CH5/CH6/CH7 and sweep channels can move sampled frames partially or fully out of the master ROI; zero-pixel stills are sampled phase evidence, not proof of no output.",
        "6. Zoom mismatch: CH17 and CH34 visibly alter wall scale, but the current virtual fan zoom does not map cleanly to wall-projected figure scale.",
        "7. Dynamic color mismatch: fixed CH8 red/cyan states are identifiable, but dynamic/chase timing and color phase still need timed capture.",
        "",
        "## Channels And Combinations That Matter Most",
        "",
        "- First-pattern show looks: CH3 + CH8 + CH5/CH6/CH7 + CH17.",
        "- First-pattern motion looks: CH3 + CH12/CH15/CH16, plus CH11 for strobe.",
        "- Dynamic/drop looks: CH3 values 128-255 with CH8 fixed/effect color and optional CH12/CH11.",
        "- Stacked looks: CH4 enabled with CH20/CH21/CH22/CH23/CH24/CH25, then CH29/CH32/CH34 only when second-pattern motion/size is needed.",
        "- Low-value/defer in this pass: auto/sound/demo behavior, haze/glow/bloom, and exhaustive second-pattern tuning.",
        "",
        "## High-priority SoundSwitch-style States",
        "",
    ])
    for case in high:
        lines.append(f"- `{case.label}`: `{dmx_spec(case.dmx).replace(',', ' ')}` - {case.purpose}")
    lines.extend([
        "",
        "## Timed/Burst Capture Required",
        "",
    ])
    for case in timed:
        lines.append(f"- `{case.label}`: {case.purpose} ({case.mismatch})")
    lines.extend([
        "",
        "## Stacked-output States",
        "",
    ])
    for case in stacked_cases:
        lines.append(f"- `{case.label}`: `{dmx_spec(case.dmx).replace(',', ' ')}` - {case.purpose}")
    lines.extend([
        "",
        "## Recommended Next Step",
        "",
        "Do a timed/burst motion pass for a small subset instead of changing renderer constants from stills:",
        "",
        "1. `line_spin`, `line_hsweep`, `line_vsweep`, and `line_strobe` for first-pattern motion/strobe timing.",
        "2. `dyn160_spin` and `show_dynamic_pink` for dynamic macro loop and colour phase behavior.",
        "3. `stack_second_spin` and `stack_second_sweep` for CH4-enabled stacked-output motion.",
        "",
        "After timed evidence exists, implement calibrated preset families for the highest-priority show-style states rather than adding broad renderer art changes.",
    ])
    report.write_text("\n".join(lines) + "\n")
    return report


def build(args: argparse.Namespace) -> None:
    roi_vals = [float(x) for x in args.roi.split(",")]
    if len(roi_vals) != 4:
        raise SystemExit("--roi must be x0,y0,x1,y1")
    roi = tuple(roi_vals)  # type: ignore[assignment]
    cases = build_cases()
    real = make_real_sheet(cases, Path(args.real), args.cols, roi)
    virtual = export_virtual(cases, Path(args.virtual), args.cols)
    comparison = make_comparison(real, virtual, Path(args.comparison))
    report = write_report(cases, Path(args.report), real, virtual, comparison, roi)
    print(real)
    print(virtual)
    print(comparison)
    print(report)


def list_cases(_args: argparse.Namespace) -> None:
    for case in build_cases():
        timed = "timed" if case.timed else "still"
        print(f"{case.label}\t{timed}\t{dmx_spec(case.dmx)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list")
    ls.set_defaults(func=list_cases)

    cap = sub.add_parser("capture")
    cap.add_argument("--device", default="2")
    cap.add_argument("--screen", action="store_true",
                     help="capture the visible macOS screen instead of opening avfoundation")
    cap.add_argument("--hold", type=float, default=0.8)
    cap.add_argument("--labels", default="")
    cap.set_defaults(func=capture)

    b = sub.add_parser("build")
    b.add_argument("--roi", default="0,0,0.56,1")
    b.add_argument("--cols", type=int, default=6)
    b.add_argument("--real", default="/tmp/vln_combo_audit_real.png")
    b.add_argument("--virtual", default="/tmp/vln_combo_audit_virtual.png")
    b.add_argument("--comparison", default="/tmp/vln_combo_audit_comparison.png")
    b.add_argument("--report", default=str(ROOT / "docs" / "COMBINATION_CHANNEL_AUDIT.md"))
    b.set_defaults(func=build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
