#!/usr/bin/env python3
"""
Timed/burst motion calibration pass for CH1-19 only.

This script is intentionally evidence-only. It drives deterministic first-pattern
DMX states, captures short wall-projection videos from the master fixture, and
builds frame strips/contact sheets plus a markdown motion characterization
report. It does not touch renderer behavior or calibration.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DMX = ROOT / "calib" / "dmx_open.py"
DEFAULT_ROOT = Path("/tmp/vln_timed_motion_ch1_19")
FRAME_RATE = 30
SIZE = "1280x720"
ROI = (0.0, 0.0, 0.56, 1.0)

ANGLE_VALUES = (0, 1, 32, 64, 96, 127)
POSITION_VALUES = (0, 1, 32, 64, 96, 127)
SPEED_VALUES_FINE = (128, 136, 144, 152, 160, 176, 192, 208, 224, 240, 255)
STROBE_VALUES_FINE = (0, 1, 16, 32, 48, 64, 96, 128, 160, 192, 224, 255)
COLOR_SPEED_VALUES_FINE = (0, 1, 4, 16, 32, 64, 96, 127, 128, 144, 160, 192, 224, 255)
GRADIENT_VALUES_FINE = (0, 1, 16, 32, 64, 96, 128, 160, 192, 224, 255)

GROUP_DIRS = {
    "controls": "00_controls",
    "ch04_pattern_select": "ch04_pattern_selection",
    "ch05_06_07_position": "ch05_ch06_ch07_position_offset",
    "ch08_color": "ch08_ch09_color_timing",
    "ch11_strobe": "ch11_strobe",
    "ch12_spin": "ch12_rotation_z",
    "ch13_rot_x": "ch13_rotation_x",
    "ch14_rot_y": "ch14_rotation_y",
    "ch15_hsweep": "ch15_horizontal_movement",
    "ch16_vsweep": "ch16_vertical_movement",
    "ch17_zoom": "ch17_zoom",
    "ch18_gradient": "ch18_gradient",
    "ch19_wave": "ch19_x_y_wave",
    "combos_ch1_19": "zz_combinations_ch1_19",
}

GROUP_PRIMARY_CHANNEL = {
    "ch04_pattern_select": 4,
    "ch11_strobe": 11,
    "ch12_spin": 12,
    "ch13_rot_x": 13,
    "ch14_rot_y": 14,
    "ch15_hsweep": 15,
    "ch16_vsweep": 16,
    "ch17_zoom": 17,
    "ch18_gradient": 18,
    "ch19_wave": 19,
}


BASES = {
    # CH4 is intentionally nonzero for the main baselines because the fixture
    # uses CH4 as the first-pattern bank selector inside each deterministic CH3
    # range. CH20-36 remain omitted, so second-pattern controls are still out of
    # scope.
    "ring": {1: 200, 2: 0, 3: 0, 4: 10, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0},
    "line": {1: 200, 2: 0, 3: 32, 4: 10, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0},
    "dual": {1: 200, 2: 0, 3: 48, 4: 10, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0},
    "arc": {1: 200, 2: 0, 3: 96, 4: 20, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0},
    "line_ch4_60": {1: 200, 2: 0, 3: 32, 4: 60, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0},
    "arc_ch4_60": {1: 200, 2: 0, 3: 96, 4: 60, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0},
}


@dataclass(frozen=True)
class MotionCase:
    test_id: str
    test_name: str
    group: str
    baseline: str
    updates: dict[int, int] = field(default_factory=dict)
    duration: float = 5.0
    priority: str = "medium"
    expected: str = "static"
    notes: str = ""

    @property
    def dmx(self) -> dict[int, int]:
        frame = {ch: 0 for ch in range(1, 20)}
        frame.update(BASES[self.baseline])
        frame.update(self.updates)
        for ch in range(20, 37):
            frame.pop(ch, None)
        return frame

    @property
    def changed(self) -> dict[int, int]:
        base = {ch: 0 for ch in range(1, 20)}
        base.update(BASES[self.baseline])
        return {ch: v for ch, v in self.dmx.items() if base.get(ch, 0) != v}


def case_id(group: str, base: str, updates: dict[int, int]) -> str:
    parts = [group, base]
    for ch, val in sorted(updates.items()):
        parts.append(f"ch{ch:02d}_{val:03d}")
    return "_".join(parts)


def add(cases: list[MotionCase], group: str, base: str, updates: dict[int, int] | None = None,
        duration: float = 5.0, priority: str = "medium", expected: str = "static",
        name: str | None = None, notes: str = "") -> None:
    updates = updates or {}
    tid = name or case_id(group, base, updates)
    cases.append(MotionCase(tid, tid.replace("_", " "), group, base, updates, duration, priority, expected, notes))


def build_cases() -> list[MotionCase]:
    cases: list[MotionCase] = []

    # Static controls.
    for base in ("ring", "line", "dual", "arc"):
        add(cases, "controls", base, name=f"ctrl_static_{base}", expected="static", notes="no-motion deterministic control")
    add(cases, "controls", "line", {1: 0}, name="ctrl_blackout", expected="blackout", notes="blackout/off control")
    add(cases, "controls", "line", {11: 0}, name="ctrl_no_strobe_line", expected="static")
    add(cases, "controls", "line", {12: 0}, name="ctrl_no_spin_line", expected="static")
    add(cases, "controls", "line", {15: 0, 16: 0, 19: 0}, name="ctrl_no_sweep_wave_line", expected="static")

    # CH4 first-pattern bank selection inside deterministic CH3 ranges.
    for base in ("ring", "line", "dual", "arc"):
        for val in (0, 1, 5, 10, 20, 60, 100, 130):
            add(cases, "ch04_pattern_select", base, {4: val}, duration=5.0, priority="high", expected="static pattern select")

    # CH11 strobe timing: line gets breakpoint coverage; other bases get mid/high spot checks.
    for val in STROBE_VALUES_FINE:
        add(cases, "ch11_strobe", "line", {11: val}, duration=8.0, priority="high", expected="strobe gate")
    for base, val in (("ring", 128), ("ring", 200), ("dual", 128), ("arc", 128)):
        add(cases, "ch11_strobe", base, {11: val}, duration=8.0, priority="high", expected="strobe gate")

    # CH12 Z rotation/spin.
    for val in (*ANGLE_VALUES, *SPEED_VALUES_FINE):
        duration = 6.0 if val < 128 else 8.0
        add(cases, "ch12_spin", "line", {12: val}, duration=duration, priority="high", expected="rotation")
    for base, val in (("ring", 150), ("ring", 220), ("dual", 150), ("arc", 150), ("arc", 220)):
        add(cases, "ch12_spin", base, {12: val}, duration=8.0, priority="high", expected="rotation")
    for base, val in (("line_ch4_60", 150), ("arc_ch4_60", 150)):
        add(cases, "ch12_spin", base, {12: val}, duration=8.0, priority="high", expected="rotation", notes="alternate CH4 bank representative")

    # CH13/CH14 were motion-relevant in the channel audit, even if lower priority.
    for ch, group in ((13, "ch13_rot_x"), (14, "ch14_rot_y")):
        for val in (*ANGLE_VALUES, 128, 160, 192, 224, 255):
            duration = 5.0 if val < 128 else 6.0
            add(cases, group, "line", {ch: val}, duration=duration, priority="medium", expected="rotation/orientation")

    # CH15 horizontal sweep.
    for val in (*POSITION_VALUES, *SPEED_VALUES_FINE):
        duration = 5.0 if val < 128 else 10.0
        add(cases, "ch15_hsweep", "line", {15: val}, duration=duration, priority="high", expected="horizontal sweep")
    for base in ("ring", "dual", "arc"):
        add(cases, "ch15_hsweep", base, {15: 200}, duration=10.0, priority="high", expected="horizontal sweep")
    for base in ("line_ch4_60", "arc_ch4_60"):
        add(cases, "ch15_hsweep", base, {15: 200}, duration=10.0, priority="high", expected="horizontal sweep", notes="alternate CH4 bank representative")

    # CH16 vertical sweep.
    for val in (*POSITION_VALUES, *SPEED_VALUES_FINE):
        duration = 5.0 if val < 128 else 10.0
        add(cases, "ch16_vsweep", "line", {16: val}, duration=duration, priority="high", expected="vertical sweep")
    for base in ("ring", "dual", "arc"):
        add(cases, "ch16_vsweep", base, {16: 200}, duration=10.0, priority="high", expected="vertical sweep")
    for base in ("line_ch4_60", "arc_ch4_60"):
        add(cases, "ch16_vsweep", base, {16: 200}, duration=10.0, priority="high", expected="vertical sweep", notes="alternate CH4 bank representative")

    # CH17 zoom/size/spread, including speed/pulse bank candidates.
    for val in (*POSITION_VALUES, *SPEED_VALUES_FINE):
        duration = 5.0 if val < 128 else 10.0
        add(cases, "ch17_zoom", "line", {17: val}, duration=duration, priority="high", expected="zoom/size")
    for base, val in (("ring", 80), ("ring", 200), ("dual", 80), ("arc", 80)):
        add(cases, "ch17_zoom", base, {17: val}, duration=8.0, priority="high", expected="zoom/size")

    # CH19 X/Y wave/deformation.
    for val in (*POSITION_VALUES, *SPEED_VALUES_FINE):
        add(cases, "ch19_wave", "line", {19: val}, duration=10.0, priority="medium", expected="wave/deformation")
    for base in ("ring", "dual", "arc"):
        add(cases, "ch19_wave", base, {19: 200}, duration=10.0, priority="medium", expected="wave/deformation")

    # CH8 fixed colors and deterministic effect/color timing. CH9 speed is only used with CH8 effect ranges.
    for val, label in ((0, "white_or_first"), (8, "red"), (14, "yellow_or_green"), (20, "cyan"), (28, "magenta"), (60, "color_effect"), (245, "gradient_effect")):
        add(cases, "ch08_color", "line", {8: val}, duration=8.0, priority="high", expected="color timing", name=f"ch08_line_{label}_{val:03d}")
    for val in COLOR_SPEED_VALUES_FINE:
        add(cases, "ch08_color", "line", {8: 60, 9: val}, duration=8.0, priority="medium", expected="color chase", name=f"ch09_line_effect_speed_{val:03d}")
    for base in ("ring", "arc"):
        add(cases, "ch08_color", base, {8: 60, 9: 128}, duration=8.0, priority="medium", expected="color chase")

    # CH18 gradient speed is CH1-19 and the manual marks it motion/timing
    # relevant. Sample it with CH8 in the gradient range.
    for val in GRADIENT_VALUES_FINE:
        add(cases, "ch18_gradient", "line", {8: 245, 18: val}, duration=8.0, priority="medium", expected="color/gradient timing", name=f"ch18_line_gradient_speed_{val:03d}")

    # CH5/CH6/CH7 static position/offset/size behavior.
    for ch, vals in ((5, (40, 90, 170)), (6, (64, 128, 192)), (7, (64, 128, 192))):
        for val in vals:
            add(cases, "ch05_06_07_position", "line", {ch: val}, duration=5.0, priority="high", expected="position/size")
    for base, updates in (("ring", {6: 64}), ("ring", {7: 192}), ("dual", {6: 192}), ("dual", {7: 64})):
        add(cases, "ch05_06_07_position", base, updates, duration=5.0, priority="medium", expected="position/size")

    # Useful SoundSwitch-like CH1-19-only combinations with deterministic CH3 bases.
    combos = [
        ("combo_line_spin", "line", {12: 150}, "smooth rotation"),
        ("combo_line_hsweep", "line", {15: 200}, "horizontal sweep"),
        ("combo_line_vsweep", "line", {16: 200}, "vertical sweep"),
        ("combo_line_strobe", "line", {11: 150, 1: 220}, "strobe gate"),
        ("combo_line_zoom", "line", {17: 80}, "zoom/size"),
        ("combo_line_wave", "line", {19: 200}, "wave/deformation"),
        ("combo_line_color_chase", "line", {8: 60, 9: 128}, "color chase"),
        ("combo_ring_spin", "ring", {12: 150}, "rotation"),
        ("combo_ring_hsweep", "ring", {15: 200}, "horizontal sweep"),
        ("combo_dual_spin", "dual", {12: 150}, "rotation"),
        ("combo_dual_hsweep", "dual", {15: 200}, "horizontal sweep"),
        ("combo_arc_spin", "arc", {12: 150}, "rotation"),
        ("combo_arc_hsweep", "arc", {15: 200}, "horizontal sweep"),
        ("combo_line_ch4_60_spin", "line_ch4_60", {12: 150}, "rotation"),
        ("combo_line_ch4_60_hsweep", "line_ch4_60", {15: 200}, "horizontal sweep"),
    ]
    for name, base, updates, expected in combos:
        add(cases, "combos_ch1_19", base, updates, duration=8.0, priority="high", expected=expected, name=name)

    return cases


def dmx_pairs(frame: dict[int, int]) -> list[str]:
    return [f"{ch}={frame.get(ch, 0)}" for ch in range(1, 20)]


def case_capture_dir(root: Path, case: MotionCase) -> Path:
    group_dir = GROUP_DIRS.get(case.group, case.group)
    primary = GROUP_PRIMARY_CHANNEL.get(case.group)
    if primary is not None:
        value_dir = f"ch{primary:02d}_{case.dmx.get(primary, 0):03d}"
    elif case.group == "ch05_06_07_position" and case.changed:
        ch = min(case.changed)
        value_dir = f"ch{ch:02d}_{case.dmx.get(ch, 0):03d}"
    elif case.group == "ch08_color":
        value_dir = f"ch08_{case.dmx.get(8, 0):03d}_ch09_{case.dmx.get(9, 0):03d}"
    else:
        value_dir = case.test_id
    return root / "captures" / group_dir / case.baseline / value_dir


def run(cmd: list[str], cwd: Path = ROOT, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=True, **kwargs)


def capture(args: argparse.Namespace) -> None:
    outroot = Path(args.root)
    outroot.mkdir(parents=True, exist_ok=True)
    manifest = outroot / "manifest.jsonl"
    selected = {x.strip() for x in args.labels.split(",") if x.strip()}
    cases = [c for c in build_cases() if not selected or c.test_id in selected]
    for idx, case in enumerate(cases, 1):
        capture_dir = case_capture_dir(outroot, case)
        capture_dir.mkdir(parents=True, exist_ok=True)
        video = capture_dir / "video.mp4"
        metadata_path = capture_dir / "metadata.json"
        print(f"[{idx}/{len(cases)}] {case.test_id} {case.duration:.1f}s", flush=True)
        run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
        run([sys.executable, str(DMX), "set", *dmx_pairs(case.dmx)], stdout=subprocess.DEVNULL)
        time.sleep(args.hold)
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        cmd = [
            "ffmpeg", "-hide_banner", "-y", "-loglevel", "error",
            "-f", "avfoundation", "-framerate", str(FRAME_RATE),
            "-pixel_format", "uyvy422", "-video_size", SIZE,
            "-i", f"{args.device}:none", "-t", f"{case.duration:.3f}",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            str(video),
        ]
        result = subprocess.run(cmd, cwd=ROOT, check=False)
        if result.returncode != 0 or not video.exists() or video.stat().st_size <= 0:
            run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
            raise SystemExit(f"capture failed for {case.test_id}; DMX blacked out")
        entry = {
            "ts": started,
            "test_id": case.test_id,
            "test_name": case.test_name,
            "group": case.group,
            "capture": str(video),
            "capture_dir": str(capture_dir),
            "metadata_path": str(metadata_path),
            "full_ch1_19_dmx": {str(ch): case.dmx.get(ch, 0) for ch in range(1, 20)},
            "active_channels_changed_from_baseline": {str(ch): v for ch, v in case.changed.items()},
            "baseline": case.baseline,
            "duration": case.duration,
            "requested_frame_rate": FRAME_RATE,
            "camera": {"device": args.device, "size": SIZE},
            "expected": case.expected,
            "priority": case.priority,
            "notes": case.notes,
            "scope_guard": {
                "ch4_used_as_first_pattern_selector": True,
                "ch20_36_omitted": True,
                "ch3_dynamic_range_used": case.dmx.get(3, 0) >= 128,
            },
        }
        metadata_path.write_text(json.dumps(entry, indent=2) + "\n")
        with manifest.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    run([sys.executable, str(DMX), "blackout"])
    print(manifest)


def crop_roi(im: Image.Image) -> Image.Image:
    w, h = im.size
    x0, y0, x1, y1 = ROI
    return im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))


def bright_points(im: Image.Image) -> tuple[list[tuple[int, int]], int, dict[str, int]]:
    roi = crop_roi(im.convert("RGB"))
    pix = roi.load()
    pts: list[tuple[int, int]] = []
    brightness = 0
    colors = {"red": 0, "green": 0, "blue": 0, "cyan": 0, "magenta": 0, "white": 0}
    for y in range(roi.height):
        for x in range(roi.width):
            r, g, b = pix[x, y]
            mx = max(r, g, b)
            brightness += mx
            if mx > 105 and (mx - min(r, g, b) > 25 or mx > 165):
                pts.append((x, y))
                if r > 140 and g < 110 and b < 120:
                    colors["red"] += 1
                elif g > 130 and r < 120 and b < 120:
                    colors["green"] += 1
                elif b > 135 and r < 120 and g < 140:
                    colors["blue"] += 1
                elif g > 110 and b > 130 and r < 120:
                    colors["cyan"] += 1
                elif r > 130 and b > 110 and g < 120:
                    colors["magenta"] += 1
                elif r > 155 and g > 155 and b > 155:
                    colors["white"] += 1
    return pts, brightness, colors


def pca_angle(pts: list[tuple[int, int]]) -> float | None:
    if len(pts) < 30:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mx, my = mean(xs), mean(ys)
    sxx = mean([(x - mx) ** 2 for x in xs])
    syy = mean([(y - my) ** 2 for y in ys])
    sxy = mean([(x - mx) * (y - my) for x, y in pts])
    return 0.5 * math.atan2(2 * sxy, sxx - syy)


def unwrap_angles(vals: list[float | None]) -> list[float]:
    out: list[float] = []
    last: float | None = None
    offset = 0.0
    for val in vals:
        if val is None:
            continue
        cur = val + offset
        if last is not None:
            while cur - last > math.pi / 2:
                offset -= math.pi
                cur = val + offset
            while cur - last < -math.pi / 2:
                offset += math.pi
                cur = val + offset
        out.append(cur)
        last = cur
    return out


def estimate_period(signal: list[float], fps: float) -> tuple[float | None, float]:
    if len(signal) < int(fps * 2):
        return None, 0.0
    mu = mean(signal)
    centered = [x - mu for x in signal]
    denom = sum(x * x for x in centered)
    if denom <= 0:
        return None, 0.0
    min_lag = max(2, int(0.35 * fps))
    max_lag = min(len(signal) - 2, int(min(len(signal) / 2, fps * 8)))
    best_lag, best_corr = None, -1.0
    for lag in range(min_lag, max_lag + 1):
        num = sum(centered[i] * centered[i - lag] for i in range(lag, len(centered)))
        corr = num / denom
        if corr > best_corr:
            best_lag, best_corr = lag, corr
    if best_lag is None or best_corr < 0.25:
        return None, max(0.0, best_corr)
    return best_lag / fps, best_corr


def extract_analysis_frames(video: Path, tmp: Path, fps: int = 12) -> list[Path]:
    outpat = tmp / "f_%04d.jpg"
    run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps},scale=320:-1", str(outpat)])
    return sorted(tmp.glob("f_*.jpg"))


def save_strip(video: Path, strip: Path, label: str, duration: float) -> None:
    strip.parent.mkdir(parents=True, exist_ok=True)
    frames: list[Image.Image] = []
    with tempfile.TemporaryDirectory(prefix="vln_strip_") as td:
        tdir = Path(td)
        for i, frac in enumerate((0.0, 0.25, 0.5, 0.75, 0.98)):
            out = tdir / f"s_{i}.jpg"
            ts = max(0.0, duration * frac)
            run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", str(video), "-frames:v", "1", str(out)])
            frames.append(crop_roi(Image.open(out).convert("RGB")).resize((220, 140), Image.Resampling.LANCZOS))
    label_h = 24
    canvas = Image.new("RGB", (220 * 5, label_h + 140), (14, 14, 14))
    draw = ImageDraw.Draw(canvas)
    draw.text((5, 6), label[:120], fill=(255, 255, 0))
    for i, im in enumerate(frames):
        canvas.paste(im, (i * 220, label_h))
    canvas.save(strip)


def analyze_video(video: Path, expected: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="vln_motion_frames_") as td:
        frames = extract_analysis_frames(video, Path(td), fps=12)
        centers: list[tuple[float, float]] = []
        areas: list[int] = []
        brights: list[float] = []
        angles: list[float | None] = []
        color_hits: list[str] = []
        clipped = False
        for fp in frames:
            im = Image.open(fp)
            pts, brightness, colors = bright_points(im)
            brights.append(float(brightness))
            areas.append(len(pts))
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                centers.append((mean(xs), mean(ys)))
                clipped = clipped or min(xs) <= 2 or min(ys) <= 2 or max(xs) >= crop_roi(im).width - 3 or max(ys) >= crop_roi(im).height - 3
            angles.append(pca_angle(pts))
            color_hits.append(max(colors, key=colors.get))
    nonblank_frames = sum(1 for a in areas if a > 20)
    valid = bool(frames)
    blank = nonblank_frames < max(2, len(frames) * 0.1)
    area_max = max(areas) if areas else 0
    area_min = min(areas) if areas else 0
    bright_mu = mean(brights) if brights else 0.0
    bright_cv = (pstdev(brights) / bright_mu) if len(brights) > 1 and bright_mu > 0 else 0.0
    xs = [c[0] for c in centers]
    ys = [c[1] for c in centers]
    x_range = max(xs) - min(xs) if xs else 0.0
    y_range = max(ys) - min(ys) if ys else 0.0
    area_range = (area_max - area_min) / area_max if area_max else 0.0
    unwrapped = unwrap_angles(angles)
    angle_range = abs(max(unwrapped) - min(unwrapped)) if unwrapped else 0.0
    dominant_colors = [c for c in color_hits if c]
    color_changes = len(set(dominant_colors)) > 1

    motion = "static"
    if blank:
        motion = "unknown/needs recapture"
    elif bright_cv > 0.8 or (area_max and area_min < area_max * 0.2):
        motion = "strobe gate" if "strobe" in expected else "brightness pulse"
    elif angle_range > math.radians(45):
        motion = "smooth rotation"
    elif x_range > 35 and x_range > y_range * 1.3:
        motion = "horizontal sweep"
    elif y_range > 35 and y_range > x_range * 1.3:
        motion = "vertical sweep"
    elif area_range > 0.35 and "zoom" in expected:
        motion = "pulse zoom"
    elif "wave" in expected and (area_range > 0.2 or angle_range > math.radians(15)):
        motion = "wave/deformation"
    elif color_changes:
        motion = "color chase"

    signal = brights
    if motion == "horizontal sweep" and xs:
        signal = xs
    elif motion == "vertical sweep" and ys:
        signal = ys
    elif "rotation" in motion and unwrapped:
        signal = unwrapped
    elif motion == "pulse zoom" and areas:
        signal = [float(a) for a in areas]
    period, confidence = estimate_period(signal, 12.0)
    if "strobe" in motion:
        low = min(brights) if brights else 0
        high = max(brights) if brights else 0
        threshold = low + (high - low) * 0.45
        crossings = 0
        last = brights[0] > threshold if brights else False
        for b in brights[1:]:
            cur = b > threshold
            if cur != last:
                crossings += 1
                last = cur
        strobe_hz = crossings / 2 / (len(brights) / 12.0) if brights else None
        duty = sum(1 for b in brights if b > threshold) / len(brights) if brights else None
    else:
        strobe_hz = None
        duty = None

    return {
        "valid": valid,
        "blank": blank,
        "clipped": clipped,
        "overexposed": area_max > 90000 or bright_cv > 1.8,
        "frame_count": len(frames),
        "analysis_fps": 12,
        "motion_type": motion,
        "static_vs_moving": "moving" if motion not in {"static", "unknown/needs recapture"} else motion,
        "x_range": round(x_range, 1),
        "y_range": round(y_range, 1),
        "area_min": area_min,
        "area_max": area_max,
        "area_range_frac": round(area_range, 3),
        "brightness_cv": round(bright_cv, 3),
        "angle_range_deg": round(math.degrees(angle_range), 1),
        "color_changes": color_changes,
        "dominant_colors": sorted(set(dominant_colors)),
        "loop_duration_estimate": round(period, 3) if period else None,
        "loop_confidence": round(confidence, 3),
        "full_loop_captured": bool(period and confidence > 0.35),
        "strobe_frequency_hz": round(strobe_hz, 3) if strobe_hz else None,
        "duty_cycle": round(duty, 3) if duty is not None else None,
        "recapture_needed": blank or clipped,
    }


def load_manifest(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def make_contact_sheet(entries: list[dict], out: Path, title: str, cols: int = 5) -> None:
    cell_w, cell_h = 220, 170
    rows = max(1, math.ceil(len(entries) / cols))
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 28), (14, 14, 14))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), title, fill=(255, 255, 255))
    for idx, entry in enumerate(entries):
        strip = Path(entry["strip"])
        if not strip.exists():
            continue
        im = Image.open(strip).convert("RGB").crop((0, 24, 220, 164))
        x = (idx % cols) * cell_w
        y = 28 + (idx // cols) * cell_h
        draw.text((x + 4, y + 4), entry["test_id"][:34], fill=(255, 255, 0))
        sheet.paste(im.resize((cell_w, 140), Image.Resampling.LANCZOS), (x, y + 24))
    sheet.save(out)


def write_report(root: Path, entries: list[dict], artifacts: dict[str, str]) -> None:
    report = ROOT / "docs" / "TIMED_MOTION_CH1_19_CALIBRATION.md"
    skipped = [
        ("CH2 auto/sound/demo", "Skipped: non-deterministic and not useful for deterministic SoundSwitch previz."),
        ("CH4 stacked/second-pattern behavior", "CH4 was included only as the first-pattern bank selector for deterministic CH3 ranges; CH20-36 second-pattern controls remained omitted."),
        ("CH10 line/dot scan", "Documented from still channel audit; not motion-timed here because it is a static scan/shape modifier."),
        ("CH18 gradient speed", "Included with CH8 in the gradient range; deeper gradient-program mapping can be refined after this pass."),
        ("CH3 >=128 dynamic macros", "Skipped by scope to avoid macro-loop confusion; deterministic CH3 values 0, 32, 48, and 96 were used."),
    ]
    recapture = [e for e in entries if e["analysis"].get("recapture_needed")]
    lines = [
        "# Timed motion calibration CH1-19",
        "",
        "Evidence-only timed/burst pass for one master fixture using wall projection, no haze, iPhone Continuity Camera device 2, and deterministic first-pattern CH3 bases only.",
        "",
        "No renderer behavior, calibration.json values, CH20-36 channels, or second-pattern behavior were changed or used in this pass. CH4 is included only as the first-pattern program selector inside deterministic CH3 banks.",
        "",
        "Important scope note: this is a broad timed-motion scaffold, not a dense breakpoint atlas. The fixture manual and live observations show that CH3 through CH19 can contain fine internal value ranges and sub-looks. Treat these captures as representative timing/interaction evidence; do not treat unsampled values as calibrated.",
        "",
        "## Artifacts",
        f"- Motion capture root: `{root}`",
        f"- Organized capture bundles: `{root / 'captures'}`",
        f"- Manifest/log: `{root / 'manifest.jsonl'}`",
        f"- Analysis manifest: `{root / 'analysis_manifest.jsonl'}`",
        f"- Master contact sheet: `{artifacts['master']}`",
    ]
    for group, path in artifacts.items():
        if group != "master":
            lines.append(f"- {group}: `{path}`")
    lines.extend([
        "",
        "## Baselines",
        "- `ring`: CH1=200 CH2=0 CH3=0 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0",
        "- `line`: CH1=200 CH2=0 CH3=32 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0",
        "- `dual`: CH1=200 CH2=0 CH3=48 CH4=10 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0",
        "- `arc`: CH1=200 CH2=0 CH3=96 CH4=20 CH5=90 CH6=128 CH7=128 CH8=20 CH9=0 CH10=0 CH11=0",
        "- `line_ch4_60` and `arc_ch4_60`: alternate CH4 bank representatives used to check that motion behavior is not unique to one CH4-selected figure.",
        "",
        "## Captured States",
        "",
        "| test_id | group | baseline | changed CH | duration | motion | loop | strobe Hz | quality | renderer support | priority |",
        "|---|---|---|---|---:|---|---:|---:|---|---|---|",
    ])
    for e in entries:
        a = e["analysis"]
        changed = " ".join(f"CH{k}={v}" for k, v in e["active_channels_changed_from_baseline"].items()) or "none"
        quality = []
        quality.append("blank" if a["blank"] else "nonblank")
        quality.append("clipped" if a["clipped"] else "not clipped")
        quality.append("overexposed" if a["overexposed"] else "not overexposed")
        support = renderer_support(a["motion_type"])
        lines.append(
            f"| `{e['test_id']}` | {e['group']} | {e['baseline']} | `{changed}` | {e['duration']} | "
            f"{a['motion_type']} | {a.get('loop_duration_estimate')} | {a.get('strobe_frequency_hz')} | "
            f"{', '.join(quality)} | {support} | {e['priority']} |"
        )
    lines.extend([
        "",
        "## Skipped Or Deferred",
        "",
    ])
    for item, reason in skipped:
        lines.append(f"- {item}: {reason}")
    lines.extend([
        "",
        "## Recapture Needed",
        "",
    ])
    if recapture:
        for e in recapture:
            a = e["analysis"]
            lines.append(f"- `{e['test_id']}`: blank={a['blank']} clipped={a['clipped']} overexposed={a['overexposed']}")
    else:
        lines.append("- None flagged by automated quality gates.")
    lines.extend([
        "",
        "## Recommended Motion Preset Table",
        "",
        "| preset | source evidence | renderer need | priority |",
        "|---|---|---|---|",
        "| static wall figure | controls + CH5/6/7/17 static states | calibrated wall-projection shape preset per deterministic CH3 family | high |",
        "| strobe gate | CH11 strobe states | timed brightness gate with frequency/duty controls | high |",
        "| smooth/stepped spin | CH12 plus CH13/CH14 sanity states | rotation axis/rate/direction preset per channel/value band | high |",
        "| CH4-selected static figures | CH4 pattern-select states | first-pattern shape preset key should include CH3 range plus CH4 selector | high |",
        "| horizontal sweep | CH15 states | pan/sweep loop with range, clip, bounce/reset behavior | high |",
        "| vertical sweep | CH16 states | vertical sweep loop with offset/range and clip behavior | high |",
        "| zoom/pulse zoom | CH17 states | static size plus possible pulse/speed bank behavior | high |",
        "| wave/deformation | CH19 states | deformation preset separate from whole-pattern movement | medium |",
        "| color chase | CH8/CH9 states | fixed-color map plus color-cycle timing/order | medium |",
        "| gradient timing | CH18 states with CH8 gradient range | gradient speed preset/color flow timing | medium |",
        "",
        "## Exact Next Implementation Step",
        "",
        "Implement dense breakpoint discovery for CH3-CH19 before tuning renderer behavior. Use CH3+CH4 as the base-look key, sweep each modifier channel finely under valid visible baselines, group adjacent values that produce the same visual behavior, then timed-capture only the representative ranges and high-value combinations. After that, implement a non-rendering calibration data layer keyed by CH3 deterministic range plus CH4 first-pattern selector, then attach CH5-CH19 modifier presets and explicit combo overrides where layered behavior fails.",
    ])
    report.write_text("\n".join(lines) + "\n")
    update_calibration_results(report, root, artifacts, recapture)


def renderer_support(motion_type: str) -> str:
    if motion_type in {"static", "horizontal sweep", "vertical sweep", "smooth rotation", "strobe gate", "color chase"}:
        return "partially supported"
    if motion_type in {"pulse zoom", "wave/deformation", "brightness pulse"}:
        return "limited/needs preset"
    return "unknown/needs evidence"


def update_calibration_results(report: Path, root: Path, artifacts: dict[str, str], recapture: list[dict]) -> None:
    path = ROOT / "docs" / "CALIBRATION_RESULTS.md"
    text = path.read_text() if path.exists() else "# Calibration Results\n"
    start = "<!-- TIMED_MOTION_CH1_19_START -->"
    end = "<!-- TIMED_MOTION_CH1_19_END -->"
    section = "\n".join([
        start,
        "## Timed Motion CH1-19 Pass",
        "",
        f"- Report: `{report}`",
        f"- Motion capture root: `{root}`",
        f"- Master contact sheet: `{artifacts['master']}`",
        f"- Automated quality-flag count: {len(recapture)}",
        "- Scope: CH1-19 only, CH4 included as first-pattern selector, CH20-36 omitted, deterministic CH3 bases only.",
        "- Key result: representative motion timing evidence now exists for CH4-selected first-pattern banks, CH11 strobe, CH12/13/14 rotation sanity, CH15/CH16 movement, CH17 zoom, CH18 gradient timing, CH19 wave, CH8/CH9 color timing, CH5/6/7 position, and deterministic CH1-19 combinations.",
        "- Limitation: CH3-CH19 all need dense breakpoint discovery before renderer tuning; this pass should not be read as complete value-by-value calibration.",
        end,
        "",
    ])
    if start in text and end in text:
        before = text.split(start, 1)[0]
        after = text.split(end, 1)[1]
        text = before + section + after.lstrip("\n")
    else:
        text = text.rstrip() + "\n\n" + section
    path.write_text(text)


def build(args: argparse.Namespace) -> None:
    root = Path(args.root)
    manifest = root / "manifest.jsonl"
    entries = load_manifest(manifest)
    analyzed: list[dict] = []
    for entry in entries:
        video = Path(entry["capture"])
        capture_dir = Path(entry.get("capture_dir", video.parent))
        strip = capture_dir / "frame_strip.png"
        save_strip(video, strip, entry["test_id"], float(entry["duration"]))
        entry["strip"] = str(strip)
        entry["analysis"] = analyze_video(video, entry.get("expected", ""))
        (capture_dir / "analysis.json").write_text(json.dumps(entry, indent=2) + "\n")
        analyzed.append(entry)
    analysis_manifest = root / "analysis_manifest.jsonl"
    with analysis_manifest.open("w") as f:
        for entry in analyzed:
            f.write(json.dumps(entry) + "\n")

    sheets = root / "contact_sheets"
    sheets.mkdir(exist_ok=True)
    artifacts: dict[str, str] = {}
    master = sheets / "timed_motion_ch1_19_master.png"
    make_contact_sheet(analyzed, master, "CH1-19 timed motion master")
    artifacts["master"] = str(master)
    group_names = {
        "ch04_pattern_select": "CH4 first-pattern bank selection",
        "ch11_strobe": "CH11 strobe",
        "ch12_spin": "CH12 spin",
        "ch15_hsweep": "CH15 horizontal sweep",
        "ch16_vsweep": "CH16 vertical sweep",
        "ch17_zoom": "CH17 zoom",
        "ch18_gradient": "CH18 gradient",
        "ch19_wave": "CH19 wave",
        "ch08_color": "CH8 color timing",
        "ch05_06_07_position": "CH5/CH6/CH7 position offset",
        "ch13_rot_x": "CH13 rotation X sanity",
        "ch14_rot_y": "CH14 rotation Y sanity",
        "combos_ch1_19": "CH1-19 deterministic combinations",
    }
    for group, title in group_names.items():
        subset = [e for e in analyzed if e["group"] == group]
        if subset:
            out = sheets / f"{group}.png"
            make_contact_sheet(subset, out, title)
            artifacts[title] = str(out)
    write_report(root, analyzed, artifacts)
    print(root)
    print(analysis_manifest)
    print(master)
    print(ROOT / "docs" / "TIMED_MOTION_CH1_19_CALIBRATION.md")


def list_cases(_args: argparse.Namespace) -> None:
    for case in build_cases():
        print(f"{case.test_id}\t{case.group}\t{case.baseline}\t{case.duration}s\t" + " ".join(dmx_pairs(case.dmx)))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.set_defaults(func=list_cases)
    cap = sub.add_parser("capture")
    cap.add_argument("--root", default=str(DEFAULT_ROOT))
    cap.add_argument("--device", default="2")
    cap.add_argument("--hold", type=float, default=0.6)
    cap.add_argument("--labels", default="")
    cap.set_defaults(func=capture)
    b = sub.add_parser("build")
    b.add_argument("--root", default=str(DEFAULT_ROOT))
    b.set_defaults(func=build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
