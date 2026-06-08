#!/usr/bin/env python3
"""Sequential CH1-19 fixture model orchestrator.

This is a measurement runner, not a renderer tuning script. Physical DMX output
is enabled only with --rig-confirmed. Without that flag it plans and runs
no-rig/code phases only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DMX = ROOT / "calib" / "dmx_open.py"        # active driver; main() may switch to pro
DMX_OPEN = ROOT / "calib" / "dmx_open.py"
DMX_PRO = ROOT / "calib" / "dmx_pro.py"
DMX_BACKEND = "open"                          # set in main() from --dmx-backend
DMX_PORT: str | None = None                   # set in main() from --dmx-port
DENSE = ROOT / "calib" / "dense_cue_breakpoints.py"
CAPTURE_ROOT = ROOT / "captures" / "fixture_model"
MANIFEST = CAPTURE_ROOT / "manifest.jsonl"
CHECKPOINT = CAPTURE_ROOT / "checkpoint.json"
SETUP_GEOMETRY_PATH = CAPTURE_ROOT / "setup_geometry.json"
ANALYSIS_GEOMETRY_PATH = CAPTURE_ROOT / "analysis_geometry.json"
MODEL_PATH = ROOT / "data" / "fixture_model.json"
SCHEMA_PATH = ROOT / "data" / "fixture_model_schema.json"
REPORT_DIR = ROOT / "docs"
HASH_GUARDS = (ROOT / "static" / "renderer.js", ROOT / "calibration.json", ROOT / "fixtures.py")
EXISTING_DENSE_ROOT = Path("/tmp/vln_dense_cue_breakpoints_20260605_200426")
MAX_CAPTURES = 10000   # ceiling on captures TAKEN THIS INVOCATION; covers the ~5236-row coarse program + Phase-3 gate expansion
SESSION_BASELINE_CAPTURES = 0   # manifest rows present when this invocation started; set in main()
DEVICE = "2"
CAMERA_NAME = os.environ.get("VLN_CAMERA_NAME", "Continuity Camera")
SIZE = os.environ.get("VLN_CAMERA_SIZE", "1280x720")
PIXEL_FORMAT = "nv12"
FPS = 60
ANALYSIS_FPS = 30
ANALYSIS_ROI_TOP_FRAC = 0.18
ANALYSIS_ROI_BOTTOM_FRAC = float(os.environ.get("VLN_ANALYSIS_ROI_BOTTOM_FRAC", "1.0"))  # fallback only; box-derived geometry is preferred
LASER_CORE_THRESHOLD_FLOOR = int(os.environ.get("VLN_LASER_CORE_THRESHOLD_FLOOR", "58"))
ANALYSIS_MASK_MAX_BRIGHT_FRACTION = float(os.environ.get("VLN_ANALYSIS_MASK_MAX_BRIGHT_FRACTION", "0.20"))
ANALYSIS_BOUNDARY_MARGIN_INCHES = float(os.environ.get("VLN_ANALYSIS_BOUNDARY_MARGIN_INCHES", "0.75"))
ANALYSIS_GLARE_CLEARANCE_PX = int(os.environ.get("VLN_ANALYSIS_GLARE_CLEARANCE_PX", "6"))
ANALYSIS_ROI_EDGE_MARGIN_PX = int(os.environ.get("VLN_ANALYSIS_ROI_EDGE_MARGIN_PX", "4"))
WHITE_REF_PATH = CAPTURE_ROOT / "phase1_single_channel" / "_white_reference" / "CH08_000_white_reference.jpg"
WATCHDOG_PATH = Path("/tmp/vln_calib_frame.heartbeat")
CORRECTED_ATLAS_STARTED_AT = "2026-06-06T03:11:00"
RUN_STATS = {"fps_resets": 0, "fps_reset_recovered": 0, "fps30": 0, "blank_retries": 0}
FRAME_STRIPS = False   # cosmetic contact sheets are opt-in; still.jpg/analysis stay required


CHANNEL_NAMES = {
    1: "master_dimmer",
    3: "static_pattern",
    4: "static_pattern_selection",
    5: "pattern_size",
    6: "horizontal_adjustment",
    7: "vertical_adjustment",
    8: "color",
    9: "color_speed",
    10: "pattern_line",
    11: "strobe",
    12: "rotation_z",
    13: "rotation_x",
    14: "rotation_y",
    15: "horizontal_movement",
    16: "vertical_movement",
    17: "zoom",
    18: "gradient",
    19: "x_y_wave",
}
MODELED_CHANNELS = tuple(CHANNEL_NAMES)
PROBE_CHANNELS = (8, 10, 12, 15, 17, 18, 19)
CH1_ON_VALUE = 220
PRIMARY_BASE = {1: CH1_ON_VALUE, 2: 0, 3: 32, 4: 10, 5: 90, 6: 128, 7: 128, 8: 20, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0}
# PRIMARY_BASE is the capture baseline for sweeps and intentionally keeps CH5=90.
# GEOMETRY_REFERENCE_BASE is preflight-only: CH3=0 / CH4 in 60-64 / CH5=0 /
# CH6=128 / CH7=128 / CH17=0 projects the max-size rectangular boundary-box
# look on the pencil ticks so analysis ROI anchoring uses the physical
# projection boundary, not the line look.
GEOMETRY_REFERENCE_BASE = {**PRIMARY_BASE, 3: 0, 4: 62, 5: 0, 6: 128, 7: 128, 17: 0}
BASES = {
    "base_CH3_032_CH4_010": {**PRIMARY_BASE, 3: 32, 4: 10},
    "base_CH3_028_CH4_000": {**PRIMARY_BASE, 3: 28, 4: 0},
    "base_CH3_000_CH4_195": {**PRIMARY_BASE, 3: 0, 4: 195},
    "base_CH3_000_CH4_203": {**PRIMARY_BASE, 3: 0, 4: 203},
    "base_CH3_041_CH4_000": {**PRIMARY_BASE, 3: 41, 4: 0},
    "base_CH3_048_CH4_000": {**PRIMARY_BASE, 3: 48, 4: 0},
}
CORPUS_CH3_CH4_PAIRS = (
    (28, 0), (0, 195), (0, 203), (41, 0), (55, 0), (28, 78),
    (0, 0), (52, 100), (17, 0), (21, 48), (24, 0), (0, 41),
    (17, 255), (41, 121), (31, 0), (0, 225), (0, 234), (41, 124),
    (50, 103), (28, 93), (28, 153), (48, 28), (31, 255),
    (38, 135), (38, 138), (28, 139), (14, 86), (0, 69), (45, 41),
    (21, 107),
)


@dataclass(frozen=True)
class Case:
    phase: str
    group: str
    state: str
    dmx: dict[int, int]
    duration: float = 3.0
    timed: bool = False
    track: str = "geometry_motion"
    baseline: str = "base_CH3_032_CH4_010"
    changed_channels: dict[int, int] = field(default_factory=dict)
    expected: str = ""
    intent: str = ""

    @property
    def rel_dir(self) -> Path:
        if self.phase in {"phase1_5_base_dependence", "phase3_composition"}:
            return Path(self.phase) / self.baseline / self.group / self.state
        return Path(self.phase) / self.group / self.state

    @property
    def test_id(self) -> str:
        return "__".join(self.rel_dir.parts)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def run(cmd: list[str], *, check: bool = True, capture_output: bool = False, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, check=check, capture_output=capture_output, timeout=timeout)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_guard() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in HASH_GUARDS}


def assert_hash_unchanged(before: dict[str, str]) -> None:
    after = hash_guard()
    if before != after:
        raise RuntimeError(f"hash guard changed: before={before} after={after}")


def checkpoint(phase: str, status: str, extra: dict[str, Any] | None = None) -> None:
    data = load_json(CHECKPOINT, {})
    data.update({"phase": phase, "status": status, "updated_at": now()})
    if extra:
        data.update(extra)
    write_json(CHECKPOINT, data)


def subprocess_ok(cmd: list[str]) -> tuple[bool, str]:
    cp = run(cmd, check=False, capture_output=True)
    return cp.returncode == 0, (cp.stdout or "") + (cp.stderr or "")


def quit_soundswitch() -> None:
    run(["osascript", "-e", 'tell application "SoundSwitch" to quit'], check=False)
    for _ in range(20):
        cp = run(["pgrep", "-x", "SoundSwitch"], check=False, capture_output=True)
        if cp.returncode != 0:
            return
        time.sleep(0.5)
    raise RuntimeError("SoundSwitch is still running after quit request; aborting before DMX output")


def ftdi_ports() -> list[Path]:
    return sorted(Path("/dev").glob("cu.usbserial-*"))


def resolve_port() -> str:
    """Explicit --dmx-port wins; else first serial port; else 'auto' (Open self-picks).
    The Open and Pro share USB VID/PID 0403:6001, so when both could be present an
    explicit --dmx-port is the only unambiguous selector."""
    if DMX_PORT:
        return DMX_PORT
    ports = ftdi_ports()
    if DMX_BACKEND == "pro":
        if not ports:
            raise RuntimeError("no /dev/cu.usbserial-* serial port found for Enttec Pro")
        if len(ports) > 1:
            names = ", ".join(str(p) for p in ports)
            raise RuntimeError(f"multiple FTDI serial ports found for Enttec Pro; pass --dmx-port explicitly: {names}")
    return str(ports[0]) if ports else "auto"


def find_enttec_frame(raw: bytes | bytearray, expected_label: int | None = None) -> tuple[int, bytes, bytes] | None:
    data = bytes(raw)
    for i, byte in enumerate(data):
        if byte != 0x7E:
            continue
        if len(data) < i + 5:
            return None
        label = data[i + 1]
        n = data[i + 2] | (data[i + 3] << 8)
        end = i + 4 + n
        if len(data) <= end:
            return None
        if data[end] != 0xE7:
            continue
        if expected_label is not None and label != expected_label:
            continue
        return label, data[i + 4:end], data[i:end + 1]
    return None


def pro_identity_ok(port: str) -> tuple[bool, str]:
    """Send Get-Widget-Parameters (label 3) and confirm a framed reply.
    Read-only: drives NO DMX output. This is also the only reliable Open-vs-Pro
    discriminator (the Open has no firmware and never replies)."""
    try:
        import serial
    except Exception as e:
        return False, f"pyserial import failed: {e}"
    try:
        s = serial.Serial(port, baudrate=115200, timeout=0.05, write_timeout=1.0)
    except Exception as e:
        return False, f"serial open failed: {e}"
    raw = bytearray()
    parsed = None
    try:
        s.reset_input_buffer()
        s.write(bytes([0x7E, 3, 0x02, 0x00, 0x00, 0x00, 0xE7]))
        s.flush()
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            chunk = s.read(64)
            if chunk:
                raw.extend(chunk)
                parsed = find_enttec_frame(raw, expected_label=3)
                if parsed is not None:
                    break
            else:
                time.sleep(0.01)
    except Exception as e:
        return False, f"serial probe failed: {e}"
    finally:
        s.close()
    if parsed is None:
        return False, f"no complete label-3 frame in reply: {bytes(raw).hex(' ') or '(empty)'}"
    _label, payload, frame = parsed
    if len(payload) < 2:
        return False, f"label-3 reply too short: {frame.hex(' ')}"
    fw = payload[0] | (payload[1] << 8)
    return True, f"pro firmware={fw} reply={frame.hex(' ')}"


def blackout() -> str:
    cmd = [sys.executable, str(DMX), "blackout"]
    if DMX_BACKEND == "pro":
        cmd.extend(["--port", resolve_port()])
    run(cmd, check=True)
    time.sleep(0.15)
    cp = run([sys.executable, str(DMX), "show"], check=True, capture_output=True)
    return cp.stdout.strip()


def dmx_pairs(frame: dict[int, int]) -> list[str]:
    full = {ch: 0 for ch in range(1, 37)}
    full.update(frame)
    return [f"{ch}={full.get(ch, 0)}" for ch in range(1, 37)]


def set_dmx(frame: dict[int, int]) -> None:
    blackout()
    run([sys.executable, str(DMX), "set", *dmx_pairs(frame)], check=True)


def start_daemon() -> subprocess.Popen[str]:
    last_out = ""
    for attempt in range(1, 4):
        port = resolve_port()
        proc = subprocess.Popen([sys.executable, str(DMX), "daemon", "--port", port], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(2.0)
        if proc.poll() is None:
            return proc
        last_out = proc.stdout.read() if proc.stdout else ""
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"DMX daemon exited during startup after retries: {last_out}")


def stop_daemon(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    killed = False
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)
        killed = True
    if killed and DMX_BACKEND == "pro":
        try:
            blackout()
        except Exception as e:
            print(f"[dmx] post-kill Pro blackout attempt failed: {e}", flush=True)


def touch_watchdog() -> None:
    WATCHDOG_PATH.touch()


def start_watchdog_heartbeat() -> tuple[threading.Event, threading.Thread]:
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            touch_watchdog()
            stop.wait(1.0)

    thread = threading.Thread(target=loop, name="dmx-watchdog-heartbeat", daemon=True)
    thread.start()
    return stop, thread


def stop_watchdog_heartbeat(stop: threading.Event | None, thread: threading.Thread | None) -> None:
    if stop is None or thread is None:
        return
    stop.set()
    thread.join(timeout=2.0)


def _numeric(value: Any) -> float:
    if value in (None, "", "N/A"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ffprobe_stream(video: Path, show_entries: str, *, count_frames: bool = False) -> dict[str, Any]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0"]
    if count_frames:
        cmd.append("-count_frames")
    cmd.extend(["-show_entries", show_entries, "-of", "json", str(video)])
    cp = run(cmd, capture_output=True)
    info = json.loads(cp.stdout)
    return (info.get("streams") or [{}])[0]


def ffprobe_fps_counted(video: Path) -> float:
    """Guaranteed delivered-frame FPS path; decodes/counts frames and is slower."""
    stream = _ffprobe_stream(video, "stream=nb_read_frames,duration", count_frames=True)
    frames = _numeric(stream.get("nb_read_frames") or stream.get("nb_frames"))
    duration = _numeric(stream.get("duration"))
    return frames / duration if frames > 0 and duration > 0 else 0.0


def ffprobe_fps(video: Path) -> float:
    """Delivered-frame FPS, using MP4 header count first and decoded count fallback.

    Do not use avg_frame_rate as the gate value: it can reflect the requested rate.
    For libx264 MP4s from this pipeline, nb_frames/duration has empirically matched
    ffprobe -count_frames while avoiding a full frame decode.
    """
    stream = _ffprobe_stream(video, "stream=nb_frames,avg_frame_rate,duration", count_frames=False)
    frames = _numeric(stream.get("nb_frames"))
    duration = _numeric(stream.get("duration"))
    if frames > 0 and duration > 0:
        return frames / duration
    return ffprobe_fps_counted(video)


def frame_strip_enabled() -> bool:
    return FRAME_STRIPS


def set_frame_strips_enabled(enabled: bool) -> None:
    global FRAME_STRIPS
    FRAME_STRIPS = bool(enabled)


def ffprobe_fps_old_counted(video: Path) -> float:
    """Compatibility alias used by readiness tests and empirical comparisons."""
    return ffprobe_fps_counted(video)


def avfoundation_video_devices() -> list[tuple[str, str]]:
    cp = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    devices: list[tuple[str, str]] = []
    in_video = False
    for line in (cp.stderr + cp.stdout).splitlines():
        if "AVFoundation video devices:" in line:
            in_video = True
            continue
        if "AVFoundation audio devices:" in line:
            break
        if not in_video:
            continue
        marker = "] ["
        if marker not in line or "] " not in line:
            continue
        tail = line.split(marker, 1)[1]
        idx, name = tail.split("] ", 1)
        devices.append((idx.strip(), name.strip()))
    return devices


def resolve_camera_device(expected_name: str) -> tuple[str, str]:
    devices = avfoundation_video_devices()
    invalid_devices = [
        f"{idx}:{name}" for idx, name in devices
        if name.lower().startswith("capture screen") or "desk view" in name.lower()
    ]
    expected = expected_name.lower()
    exact_matches = [(idx, name) for idx, name in devices if name.lower() == expected]
    substring_matches = [(idx, name) for idx, name in devices if expected in name.lower()]
    matches = exact_matches or substring_matches
    if not matches:
        available = ", ".join(f"{idx}:{name}" for idx, name in devices) or "(none)"
        raise RuntimeError(
            f"expected camera containing {expected_name!r} not found. "
            f"Available AVFoundation video devices: {available}. "
            f"Refusing to fall back to numeric device {DEVICE}; invalid devices seen: {', '.join(invalid_devices) or '(none)'}"
        )
    idx, name = matches[0]
    lowered = name.lower()
    if lowered.startswith("capture screen") or "desk view" in lowered:
        raise RuntimeError(f"resolved camera is not the fixture-facing camera ({idx}:{name}); refusing capture")
    return idx, name


def assert_camera_device(expected_name: str) -> tuple[str, str]:
    global DEVICE
    idx, name = resolve_camera_device(expected_name)
    DEVICE = idx
    return idx, name


def frame_looks_like_desktop(path: Path) -> bool:
    im = Image.open(path).convert("L")
    w, h = im.size
    if w <= 0 or h <= 0:
        return False
    top = im.crop((0, 0, w, max(1, int(h * 0.08))))
    edges = top.filter(ImageFilter.FIND_EDGES)
    vals = list(edges.getdata())
    edge_density = sum(1 for v in vals if v > 35) / max(1, len(vals))
    top_vals = list(top.getdata())
    top_mean = sum(top_vals) / max(1, len(top_vals))
    return edge_density > 0.11 and 25 <= top_mean <= 130


def assert_not_desktop_capture(still: Path, label: str) -> None:
    if frame_looks_like_desktop(still):
        raise RuntimeError(f"{label} looks like a macOS desktop/screen capture, not the laser wall: {still}")


def capture_video(out: Path, duration: float) -> None:
    assert_camera_device(CAMERA_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-hide_banner", "-y", "-loglevel", "error",
        "-f", "avfoundation", "-framerate", str(FPS),
        "-pixel_format", PIXEL_FORMAT, "-video_size", SIZE,
        "-i", f"{DEVICE}:none", "-t", f"{duration:.3f}",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", str(out),
    ])


def throwaway_capture(label: str, duration: float = 1.0) -> float:
    out = CAPTURE_ROOT / "throwaway" / f"{label}_{int(time.time())}.mp4"
    capture_video(out, duration)
    return ffprobe_fps(out)


def reset_continuity_camera() -> None:
    RUN_STATS["fps_resets"] += 1
    run(["killall", "ContinuityCaptureAgent"], check=False)
    time.sleep(1.0)


def recover_fps(label: str) -> tuple[bool, list[float]]:
    reset_continuity_camera()
    fps_values = []
    for idx in range(2):
        fps_values.append(throwaway_capture(f"{label}_fps_warmup_{idx + 1}", 1.0))
    recovered = any(fps >= 55 for fps in fps_values)
    if recovered:
        RUN_STATS["fps_reset_recovered"] += 1
    return recovered, fps_values


def parse_inches(value: str) -> float:
    """Parse simple user-measured strings such as '3 ft 4 in' or ranges."""
    text = str(value).replace("~", "").strip().lower()
    if " to " in text:
        parts = [parse_inches(part) for part in text.split(" to ")]
        return statistics.mean(parts)
    feet = 0.0
    inches = 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*ft", text)
    if m:
        feet = float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:in|\"|$)", text)
    if m:
        inches = float(m.group(1))
    if feet == 0.0 and inches == 0.0:
        raise ValueError(f"cannot parse measurement as inches: {value!r}")
    return feet * 12.0 + inches


def setup_geometry_measurements() -> dict[str, float]:
    setup = load_json(SETUP_GEOMETRY_PATH, {})
    boxes = setup.get("boundary_reference_measurements", {})
    left = boxes.get("image_left_aperture_box", {})
    right = boxes.get("image_right_aperture_box", {})
    gap = boxes.get("gap_between_boxes", {})
    left_top = parse_inches(left["floor_to_top_edge"]["value"])
    left_bottom = parse_inches(left["floor_to_bottom_edge"]["value"])
    right_top = parse_inches(right["floor_to_top_edge"]["value"])
    right_bottom = parse_inches(right["floor_to_bottom_edge"]["value"])
    return {
        "box_height_inches": statistics.mean([left_top - left_bottom, right_top - right_bottom]),
        "left_width_inches": parse_inches(left["left_edge_to_right_edge"]["value"]),
        "right_width_inches": parse_inches(right["left_edge_to_right_edge"]["value"]),
        "gap_inches": parse_inches(gap["value"]),
    }


def laser_core_mask(arr: "Any", threshold: int = LASER_CORE_THRESHOLD_FLOOR) -> tuple["Any", dict[str, float]]:
    """Mask scanned laser cores while rejecting broad wall bloom."""
    import numpy as np
    if arr.size == 0:
        return np.zeros(arr.shape[:2], dtype=bool), {
            "median": 0.0,
            "p90": 0.0,
            "threshold": float(threshold),
        }
    mx = arr.max(axis=2)
    median = float(np.percentile(mx, 50))
    p90 = float(np.percentile(mx, 90))
    adaptive_floor = median + max(35.0, (p90 - median) * 2.5)
    core_threshold = min(255.0, max(float(threshold), adaptive_floor))
    return mx >= core_threshold, {
        "median": median,
        "p90": p90,
        "threshold": core_threshold,
    }


def _component_boxes(mask: "Any", *, y_offset: int = 0, min_area: int = 400, min_width: int = 80, min_height: int = 80) -> list[dict[str, Any]]:
    import numpy as np
    h, w = mask.shape[:2]
    seen = np.zeros((h, w), dtype=bool)
    boxes: list[dict[str, Any]] = []
    ys_all, xs_all = np.nonzero(mask)
    for seed_y, seed_x in zip(ys_all.astype(int).tolist(), xs_all.astype(int).tolist()):
        if seen[seed_y, seed_x]:
            continue
        stack = [(seed_y, seed_x)]
        seen[seed_y, seed_x] = True
        xs: list[int] = []
        ys: list[int] = []
        while stack:
            y, x = stack.pop()
            xs.append(x)
            ys.append(y)
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if ny < 0 or nx < 0 or ny >= h or nx >= w or seen[ny, nx] or not mask[ny, nx]:
                        continue
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        area = len(xs)
        if area < min_area:
            continue
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys) + y_offset, max(ys) + y_offset
        width = x1 - x0 + 1
        height = y1 - y0 + 1
        if width < min_width or height < min_height:
            continue
        boxes.append({
            "bbox": [int(x0), int(y0), int(x1), int(y1)],
            "area_px": int(area),
            "width_px": int(width),
            "height_px": int(height),
            "corners": [[int(x0), int(y0)], [int(x1), int(y0)], [int(x1), int(y1)], [int(x0), int(y1)]],
        })
    return sorted(boxes, key=lambda box: (box["bbox"][0], -box["area_px"]))


def detect_projection_boxes(reference_still: Path) -> dict[str, Any]:
    import numpy as np
    im = Image.open(reference_still).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    h, w = arr.shape[:2]
    top = max(0, min(h - 1, int(h * ANALYSIS_ROI_TOP_FRAC))) if h > 1 else 0
    threshold_bottom = max(top + 1, min(h, int(h * 0.86)))
    _sample_mask, mask_stats = laser_core_mask(arr[top:threshold_bottom, :, :])
    mx = arr[top:, :, :].max(axis=2)
    mask = mx >= mask_stats["threshold"]
    # Dilation connects outline segments into one component per aperture box.
    mask_img = Image.fromarray((mask * 255).astype("uint8")).filter(ImageFilter.MaxFilter(9))
    boxes = _component_boxes(np.asarray(mask_img) > 0, y_offset=top)
    boxes = [
        box for box in boxes
        if box["bbox"][1] < int(h * 0.80)
        and box["width_px"] < int(w * 0.80)
        and box["height_px"] < int(h * 0.80)
    ]
    boxes = sorted(boxes, key=lambda box: box["area_px"], reverse=True)[:2]
    boxes = sorted(boxes, key=lambda box: box["bbox"][0])
    if len(boxes) != 2:
        raise RuntimeError(f"expected two projection boxes in {reference_still}, found {len(boxes)}")
    for label, box in zip(("image_left", "image_right"), boxes):
        box["label"] = label
    combined = [
        min(box["bbox"][0] for box in boxes),
        min(box["bbox"][1] for box in boxes),
        max(box["bbox"][2] for box in boxes),
        max(box["bbox"][3] for box in boxes),
    ]
    return {
        "source_still": str(reference_still),
        "source_image_size": {"width": w, "height": h},
        "top_crop_px": top,
        "boxes": boxes,
        "combined_bbox": [int(v) for v in combined],
        "laser_core_mask": {
            "threshold_floor": LASER_CORE_THRESHOLD_FLOOR,
            "threshold": round(mask_stats["threshold"], 3),
            "wall_luma_median": round(mask_stats["median"], 3),
            "wall_luma_p90": round(mask_stats["p90"], 3),
            "bright_pixels": int(mask.sum()),
        },
    }


def estimate_glare_band(arr: "Any", combined_bbox: list[int]) -> dict[str, Any]:
    import numpy as np
    h, _w = arr.shape[:2]
    mx = arr.max(axis=2)
    wall_top = max(0, int(arr.shape[0] * ANALYSIS_ROI_TOP_FRAC))
    wall_bottom = min(h, max(wall_top + 1, combined_bbox[3] - 20))
    wall_med = float(np.median(mx[wall_top:wall_bottom, :])) if wall_bottom > wall_top else float(np.median(mx))
    row_med = np.median(mx, axis=1)
    row_p75 = np.percentile(mx, 75, axis=1)
    row_p90 = np.percentile(mx, 90, axis=1)
    flags = (row_med > wall_med + 28.0) | (row_p75 > wall_med + 40.0) | (row_p90 > wall_med + 60.0)
    search_start = min(h - 1, max(combined_bbox[3] + 30, int(h * 0.72)))
    min_run = 8
    start_y: int | None = None
    y = h - 1
    while y >= search_start:
        if not bool(flags[y]):
            y -= 1
            continue
        end = y
        while y >= search_start and bool(flags[y]):
            y -= 1
        start = y + 1
        if end - start + 1 >= min_run:
            start_y = int(start)
            break
    return {
        "detected": start_y is not None,
        "start_y": start_y,
        "wall_luma_median": round(wall_med, 3),
        "method": "bottom-up broad-row brightness run below the projection boxes",
        "min_run_rows": min_run,
    }


def derive_analysis_geometry(reference_still: Path, *, write: bool = False) -> dict[str, Any]:
    import numpy as np
    im = Image.open(reference_still).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    detected = detect_projection_boxes(reference_still)
    measurements = setup_geometry_measurements()
    box_heights = [box["height_px"] for box in detected["boxes"]]
    px_per_inch = statistics.mean(box_heights) / measurements["box_height_inches"]
    left, right = detected["boxes"]
    detected_gap_px = right["bbox"][0] - left["bbox"][2] - 1
    cross_checks = {
        "box_height_inches": measurements["box_height_inches"],
        "left_width_inches_expected": measurements["left_width_inches"],
        "left_width_inches_detected": round(left["width_px"] / px_per_inch, 2),
        "right_width_inches_expected": measurements["right_width_inches"],
        "right_width_inches_detected": round(right["width_px"] / px_per_inch, 2),
        "gap_inches_expected": measurements["gap_inches"],
        "gap_inches_detected": round(detected_gap_px / px_per_inch, 2),
    }
    warnings: list[str] = []
    for key, expected_key, detected_key in (
        ("left_width", "left_width_inches_expected", "left_width_inches_detected"),
        ("right_width", "right_width_inches_expected", "right_width_inches_detected"),
        ("gap", "gap_inches_expected", "gap_inches_detected"),
    ):
        expected = float(cross_checks[expected_key])
        detected_inches = float(cross_checks[detected_key])
        rel = abs(detected_inches - expected) / max(1.0, expected)
        cross_checks[f"{key}_relative_error"] = round(rel, 4)
        if rel > 0.25:
            warnings.append(f"{key} detection differs from setup_geometry by {rel:.1%}")
    combined = detected["combined_bbox"]
    desired_margin_px = int(round(ANALYSIS_BOUNDARY_MARGIN_INCHES * px_per_inch))
    desired_bottom = combined[3] + desired_margin_px
    glare = estimate_glare_band(arr, combined)
    glare_start = int(glare["start_y"]) if glare.get("detected") and glare.get("start_y") is not None else arr.shape[0]
    max_bottom_before_glare = max(combined[3] + 1, glare_start - ANALYSIS_GLARE_CLEARANCE_PX)
    conflict = desired_bottom > max_bottom_before_glare
    roi_bottom = min(arr.shape[0], desired_bottom, max_bottom_before_glare)
    roi_top = detected["top_crop_px"]
    headroom_px = max(0, roi_bottom - combined[3])
    if conflict:
        warnings.append(
            "roi_boundary_glare_conflict: desired boundary-nudge margin overlaps the detected glare/baseboard band"
        )
    geometry = {
        "version": 1,
        "created_at": now(),
        "source_still": str(reference_still),
        "source_image_size": detected["source_image_size"],
        "laser_core_threshold_floor": LASER_CORE_THRESHOLD_FLOOR,
        "boxes": detected["boxes"],
        "combined_bbox": combined,
        "scale": {
            "px_per_inch": round(px_per_inch, 4),
            "source": "mean detected aperture-box height divided by setup_geometry box floor_to_top-floor_to_bottom height",
            "measured_box_height_inches": round(measurements["box_height_inches"], 3),
        },
        "analysis_roi": [0, int(roi_top), int(arr.shape[1]), int(roi_bottom)],
        "boundary_margin": {
            "desired_inches": ANALYSIS_BOUNDARY_MARGIN_INCHES,
            "desired_px": desired_margin_px,
            "actual_headroom_px": int(headroom_px),
            "actual_headroom_inches": round(headroom_px / px_per_inch, 3) if px_per_inch else 0.0,
            "roi_boundary_glare_conflict": bool(conflict),
        },
        "glare_band": {
            **glare,
            "clearance_px": ANALYSIS_GLARE_CLEARANCE_PX,
            "max_bottom_before_glare": int(max_bottom_before_glare),
        },
        "geometry_cross_check": cross_checks,
        "warnings": warnings,
    }
    if write:
        write_json(ANALYSIS_GEOMETRY_PATH, geometry)
    return geometry


GEOMETRY_REFERENCE_FRAME_TIMESTAMPS = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def geometry_warning_is_blocking(warning: str) -> bool:
    # Width errors mean the still caught an incomplete scan-phase box. A gap-only
    # warning can occur from a plausible perspective/framing shift and is
    # handled as a softer cross-check.
    return "width detection differs" in warning or "roi_boundary_glare_conflict" in warning


def geometry_quality_score(geometry: dict[str, Any]) -> tuple[int, int, float]:
    cross = geometry.get("geometry_cross_check", {})
    warnings = list(geometry.get("warnings") or [])
    blocking = sum(1 for warning in warnings if geometry_warning_is_blocking(str(warning)))
    soft = len(warnings) - blocking
    error_sum = sum(
        float(cross.get(key, 1.0))
        for key in ("left_width_relative_error", "right_width_relative_error", "gap_relative_error")
    )
    return (blocking, soft, error_sum)


def select_geometry_reference_frame(video: Path, still: Path) -> dict[str, Any]:
    candidate_dir = video.parent / "_geometry_frame_candidates"
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    scored: list[tuple[tuple[int, int, float], float, Path, dict[str, Any]]] = []
    errors: list[str] = []
    for idx, ts in enumerate(GEOMETRY_REFERENCE_FRAME_TIMESTAMPS, start=1):
        candidate = candidate_dir / f"geometry_frame_{idx:02d}_{ts:.2f}.jpg"
        try:
            extract_frame(video, candidate, ts)
            assert_not_desktop_capture(candidate, f"preflight geometry candidate at {ts:.2f}s")
            geometry = derive_analysis_geometry(candidate, write=False)
            scored.append((geometry_quality_score(geometry), ts, candidate, geometry))
        except Exception as exc:
            errors.append(f"{ts:.2f}s: {exc}")
    if not scored:
        raise RuntimeError(f"no usable preflight geometry frame candidates from {video}: {errors}")
    scored.sort(key=lambda item: item[0])
    score, ts, candidate, geometry = scored[0]
    blocking = score[0]
    if blocking:
        raise RuntimeError(
            "no preflight geometry frame candidate had plausible width geometry; "
            f"best ts={ts:.2f}s score={score} warnings={geometry.get('warnings')} errors={errors}"
        )
    shutil.copyfile(candidate, still)
    geometry = derive_analysis_geometry(still, write=True)
    geometry["selected_frame_timestamp"] = ts
    geometry["selected_frame_score"] = {
        "blocking_warnings": score[0],
        "soft_warnings": score[1],
        "relative_error_sum": round(score[2], 4),
    }
    write_json(ANALYSIS_GEOMETRY_PATH, geometry)
    return geometry


def load_analysis_geometry() -> dict[str, Any] | None:
    path = Path(os.environ.get("VLN_ANALYSIS_GEOMETRY_PATH") or ANALYSIS_GEOMETRY_PATH)
    if not path.exists():
        return None
    try:
        return load_json(path, {})
    except Exception:
        return None


def analysis_roi_for_size(width: int, height: int) -> dict[str, Any]:
    geometry = load_analysis_geometry()
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
            "geometry": geometry,
        }
    top = max(0, min(height - 1, int(height * ANALYSIS_ROI_TOP_FRAC))) if height > 1 else 0
    bottom = max(top + 1, min(height, int(height * ANALYSIS_ROI_BOTTOM_FRAC))) if height > 0 else 0
    return {
        "top": top,
        "bottom": bottom,
        "source": "fraction_fallback",
        "geometry_source_still": None,
        "geometry": None,
    }


def capture_white_reference() -> dict[str, Any]:
    outdir = WHITE_REF_PATH.parent
    outdir.mkdir(parents=True, exist_ok=True)
    video = outdir / "CH08_000_white_reference.mp4"
    frame = dict(PRIMARY_BASE)
    frame[1] = 220
    frame[8] = 0
    set_dmx(frame)
    time.sleep(0.65)
    capture_video(video, 1.0)
    fps = ffprobe_fps(video)
    extract_frame(video, WHITE_REF_PATH, 0.5)
    assert_not_desktop_capture(WHITE_REF_PATH, "white reference")
    stats = frame_stats(WHITE_REF_PATH)
    os.environ["VLN_WHITE_REFERENCE"] = str(WHITE_REF_PATH)
    os.environ["VLN_ANALYSIS_ROI_TOP_FRAC"] = str(ANALYSIS_ROI_TOP_FRAC)
    os.environ["VLN_ANALYSIS_ROI_BOTTOM_FRAC"] = str(ANALYSIS_ROI_BOTTOM_FRAC)
    os.environ["VLN_ANALYSIS_GEOMETRY_PATH"] = str(ANALYSIS_GEOMETRY_PATH)
    os.environ["VLN_LASER_CORE_THRESHOLD_FLOOR"] = str(LASER_CORE_THRESHOLD_FLOOR)
    write_json(outdir / "metadata.json", {
        "phase": "phase1_single_channel",
        "test_id": "CH08_000_white_reference",
        "ch1_19": {f"CH{ch}": frame.get(ch, 0) for ch in range(1, 20)},
        "capture_path": str(WHITE_REF_PATH.relative_to(CAPTURE_ROOT)),
        "fps": round(fps, 3),
        "analysis_roi_top_frac": ANALYSIS_ROI_TOP_FRAC,
        "analysis_roi_bottom_frac": ANALYSIS_ROI_BOTTOM_FRAC,
        "frame_stats": stats,
        "timestamp": now(),
    })
    checkpoint("phase1_single_channel", "white_reference_captured", {"white_reference": str(WHITE_REF_PATH), "white_reference_fps": round(fps, 3), "white_reference_stats": stats})
    return {"white_reference": str(WHITE_REF_PATH), "white_reference_fps": round(fps, 3), "white_reference_stats": stats}


def reuse_or_capture_white_reference() -> dict[str, Any]:
    os.environ["VLN_ANALYSIS_ROI_TOP_FRAC"] = str(ANALYSIS_ROI_TOP_FRAC)
    os.environ["VLN_ANALYSIS_ROI_BOTTOM_FRAC"] = str(ANALYSIS_ROI_BOTTOM_FRAC)
    os.environ["VLN_ANALYSIS_GEOMETRY_PATH"] = str(ANALYSIS_GEOMETRY_PATH)
    os.environ["VLN_LASER_CORE_THRESHOLD_FLOOR"] = str(LASER_CORE_THRESHOLD_FLOOR)
    if WHITE_REF_PATH.exists():
        os.environ["VLN_WHITE_REFERENCE"] = str(WHITE_REF_PATH)
        stats = frame_stats(WHITE_REF_PATH)
        detail = {
            "white_reference": str(WHITE_REF_PATH),
            "white_reference_reused": True,
            "white_reference_stats": stats,
        }
        checkpoint("phase1_single_channel", "white_reference_reused", detail)
        return detail
    return capture_white_reference()


def extract_frame(video: Path, out: Path, ts: float = 0.25) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", str(video), "-frames:v", "1"]
    if out.suffix.lower() in {".jpg", ".jpeg"}:
        cmd.extend(["-strict", "unofficial"])
    cmd.append(str(out))
    run(cmd)


def frame_stats(path: Path) -> dict[str, Any]:
    import numpy as np
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    h, w = arr.shape[:2]
    roi_info = analysis_roi_for_size(w, h)
    top = int(roi_info["top"])
    bottom = int(roi_info["bottom"])
    roi = arr[top:bottom, :, :]
    mask, mask_stats = laser_core_mask(roi)
    mx = roi.max(axis=2) if roi.size else np.asarray([], dtype=np.float32)
    mean_luma = float(mx.mean()) if mx.size else 0.0
    if mask.size:
        ys, xs = np.nonzero(mask)
    else:
        ys = xs = np.asarray([], dtype=int)
    bright_pixels = int(mask.sum())
    bbox = None
    clipped_roi_bottom = False
    if bright_pixels:
        bbox = [int(xs.min()), int(ys.min() + top), int(xs.max()), int(ys.max() + top)]
        clipped_roi_bottom = bool(bbox[3] >= bottom - ANALYSIS_ROI_EDGE_MARGIN_PX)
    roi_pixels = int(mask.size)
    geometry = roi_info.get("geometry") or {}
    scale = float(geometry.get("scale", {}).get("px_per_inch") or 0.0)
    headroom_px = int(bottom - bbox[3]) if bbox else None
    return {
        "mean_luma": round(mean_luma, 3),
        "bright_pixels": bright_pixels,
        "bright_fraction": round(bright_pixels / max(1, roi_pixels), 6),
        "blank": bright_pixels < 20,
        "bbox": bbox,
        "laser_core_threshold": round(mask_stats["threshold"], 3),
        "analysis_roi": [0, top, w, bottom],
        "analysis_roi_top_frac": ANALYSIS_ROI_TOP_FRAC,
        "analysis_roi_bottom_frac": ANALYSIS_ROI_BOTTOM_FRAC,
        "analysis_roi_source": roi_info["source"],
        "analysis_geometry_source_still": roi_info.get("geometry_source_still"),
        "analysis_clip_margin_px": ANALYSIS_ROI_EDGE_MARGIN_PX,
        "clipped_roi_bottom": clipped_roi_bottom,
        "geometry_clipped_low": clipped_roi_bottom,
        "roi_bottom_headroom_px": headroom_px,
        "roi_bottom_headroom_inches": round(headroom_px / scale, 3) if headroom_px is not None and scale else None,
        "wall_luma_median": round(mask_stats["median"], 3),
        "wall_luma_p90": round(mask_stats["p90"], 3),
    }


def assert_analysis_mask_sane(stats: dict[str, Any], label: str) -> None:
    if stats.get("blank"):
        raise RuntimeError(f"{label} analysis mask is blank; expected a visible static reference")
    bright_fraction = float(stats.get("bright_fraction") or 0.0)
    if bright_fraction > ANALYSIS_MASK_MAX_BRIGHT_FRACTION:
        raise RuntimeError(
            f"{label} analysis mask covers too much of the ROI "
            f"({bright_fraction:.3%} > {ANALYSIS_MASK_MAX_BRIGHT_FRACTION:.1%}); "
            f"bbox={stats.get('bbox')} roi={stats.get('analysis_roi')} "
            "This usually means bloom/table glare/background is being counted as geometry."
        )
    bbox = stats.get("bbox")
    roi = stats.get("analysis_roi")
    if bbox and roi:
        _x0, y0, _x1, y1 = roi
        if bbox[3] >= y1 - 2:
            raise RuntimeError(
                f"{label} analysis mask touches the bottom ROI edge; bbox={bbox} roi={roi}. "
                "Regenerate analysis geometry or resolve the boundary-vs-glare conflict before capture."
            )


def frame_strip(video: Path, out: Path, label: str, duration: float) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    thumbs: list[Image.Image] = []
    with tempfile.TemporaryDirectory(prefix="vln_fixture_strip_") as td:
        tmp = Path(td)
        for idx, frac in enumerate((0.0, 0.25, 0.5, 0.75, 0.98)):
            fp = tmp / f"frame_{idx}.png"
            for ts in (max(0.0, duration * frac), max(0.0, duration * 0.90), max(0.0, duration * 0.50)):
                try:
                    extract_frame(video, fp, ts)
                except subprocess.CalledProcessError:
                    pass
                if fp.exists() and fp.stat().st_size > 0:
                    break
            if fp.exists() and fp.stat().st_size > 0:
                thumb = Image.open(fp).convert("RGB").resize((220, 124), Image.Resampling.LANCZOS)
            else:
                thumb = Image.new("RGB", (220, 124), (0, 0, 0))
            thumbs.append(thumb)
    canvas = Image.new("RGB", (220 * len(thumbs), 148), (12, 12, 12))
    draw = ImageDraw.Draw(canvas)
    draw.text((5, 5), label[:130], fill=(255, 255, 0))
    for idx, thumb in enumerate(thumbs):
        canvas.paste(thumb, (idx * 220, 24))
    canvas.save(out)


def analyze_with_dense(entry: dict[str, Any]) -> dict[str, Any]:
    os.environ["VLN_ANALYSIS_ROI_TOP_FRAC"] = str(ANALYSIS_ROI_TOP_FRAC)
    os.environ["VLN_ANALYSIS_ROI_BOTTOM_FRAC"] = str(ANALYSIS_ROI_BOTTOM_FRAC)
    os.environ["VLN_ANALYSIS_GEOMETRY_PATH"] = str(ANALYSIS_GEOMETRY_PATH)
    os.environ["VLN_LASER_CORE_THRESHOLD_FLOOR"] = str(LASER_CORE_THRESHOLD_FLOOR)
    if WHITE_REF_PATH.exists():
        os.environ["VLN_WHITE_REFERENCE"] = str(WHITE_REF_PATH)
    sys.path.insert(0, str(ROOT / "calib"))
    import dense_cue_breakpoints as dense
    return dense.analyze_existing_entry(entry, ANALYSIS_FPS, LASER_CORE_THRESHOLD_FLOOR)["analysis"]


def base_model() -> dict[str, Any]:
    return {
        "fixture": "RGB Fullcolor Beam Effect Light (36CH; CH1-19 modeled)",
        "schema_version": 1,
        "model_version": "fixture-model-v1",
        "model_status": "draft",
        "method": {
            "capture_fps": FPS,
            "analysis_fps": ANALYSIS_FPS,
            "reanalysis_fps_allowed": 60,
            "frequency_ceiling_hz_30fps": 15,
            "exposure_tracks": ["geometry_motion", "color"],
            "primary_base": {"label": "line", "ch3": 32, "ch4": 10},
            "rig": f"Enttec {DMX_BACKEND.upper()} ({'pyserial' if DMX_BACKEND == 'pro' else 'pyftdi'}), iPhone Continuity Camera, wall projection",
            "channel_scope": {
                "CH1": "binary gate only: 0=off, any value >0=on; not a dimmer",
                "CH2": "out of scope and held at 0; auto/sound/demo is unimportant for this fixture model",
            },
        },
        "provenance": {
            "cue_dataset": "data/soundswitch_laser_cues.json",
            "coverage": "data/soundswitch_cue_motion_coverage.json",
            "dense_capture_root": str(EXISTING_DENSE_ROOT),
        },
        "channels": {},
        "base_looks": {},
        "interactions": {"gating": [], "compositional": [], "independent": [], "higher_order": []},
        "composition": {
            "model_form": "base(CH3,CH4) plus gated modifier transfer functions",
            "evaluation_order": ["base", "colour", "translate", "scale", "orientation", "strobe"],
            "gate_evaluation": "pre",
            "default_combination": "compose_measured_transfer_outputs",
            "operand_space": "transfer_output",
            "higher_order_assumption": "interactions beyond measured pairs/triples are negligible unless Phase 6 real-cue validation proves otherwise",
        },
        "validation": {"authored_channels_unknown": True, "cues_checked": 0, "captured_exact_vectors": 0, "mismatches": []},
    }


def merge_model(update: dict[str, Any]) -> None:
    model = load_json(MODEL_PATH, base_model())
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(model.get(key), dict):
            model[key].update(value)
        else:
            model[key] = value
    write_json(MODEL_PATH, model)


def merge_phase_observations(phase: str, summary: dict[str, Any]) -> None:
    model = load_json(MODEL_PATH, base_model())
    model.setdefault("method", {}).setdefault("phase_summaries", {})[phase] = summary
    channels = model.setdefault("channels", {})
    for row in read_jsonl(MANIFEST):
        if row.get("phase") != phase:
            continue
        if row.get("folder") in superseded_capture_folders():
            continue
        for ch in (row.get("changed_channels") or {}):
            channels.setdefault(ch, {
                "name": CHANNEL_NAMES.get(int(ch.replace("CH", "")), ch) if isinstance(ch, str) and ch.startswith("CH") else str(ch),
                "role": "measured",
                "banks": [],
                "base_dependence": "unknown",
                "confidence": "low",
                "evidence": [],
            })
            evidence = row.get("folder")
            if evidence and evidence not in channels[ch]["evidence"]:
                channels[ch]["evidence"].append(evidence)
    write_json(MODEL_PATH, model)


def existing_capture_count() -> int:
    return len(read_jsonl(MANIFEST))


def session_new_captures() -> int:
    """Captures appended since this invocation began (resume-safe)."""
    return existing_capture_count() - SESSION_BASELINE_CAPTURES


def assert_capture_budget(additional: int) -> None:
    # Count only captures taken THIS run so a resumed run is not penalised for
    # rows already on disk; the flag is --max-new-captures and now means exactly that.
    new_so_far = session_new_captures()
    if new_so_far + additional > MAX_CAPTURES:
        raise RuntimeError(
            f"capture cap would be exceeded: new_this_run={new_so_far} additional={additional} "
            f"cap={MAX_CAPTURES} (raise --max-new-captures to proceed)"
        )


def completed_capture_folders() -> set[str]:
    done: set[str] = set()
    superseded = superseded_capture_folders()
    for row in read_jsonl(MANIFEST):
        folder = row.get("folder")
        if not folder:
            continue
        if folder in superseded:
            continue
        analysis = row.get("analysis") or {}
        if not analysis.get("recapture_pending") or folder == "phase1_single_channel/CH01_master_dimmer/CH01_000":
            done.add(folder)
    return done


def superseded_capture_folders() -> set[str]:
    """Standalone CH3/CH4 Phase 1 rows are evidence, but not valid model inputs.

    CH3 selects the bank and CH4 selects a program inside that bank. Earlier
    interrupted runs captured them as independent single-channel sweeps; keep
    the files/manifests for audit, but exclude them from model merges.
    """
    bad_groups = (
        "phase1_single_channel/CH03_static_pattern/",
        "phase1_single_channel/CH04_static_pattern_selection/",
    )
    valid_atlas_ids = {
        "__".join(("phase1_single_channel", "CH03_CH04_base_look_atlas", state))
        for ch3 in ch3_static_values()
        for ch4 in ch4_static_program_values()
        for state in (f"CH03_{ch3:03d}_CH04_{ch4:03d}", f"CH03_{ch3:03d}_CH04_{ch4:03d}_color")
    }
    folders: set[str] = set()
    for row in read_jsonl(MANIFEST):
        folder = str(row.get("folder", ""))
        if any(folder.startswith(prefix) for prefix in bad_groups):
            folders.add(folder)
            continue
        if folder.startswith("phase1_single_channel/CH03_CH04_base_look_atlas/") and row.get("test_id") not in valid_atlas_ids:
            folders.add(folder)
    return folders


def sweep_values() -> list[int]:
    vals = list(range(0, 253, 4))
    if 255 not in vals:
        vals.append(255)
    return vals


def ch3_static_values() -> list[int]:
    # Manual/user-authoritative: one representative inside each CH3 static folder.
    return [8, 24, 40, 56, 96]


def ch4_static_program_values() -> list[int]:
    # Manual/user-authoritative: CH4 selects a new program every 5 values.
    # Sample mid-bin values and explicitly include 255 as the terminal look.
    vals = list(range(2, 253, 5))
    if 255 not in vals:
        vals.append(255)
    return vals


def probe_values() -> list[int]:
    return sorted({0, 1, 4, 8, 16, 32, 44, 60, 64, 80, 96, 120, 127, 128, 136, 144, 152, 160, 192, 220, 240, 255})


def case_for(phase: str, ch: int, val: int, base_name: str, track: str = "geometry_motion") -> Case:
    dmx = dict(BASES[base_name])
    dmx[ch] = val
    timed = ch in {9, 11, 12, 13, 14, 15, 16, 17, 18, 19}
    duration = 8.0 if timed else 3.0
    group = f"CH{ch:02d}_{CHANNEL_NAMES[ch]}"
    state = f"CH{ch:02d}_{val:03d}" if track == "geometry_motion" else f"CH{ch:02d}_{val:03d}_{track}"
    return Case(phase, group, state, dmx, duration, timed, track, base_name, {ch: val}, CHANNEL_NAMES[ch])


def ch3_ch4_atlas_case(ch3: int, ch4: int, track: str = "geometry_motion") -> Case:
    dmx = dict(PRIMARY_BASE)
    dmx[3] = ch3
    dmx[4] = ch4
    state = f"CH03_{ch3:03d}_CH04_{ch4:03d}" if track == "geometry_motion" else f"CH03_{ch3:03d}_CH04_{ch4:03d}_{track}"
    return Case(
        "phase1_single_channel",
        "CH03_CH04_base_look_atlas",
        state,
        dmx,
        3.0,
        False,
        track,
        f"base_CH3_{ch3:03d}_CH4_{ch4:03d}",
        {3: ch3, 4: ch4},
        "CH3_CH4_base_look",
    )


def ch3_ch4_atlas_cases() -> list[Case]:
    pairs = {(ch3, ch4) for ch3 in ch3_static_values() for ch4 in ch4_static_program_values()}
    cases: list[Case] = []
    for ch3, ch4 in sorted(pairs):
        cases.append(ch3_ch4_atlas_case(ch3, ch4, "geometry_motion"))
        cases.append(ch3_ch4_atlas_case(ch3, ch4, "color"))
    return cases


def phase1_cases() -> list[Case]:
    cases: list[Case] = [
        case_for("phase1_single_channel", 1, 0, "base_CH3_032_CH4_010"),
        case_for("phase1_single_channel", 1, CH1_ON_VALUE, "base_CH3_032_CH4_010"),
    ]
    cases.extend(ch3_ch4_atlas_cases())
    for ch in MODELED_CHANNELS:
        if ch in {1, 3, 4}:
            continue
        for val in sweep_values():
            cases.append(case_for("phase1_single_channel", ch, val, "base_CH3_032_CH4_010", "geometry_motion"))
            cases.append(case_for("phase1_single_channel", ch, val, "base_CH3_032_CH4_010", "color"))
    return cases


def phase15_cases() -> list[Case]:
    cases: list[Case] = []
    for base_name in BASES:
        for ch in PROBE_CHANNELS:
            for val in probe_values():
                cases.append(case_for("phase1_5_base_dependence", ch, val, base_name, "geometry_motion"))
                cases.append(case_for("phase1_5_base_dependence", ch, val, base_name, "color"))
    return cases


def combo_case(phase: str, group: str, values: dict[int, int], duration: float = 8.0, base: str = "base_CH3_032_CH4_010") -> Case:
    dmx = dict(BASES[base])
    dmx.update(values)
    state = "_".join(f"CH{ch:02d}_{val:03d}" for ch, val in sorted(values.items()))
    return Case(phase, group, state, dmx, duration, True, "geometry_motion", base, values, group)


def phase2_cases() -> list[Case]:
    cases: list[Case] = []
    for ch in (5, 8, 11, 12, 15, 17, 19):
        cases.append(combo_case("phase2_gating", "gate_CH01_enables_all", {1: 0, ch: 200}, 4.0))
        cases.append(combo_case("phase2_gating", "gate_CH01_enables_all", {1: 220, ch: 200}, 4.0))
    for ch3 in (32, 160):
        cases.append(combo_case("phase2_gating", "gate_CH03_static_dynamic_split", {3: ch3, 15: 200}, 8.0))
    for ch8 in (0, 20, 60, 245):
        cases.append(combo_case("phase2_gating", "gate_CH08_enables_CH09", {8: ch8, 9: 128}, 8.0))
        cases.append(combo_case("phase2_gating", "not_gate_CH08_CH18", {8: ch8, 18: 160}, 8.0))
    for ch3, ch4 in ((0, 195), (28, 0), (32, 10), (41, 0), (48, 0)):
        cases.append(combo_case("phase2_gating", "gate_CH03_CH04_shape", {3: ch3, 4: ch4}, 4.0))
    return cases


def grid_values(n: int = 8) -> list[int]:
    if n <= 1:
        return [0]
    return sorted({round(i * 255 / (n - 1)) for i in range(n)})


def phase3_cases(scope: dict[str, Any] | None = None) -> list[Case]:
    vals = grid_values(8)
    cases: list[Case] = []
    groups = [
        ("colour_CH8xCH9", (8, 9)),
        ("colour_CH8xCH18", (8, 18)),
        ("translate_CH6xCH15", (6, 15)),
        ("translate_CH7xCH16", (7, 16)),
        ("scale_CH5xCH17", (5, 17)),
        ("rotation_move_CH12xCH15", (12, 15)),
        ("move_wave_CH15xCH19", (15, 19)),
    ]
    verdicts = ((scope or {}).get("phase1_5_verdicts") or (load_json(MODEL_PATH, {}).get("method", {}).get("base_dependence_gate", {}).get("phase1_5_verdicts") if MODEL_PATH.exists() else {}) or {})
    varied = {int(ch.replace("CH", "")) for ch, verdict in verdicts.items() if verdict == "base_dependent" and str(ch).startswith("CH")}
    for group, (a, b) in groups:
        bases = tuple(BASES) if (a in varied or b in varied) else ("base_CH3_032_CH4_010",)
        for base in bases:
            for va in vals:
                for vb in vals:
                    cases.append(combo_case("phase3_composition", f"group_{group}", {a: va, b: vb}, 8.0, base=base))
    orient_vals = grid_values(6)
    orient_bases = tuple(BASES) if ({12, 13, 14} & varied) else ("base_CH3_032_CH4_010",)
    for base in orient_bases:
        for v12 in orient_vals:
            for v13 in orient_vals:
                for v14 in orient_vals:
                    cases.append(combo_case("phase3_composition", "group_orientation_CH12xCH13xCH14", {12: v12, 13: v13, 14: v14}, 8.0, base=base))
    return cases


def phase4_cases() -> list[Case]:
    pairs = ((11, 8), (11, 12), (17, 8), (19, 8), (12, 8), (11, 15))
    vals = grid_values(8)
    cases = []
    for a, b in pairs:
        for v in vals:
            cases.append(combo_case("phase4_independence", f"independent_CH{a:02d}xCH{b:02d}", {a: v, b: 255 - v}, 8.0))
    return cases


def cue_validation_cases() -> list[Case]:
    cues = load_json(ROOT / "data" / "soundswitch_laser_cues.json", [])
    cases: list[Case] = []
    if isinstance(cues, dict):
        rows = cues.get("cues", [])
    else:
        rows = cues
    seen: set[tuple[int, ...]] = set()
    for idx, cue in enumerate(rows, 1):
        dmx_src = cue.get("ch1_19") or cue.get("dmx") or cue.get("channels") or {}
        dmx = {ch: int(dmx_src.get(f"CH{ch}", dmx_src.get(str(ch), 0))) for ch in range(1, 20)}
        vector = tuple(dmx[ch] for ch in range(1, 20))
        if vector in seen:
            continue
        seen.add(vector)
        name = "".join(c.lower() if c.isalnum() else "_" for c in str(cue.get("name") or cue.get("cue_name") or idx))[:40].strip("_")
        cases.append(Case("phase6_cue_validation", "cue_relevant", f"cue_{idx:03d}_{name}", dmx, 8.0, True, "geometry_motion", "resolved_cue", dmx, "cue_validation"))
    return cases


def expected_blank_reason(case: Case) -> str | None:
    if case.phase == "phase1_single_channel" and case.changed_channels == {1: 0}:
        return "ch1_off_blackout"
    return None


def valid_measured_blank_reason(case: Case) -> str | None:
    if case.phase == "phase1_single_channel" and set(case.changed_channels) & {6, 7}:
        return "ch6_ch7_out_of_bounds_closed_light"
    return None


def capture_one(case: Case) -> dict[str, Any]:
    outdir = CAPTURE_ROOT / case.rel_dir
    video = outdir / ("video_color.mp4" if case.track == "color" else "video.mp4")
    still = outdir / ("still_color.jpg" if case.track == "color" else "still.jpg")
    strip = outdir / "frame_strip.jpg"
    metadata_path = outdir / "metadata.json"
    analysis_path = outdir / "analysis.json"
    last_analysis: dict[str, Any] = {}
    fps_history: list[float] = []
    fps_recovery_events: list[dict[str, Any]] = []
    blank_attempts = 0
    expected_blank = expected_blank_reason(case)
    valid_blank = valid_measured_blank_reason(case)
    for attempt in range(1, 4):
        set_dmx(case.dmx)
        time.sleep(0.65)
        capture_video(video, case.duration)
        actual_fps = ffprobe_fps(video)
        fps_history.append(round(actual_fps, 3))
        fps_retry = 0
        while actual_fps < 55 and fps_retry < 3:
            fps_retry += 1
            recovered, warmups = recover_fps(case.test_id)
            fps_recovery_events.append({"attempt": attempt, "fps_retry": fps_retry, "initial_fps": round(actual_fps, 3), "warmup_fps": [round(v, 3) for v in warmups], "recovered": recovered})
            if recovered:
                capture_video(video, case.duration)
                actual_fps = ffprobe_fps(video)
                fps_history.append(round(actual_fps, 3))
                if actual_fps >= 55:
                    break
            else:
                break
        extract_frame(video, still, min(0.5, case.duration / 2))
        assert_not_desktop_capture(still, case.test_id)
        stats = frame_stats(still)
        if FRAME_STRIPS:
            frame_strip(video, strip, case.test_id, case.duration)
        dense_entry = {
            "test_id": case.test_id,
            "cue_id": case.test_id,
            "cue_name": case.test_id,
            "family": case.expected,
            "capture": str(video),
            "capture_dir": str(outdir),
            "full_ch1_19_dmx": {str(ch): case.dmx.get(ch, 0) for ch in range(1, 20)},
            "duration": case.duration,
        }
        analysis = analyze_with_dense(dense_entry)
        analysis.setdefault("quality", {})
        analysis["quality"].update(stats)
        analysis["actual_fps"] = round(actual_fps, 3)
        analysis["fps_history"] = fps_history
        analysis["fps_recovery_events"] = fps_recovery_events
        geometry_clipped_low = bool(
            stats.get("geometry_clipped_low")
            or analysis.get("geometry_clipped_low")
            or analysis.get("clipped_roi_bottom_any")
        )
        if geometry_clipped_low:
            analysis["geometry_clipped_low"] = True
            flags = list(analysis.get("quality_flags") or [])
            if "geometry_clipped_low" not in flags:
                flags.append("geometry_clipped_low")
            analysis["quality_flags"] = flags
        if actual_fps < 55:
            analysis["fps30"] = True
            RUN_STATS["fps30"] += 1
        observed_blank = bool(stats["blank"] or analysis.get("blank"))
        if expected_blank or not observed_blank or (valid_blank and observed_blank):
            last_analysis = analysis
            break
        last_analysis = analysis
        blank_attempts += 1
        RUN_STATS["blank_retries"] += 1
        time.sleep(0.25)
    metadata = {
        "phase": case.phase,
        "test_id": case.test_id,
        "ch1_19": {f"CH{ch}": case.dmx.get(ch, 0) for ch in range(1, 20)},
        "changed_channels": {f"CH{ch}": val for ch, val in case.changed_channels.items()},
        "ch3_bank": case.dmx.get(3, 0),
        "ch4_program": case.dmx.get(4, 0),
        "baseline": case.baseline,
        "exposure_track": case.track,
        "camera": {"device": DEVICE, "expected_name": CAMERA_NAME, "size": SIZE, "fps": FPS, "pixel_format": PIXEL_FORMAT, "exposure": "locked externally", "white_balance": "locked externally"},
        "fps": last_analysis.get("actual_fps"),
        "duration": case.duration,
        "capture_path": str(case.rel_dir),
        "timestamp": now(),
        "scope_guard": {"ch20_36_omitted": True, "renderer_untouched": True, "decode_36ch_contract_untouched": True},
        "frame_strip_enabled": FRAME_STRIPS,
    }
    if expected_blank:
        last_analysis["expected_blank"] = True
        last_analysis["blank_observation_reason"] = expected_blank
        last_analysis["recapture_pending"] = False
    elif valid_blank and (last_analysis.get("blank") or last_analysis.get("quality", {}).get("blank")):
        last_analysis["blank_zone_observed"] = True
        last_analysis["blank_observation_reason"] = valid_blank
        last_analysis["recapture_pending"] = False
    elif last_analysis.get("blank") or last_analysis.get("quality", {}).get("blank"):
        last_analysis["recapture_pending"] = True
    if (
        bool(last_analysis.get("geometry_clipped_low") or last_analysis.get("quality", {}).get("geometry_clipped_low"))
        and set(case.changed_channels) & {16, 17}
    ):
        last_analysis["recapture_pending"] = True
        last_analysis["recapture_pending_reason"] = "geometry_clipped_low"
    metadata["attempts"] = attempt
    metadata["blank_retries"] = blank_attempts
    metadata["fps_history"] = fps_history
    metadata["fps_recovery_events"] = fps_recovery_events
    write_json(metadata_path, metadata)
    write_json(analysis_path, last_analysis)
    row = {**metadata, "intent": case.intent, "analysis": {k: last_analysis.get(k) for k in ("motion_type", "motion_direction", "motion_direction_confidence", "motion_direction_source", "motion_signed_slope_per_second", "loop_duration_estimate", "loop_confidence", "blank", "usable_evidence", "actual_fps", "fps30", "fps_history", "fps_recovery_events", "expected_blank", "blank_zone_observed", "blank_observation_reason", "geometry_clipped_low", "clipped_roi_bottom_any", "quality_flags", "recapture_pending", "recapture_pending_reason", "lowfps_30_ok")}, "folder": str(case.rel_dir)}
    append_jsonl(MANIFEST, row)
    checkpoint(case.phase, "capture_completed", {"last_capture": case.test_id, "capture_count": existing_capture_count(), "running_total": existing_capture_count(), "run_stats": RUN_STATS})
    return row


def run_capture_phase(phase: str, cases: list[Case], rig_confirmed: bool, start_index: int = 0) -> dict[str, Any]:
    if not rig_confirmed:
        checkpoint(phase, "planned_dry_run", {"planned_captures": len(cases)})
        return {"captures_taken": 0, "planned_captures": len(cases), "dry_run": True}
    done = completed_capture_folders()
    pending_cases = [case for case in cases[start_index:] if str(case.rel_dir) not in done]
    assert_capture_budget(len(pending_cases))
    before = hash_guard()
    daemon: subprocess.Popen[str] | None = None
    watchdog_stop: threading.Event | None = None
    watchdog_thread: threading.Thread | None = None
    rows: list[dict[str, Any]] = []
    try:
        daemon = start_daemon()
        watchdog_stop, watchdog_thread = start_watchdog_heartbeat()
        if phase == "phase1_ch1":
            warmup_fps = throwaway_capture("session_warmup_discard", 1.0)
            white = reuse_or_capture_white_reference()
            checkpoint("phase1_single_channel", "warmup_and_white_reference_done", {"warmup_discard_fps": round(warmup_fps, 3), **white})
        for idx, case in enumerate(pending_cases, 1):
            print(f"[{phase}] {idx}/{len(pending_cases)} {case.test_id}", flush=True)
            rows.append(capture_one(case))
        safety = blackout()
        checkpoint(phase, "captured", {"captures_taken": len(rows), "safety_state": safety})
    except BaseException as exc:
        try:
            safety = blackout()
        except Exception as blackout_exc:
            safety = f"blackout_failed: {blackout_exc}"
        checkpoint(phase, "halted", {"error": str(exc), "resume_index": start_index + len(rows), "safety_state": safety})
        raise
    finally:
        stop_watchdog_heartbeat(watchdog_stop, watchdog_thread)
        stop_daemon(daemon)
        assert_hash_unchanged(before)
    return summarize_rows(rows)


def ch1_binary_gate(rows: list[dict[str, Any]] | None = None) -> tuple[bool, dict[str, Any]]:
    rows = rows or [r for r in read_jsonl(MANIFEST) if r.get("phase") == "phase1_single_channel" and "CH01_master_dimmer" in r.get("folder", "")]
    points: list[tuple[int, float]] = []
    for row in rows:
        ch1 = int((row.get("ch1_19") or {}).get("CH1", 0))
        analysis_path = CAPTURE_ROOT / row["folder"] / "analysis.json"
        analysis = load_json(analysis_path, {})
        q = analysis.get("quality") or {}
        points.append((ch1, float(q.get("bright_pixels") or q.get("mean_luma") or 0)))
    points.sort()
    nonzero = [metric for val, metric in points if val > 0]
    blackout = [metric for val, metric in points if val == 0]
    ok = bool(blackout) and bool(nonzero) and (max(nonzero or [0]) > max(20.0, max(blackout or [0]) * 2))
    detail = {
        "points": len(points),
        "max_nonzero_metric": max(nonzero or [0]),
        "blackout_metric": max(blackout or [0]),
        "verdict": "binary_on_off_gate" if ok else "ch1_gate_unresolved",
        "rule": "CH1=0 blacks out; any CH1>0 is on. CH1 is not a dimmer and must not be used for dual-track brightness.",
        "dual_track_method": "camera_exposure_bracketing",
    }
    return ok, detail


def phase1(rig_confirmed: bool) -> dict[str, Any]:
    cases = phase1_cases()
    ch1_cases = [case for case in cases if case.changed_channels.keys() == {1}]
    rest = [case for case in cases if case not in ch1_cases]
    if not rig_confirmed:
        return run_capture_phase("phase1", cases, False)
    first = run_capture_phase("phase1_ch1", ch1_cases, True)
    ok, detail = ch1_binary_gate()
    checkpoint("phase1_single_channel", "ch1_binary_gate", detail)
    if not ok:
        safety = blackout()
        checkpoint("phase1_single_channel", "halted_ch1_gate_unresolved", {"ch1_gate": detail, "camera_bracketing_required": True, "safety_state": safety})
        raise RuntimeError(f"CH1 binary gate unresolved; camera exposure bracketing required: {detail}")
    second = run_capture_phase("phase1_rest", rest, True)
    summary = {**second, "ch1_gate": detail, "ch1_captures": first.get("captures_taken", 0), "captures_taken": first.get("captures_taken", 0) + second.get("captures_taken", 0)}
    merge_phase_observations("phase1_single_channel", summary)
    return summary


def capture_phase_and_merge(phase_name: str, phase_key: str, cases: list[Case], rig_confirmed: bool) -> dict[str, Any]:
    summary = run_capture_phase(phase_name, cases, rig_confirmed)
    merge_phase_observations(phase_key, summary)
    return summary


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fps_values = [float(r.get("analysis", {}).get("actual_fps") or 0) for r in rows]
    by_group: dict[str, int] = {}
    for row in rows:
        folder = row.get("folder", "")
        group = folder.split("/")[1] if "/" in folder else folder
        by_group[group] = by_group.get(group, 0) + 1
    return {
        "captures_taken": len(rows),
        "running_total": existing_capture_count(),
        "blanks_or_recapture_pending": sum(1 for r in rows if r.get("analysis", {}).get("recapture_pending")),
        "fps30": sum(1 for r in rows if r.get("analysis", {}).get("fps30")),
        "fps_min": round(min(fps_values), 3) if fps_values else None,
        "fps_max": round(max(fps_values), 3) if fps_values else None,
        "fps_resets_total": RUN_STATS["fps_resets"],
        "fps_reset_recovered_total": RUN_STATS["fps_reset_recovered"],
        "blank_retries_total": RUN_STATS["blank_retries"],
        "by_group": by_group,
        "motion_types": sorted({str(r.get("analysis", {}).get("motion_type")) for r in rows}),
    }


def preflight(rig_confirmed: bool) -> None:
    if not rig_confirmed:
        checkpoint("preflight", "dry_run_no_dmx", {"rig_confirmed": False})
        return
    quit_soundswitch()
    ports = ftdi_ports()
    if not ports and not DMX_PORT:
        raise RuntimeError("no /dev/cu.usbserial-* serial port found")
    port = resolve_port()
    ok, out = subprocess_ok(["lsof", port])
    if ok and out.strip():
        raise RuntimeError(f"DMX device busy ({port}):\n{out}")
    if DMX_BACKEND == "pro":
        ok, out = pro_identity_ok(port)
        if not ok:
            raise RuntimeError(f"Enttec Pro identity probe failed on {port}:\n{out}")
        print(f"[preflight] {out}", flush=True)
    else:
        py = "from pyftdi.ftdi import Ftdi\nf=Ftdi(); devs=Ftdi.list_devices(); assert devs, 'no FTDI'; d,i=devs[0]; sn=getattr(d,'sn',None); url=f'ftdi://ftdi:0x{d.pid:x}:{sn}/1' if sn else f'ftdi://ftdi:0x{d.pid:x}/1'; f.open_from_url(url); f.set_latency_timer(1); f.close(); print(url)"
        ok, out = subprocess_ok([sys.executable, "-c", py])
        if not ok:
            raise RuntimeError(f"pyftdi open/set_latency_timer(1) failed:\n{out}")
    camera_idx, camera_name = assert_camera_device(CAMERA_NAME)
    ok, out = subprocess_ok(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-framerate", "60", "-pixel_format", PIXEL_FORMAT, "-video_size", SIZE, "-i", f"{DEVICE}:none", "-t", "0.2", "-f", "null", "-"])
    if not ok:
        raise RuntimeError(f"ffmpeg avfoundation device {DEVICE} ({camera_name}) at 60fps failed:\n{out}")
    daemon = None
    try:
        daemon = start_daemon()
        safety = blackout()
        if safety.strip() != "(all zero)":
            raise RuntimeError(f"blackout frame-file verify failed: {safety}")
        test = CAPTURE_ROOT / "preflight" / "test_frame.mp4"
        set_dmx(PRIMARY_BASE)
        time.sleep(0.65)
        capture_video(test, 1.0)
        fps = ffprobe_fps(test)
        fps_recovery_events: list[dict[str, Any]] = []
        fps_retry = 0
        while fps < 55 and fps_retry < 3:
            fps_retry += 1
            recovered, warmups = recover_fps(f"preflight_{fps_retry}")
            fps_recovery_events.append({
                "fps_retry": fps_retry,
                "initial_fps": round(fps, 3),
                "warmup_fps": [round(v, 3) for v in warmups],
                "recovered": recovered,
            })
            if not recovered:
                break
            capture_video(test, 1.0)
            fps = ffprobe_fps(test)
            if fps >= 55:
                break
        still = test.with_suffix(".jpg")
        extract_frame(test, still, 0.25)
        assert_not_desktop_capture(still, "preflight test frame")
        # Box-anchored ROI must be derived from the preflight-only max-size
        # boundary-box look (CH3=0, CH4~62, CH5=0, CH6/CH7=128, CH17=0), not
        # the PRIMARY_BASE "line" capture baseline with CH5=90. Project the box
        # look on a separate clip and derive geometry from it; mask sanity also
        # runs on this static physical-boundary reference.
        geom_video = CAPTURE_ROOT / "preflight" / "geometry_frame.mp4"
        set_dmx(GEOMETRY_REFERENCE_BASE)
        time.sleep(0.65)
        capture_video(geom_video, 1.0)
        geom_still = geom_video.with_suffix(".jpg")
        geometry = select_geometry_reference_frame(geom_video, geom_still)
        assert_not_desktop_capture(geom_still, "preflight geometry frame")
        stats = frame_stats(geom_still)
        assert_analysis_mask_sane(stats, "preflight geometry reference")
        if fps < 55:
            raise RuntimeError(f"preflight camera fps below 55 ({fps:.2f}); disable iOS Auto FPS or raise scene luma to >=~20")
        checkpoint("preflight", "passed", {"fps": fps, "fps_recovery_events": fps_recovery_events, "frame_stats": stats, "analysis_geometry": geometry, "analysis_mask_sane": True, "safety_state": safety, "camera_device": camera_idx, "camera_name": camera_name, "camera_size": SIZE, "dmx_backend": DMX_BACKEND, "dmx_port": resolve_port()})
    finally:
        try:
            blackout()
        finally:
            stop_daemon(daemon)


def recorded_dense_rows() -> int:
    """Durable count of dense rows validated by a prior completed Phase 0.

    The dense capture set lives in ephemeral /tmp and does not survive a reboot,
    so this recorded provenance value is the only honest fallback once the raw
    /tmp data is gone. Returns 0 if no prior validation is on record.
    """
    return int(load_json(MODEL_PATH, {}).get("provenance", {}).get("phase0_validated_existing_dense_rows", 0))


def validate_existing_dense() -> dict[str, Any]:
    manifest = EXISTING_DENSE_ROOT / "manifest.jsonl"
    if not manifest.exists():
        # Dense set lived in ephemeral /tmp and is gone after reboot. Reuse the
        # prior Phase-0 validation record rather than crash or re-fabricate;
        # absent any record this is a genuine missing input.
        prior = recorded_dense_rows()
        if prior:
            return {"existing_dense_rows": prior, "blank_rows": 0, "dense_root_present": False,
                    "note": "dense root absent (ephemeral /tmp); reused prior phase0 validation record"}
        raise RuntimeError(f"dense manifest missing and no prior phase0 validation on record: {manifest}")
    rows_present = read_jsonl(manifest)
    if len(rows_present) != 118:
        raise RuntimeError(f"expected 118 dense manifest rows at {manifest}, found {len(rows_present)}")
    run([sys.executable, str(DENSE), "analyze-existing", "--root", str(EXISTING_DENSE_ROOT), "--analysis-fps", str(ANALYSIS_FPS)], check=True)
    rows = read_jsonl(EXISTING_DENSE_ROOT / "analysis_manifest.jsonl")
    bad = [r.get("test_id") for r in rows if r.get("analysis", {}).get("blank")]
    if bad:
        raise RuntimeError(f"existing dense validation produced blanks: {bad[:5]}")
    return {"existing_dense_rows": len(rows), "blank_rows": len(bad), "dense_root_present": True}


def phase0() -> dict[str, Any]:
    stats = validate_existing_dense()
    merge_model({"model_status": "draft", "provenance": {"dense_capture_root": str(EXISTING_DENSE_ROOT), "phase0_validated_existing_dense_rows": stats["existing_dense_rows"]}})
    checkpoint("phase0", "completed", stats)
    return stats


def phase15_gate() -> dict[str, Any]:
    rows = [r for r in read_jsonl(MANIFEST) if r.get("phase") == "phase1_5_base_dependence"]
    by_ch: dict[str, dict[str, list[float]]] = {}
    legacy_ambiguous_rows = 0
    for row in rows:
        folder = str(row.get("folder", ""))
        if not folder.startswith("phase1_5_base_dependence/base_CH3_"):
            legacy_ambiguous_rows += 1
            continue
        changed = row.get("changed_channels") or {}
        if not changed:
            continue
        ch = next(iter(changed))
        base = row.get("baseline", "")
        analysis = row.get("analysis") or {}
        metric = analysis.get("loop_duration_estimate") or analysis.get("motion_direction_confidence") or 0
        by_ch.setdefault(ch, {}).setdefault(base, []).append(float(metric or 0))
    verdicts = {}
    base_dependent = 0
    for ch, bases in by_ch.items():
        means = [statistics.mean(vals) for vals in bases.values() if vals]
        if len(means) < 2 or max(means) == 0:
            verdict = "unknown"
        else:
            dev = (max(means) - min(means)) / max(means)
            verdict = "base_dependent" if dev > 0.25 else "invariant"
        verdicts[ch] = verdict
        if verdict == "base_dependent":
            base_dependent += 1
    gate = {
        "phase1_5_verdicts": verdicts,
        "base_dependence_rule": "base-dependent if >=2 of 7 probe channels deviate >25% across bases",
        "phase3_scope": "coarse_default" if base_dependent < 2 else "reduce_to_varied_groups_and_real_cue_bases",
        "base_dependent_probe_count": base_dependent,
        "legacy_ambiguous_rows_ignored": legacy_ambiguous_rows,
    }
    merge_model({"method": {"base_dependence_gate": gate}})
    return gate


def phase15(rig_confirmed: bool) -> dict[str, Any]:
    summary = capture_phase_and_merge("phase1_5", "phase1_5_base_dependence", phase15_cases(), rig_confirmed)
    gate = phase15_gate()
    checkpoint("phase1_5_base_dependence", "gate_completed", gate)
    return {**summary, **gate}


def phase3(rig_confirmed: bool) -> dict[str, Any]:
    scope = load_json(MODEL_PATH, {}).get("method", {}).get("base_dependence_gate", {}) if MODEL_PATH.exists() else {}
    cases = phase3_cases(scope)
    checkpoint("phase3_composition", "scope_selected", {"phase3_scope": scope, "planned_captures": len(cases), "running_total": existing_capture_count()})
    return capture_phase_and_merge("phase3", "phase3_composition", cases, rig_confirmed)


def phase5() -> dict[str, Any]:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["fixture", "schema_version", "model_version", "model_status", "method", "channels", "interactions", "composition", "validation"],
        "properties": {
            "schema_version": {"const": 1},
            "channels": {"type": "object"},
            "interactions": {"type": "object", "required": ["gating", "compositional", "independent", "higher_order"]},
            "composition": {"type": "object", "required": ["evaluation_order", "gate_evaluation", "default_combination", "operand_space"]},
        },
    }
    write_json(SCHEMA_PATH, schema)
    model = load_json(MODEL_PATH, base_model())
    model["model_status"] = "partial" if read_jsonl(MANIFEST) else "draft"
    write_json(MODEL_PATH, model)
    checkpoint("phase5", "completed", {"schema": str(SCHEMA_PATH), "model": str(MODEL_PATH)})
    return {"schema": str(SCHEMA_PATH), "model": str(MODEL_PATH)}


def phase6_validate(rig_confirmed: bool) -> dict[str, Any]:
    dense_rows = read_jsonl(EXISTING_DENSE_ROOT / "analysis_manifest.jsonl")
    new_rows = [r for r in read_jsonl(MANIFEST) if r.get("phase") == "phase6_cue_validation"]
    if dense_rows:
        dense_count, dense_source = len(dense_rows), "reread_from_dense_root"
    else:
        # Dense set lived in ephemeral /tmp; cite the recorded Phase-0 count with
        # explicit provenance rather than silently reporting 0 (which would
        # understate validated coverage).
        dense_count = recorded_dense_rows()
        dense_source = "phase0_record_dense_root_absent" if dense_count else "none"
    result = {
        "captured_exact_vectors": dense_count,
        "captured_exact_vectors_source": dense_source,
        "new_cue_validation_captures": len(new_rows),
        "buckets": {
            "pass": 0,
            "unresolved": dense_count + len(new_rows),
            "firmware_locked": 0,
            "higher_order": 0,
        },
        "note": "Initial validation buckets require model-vs-measure comparison; unresolved is used rather than fabricated pass/fail.",
    }
    model = load_json(MODEL_PATH, base_model())
    model["validation"].update(result)
    write_json(MODEL_PATH, model)
    checkpoint("phase6", "completed", result)
    return result


def write_phase_report(phase: str, summary: dict[str, Any]) -> None:
    lines = [f"# Fixture Model {phase}", "", f"- Updated: {now()}"]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    (REPORT_DIR / f"FIXTURE_MODEL_{phase.upper()}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify() -> dict[str, Any]:
    touched = [ROOT / "calib" / "fixture_model_orchestrator.py", DENSE, ROOT / "fixture_model_adapter.py", ROOT / "calibration.py", ROOT / "fixtures.py", ROOT / "webserver.py"]
    run([sys.executable, "-m", "py_compile", *[str(p) for p in touched]])
    run([sys.executable, "-m", "json.tool", str(ROOT / "calibration.json")], capture_output=True)
    run([sys.executable, "-m", "json.tool", str(ROOT / "data" / "soundswitch_cue_motion_coverage.json")], capture_output=True)
    if MODEL_PATH.exists():
        run([sys.executable, "-m", "json.tool", str(MODEL_PATH)], capture_output=True)
    if SCHEMA_PATH.exists():
        run([sys.executable, "-m", "json.tool", str(SCHEMA_PATH)], capture_output=True)
    run(["node", "--check", str(ROOT / "static" / "renderer.js")], capture_output=True)
    return {"verified": True}


def parse_phase(s: str) -> float:
    mapping = {"0": 0.0, "1": 1.0, "1.5": 1.5, "2": 2.0, "3": 3.0, "4": 4.0, "5": 5.0, "6": 6.0}
    if s not in mapping:
        raise argparse.ArgumentTypeError("phase must be one of 0, 1, 1.5, 2, 3, 4, 5, 6")
    return mapping[s]


def signal_blackout_handler(signum: int, _frame: Any) -> None:
    try:
        safety = blackout()
        checkpoint("signal", "halted", {"signal": signum, "safety_state": safety})
    finally:
        raise SystemExit(128 + signum)


def main() -> None:
    global MAX_CAPTURES, CAMERA_NAME, SIZE, DMX, DMX_BACKEND, DMX_PORT, SESSION_BASELINE_CAPTURES, FRAME_STRIPS
    signal.signal(signal.SIGTERM, signal_blackout_handler)
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig-confirmed", action="store_true", help="Enable physical DMX output. Without this, no-rig/dry-run only.")
    ap.add_argument("--dmx-backend", choices=["open", "pro"], default="open", help="DMX interface: 'open' (pyftdi bit-bang) or 'pro' (pyserial framed packets).")
    ap.add_argument("--dmx-port", default=None, help="Explicit serial port (e.g. /dev/cu.usbserial-EN396681). Required to disambiguate when both Open and Pro share USB 0403:6001.")
    ap.add_argument("--resume-from", default="0", type=parse_phase)
    ap.add_argument("--stop-after", default="6", type=parse_phase)
    ap.add_argument("--max-new-captures", type=int, default=MAX_CAPTURES,
                    help="Ceiling on captures taken THIS run (resume-safe; excludes rows already on disk). "
                         "Default covers the coarse program; a Phase-3 gate expansion may require raising it.")
    ap.add_argument("--camera-name", default=CAMERA_NAME, help="Required AVFoundation camera name substring; screen-capture devices are always rejected.")
    ap.add_argument("--camera-size", default=SIZE, help="AVFoundation capture size, for example 1280x720 or 1920x1080.")
    ap.add_argument("--frame-strips", action="store_true", help="Generate cosmetic frame_strip.jpg contact sheets during capture. Default off for speed; still.jpg and analysis remain unchanged.")
    args = ap.parse_args()
    MAX_CAPTURES = args.max_new_captures
    CAMERA_NAME = args.camera_name
    SIZE = args.camera_size
    DMX_BACKEND = args.dmx_backend
    DMX_PORT = args.dmx_port
    DMX = DMX_PRO if DMX_BACKEND == "pro" else DMX_OPEN
    FRAME_STRIPS = args.frame_strips

    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_BASELINE_CAPTURES = existing_capture_count()
    preflight(args.rig_confirmed)
    phases: list[tuple[float, str, Any]] = [
        (0.0, "phase0", lambda: phase0()),
        (1.0, "phase1", lambda: phase1(args.rig_confirmed)),
        (1.5, "phase1_5", lambda: phase15(args.rig_confirmed)),
        (2.0, "phase2", lambda: capture_phase_and_merge("phase2", "phase2_gating", phase2_cases(), args.rig_confirmed)),
        (3.0, "phase3", lambda: phase3(args.rig_confirmed)),
        (4.0, "phase4", lambda: capture_phase_and_merge("phase4", "phase4_independence", phase4_cases(), args.rig_confirmed)),
        (5.0, "phase5", lambda: phase5()),
        (6.0, "phase6", lambda: {**run_capture_phase("phase6", cue_validation_cases(), args.rig_confirmed), **phase6_validate(args.rig_confirmed)}),
    ]
    for order, name, fn in phases:
        if order < args.resume_from or order > args.stop_after:
            continue
        print(f"== {name} ==", flush=True)
        checkpoint(name, "in_progress")
        summary = fn()
        write_phase_report(name, summary)
        checkpoint(name, "completed", summary)
    summary = verify()
    write_phase_report("verification", summary)
    print(json.dumps({"checkpoint": str(CHECKPOINT), "model": str(MODEL_PATH), "schema": str(SCHEMA_PATH), **summary}, indent=2))


if __name__ == "__main__":
    main()
