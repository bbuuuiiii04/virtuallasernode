#!/usr/bin/env python3
"""
Full 36CH wall projection channel audit for the master fixture.

Each test changes one DMX channel from a stable baseline, captures through
caplog.py, and records exact DMX provenance in calib/captures/manifest.jsonl.
The report classifies every channel for calibration priority and whether timed
motion evidence is required.
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

MASTER_VISIBLE_BASELINE = {
    1: 200, 2: 0, 3: 32, 4: 0, 5: 90, 6: 128, 7: 128, 8: 20,
    9: 0, 10: 0, 11: 0,
}
SECOND_PATTERN_VISIBLE_BASELINE = {
    1: 200, 2: 0, 3: 32, 4: 10, 5: 90, 6: 128, 7: 128, 8: 20,
    9: 0, 10: 0, 11: 0, 20: 32, 21: 10, 22: 90, 23: 128,
    24: 128, 25: 20, 26: 0, 27: 0, 28: 0,
}
COLOR_EFFECT_BASELINE = {**MASTER_VISIBLE_BASELINE, 8: 60, 9: 0}
GRADIENT_BASELINE = {**MASTER_VISIBLE_BASELINE, 8: 245, 18: 0}
SECOND_COLOR_EFFECT_BASELINE = {**SECOND_PATTERN_VISIBLE_BASELINE, 25: 60, 26: 0}
SECOND_GRADIENT_BASELINE = {**SECOND_PATTERN_VISIBLE_BASELINE, 25: 245, 35: 0}

CHANNELS = {
    1: ("Dimmer / laser on-off", "0 off, 1-255 brightness"),
    2: ("Auto / sound active", "0-26 auto default, 27-127 auto speed, 128-255 sound sensitivity"),
    3: ("First pattern group / macro", "static 0-127, dynamic 128-255"),
    4: ("First pattern select / second-pattern enable", "static select; CH4>=1 enables second pattern"),
    5: ("First pattern size", "pattern size"),
    6: ("First horizontal position", "128 center, edges can blank"),
    7: ("First vertical position", "128 center, edges can blank"),
    8: ("First color", "fixed colors and color effects"),
    9: ("First color speed", "color effect speed/direction"),
    10: ("First line/dot scan", "line/dot scan modes"),
    11: ("First strobe", "strobe speed"),
    12: ("First rotation Z", "angle 1-127, speed 128-255"),
    13: ("First rotation X", "angle 1-127, speed 128-255"),
    14: ("First rotation Y", "angle 1-127, speed 128-255"),
    15: ("First horizontal movement", "position 1-127, speed 128-255"),
    16: ("First vertical movement", "position 1-127, speed 128-255"),
    17: ("First zoom", "size 1-127, speed 128-255"),
    18: ("First gradient", "gradient speed"),
    19: ("First X/Y wave", "1-127 X-wave, 128-255 Y-wave"),
    20: ("Second pattern group", "static-only group"),
    21: ("Second pattern select", "static pattern select"),
    22: ("Second pattern size", "second pattern size"),
    23: ("Second horizontal position", "second pattern H position"),
    24: ("Second vertical position", "second pattern V position"),
    25: ("Second color", "second pattern color"),
    26: ("Second color speed", "second color effect speed"),
    27: ("Second line/dot scan", "second line/dot scan"),
    28: ("Second strobe", "second strobe"),
    29: ("Second rotation Z", "second Z rotation"),
    30: ("Second rotation X", "second X rotation"),
    31: ("Second rotation Y", "second Y rotation"),
    32: ("Second horizontal movement", "second H movement"),
    33: ("Second vertical movement", "second V movement"),
    34: ("Second zoom", "second zoom"),
    35: ("Second gradient", "second gradient speed"),
    36: ("Second X/Y wave", "second X/Y wave"),
}

TEST_VALUES = {
    1: [0, 1, 80, 200, 255],
    2: [0, 27, 80, 128, 200, 255],
    4: [0, 1, 5, 20, 60, 130, 255],
    5: [0, 40, 90, 128, 210, 255],
    6: [0, 40, 64, 128, 192, 252, 255],
    7: [0, 40, 64, 128, 192, 252, 255],
    8: [0, 2, 6, 10, 14, 18, 22, 26, 30, 32, 36, 60, 150, 245],
    9: [0, 4, 64, 127, 200, 255],
    10: [0, 32, 64, 100, 128, 200, 255],
    11: [0, 1, 60, 128, 200, 255],
    12: [0, 1, 40, 80, 127, 150, 200, 255],
    13: [0, 1, 40, 80, 127, 150, 200, 255],
    14: [0, 1, 40, 80, 127, 150, 200, 255],
    15: [0, 1, 40, 64, 96, 127, 160, 200, 255],
    16: [0, 1, 40, 64, 96, 127, 160, 200, 255],
    17: [0, 1, 40, 80, 127, 160, 200, 255],
    18: [0, 1, 80, 160, 255],
    19: [0, 1, 64, 127, 128, 200, 255],
    20: [0, 16, 32, 48, 64, 96, 127],
    21: [0, 5, 20, 60, 130, 255],
    22: [0, 40, 90, 128, 210, 255],
    23: [0, 40, 64, 128, 192, 252, 255],
    24: [0, 40, 64, 128, 192, 252, 255],
    25: [0, 2, 6, 10, 14, 18, 22, 26, 30, 60],
    26: [0, 4, 64, 127, 200, 255],
    27: [0, 32, 64, 100, 128, 200, 255],
    28: [0, 1, 60, 128, 200, 255],
    29: [0, 40, 127, 150, 200, 255],
    30: [0, 40, 127, 150, 200, 255],
    31: [0, 40, 127, 150, 200, 255],
    32: [0, 1, 64, 127, 160, 200, 255],
    33: [0, 1, 64, 127, 160, 200, 255],
    34: [0, 1, 80, 127, 160, 200, 255],
    35: [0, 1, 80, 160, 255],
    36: [0, 1, 64, 127, 128, 200, 255],
}

CH3_EVIDENCE = [
    ("ch3_atlas", "wall_atlas_ch3_032", "1=200,3=32,4=0,5=90,6=128,7=128,8=20"),
    ("ch3_dynamic", "wall_atlas_ch3_144", "1=200,3=144,4=0,5=90,6=128,7=128,8=20"),
]


def run(cmd: list[str], **kwargs) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)


def frame_for(channel: int, value: int) -> dict[int, int]:
    frame = dict(SECOND_PATTERN_VISIBLE_BASELINE if channel >= 20 else MASTER_VISIBLE_BASELINE)
    if channel == 9:
        frame = dict(COLOR_EFFECT_BASELINE)
    if channel == 18:
        frame = dict(GRADIENT_BASELINE)
    if channel == 26:
        frame = dict(SECOND_COLOR_EFFECT_BASELINE)
    if channel == 35:
        frame = dict(SECOND_GRADIENT_BASELINE)
    frame[channel] = value
    return frame


def baseline_for(channel: int) -> tuple[str, dict[int, int]]:
    if channel == 9:
        return "COLOR_EFFECT_BASELINE", dict(COLOR_EFFECT_BASELINE)
    if channel == 18:
        return "GRADIENT_BASELINE", dict(GRADIENT_BASELINE)
    if channel == 26:
        return "SECOND_COLOR_EFFECT_BASELINE", dict(SECOND_COLOR_EFFECT_BASELINE)
    if channel == 35:
        return "SECOND_GRADIENT_BASELINE", dict(SECOND_GRADIENT_BASELINE)
    if channel >= 20:
        return "SECOND_PATTERN_VISIBLE_BASELINE", dict(SECOND_PATTERN_VISIBLE_BASELINE)
    return "MASTER_VISIBLE_BASELINE", dict(MASTER_VISIBLE_BASELINE)


def dmx_spec(frame: dict[int, int]) -> str:
    return ",".join(f"{ch}={frame[ch]}" for ch in sorted(frame))


def audit_items(channels: list[int] | None = None) -> list[tuple[int, int, str, str]]:
    out: list[tuple[int, int, str, str]] = []
    selected = channels or sorted(TEST_VALUES)
    for ch in selected:
        for val in TEST_VALUES[ch]:
            label = f"ch{ch:02d}_{val:03d}"
            name = f"wall_audit_ch{ch:02d}_{val:03d}"
            out.append((ch, val, label, name))
    return out


def capture(args: argparse.Namespace) -> None:
    channels = [int(x) for x in args.channels.split(",")] if args.channels else None
    last_channel = None
    for ch, val, label, name in audit_items(channels):
        if ch != last_channel:
            baseline_name, baseline = baseline_for(ch)
            base_capture = f"wall_audit_ch{ch:02d}_baseline"
            base_note = (
                f"wall channel audit baseline confirmation: CH{ch} from {baseline_name}; "
                "visible output must exist before target-channel values are tested"
            )
            run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
            run([sys.executable, str(DMX), "set", *dmx_spec(baseline).split(",")], stdout=subprocess.DEVNULL)
            time.sleep(args.hold)
            run([sys.executable, str(CAPLOG), "--device", args.device, base_capture, base_note])
            last_channel = ch
        frame = frame_for(ch, val)
        baseline_name, _baseline = baseline_for(ch)
        note = (
            f"wall channel audit: CH{ch}={val} {CHANNELS[ch][0]}; "
            f"one-channel sweep from {baseline_name}; iPhone Continuity Camera; "
            "left projection master ROI; no haze"
        )
        run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
        run([sys.executable, str(DMX), "set", *dmx_spec(frame).split(",")], stdout=subprocess.DEVNULL)
        time.sleep(args.hold)
        run([sys.executable, str(CAPLOG), "--device", args.device, name, note])
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


def make_sheet(items: list[tuple[str, str]], out: Path, cols: int, roi: tuple[float, float, float, float]) -> Path:
    cell_w, cell_h, label_h = 230, 155, 22
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (16, 16, 16))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, name) in enumerate(items):
        path = CAPDIR / f"{name}.png"
        if not path.exists():
            continue
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle([x, y, x + cell_w, y + label_h], fill=(0, 0, 0))
        draw.text((x + 5, y + 6), label, fill=(255, 255, 0))
        im = crop_roi(Image.open(path).convert("RGB"), roi)
        paste_scaled(sheet, im, (x, y + label_h, x + cell_w, y + cell_h))
    sheet.save(out)
    return out


def metrics(name: str, roi: tuple[float, float, float, float]) -> dict:
    path = CAPDIR / f"{name}.png"
    if not path.exists():
        return {"pixels": 0}
    im = crop_roi(Image.open(path).convert("RGB"), roi)
    pix = im.load()
    coords = []
    red = cyan = blue = magenta = white = 0
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = pix[x, y]
            is_red = r > 135 and g < 100 and b < 115
            is_cyan = g > 95 and b > 120 and r < 100
            is_blue = b > 130 and r < 105 and g < 140
            is_magenta = r > 130 and b > 100 and g < 110
            is_white = r > 150 and g > 150 and b > 150
            if is_red or is_cyan or is_blue or is_magenta or is_white:
                coords.append((x, y))
                red += int(is_red); cyan += int(is_cyan); blue += int(is_blue)
                magenta += int(is_magenta); white += int(is_white)
    if not coords:
        return {"pixels": 0}
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    colors = {"red": red, "cyan": cyan, "blue": blue, "magenta": magenta, "white": white}
    return {
        "pixels": len(coords),
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "center": [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)],
        "dominant": max(colors, key=colors.get),
    }


def latest_manifest_by_name() -> dict[str, dict]:
    out = {}
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


def classification(ch: int) -> tuple[str, str, str, list[str]]:
    high = {3, 4, 5, 6, 7, 8, 11, 12, 15, 16, 17}
    medium = {1, 9, 10, 13, 14, 18, 19, 20, 21, 22, 23, 24, 25, 28, 29, 32, 33, 34, 36}
    timed = {9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36}
    skipish = {2}
    if ch in high:
        bucket = "Deep calibrate now"
        priority = "high"
    elif ch in medium:
        bucket = "Light document now"
        priority = "medium"
    elif ch in skipish:
        bucket = "Skip/defer"
        priority = "skip"
    else:
        bucket = "Light document only"
        priority = "low"
    needs = []
    if ch in timed:
        needs.append("timed/burst")
    if ch >= 20:
        needs.append("second-pattern interaction")
    return bucket, priority, "yes" if ch in timed else "no", needs


def behavior_flags(ch: int) -> dict[str, str]:
    return {
        "visible": "yes",
        "static_shape": "yes" if ch in {3, 4, 5, 10, 17, 19, 20, 21, 22, 27, 34, 36} else "no",
        "motion": "yes" if ch in {2, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36} else "no",
        "color": "yes" if ch in {8, 9, 18, 25, 26, 35} else "no",
        "brightness_strobe": "yes" if ch in {1, 2, 10, 11, 27, 28} else "no",
        "position": "yes" if ch in {6, 7, 15, 16, 23, 24, 32, 33} else "no",
        "zoom": "yes" if ch in {5, 17, 22, 34} else "no",
        "auto_demo": "yes" if ch == 2 else "no",
    }


def write_report(report: Path, channel_sheets: dict[int, Path], roi: tuple[float, float, float, float]) -> Path:
    manifest = latest_manifest_by_name()
    lines = [
        "# Full DMX channel wall audit",
        "",
        "Master fixture wall-pattern audit using iPhone Continuity Camera device 2, no haze, fixed camera, left wall projection cropped as the master ROI. Channels 1-19 use the first-pattern baseline. Channels 20-36 use a second-pattern-active baseline because CH4>=1 is required to enable the second pattern block.",
        "",
        "## Baselines",
        f"- `MASTER_VISIBLE_BASELINE`: `{dmx_spec(MASTER_VISIBLE_BASELINE)}`",
        "  - Chosen because it turns output on, disables strobe/sound/random modes, selects a visible static CH3 line-family look, uses fixed cyan, centers position, and keeps motion neutral for safe wall projection.",
        f"- `SECOND_PATTERN_VISIBLE_BASELINE`: `{dmx_spec(SECOND_PATTERN_VISIBLE_BASELINE)}`",
        "  - Chosen because CH4>=1 is required before CH20-36 can visibly affect the stacked second-pattern block.",
        f"- `COLOR_EFFECT_BASELINE`: `{dmx_spec(COLOR_EFFECT_BASELINE)}`",
        "  - Used for CH9 because color speed has no visible timing dependency unless CH8 is in an animated color/effect range.",
        f"- `GRADIENT_BASELINE`: `{dmx_spec(GRADIENT_BASELINE)}`",
        "  - Used for CH18 because gradient speed needs CH8 in the gradient/effect range.",
        f"- `SECOND_COLOR_EFFECT_BASELINE`: `{dmx_spec(SECOND_COLOR_EFFECT_BASELINE)}`",
        "  - Used for CH26 because second color speed needs CH25 in an animated color/effect range.",
        f"- `SECOND_GRADIENT_BASELINE`: `{dmx_spec(SECOND_GRADIENT_BASELINE)}`",
        "  - Used for CH35 because second gradient speed needs CH25 in the gradient/effect range.",
        "- CH3 full look-family atlas evidence: `docs/WALL_CH3_LOOK_ATLAS.md`",
        "- For every audited channel, `wall_audit_chXX_baseline.png` confirms visible output under the correct baseline before target values are tested.",
        "",
        "## Channel Dependencies",
        "",
        "- CH9 depends on CH8 being in a color-effect range; otherwise speed changes can look inactive.",
        "- CH18 depends on CH8 gradient/effect modes.",
        "- CH20-36 depend on CH4>=1 to enable second-pattern stacked output.",
        "- CH26 depends on CH25 being in a color-effect range.",
        "- CH35 depends on CH25 gradient/effect modes.",
        "- CH11/CH28 strobe, CH12-CH17/CH29-CH34 motion/zoom speed, and CH19/CH36 wave channels require timed/burst capture for rate/phase; still frames only show sampled phase.",
        "- CH2 auto/sound behavior can depend on ambient audio and is not deterministic show previz control.",
        "",
        "## Important Contact Sheets",
    ]
    for ch in sorted(channel_sheets):
        bucket, priority, timed, _needs = classification(ch)
        if priority in {"high", "medium"}:
            lines.append(f"- CH{ch:02d} {CHANNELS[ch][0]}: `{channel_sheets[ch]}`")
    lines.extend([
        "",
        "## Channel Summary",
        "",
        "| CH | Function | Expected behavior | Visible | Static shape | Motion | Color | Brightness/strobe | Position | Zoom/size | Auto/demo | SoundSwitch priority | Class | Timed needed | Evidence |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for ch in range(1, 37):
        func, expected = CHANNELS[ch]
        flags = behavior_flags(ch)
        bucket, priority, timed, needs = classification(ch)
        if ch == 3:
            evidence = "`/tmp/vln_wall_ch3_atlas_comparison_dynamiccolorfix.png`"
        else:
            vals = TEST_VALUES.get(ch, [])
            baseline = f"wall_audit_ch{ch:02d}_baseline"
            base_pixels = metrics(baseline, roi).get("pixels", 0)
            evidence_names = [f"wall_audit_ch{ch:02d}_{v:03d}" for v in vals]
            pix = []
            for name in evidence_names:
                m = metrics(name, roi)
                pix.append(str(m.get("pixels", 0)))
            evidence = f"`{channel_sheets.get(ch, '')}` baseline_pixels={base_pixels} value_pixels={','.join(pix[:8])}{'...' if len(pix) > 8 else ''}"
        lines.append(
            f"| {ch} | {func} | {expected} | {flags['visible']} | {flags['static_shape']} | "
            f"{flags['motion']} | {flags['color']} | {flags['brightness_strobe']} | {flags['position']} | "
            f"{flags['zoom']} | {flags['auto_demo']} | {priority} | {bucket} | {timed} | {evidence} |"
        )
    lines.extend([
        "",
        "## High-priority channels",
        "",
        "- CH3 pattern/macro group: broad look-family selector; already atlas-swept.",
        "- CH4 pattern select and second-pattern enable: changes selected figures and activates stacked output.",
        "- CH5/CH17 size and zoom: strong wall geometry impact.",
        "- CH6/CH7 position: strong pan/vertical offset and blanking behavior.",
        "- CH8 color: direct fixed/effect color control.",
        "- CH11 strobe: show-critical but still frames only catch phase.",
        "- CH12/CH15/CH16 rotation and movement: show-critical, timed capture required.",
        "",
        "## Timed/burst capture required",
        "",
        "- CH9 color chase timing",
        "- CH11 and CH28 strobe rate/duty",
        "- CH12-CH16 first-pattern rotations/movement",
        "- CH17 zoom speed bank",
        "- CH18 gradient timing",
        "- CH19 and CH36 wave deformation",
        "- CH26/CH35 second-pattern color/gradient timing",
        "- CH29-CH34 second-pattern rotation/movement/zoom speed banks",
        "- CH3 dynamic macro motion loops",
        "",
        "## Skip/defer",
        "",
        "- CH2 auto/sound/demo behavior: not useful for deterministic SoundSwitch previz except to document as sound-gated/demo.",
        "- Deep second-pattern tuning can wait until first-pattern preset families are stable; document it as stacked-output behavior for now.",
        "- Haze/glow/bloom remains deferred.",
    ])
    report.write_text("\n".join(lines) + "\n")
    return report


def build(args: argparse.Namespace) -> None:
    roi_vals = [float(x) for x in args.roi.split(",")]
    if len(roi_vals) != 4:
        raise SystemExit("--roi must be x0,y0,x1,y1")
    roi = tuple(roi_vals)  # type: ignore[assignment]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    channel_sheets = {}
    for ch in sorted(TEST_VALUES):
        base_name, _base = baseline_for(ch)
        items = [(base_name, f"wall_audit_ch{ch:02d}_baseline")]
        items.extend((f"CH{ch}={v}", f"wall_audit_ch{ch:02d}_{v:03d}") for v in TEST_VALUES[ch])
        channel_sheets[ch] = make_sheet(items, outdir / f"vln_channel_audit_ch{ch:02d}.png", args.cols, roi)
    overview_items = []
    for ch in sorted(TEST_VALUES):
        overview_items.append((f"CH{ch} base", f"wall_audit_ch{ch:02d}_baseline"))
        vals = TEST_VALUES[ch]
        for v in vals[: min(3, len(vals))]:
            overview_items.append((f"CH{ch}={v}", f"wall_audit_ch{ch:02d}_{v:03d}"))
    overview = make_sheet(overview_items, Path(args.overview), 8, roi)
    report = write_report(Path(args.report), channel_sheets, roi)
    print(overview)
    print(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--device", default="2")
    cap.add_argument("--hold", type=float, default=0.8)
    cap.add_argument("--channels", default="")
    cap.set_defaults(func=capture)

    b = sub.add_parser("build")
    b.add_argument("--roi", default="0,0,0.56,1")
    b.add_argument("--cols", type=int, default=8)
    b.add_argument("--outdir", default="/tmp/vln_channel_audit")
    b.add_argument("--overview", default="/tmp/vln_channel_audit_overview.png")
    b.add_argument("--report", default=str(ROOT / "docs" / "DMX_CHANNEL_AUDIT.md"))
    b.set_defaults(func=build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
