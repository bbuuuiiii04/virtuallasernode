#!/usr/bin/env python3
"""
Dense cue-family breakpoint capture for real SoundSwitch laser cues.

Evidence-only tool:
- targets only cues currently marked needs_dense_breakpoint_capture
- captures only the 30fps-resolvable subset by default
- defers fast motion families to a higher-fps rig
- logs exact CH1-19 DMX states and writes additive coverage annotations

It does not tune renderer behavior or calibration.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DMX = ROOT / "calib" / "dmx_open.py"
CUE_PATH = ROOT / "data" / "soundswitch_laser_cues.json"
COVERAGE_PATH = ROOT / "data" / "soundswitch_cue_motion_coverage.json"
UPDATED_COVERAGE_PATH = ROOT / "data" / "soundswitch_cue_motion_coverage.json"
REPORT_PATH = ROOT / "docs" / "SOUNDSWITCH_CUE_MOTION_COVERAGE.md"
DENSE_REPORT_PATH = ROOT / "docs" / "DENSE_CUE_BREAKPOINT_CAPTURE.md"
DEFAULT_ROOT = Path("/tmp") / f"vln_dense_cue_breakpoints_{time.strftime('%Y%m%d_%H%M%S')}"
DEFAULT_FRAME_RATE = 30
DEFAULT_ANALYSIS_RATE = 12
DEFAULT_SIZE = "1280x720"
DEFAULT_PIXEL_FORMAT = "uyvy422"
ANALYSIS_GEOMETRY_DEFAULT = ROOT / "captures" / "fixture_model" / "analysis_geometry.json"
LASER_CORE_THRESHOLD_FLOOR = int(os.environ.get("VLN_LASER_CORE_THRESHOLD_FLOOR", "58"))
ANALYSIS_ROI_EDGE_MARGIN_PX = int(os.environ.get("VLN_ANALYSIS_ROI_EDGE_MARGIN_PX", "4"))

FAST_MOTION_TOKENS = (
    "xmove",
    "ymove",
    "wave",
    "zrot",
    "xrot",
    "yrot",
    "zoom",
    "motion_macro",
)

MOTION_CHANNELS = {
    12: "z_rotation",
    13: "x_rotation",
    14: "y_rotation",
    15: "horizontal_movement",
    16: "vertical_movement",
    17: "zoom",
    19: "wave",
}


def _analysis_geometry() -> dict[str, Any] | None:
    path = Path(os.environ.get("VLN_ANALYSIS_GEOMETRY_PATH") or ANALYSIS_GEOMETRY_DEFAULT)
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def _analysis_roi_info(width: int, height: int) -> dict[str, Any]:
    geometry = _analysis_geometry()
    if geometry and geometry.get("analysis_roi") and geometry.get("source_image_size"):
        src = geometry["source_image_size"]
        src_h = max(1, int(src.get("height") or height))
        roi = geometry["analysis_roi"]
        top = int(round(float(roi[1]) * height / src_h))
        bottom = int(round(float(roi[3]) * height / src_h))
        return {
            "top": max(0, min(height - 1, top)) if height > 1 else 0,
            "bottom": max(1, min(height, bottom)) if height > 0 else 0,
            "source": "analysis_geometry",
            "geometry_source_still": geometry.get("source_still"),
        }
    top_frac = float(os.environ.get("VLN_ANALYSIS_ROI_TOP_FRAC", "0") or 0)
    bottom_frac = float(os.environ.get("VLN_ANALYSIS_ROI_BOTTOM_FRAC", "1") or 1)
    top = max(0, min(height - 1, int(height * top_frac))) if height > 1 else 0
    bottom = max(top + 1, min(height, int(height * bottom_frac))) if height > 0 else 0
    return {
        "top": top,
        "bottom": bottom,
        "source": "fraction_fallback",
        "geometry_source_still": None,
    }


def _analysis_roi_bounds(height: int, width: int | None = None) -> tuple[int, int]:
    info = _analysis_roi_info(width or 0, height)
    return int(info["top"]), int(info["bottom"])


def _analysis_array(image: Image.Image) -> tuple["Any", dict[str, Any]]:
    import numpy as np
    arr = np.asarray(image.convert("RGB"), dtype=np.float32)
    info = _analysis_roi_info(arr.shape[1], arr.shape[0])
    top, bottom = int(info["top"]), int(info["bottom"])
    return arr[top:bottom, :, :], info


def _laser_core_mask(arr: "Any", threshold: int | None = None) -> tuple["Any", float]:
    """Return a mask for scanned-line core pixels, rejecting broad wall bloom.

    Fixed thresholds such as mx > 110 work on dark walls but fail when laser spill
    softly lights the wall. Use the local wall distribution to require pixels to
    rise above the bloom/background, while keeping the old dim-beam floor.
    """
    import numpy as np
    threshold = max(int(threshold or LASER_CORE_THRESHOLD_FLOOR), LASER_CORE_THRESHOLD_FLOOR)
    if arr.size == 0:
        return np.zeros(arr.shape[:2], dtype=bool), float(threshold)
    mx = arr.max(axis=2)
    median = float(np.percentile(mx, 50))
    p90 = float(np.percentile(mx, 90))
    adaptive_floor = median + max(35.0, (p90 - median) * 2.5)
    core_threshold = max(float(threshold), adaptive_floor)
    return mx >= core_threshold, core_threshold

STATIC_COLOR_STROBE_TYPES = {
    "static",
    "static_or_timed",
    "color_timing",
    "strobe_timing",
}


@dataclass(frozen=True)
class CaptureCase:
    test_id: str
    cue_id: str
    cue_name: str
    family: str
    dmx: dict[int, int]
    duration: float
    mode: str
    reason: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def cue_dmx_from_coverage(entry: dict[str, Any]) -> dict[int, int]:
    return {ch: int(entry["ch1_19"][f"CH{ch}"]) for ch in range(1, 20)}


def dmx_pairs(frame: dict[int, int]) -> list[str]:
    return [f"{ch}={frame.get(ch, 0)}" for ch in range(1, 20)]


def family_is_fast_motion(family: str) -> bool:
    return any(token in family for token in FAST_MOTION_TOKENS)


def select_targets(coverage: dict[str, Any], include_fast_motion: bool) -> tuple[list[CaptureCase], list[dict[str, Any]]]:
    captures: list[CaptureCase] = []
    deferred: list[dict[str, Any]] = []
    seen_exact: set[tuple[int, ...]] = set()
    for cue in coverage["cues"]:
        if cue.get("recommended_next_action") != "needs_dense_breakpoint_capture":
            continue
        family = cue["recommended_renderer_preset_family"]
        dmx = cue_dmx_from_coverage(cue)
        is_fast = family_is_fast_motion(family)
        if is_fast and not include_fast_motion:
            deferred.append({
                "cue_id": cue["cue_id"],
                "cue_name": cue["cue_name"],
                "family": family,
                "ch1_19": cue["ch1_19"],
                "reason": "fast spin/sweep/zoom/wave/path family; 30fps->12fps analysis aliases timing, so dense 30fps capture is deferred to higher-fps rig",
            })
            continue
        vector = tuple(dmx[ch] for ch in range(1, 20))
        if vector in seen_exact:
            continue
        seen_exact.add(vector)
        mode = "timed" if (is_fast or "gradient" in family or cue.get("is_motion") or cue.get("calibration_type") != "static") else "still"
        duration = 10.0 if is_fast else (8.0 if mode == "timed" else 3.0)
        safe_name = "".join(c.lower() if c.isalnum() else "_" for c in cue["cue_name"])[:48].strip("_")
        captures.append(CaptureCase(
            test_id=f"cue_{len(captures)+1:03d}_{safe_name or cue['cue_id'][:8]}",
            cue_id=cue["cue_id"],
            cue_name=cue["cue_name"],
            family=family,
            dmx=dmx,
            duration=duration,
            mode=mode,
            reason=(
                "higher-fps exact cue state: fast-motion family captured as video evidence"
                if is_fast else
                "30fps-resolvable exact cue state: static/color/gradient/position-only family"
            ),
        ))
    return captures, deferred


def channel_variance(cues: list[dict[str, Any]]) -> dict[str, list[int]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cue in cues:
        grouped[cue["recommended_renderer_preset_family"]].append(cue)
    out: dict[str, list[int]] = {}
    for family, rows in grouped.items():
        varying: list[int] = []
        for ch in range(1, 20):
            vals = {int(row["ch1_19"][f"CH{ch}"]) for row in rows}
            if len(vals) > 1:
                varying.append(ch)
        out[family] = varying
    return out


def run(cmd: list[str], cwd: Path = ROOT, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=True, **kwargs)


def quit_soundswitch() -> None:
    subprocess.run(["osascript", "-e", 'tell application "SoundSwitch" to quit'], check=False)
    time.sleep(1.0)


def ftdi_port_hint() -> str:
    ports = sorted(Path("/dev").glob("cu.usbserial*"))
    if ports:
        return str(ports[0])
    return "auto"


def start_dmx_daemon() -> subprocess.Popen[str]:
    port = ftdi_port_hint()
    return subprocess.Popen(
        [sys.executable, str(DMX), "daemon", "--port", port],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def set_dmx(frame: dict[int, int]) -> None:
    run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
    run([sys.executable, str(DMX), "set", *dmx_pairs(frame)], stdout=subprocess.DEVNULL)


def blackout() -> str:
    run([sys.executable, str(DMX), "blackout"], stdout=subprocess.DEVNULL)
    return subprocess.check_output([sys.executable, str(DMX), "show"], cwd=ROOT, text=True).strip()


def ffmpeg_capture(device: str, duration: float, video: Path, fps: int, pixel_format: str, size: str) -> None:
    cmd = [
        "ffmpeg", "-hide_banner", "-y", "-loglevel", "error",
        "-f", "avfoundation",
        "-framerate", str(fps),
        "-pixel_format", pixel_format,
        "-video_size", size,
        "-i", f"{device}:none",
        "-t", f"{duration:.3f}",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        str(video),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def extract_frame(video: Path, out: Path, ts: float) -> None:
    run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", str(video), "-frames:v", "1", str(out)])


def bright_stats(image: Image.Image) -> dict[str, Any]:
    import numpy as np
    arr, roi_info = _analysis_array(image)
    top, bottom = int(roi_info["top"]), int(roi_info["bottom"])
    mask, core_threshold = _laser_core_mask(arr, threshold=LASER_CORE_THRESHOLD_FLOOR)
    ys, xs = np.nonzero(mask)
    pts = list(zip(xs.astype(int).tolist(), ys.astype(int).tolist()))
    mx = arr.max(axis=2) if arr.size else np.asarray([], dtype=np.float32)
    brightness = int(mx.sum()) if mx.size else 0
    colors = Counter()
    if arr.size:
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        color_masks = {
            "red": mask & (r > 140) & (g < 110) & (b < 120),
            "green": mask & (g > 130) & (r < 120) & (b < 120),
            "blue": mask & (b > 135) & (r < 120) & (g < 140),
            "cyan": mask & (g > 110) & (b > 130) & (r < 120),
            "magenta": mask & (r > 130) & (b > 110) & (g < 120),
            "white": mask & (r > 155) & (g > 155) & (b > 155),
        }
        for name, cmask in color_masks.items():
            count = int(cmask.sum())
            if count:
                colors[name] = count
    bbox = None
    clipped = False
    clipped_roi_bottom = False
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        crop_h, crop_w = arr.shape[:2]
        clipped = min(xs) <= 2 or min(ys) <= 2 or max(xs) >= crop_w - 3 or max(ys) >= crop_h - 3
        clipped_roi_bottom = max(ys) >= crop_h - ANALYSIS_ROI_EDGE_MARGIN_PX
    return {
        "bright_pixels": len(pts),
        "blank": len(pts) < 20,
        "brightness": brightness,
        "bbox": bbox,
        "clipped_full_frame": clipped,
        "clipped_roi_bottom": clipped_roi_bottom,
        "geometry_clipped_low": clipped_roi_bottom,
        "analysis_roi": [0, top, image.width, bottom],
        "analysis_roi_source": roi_info["source"],
        "analysis_geometry_source_still": roi_info.get("geometry_source_still"),
        "analysis_clip_margin_px": ANALYSIS_ROI_EDGE_MARGIN_PX,
        "laser_core_threshold": round(core_threshold, 3),
        "bright_fraction": round(len(pts) / max(1, int(mask.size)), 6),
        "dominant_color": colors.most_common(1)[0][0] if colors else "none",
    }


def bright_points(image: Image.Image, threshold: int = 58) -> tuple[list[tuple[int, int]], int, Counter[str]]:
    import numpy as np
    arr, _roi_info = _analysis_array(image)
    wb_path = os.environ.get("VLN_WHITE_REFERENCE")
    if wb_path:
        gains = white_balance_gains(Path(wb_path))
        arr = np.clip(arr * np.asarray(gains, dtype=np.float32), 0, 255)
    mask, _core_threshold = _laser_core_mask(arr, threshold=threshold)
    ys, xs = np.nonzero(mask)
    pts = list(zip(xs.astype(int).tolist(), ys.astype(int).tolist()))
    brightness = int(arr.max(axis=2).sum()) if arr.size else 0
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    colors: Counter[str] = Counter()
    color_masks = {
        "red": mask & (r > 95) & (g < 90) & (b < 90),
        "green": mask & (g > 90) & (r < 95) & (b < 95),
        "blue": mask & (b > 95) & (r < 95) & (g < 105),
        "cyan": mask & (g > 80) & (b > 90) & (r < 95),
        "magenta": mask & (r > 90) & (b > 85) & (g < 95),
        "white": mask & (r > 115) & (g > 115) & (b > 115),
    }
    for name, cmask in color_masks.items():
        count = int(cmask.sum())
        if count:
            colors[name] = count
    return pts, brightness, colors


_WHITE_BALANCE_CACHE: dict[str, tuple[float, float, float]] = {}


def white_balance_gains(path: Path) -> tuple[float, float, float]:
    key = str(path)
    if key in _WHITE_BALANCE_CACHE:
        return _WHITE_BALANCE_CACHE[key]
    import numpy as np
    arr, _roi_info = _analysis_array(Image.open(path).convert("RGB"))
    mask, _core_threshold = _laser_core_mask(arr, threshold=LASER_CORE_THRESHOLD_FLOOR)
    if int(mask.sum()) < 20:
        _WHITE_BALANCE_CACHE[key] = (1.0, 1.0, 1.0)
        return _WHITE_BALANCE_CACHE[key]
    means = arr[mask].mean(axis=0)
    target = float(means.mean())
    gains = tuple(float(max(0.2, min(5.0, target / max(1.0, val)))) for val in means)
    _WHITE_BALANCE_CACHE[key] = gains
    return gains


def pca_angle(pts: list[tuple[int, int]]) -> float | None:
    if len(pts) < 25:
        return None
    import numpy as np
    arr = np.asarray(pts, dtype=float)
    xs = arr[:, 0]
    ys = arr[:, 1]
    mx, my = float(xs.mean()), float(ys.mean())
    sxx = float(((xs - mx) ** 2).mean())
    syy = float(((ys - my) ** 2).mean())
    sxy = float(((xs - mx) * (ys - my)).mean())
    import math
    return 0.5 * math.atan2(2 * sxy, sxx - syy)


def unwrap_angles(vals: list[float | None]) -> list[float]:
    import math
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
    """Estimate periodicity, allowing 3-15 Hz motion at 30fps analysis.

    Before this pass the equivalent timed analyzer used a 0.35s minimum lag,
    which floored detection around 2.85Hz. Dense 60fps footage is analyzed at
    30fps here, so use ~0.07s instead: 2 frames at 30fps, allowing up to ~15Hz.
    """
    if len(signal) < max(8, int(fps)):
        return None, 0.0
    mu = mean(signal)
    centered = [x - mu for x in signal]
    denom = sum(x * x for x in centered)
    if denom <= 0:
        return None, 0.0
    min_lag = max(2, int(0.07 * fps))
    max_lag = min(len(signal) - 2, int(min(len(signal) / 2, fps * 8)))
    best_lag, best_corr = None, -1.0
    for lag in range(min_lag, max_lag + 1):
        num = sum(centered[i] * centered[i - lag] for i in range(lag, len(centered)))
        corr = num / denom
        if corr > best_corr:
            best_lag, best_corr = lag, corr
    if best_lag is None or best_corr < 0.20:
        return None, max(0.0, best_corr)
    return best_lag / fps, max(0.0, best_corr)


def strobe_crossing_rate(brights: list[float], fps: float) -> tuple[float | None, float | None, int]:
    if len(brights) < 4:
        return None, None, 0
    low, high = min(brights), max(brights)
    if high <= low:
        return None, None, 0
    threshold = low + (high - low) * 0.45
    above = [b > threshold for b in brights]
    crossings = sum(1 for prev, cur in zip(above, above[1:]) if prev != cur)
    seconds = len(brights) / fps
    hz = crossings / 2 / seconds if seconds > 0 and crossings > 0 else None
    duty = sum(above) / len(above)
    return hz, duty, crossings


def regression_slope(vals: list[float], fps: float) -> tuple[float, float]:
    """Return value-per-second slope and a simple normalized confidence."""
    if len(vals) < 3:
        return 0.0, 0.0
    xs = [i / fps for i in range(len(vals))]
    x_mu = mean(xs)
    y_mu = mean(vals)
    denom = sum((x - x_mu) ** 2 for x in xs)
    if denom <= 0:
        return 0.0, 0.0
    slope = sum((x - x_mu) * (y - y_mu) for x, y in zip(xs, vals)) / denom
    fitted = [y_mu + slope * (x - x_mu) for x in xs]
    residual = sum((y - fit) ** 2 for y, fit in zip(vals, fitted))
    total = sum((y - y_mu) ** 2 for y in vals)
    confidence = 0.0 if total <= 0 else max(0.0, min(1.0, 1.0 - residual / total))
    return slope, confidence


def movement_signal_for(motion_type: str, xs: list[float], ys: list[float], areas: list[int], brights: list[float], angles: list[float]) -> list[float]:
    if motion_type == "horizontal_sweep":
        return xs
    if motion_type == "vertical_sweep":
        return ys
    if motion_type in {"smooth_rotation", "stepped_rotation"}:
        return angles
    if motion_type == "pulse_zoom":
        return [float(a) for a in areas]
    if motion_type in {"wave_deformation", "motion_macro"}:
        return [float(a) for a in areas]
    return brights


def classify_motion(entry: dict[str, Any], metrics: dict[str, Any]) -> str:
    dmx = {int(ch): int(val) for ch, val in entry["full_ch1_19_dmx"].items()}
    family = entry.get("family", "")
    if metrics["blank"]:
        return "unknown"
    if dmx.get(11, 0) > 0 and metrics.get("strobe_frequency_hz"):
        return "strobe_gate"
    if metrics["angle_range_deg"] >= 35 and (dmx.get(12, 0) >= 144 or dmx.get(13, 0) or dmx.get(14, 0)):
        return "smooth_rotation"
    if metrics["x_range"] >= 18 and metrics["x_range"] > metrics["y_range"] * 1.20 and dmx.get(15, 0):
        return "horizontal_sweep"
    if metrics["y_range"] >= 18 and metrics["y_range"] > metrics["x_range"] * 1.20 and dmx.get(16, 0):
        return "vertical_sweep"
    if metrics["area_range_frac"] >= 0.24 and dmx.get(17, 0):
        return "pulse_zoom"
    if dmx.get(19, 0) and (metrics["area_range_frac"] >= 0.16 or metrics["angle_range_deg"] >= 18 or metrics["x_range"] >= 14 or metrics["y_range"] >= 14):
        return "wave_deformation"
    if "motion_macro" in family and (metrics["x_range"] >= 12 or metrics["y_range"] >= 12 or metrics["area_range_frac"] >= 0.12):
        return "motion_macro"
    if len(metrics.get("dominant_colors", [])) > 1:
        return "color_chase"
    if metrics["x_range"] >= 16 and dmx.get(15, 0):
        return "horizontal_sweep"
    if metrics["y_range"] >= 16 and dmx.get(16, 0):
        return "vertical_sweep"
    return "static"


def extract_analysis_sequence(video: Path, outdir: Path, fps: int) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    outpat = outdir / "analysis_%04d.jpg"
    run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps},scale=320:-1", str(outpat)])
    return sorted(outdir.glob("analysis_*.jpg"))


def analyze_video(video: Path, duration: float, frame_dir: Path, strip_path: Path, label: str, analysis_fps: int) -> dict[str, Any]:
    frame_dir.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    thumbs: list[Image.Image] = []
    for idx, frac in enumerate((0.0, 0.25, 0.5, 0.75, 0.98)):
        frame = frame_dir / f"frame_{idx:02d}.jpg"
        extract_frame(video, frame, max(0.0, duration * frac))
        im = Image.open(frame).convert("RGB")
        samples.append({"frame": str(frame), "t_fraction": frac, **bright_stats(im)})
        thumbs.append(im.resize((220, 124), Image.Resampling.LANCZOS))
    canvas = Image.new("RGB", (220 * len(thumbs), 148), (12, 12, 12))
    draw = ImageDraw.Draw(canvas)
    draw.text((5, 5), label[:130], fill=(255, 255, 0))
    for i, thumb in enumerate(thumbs):
        canvas.paste(thumb, (i * 220, 24))
    strip_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(strip_path)
    analysis_frames = extract_analysis_sequence(video, frame_dir / "analysis", analysis_fps)
    analysis_stats = []
    for fp in analysis_frames:
        analysis_stats.append(bright_stats(Image.open(fp).convert("RGB")))
    nonblank = [s for s in samples if not s["blank"]]
    analysis_nonblank = [s for s in analysis_stats if not s["blank"]]
    brights = [float(s["brightness"]) for s in samples]
    dominant_colors = {s["dominant_color"] for s in nonblank}
    return {
        "valid": True,
        "blank": len(analysis_nonblank) == 0 if analysis_stats else len(nonblank) == 0,
        "nonblank_sample_frames": len(nonblank),
        "analysis_frame_count": len(analysis_stats),
        "analysis_nonblank_frames": len(analysis_nonblank),
        "analysis_fps": analysis_fps,
        "clipped_full_frame_any": any(s["clipped_full_frame"] for s in samples),
        "clipped_roi_bottom_any": any(s.get("clipped_roi_bottom") for s in samples + analysis_stats),
        "geometry_clipped_low": any(s.get("geometry_clipped_low") for s in samples + analysis_stats),
        "dominant_colors": sorted(dominant_colors),
        "brightness_cv": (pstdev(brights) / mean(brights)) if len(brights) > 1 and mean(brights) > 0 else 0.0,
        "timing_reliability": (
            "high-fps capture evidence; detailed motion rate extraction deferred to renderer-motion analysis"
            if analysis_fps > DEFAULT_ANALYSIS_RATE else
            "gradient/color evidence only; fast path timing not inferred"
        ),
        "samples": samples,
    }


def analyze_existing_entry(entry: dict[str, Any], analysis_fps: int, threshold: int) -> dict[str, Any]:
    video = Path(entry["capture"])
    analysis_dir = Path(entry["capture_dir"]) / f"motion_analysis_{analysis_fps}fps"
    frames = extract_analysis_sequence(video, analysis_dir, analysis_fps)
    centers: list[tuple[float, float]] = []
    xs: list[float] = []
    ys: list[float] = []
    areas: list[int] = []
    widths: list[int] = []
    heights: list[int] = []
    brights: list[float] = []
    angles_raw: list[float | None] = []
    color_hits: list[str] = []
    clipped = False
    clipped_roi_bottom = False
    for fp in frames:
        im = Image.open(fp).convert("RGB")
        pts, brightness, colors = bright_points(im, threshold=threshold)
        brights.append(float(brightness))
        areas.append(len(pts))
        if pts:
            px = [p[0] for p in pts]
            py = [p[1] for p in pts]
            x0, x1 = min(px), max(px)
            y0, y1 = min(py), max(py)
            cx, cy = mean(px), mean(py)
            centers.append((cx, cy))
            xs.append(cx)
            ys.append(cy)
            widths.append(x1 - x0)
            heights.append(y1 - y0)
            top, bottom = _analysis_roi_bounds(im.height, im.width)
            crop_h = max(1, bottom - top)
            clipped = clipped or x0 <= 1 or y0 <= 1 or x1 >= im.width - 2 or y1 >= crop_h - 2
            clipped_roi_bottom = clipped_roi_bottom or y1 >= crop_h - ANALYSIS_ROI_EDGE_MARGIN_PX
        angles_raw.append(pca_angle(pts))
        color_hits.append(colors.most_common(1)[0][0] if colors else "none")

    nonblank_frames = sum(1 for area in areas if area > 10)
    blank = nonblank_frames < max(2, len(frames) * 0.06)
    area_max = max(areas) if areas else 0
    area_min = min(areas) if areas else 0
    area_range_frac = (area_max - area_min) / area_max if area_max else 0.0
    bright_mu = mean(brights) if brights else 0.0
    brightness_cv = (pstdev(brights) / bright_mu) if len(brights) > 1 and bright_mu > 0 else 0.0
    x_range = max(xs) - min(xs) if xs else 0.0
    y_range = max(ys) - min(ys) if ys else 0.0
    unwrapped = unwrap_angles(angles_raw)
    import math
    angle_range_deg = math.degrees(abs(max(unwrapped) - min(unwrapped))) if unwrapped else 0.0
    dominant_colors = sorted({c for c in color_hits if c and c != "none"})
    strobe_hz, duty_cycle, crossings = strobe_crossing_rate(brights, float(analysis_fps))
    base_metrics = {
        "valid": bool(frames),
        "blank": blank,
        "clipped": bool(clipped or clipped_roi_bottom),
        "clipped_roi_bottom_any": bool(clipped_roi_bottom),
        "geometry_clipped_low": bool(clipped_roi_bottom),
        "analysis_fps": analysis_fps,
        "analysis_frame_count": len(frames),
        "analysis_nonblank_frames": nonblank_frames,
        "x_range": round(x_range, 3),
        "y_range": round(y_range, 3),
        "angle_range_deg": round(angle_range_deg, 3),
        "area_range_frac": round(area_range_frac, 5),
        "brightness_cv": round(brightness_cv, 5),
        "dominant_colors": dominant_colors,
        "strobe_frequency_hz": round(strobe_hz, 3) if strobe_hz is not None else None,
        "duty_cycle": round(duty_cycle, 3) if duty_cycle is not None else None,
        "strobe_crossings": crossings,
    }
    motion_type = classify_motion(entry, base_metrics)
    signal = movement_signal_for(motion_type, xs, ys, areas, brights, unwrapped)
    period, confidence = estimate_period(signal, float(analysis_fps))
    if motion_type == "strobe_gate" and strobe_hz:
        period = 1.0 / strobe_hz if strobe_hz > 0 else None
        confidence = max(confidence, min(1.0, crossings / max(4.0, len(frames) / analysis_fps)))
    duration = float(entry.get("duration") or (len(frames) / analysis_fps if analysis_fps else 0))
    periodic = motion_type not in {"static", "color_chase", "unknown"}
    motion_characterized = (
        motion_type == "strobe_gate" and strobe_hz is not None
    ) or (
        motion_type not in {"static", "unknown"} and confidence >= 0.35
    )
    direction = "unknown_from_numeric_analysis"
    direction_source = "numeric_regression_slope"
    direction_confidence = 0.0
    signed_slope = 0.0
    if motion_type == "horizontal_sweep" and len(xs) > 3:
        signed_slope, direction_confidence = regression_slope(xs, float(analysis_fps))
        direction = "rightward" if signed_slope > 0 else "leftward"
    elif motion_type == "vertical_sweep" and len(ys) > 3:
        signed_slope, direction_confidence = regression_slope(ys, float(analysis_fps))
        direction = "downward" if signed_slope > 0 else "upward"
    elif motion_type in {"smooth_rotation", "stepped_rotation"} and len(unwrapped) > 3:
        signed_slope, direction_confidence = regression_slope(unwrapped, float(analysis_fps))
        direction = "clockwise_or_counterclockwise_requires_visual_review"
        direction_source = "pca_regression_requires_visual_review"
    elif motion_type == "pulse_zoom" and len(areas) > 3:
        signed_slope, direction_confidence = regression_slope([float(a) for a in areas], float(analysis_fps))
        direction = "growing" if signed_slope > 0 else "shrinking"
    elif motion_type == "wave_deformation":
        direction = "wave_direction_requires_visual_review"
        direction_source = "visual_review_required"

    return {
        **entry,
        "analysis": {
            **base_metrics,
            "motion_type": motion_type,
            "motion_direction": direction,
            "motion_direction_source": direction_source,
            "motion_direction_confidence": round(direction_confidence, 4),
            "motion_signed_slope_per_second": round(signed_slope, 5),
            "loop_duration_estimate": round(period, 4) if period is not None else None,
            "loop_confidence": round(confidence, 4),
            "full_loop_captured": bool(period is not None and duration >= period * 1.15),
            "periodic_motion": periodic,
            "motion_characterized": motion_characterized,
            "fast_motion_timing_inferred": bool(motion_characterized and motion_type not in {"strobe_gate", "static", "color_chase"}),
            "usable_evidence": bool(not blank and not clipped_roi_bottom and (confidence >= 0.35 or motion_type == "strobe_gate")),
            "analysis_notes": "ROI-bottom clipping is surfaced as geometry_clipped_low; dim-beam threshold lowered for super-dim footage; direction labels from numeric trend are provisional unless visually reviewed",
        },
    }


def analyze_existing(args: argparse.Namespace) -> None:
    root = Path(args.root)
    manifest = root / "manifest.jsonl"
    out = root / "analysis_manifest.jsonl"
    rows = load_jsonl(manifest)
    with out.open("w", encoding="utf-8") as fh:
        for idx, entry in enumerate(rows, 1):
            print(f"[{idx}/{len(rows)}] analyze {entry['test_id']}", flush=True)
            analyzed = analyze_existing_entry(entry, args.analysis_fps, args.threshold)
            fh.write(json.dumps(analyzed) + "\n")
    print(out)


def case_dir(root: Path, case: CaptureCase) -> Path:
    family_slug = case.family.replace("+", "__").replace("|", "__")
    return root / "captures" / family_slug / case.test_id


def capture(args: argparse.Namespace) -> None:
    coverage = load_json(COVERAGE_PATH)
    include_fast_motion = bool(args.include_fast_motion or args.fps >= 60)
    capture_cases, deferred = select_targets(coverage, include_fast_motion)
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.jsonl"
    defer_path = root / "deferred_high_fps_cues.json"
    plan_path = root / "capture_plan.json"
    write_json(plan_path, {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "capture_now_count": len(capture_cases),
        "deferred_high_fps_count": len(deferred),
        "fps": args.fps,
        "analysis_fps": args.analysis_fps,
        "pixel_format": args.pixel_format,
        "video_size": args.size,
        "include_fast_motion": include_fast_motion,
        "capture_cases": [case.__dict__ | {"ch1_19": {f"CH{ch}": case.dmx[ch] for ch in range(1, 20)}} for case in capture_cases],
        "deferred_high_fps": deferred,
    })
    write_json(defer_path, deferred)

    if args.plan_only:
        print(plan_path)
        print(defer_path)
        return

    quit_soundswitch()
    daemon: subprocess.Popen[str] | None = None
    try:
        if args.start_daemon:
            daemon = start_dmx_daemon()
            time.sleep(2.0)
        for idx, case in enumerate(capture_cases, 1):
            outdir = case_dir(root, case)
            outdir.mkdir(parents=True, exist_ok=True)
            video = outdir / "video.mp4"
            strip = root / "frame_strips" / f"{case.test_id}.png"
            frames = outdir / "frames"
            metadata = outdir / "metadata.json"
            print(f"[{idx}/{len(capture_cases)}] {case.test_id} {case.duration:.1f}s {case.family}", flush=True)
            set_dmx(case.dmx)
            time.sleep(args.hold)
            started = time.strftime("%Y-%m-%dT%H:%M:%S")
            ffmpeg_capture(args.device, case.duration, video, args.fps, args.pixel_format, args.size)
            analysis = analyze_video(video, case.duration, frames, strip, f"{case.cue_name} | {case.family}", args.analysis_fps)
            entry = {
                "ts": started,
                "test_id": case.test_id,
                "cue_id": case.cue_id,
                "cue_name": case.cue_name,
                "family": case.family,
                "capture": str(video),
                "capture_dir": str(outdir),
                "frame_strip": str(strip),
                "metadata_path": str(metadata),
                "full_ch1_19_dmx": {str(ch): case.dmx[ch] for ch in range(1, 20)},
                "duration": case.duration,
                "requested_frame_rate": args.fps,
                "analysis_frame_rate": args.analysis_fps,
                "camera": {"device": args.device, "size": args.size, "pixel_format": args.pixel_format},
                "mode": case.mode,
                "reason": case.reason,
                "analysis": analysis,
                "scope_guard": {
                    "ch20_36_omitted": True,
                    "renderer_untouched": True,
                    "fast_motion_timing_inferred": bool(args.fps >= 60 and args.analysis_fps > DEFAULT_ANALYSIS_RATE),
                },
            }
            write_json(metadata, entry)
            with manifest_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
    finally:
        safety = blackout()
        (root / "safety_state.txt").write_text(safety + "\n", encoding="utf-8")
        if daemon is not None:
            daemon.terminate()
            try:
                daemon.wait(timeout=3)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait(timeout=3)
        print(f"safety: {safety}", flush=True)
    print(manifest_path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def make_contact_sheet(entries: list[dict[str, Any]], out: Path, title: str) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    thumbs: list[tuple[str, Image.Image]] = []
    for entry in entries:
        samples = entry.get("analysis", {}).get("samples") or []
        sample = samples[len(samples) // 2] if samples else None
        if not sample:
            continue
        im = Image.open(sample["frame"]).convert("RGB").resize((260, 146), Image.Resampling.LANCZOS)
        thumbs.append((entry["cue_name"], im))
    cols = 2
    label_h = 34
    cell_w, cell_h = 260, 146 + label_h
    rows = max(1, (len(thumbs) + cols - 1) // cols)
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h + 28), (10, 10, 10))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), title[:150], fill=(255, 255, 0))
    for idx, (label, im) in enumerate(thumbs):
        x = (idx % cols) * cell_w
        y = 28 + (idx // cols) * cell_h
        draw.text((x + 5, y + 5), label[:45], fill=(255, 255, 0))
        canvas.paste(im, (x, y + label_h))
    canvas.save(out)
    return out


def render_virtual_sheet(entries: list[dict[str, Any]], out: Path) -> Path | None:
    if not entries:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    chunk_paths: list[Path] = []
    chunk_size = 24
    for chunk_idx in range(0, len(entries), chunk_size):
        chunk = entries[chunk_idx:chunk_idx + chunk_size]
        args = []
        for entry in chunk:
            dmx = entry["full_ch1_19_dmx"]
            spec = ",".join(f"{ch}={dmx[str(ch)]}" for ch in range(1, 20))
            label = entry["cue_name"].replace("|", "/")[:45]
            args.append(f"{label}|{spec}")
        chunk_out = out.with_name(f"{out.stem}_part{len(chunk_paths)+1:02d}{out.suffix}")
        width = 600
        height = max(220, ((len(args) + 1) // 2) * 190)
        run([sys.executable, str(ROOT / "calib" / "export_grid.py"), str(chunk_out), f"{width}x{height}", *args])
        chunk_paths.append(chunk_out)
    images = [Image.open(path).convert("RGB") for path in chunk_paths]
    stitched = Image.new("RGB", (max(im.width for im in images), sum(im.height for im in images)), (0, 0, 0))
    y = 0
    for im in images:
        stitched.paste(im, (0, y))
        y += im.height
    stitched.save(out)
    return out


def make_comparison_sheet(real_sheet: Path, virtual_sheet: Path | None, out: Path) -> Path | None:
    if virtual_sheet is None or not virtual_sheet.exists() or not real_sheet.exists():
        return None
    real = Image.open(real_sheet).convert("RGB")
    virtual = Image.open(virtual_sheet).convert("RGB")
    target_w = 600
    real = real.resize((target_w, max(1, int(real.height * target_w / real.width))), Image.Resampling.LANCZOS)
    virtual = virtual.resize((target_w, max(1, int(virtual.height * target_w / virtual.width))), Image.Resampling.LANCZOS)
    height = max(real.height, virtual.height) + 34
    canvas = Image.new("RGB", (target_w * 2, height), (8, 8, 8))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), "REAL WALL CAPTURES", fill=(255, 255, 0))
    draw.text((target_w + 8, 8), "VIRTUAL RENDERS", fill=(255, 255, 0))
    canvas.paste(real, (0, 34))
    canvas.paste(virtual, (target_w, 34))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def build(args: argparse.Namespace) -> None:
    root = Path(args.root)
    manifest = root / "manifest.jsonl"
    entries = load_jsonl(manifest)
    coverage = load_json(COVERAGE_PATH)
    existing_dense_stats = coverage.get("statistics", {}).get("dense_breakpoint_pass") or {}
    before_actions = Counter(existing_dense_stats.get("before_next_actions") or Counter(c["recommended_next_action"] for c in coverage["cues"]))
    before_match = Counter(existing_dense_stats.get("before_match_types") or Counter(c["match_type"] for c in coverage["cues"]))
    exact_by_cue = {entry["cue_id"]: entry for entry in entries if not entry.get("analysis", {}).get("blank")}
    exact_by_vector = {
        tuple(int(entry["full_ch1_19_dmx"][str(ch)]) for ch in range(1, 20)): entry
        for entry in entries
        if not entry.get("analysis", {}).get("blank")
    }
    deferred = load_json(root / "deferred_high_fps_cues.json") if (root / "deferred_high_fps_cues.json").exists() else []

    for cue in coverage["cues"]:
        cue_vector = tuple(int(cue["ch1_19"][f"CH{ch}"]) for ch in range(1, 20))
        if cue["cue_id"] in exact_by_cue or cue_vector in exact_by_vector:
            cap = exact_by_cue.get(cue["cue_id"]) or exact_by_vector[cue_vector]
            cue["best_capture_match_id"] = cap["test_id"]
            cue["best_capture_path"] = cap["capture"]
            cue["best_capture_motion_type"] = "gradient/color/static exact cue evidence"
            cue["best_capture_quality_usable"] = True
            cue["best_capture_loop_confidence"] = None
            cue["match_type"] = "exact_ch1_19_match"
            cue["match_confidence"] = 1.0
            cue["evidence_quality"] = "direct_dense_breakpoint_evidence"
            cue["timing_reliability"] = "gradient/color evidence captured at 30fps; fast motion not inferred"
            cue["missing_evidence_reason"] = ""
            cue["recommended_next_action"] = "ready_motion_mapping" if cue.get("is_motion") or cue.get("calibration_type") != "static" else "ready_static_validation"
            cue["dense_breakpoint_capture"] = {
                "capture_root": str(root),
                "manifest": str(manifest),
                "test_id": cap["test_id"],
                "frame_strip": cap["frame_strip"],
                "captured_at": cap["ts"],
                "matched_by": "cue_id" if cue["cue_id"] == cap["cue_id"] else "identical_ch1_19_vector",
            }
        elif cue.get("recommended_next_action") == "needs_dense_breakpoint_capture" and family_is_fast_motion(cue["recommended_renderer_preset_family"]):
            cue["recommended_next_action"] = "needs_timed_capture"
            cue["missing_evidence_reason"] = "fast spin/sweep/zoom/wave/path family deferred to higher-fps timed capture; 30fps->12fps analysis aliases timing"
            cue["dense_breakpoint_defer_reason"] = "requires 60/120/240fps capture and higher analysis extraction fps"

    after_actions = Counter(c["recommended_next_action"] for c in coverage["cues"])
    after_match = Counter(c["match_type"] for c in coverage["cues"])
    coverage.setdefault("inputs", {})["dense_breakpoint_capture_root"] = str(root)
    coverage.setdefault("inputs", {})["attribute_cue_layering_note"] = (
        "SoundSwitch Attribute Cues may be sparse/layered workflow cues. The current extracted JSON has resolved CH1-19 DMX values "
        "but no checked/authored-channel metadata, so dense captures prove resolved-vector evidence, not that every cue independently authors every channel."
    )
    coverage.setdefault("statistics", {})["dense_breakpoint_pass"] = {
        "capture_root": str(root),
        "manifest": str(manifest),
        "exact_cue_captures": len(exact_by_cue),
        "exact_cues_covered_including_duplicate_vectors": sum(1 for c in coverage["cues"] if c.get("match_type") == "exact_ch1_19_match"),
        "high_fps_deferred_cues": len(deferred),
        "before_next_actions": dict(before_actions),
        "after_next_actions": dict(after_actions),
        "before_match_types": dict(before_match),
        "after_match_types": dict(after_match),
    }
    write_json(UPDATED_COVERAGE_PATH, coverage)

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_family[entry["family"]].append(entry)
    contact_paths = []
    for family, rows in sorted(by_family.items()):
        slug = family.replace("+", "__").replace("|", "__")
        contact_paths.append(make_contact_sheet(rows, root / "contact_sheets" / f"{slug}.png", family))
    master_contact = make_contact_sheet(entries, root / "contact_sheets" / "dense_breakpoint_master.png", "Dense cue breakpoint exact-state captures")
    virtual_sheet = render_virtual_sheet(entries, root / "virtual_sheets" / "dense_breakpoint_virtual.png") if args.virtual else None
    comparison_sheet = make_comparison_sheet(master_contact, virtual_sheet, root / "comparison_sheets" / "dense_breakpoint_real_vs_virtual.png")

    target_cues = [c for c in load_json(COVERAGE_PATH)["cues"] if c["recommended_next_action"] == "needs_dense_breakpoint_capture"]
    variance = channel_variance(target_cues)
    lines = [
        "# Dense cue breakpoint capture",
        "",
        "Evidence-only pass using real extracted SoundSwitch cue states. Renderer behavior and calibration render values were not changed.",
        "",
        "## Scope",
        f"- Capture root: `{root}`",
        f"- Manifest: `{manifest}`",
        f"- Capture-now exact cue states: {len(entries)}",
        f"- Fast-motion cues deferred to high-fps capture: {len(deferred)}",
        "- Fast-motion dense capture at 30fps was intentionally skipped because the existing 30fps->12fps analysis aliases spin/sweep/zoom/wave timing.",
        "- Full-frame capture was used for this pass; the previous left-side ROI is not used here.",
        "- SoundSwitch Attribute Cues may be layered. The current cue JSON exposes resolved CH1-19 DMX values but not checked/authored-channel metadata, so this report treats captures as resolved-vector evidence rather than proof that each cue independently defines every channel.",
        "",
        "## Artifacts",
        f"- Master real contact sheet: `{master_contact}`",
        f"- Virtual render sheet: `{virtual_sheet}`" if virtual_sheet else "- Virtual render sheet: not generated",
        f"- Real-vs-virtual comparison sheet: `{comparison_sheet}`" if comparison_sheet else "- Real-vs-virtual comparison sheet: not generated",
        f"- Deferred high-fps cue list: `{root / 'deferred_high_fps_cues.json'}`",
        f"- Updated coverage JSON: `{UPDATED_COVERAGE_PATH}`",
        "",
        "Family contact sheets:",
    ]
    for path in contact_paths:
        lines.append(f"- `{path}`")
    lines.extend([
        "",
        "## Captured Cue States",
        "",
        "| cue | family | CH1-19 | capture | frame strip |",
        "|---|---|---|---|---|",
    ])
    for entry in entries:
        dmx = " ".join(f"CH{ch}={entry['full_ch1_19_dmx'][str(ch)]}" for ch in range(1, 20))
        lines.append(f"| {entry['cue_name']} | `{entry['family']}` | `{dmx}` | `{entry['capture']}` | `{entry['frame_strip']}` |")
    lines.extend([
        "",
        "## Coverage Change",
        f"- Before next_action: `{dict(before_actions)}`",
        f"- After next_action: `{dict(after_actions)}`",
        f"- Before match_type: `{dict(before_match)}`",
        f"- After match_type: `{dict(after_match)}`",
        f"- Exact CH1-19 matches gained: {after_match.get('exact_ch1_19_match', 0) - before_match.get('exact_ch1_19_match', 0)}",
        "",
        "## Target Family Channel Variance",
    ])
    for family, channels in sorted(variance.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:30]:
        lines.append(f"- `{family}` varies CH{', CH'.join(map(str, channels)) if channels else 'none'}")
    lines.extend([
        "",
        "## High-Fps Deferred Cues",
        f"- Count: {len(deferred)}",
        "- Reason: fast-motion families need 60/120/240fps capture and analysis extraction above 12fps.",
        "",
        "## Next Recommendation",
        "Use the direct dense captures for gradient/static exact-state renderer mapping next. Keep CH11 strobe as the highest-confidence timed family. Run a separate high-fps timed pass for the 116 deferred fast-motion cues before tuning spin, sweep, zoom-pulse, or wave rates.",
    ])
    DENSE_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Append a short pointer to the main coverage report without rewriting its
    # original bridge narrative.
    existing = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else ""
    marker = "\n## Dense Cue Breakpoint Pass\n"
    if marker in existing:
        existing = existing.split(marker, 1)[0].rstrip() + "\n"
    existing += marker
    existing += f"\n- Dense capture report: `{DENSE_REPORT_PATH}`\n"
    existing += f"- Dense capture root: `{root}`\n"
    existing += f"- Exact CH1-19 matches gained: {after_match.get('exact_ch1_19_match', 0) - before_match.get('exact_ch1_19_match', 0)}\n"
    existing += f"- Fast-motion cues deferred to high-fps timed capture: {len(deferred)}\n"
    existing += "- Renderer behavior and calibration render values were not changed.\n"
    REPORT_PATH.write_text(existing, encoding="utf-8")
    print(DENSE_REPORT_PATH)


def dmx_from_cue_entry(cue: dict[str, Any]) -> dict[int, int]:
    return {ch: int(cue["ch1_19"][f"CH{ch}"]) for ch in range(1, 20)}


def dynamic_ch3(dmx: dict[int, int]) -> bool:
    return dmx[3] >= 128


def has_periodic_motion_channel(dmx: dict[int, int], family: str) -> bool:
    return any((
        dmx[12] >= 144,
        dmx[13] >= 128,
        dmx[14] >= 128,
        dmx[15] >= 128,
        dmx[16] >= 128,
        dmx[17] >= 152,
        dmx[19] > 0,
        "motion_macro" in family,
    ))


def static_color_strobe_ready(cue: dict[str, Any], dmx: dict[int, int], analysis: dict[str, Any] | None) -> bool:
    if dmx[11] > 0 and cue.get("strobe_timing_evidence_usable"):
        return True
    if analysis and analysis.get("motion_type") in {"static", "color_chase"} and not has_periodic_motion_channel(dmx, cue["recommended_renderer_preset_family"]):
        return True
    if cue.get("calibration_type") in STATIC_COLOR_STROBE_TYPES and not has_periodic_motion_channel(dmx, cue["recommended_renderer_preset_family"]):
        return True
    if "gradient" in cue["recommended_renderer_preset_family"] and not has_periodic_motion_channel(dmx, cue["recommended_renderer_preset_family"]):
        return True
    return False


def reclassify_coverage(args: argparse.Namespace) -> None:
    root = Path(args.root)
    analysis_path = Path(args.analysis) if args.analysis else root / "analysis_manifest.jsonl"
    coverage = load_json(COVERAGE_PATH)
    before_actions = Counter(c["recommended_next_action"] for c in coverage["cues"])
    before_timing = Counter(c.get("timing_reliability") for c in coverage["cues"])
    analysis_rows = load_jsonl(analysis_path)
    by_vector = {
        tuple(int(row["full_ch1_19_dmx"][str(ch)]) for ch in range(1, 20)): row
        for row in analysis_rows
    }
    by_cue = {row["cue_id"]: row for row in analysis_rows}

    motion_family_captures = [
        row for row in analysis_rows
        if family_is_fast_motion(row.get("family", ""))
    ]
    resolved_motion_captures = [
        row for row in motion_family_captures
        if row.get("analysis", {}).get("motion_characterized")
    ]
    pending_motion_captures = [
        row for row in motion_family_captures
        if not row.get("analysis", {}).get("motion_characterized")
    ]

    for cue in coverage["cues"]:
        dmx = dmx_from_cue_entry(cue)
        vector = tuple(dmx[ch] for ch in range(1, 20))
        analysis_row = by_cue.get(cue["cue_id"]) or by_vector.get(vector)
        analysis = analysis_row.get("analysis") if analysis_row else None
        if dynamic_ch3(dmx):
            cue["recommended_next_action"] = "defer"
            cue["timing_reliability"] = "dynamic_macro_out_of_scope"
            cue["missing_evidence_reason"] = "dynamic macro - out of CH1-19 deterministic dense motion scope"
            continue

        if analysis_row:
            cue["best_capture_match_id"] = analysis_row["test_id"]
            cue["best_capture_path"] = analysis_row["capture"]
            cue["best_capture_motion_type"] = analysis.get("motion_type")
            cue["best_capture_quality_usable"] = not analysis.get("blank", True)
            cue["best_capture_loop_confidence"] = analysis.get("loop_confidence")
            cue["match_type"] = "exact_ch1_19_match"
            cue["match_confidence"] = 1.0
            cue["dense_motion_analysis"] = {
                "analysis_manifest": str(analysis_path),
                "test_id": analysis_row["test_id"],
                "motion_type": analysis.get("motion_type"),
                "motion_characterized": analysis.get("motion_characterized"),
                "loop_duration_estimate": analysis.get("loop_duration_estimate"),
                "loop_confidence": analysis.get("loop_confidence"),
                "strobe_frequency_hz": analysis.get("strobe_frequency_hz"),
                "motion_direction": analysis.get("motion_direction"),
            }
            if analysis.get("motion_characterized") and analysis.get("motion_type") not in {"static", "color_chase"}:
                cue["recommended_next_action"] = "ready_motion_mapping"
                cue["timing_reliability"] = "motion_extracted_from_60fps_dense_capture"
                cue["evidence_quality"] = "motion_characterized_dense_60fps"
                cue["missing_evidence_reason"] = ""
            elif static_color_strobe_ready(cue, dmx, analysis):
                cue["recommended_next_action"] = "ready_static_color_strobe"
                cue["timing_reliability"] = (
                    "reliable_strobe_timing" if dmx[11] > 0 and cue.get("strobe_timing_evidence_usable")
                    else "exact_static_color_gradient_resolved_vector"
                )
                cue["evidence_quality"] = "direct_static_color_strobe_evidence"
                cue["missing_evidence_reason"] = ""
            else:
                cue["recommended_next_action"] = "motion_analysis_pending"
                cue["timing_reliability"] = "60fps_footage_analyzed_but_motion_unresolved"
                cue["evidence_quality"] = "exact_vector_filmed_motion_unresolved"
                cue["missing_evidence_reason"] = "exact vector filmed at 60fps, but motion_type/period did not pass confidence gate"
        elif cue.get("strobe_timing_evidence_usable"):
            cue["recommended_next_action"] = "ready_static_color_strobe"
            cue["timing_reliability"] = "reliable_strobe_timing"
            cue["evidence_quality"] = "representative_reliable_strobe_timing"
            cue["missing_evidence_reason"] = ""
        elif cue.get("recommended_next_action") == "ready_static_validation":
            cue["recommended_next_action"] = "ready_static_color_strobe"
            cue["timing_reliability"] = "static_or_not_timed"
        else:
            cue["recommended_next_action"] = "motion_analysis_pending"
            cue["timing_reliability"] = "no_dense_motion_analysis_match"
            cue["missing_evidence_reason"] = "no exact dense analysis row matched this cue"

    after_actions = Counter(c["recommended_next_action"] for c in coverage["cues"])
    after_timing = Counter(c.get("timing_reliability") for c in coverage["cues"])
    per_channel: dict[str, list[dict[str, Any]]] = {str(ch): [] for ch in (12, 15, 16, 17, 19)}
    for row in analysis_rows:
        dmx = {int(ch): int(val) for ch, val in row["full_ch1_19_dmx"].items()}
        analysis = row["analysis"]
        for ch in (12, 15, 16, 17, 19):
            if dmx.get(ch, 0):
                per_channel[str(ch)].append({
                    "test_id": row["test_id"],
                    "cue_name": row["cue_name"],
                    "value": dmx[ch],
                    "motion_type": analysis.get("motion_type"),
                    "direction": analysis.get("motion_direction"),
                    "loop_duration_estimate": analysis.get("loop_duration_estimate"),
                    "loop_confidence": analysis.get("loop_confidence"),
                    "strobe_frequency_hz": analysis.get("strobe_frequency_hz"),
                    "motion_characterized": analysis.get("motion_characterized"),
                })

    coverage.setdefault("inputs", {})["dense_motion_analysis_manifest"] = str(analysis_path)
    coverage.setdefault("inputs", {})["attribute_cue_layering_note"] = (
        "SoundSwitch Attribute Cues may be sparse/layered workflow cues. The current extracted JSON has resolved CH1-19 DMX values "
        "but no checked/authored-channel metadata, so coverage describes resolved-vector behavior, not per-channel cue authorship."
    )
    coverage.setdefault("statistics", {})["dense_motion_reclassification"] = {
        "analysis_manifest": str(analysis_path),
        "min_lag_floor_before": "0.35s coefficient, about 2.85Hz max detectable periodic motion",
        "min_lag_floor_after": "0.07s coefficient, about 15Hz at 30fps analysis",
        "before_next_actions": dict(before_actions),
        "after_next_actions": dict(after_actions),
        "before_timing_reliability": dict(before_timing),
        "after_timing_reliability": dict(after_timing),
        "motion_family_captures": len(motion_family_captures),
        "motion_family_captures_resolved": len(resolved_motion_captures),
        "motion_family_captures_pending": len(pending_motion_captures),
        "per_channel_motion_summary": per_channel,
    }
    write_json(UPDATED_COVERAGE_PATH, coverage)
    write_motion_report(root, coverage, analysis_rows, before_actions, after_actions, per_channel)
    print(UPDATED_COVERAGE_PATH)


def write_motion_report(
    root: Path,
    coverage: dict[str, Any],
    analysis_rows: list[dict[str, Any]],
    before_actions: Counter[str],
    after_actions: Counter[str],
    per_channel: dict[str, list[dict[str, Any]]],
) -> None:
    stats = coverage["statistics"]["dense_motion_reclassification"]
    lines = [
        "# SoundSwitch cue motion coverage",
        "",
        "Corrected evidence bridge between extracted SoundSwitch Attribute Cue resolved DMX vectors and physical capture evidence.",
        "",
        "Renderer behavior and calibration render values were not changed.",
        "",
        "Important cue semantics: SoundSwitch Attribute Cues may be sparse/layered workflow cues. The current extracted JSON exposes resolved CH1-19 DMX values but not checked/authored-channel metadata, so this coverage describes resolved-vector behavior, not proof that each cue independently authors every channel.",
        "",
        "## Dense Motion Analysis",
        f"- Capture root: `{root}`",
        f"- Analysis manifest: `{stats['analysis_manifest']}`",
        "- No new physical capture was run.",
        "- Frequency floor changed from `0.35s` min lag to `0.07s` min lag for non-strobe periodic analysis.",
        "- Strobe remains on crossing-count frequency estimation.",
        "- Clipping is ignored for usability; true blanks and confidence gate drive classification.",
        "",
        "## Corrected Buckets",
        f"- Before recommended_next_action: `{dict(before_actions)}`",
        f"- After recommended_next_action: `{dict(after_actions)}`",
        f"- Genuinely motion-ready: {after_actions.get('ready_motion_mapping', 0)}",
        f"- Static/colour/strobe-ready: {after_actions.get('ready_static_color_strobe', 0)}",
        f"- Motion analysis pending: {after_actions.get('motion_analysis_pending', 0)}",
        f"- Deferred dynamic CH3 macros: {after_actions.get('defer', 0)}",
        "",
        "## Motion Capture Resolution",
        f"- Motion-family captures analyzed: {stats['motion_family_captures']}",
        f"- Motion-family captures resolved to confidence-gated motion: {stats['motion_family_captures_resolved']}",
        f"- Motion-family captures still pending/unresolved: {stats['motion_family_captures_pending']}",
        "",
        "## Per-Channel Motion Summary",
    ]
    for ch in ("12", "15", "16", "17", "19"):
        rows = per_channel[ch]
        resolved = [r for r in rows if r["motion_characterized"]]
        lines.extend([
            "",
            f"### CH{ch} {MOTION_CHANNELS[int(ch)]}",
            f"- States with CH{ch} active: {len(rows)}",
            f"- Resolved: {len(resolved)}",
            "",
            "| value | cue | motion | direction | period_s | confidence | strobe_hz | status |",
            "|---:|---|---|---|---:|---:|---:|---|",
        ])
        for row in rows[:80]:
            status = "resolved" if row["motion_characterized"] else "pending"
            lines.append(
                f"| {row['value']} | {row['cue_name']} | {row['motion_type']} | {row['direction']} | "
                f"{row['loop_duration_estimate']} | {row['loop_confidence']} | {row['strobe_frequency_hz']} | {status} |"
            )
    pending = [c for c in coverage["cues"] if c["recommended_next_action"] == "motion_analysis_pending"]
    lines.extend([
        "",
        "## Pending Cues",
        "",
        "| cue | family | reason |",
        "|---|---|---|",
    ])
    for cue in pending:
        lines.append(f"| {cue['cue_name']} | `{cue['recommended_renderer_preset_family']}` | {cue.get('missing_evidence_reason', '')} |")
    lines.extend([
        "",
        "## Exact Next Recommendation",
        "Use `ready_static_color_strobe` cues for static, colour, gradient, position, and strobe preset mapping. Use `ready_motion_mapping` only for cues whose dense analysis has `motion_characterized=true`. Do not tune unresolved spin/sweep/zoom/wave families until they either pass this analysis gate or are visually reviewed from frame strips for direction and period.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense cue breakpoint evidence capture")
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--root", default=str(DEFAULT_ROOT))
    plan.add_argument("--fps", type=int, default=DEFAULT_FRAME_RATE)
    plan.add_argument("--analysis-fps", type=int, default=DEFAULT_ANALYSIS_RATE)
    plan.add_argument("--pixel-format", default=DEFAULT_PIXEL_FORMAT)
    plan.add_argument("--size", default=DEFAULT_SIZE)
    plan.add_argument("--include-fast-motion", action="store_true")
    plan.set_defaults(func=lambda a: capture(argparse.Namespace(root=a.root, plan_only=True, start_daemon=False, device="2", hold=0.8, fps=a.fps, analysis_fps=a.analysis_fps, pixel_format=a.pixel_format, size=a.size, include_fast_motion=a.include_fast_motion)))
    cap = sub.add_parser("capture")
    cap.add_argument("--root", default=str(DEFAULT_ROOT))
    cap.add_argument("--device", default="2")
    cap.add_argument("--hold", type=float, default=0.8)
    cap.add_argument("--fps", type=int, default=DEFAULT_FRAME_RATE)
    cap.add_argument("--analysis-fps", type=int, default=DEFAULT_ANALYSIS_RATE)
    cap.add_argument("--pixel-format", default=DEFAULT_PIXEL_FORMAT)
    cap.add_argument("--size", default=DEFAULT_SIZE)
    cap.add_argument("--include-fast-motion", action="store_true")
    cap.add_argument("--start-daemon", action="store_true")
    cap.add_argument("--plan-only", action="store_true")
    cap.set_defaults(func=capture)
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--root", required=True)
    build_cmd.add_argument("--virtual", action="store_true")
    build_cmd.set_defaults(func=build)
    analyze_cmd = sub.add_parser("analyze-existing")
    analyze_cmd.add_argument("--root", required=True)
    analyze_cmd.add_argument("--analysis-fps", type=int, default=30)
    analyze_cmd.add_argument("--threshold", type=int, default=58)
    analyze_cmd.set_defaults(func=analyze_existing)
    reclass = sub.add_parser("reclassify")
    reclass.add_argument("--root", required=True)
    reclass.add_argument("--analysis")
    reclass.set_defaults(func=reclassify_coverage)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
