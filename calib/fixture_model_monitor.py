#!/usr/bin/env python3
"""Non-invasive monitor for fixture-model capture runs.

This script never drives DMX and never edits run artifacts. It reports current
progress, process state, safety frame-file state, and writes a small contact
sheet of the most recent saved stills so camera/source drift is visible during
long unattended runs.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "captures" / "fixture_model"
CHECKPOINT = CAPTURE_ROOT / "checkpoint.json"
MANIFEST = CAPTURE_ROOT / "manifest.jsonl"
MONITOR_DIR = CAPTURE_ROOT / "_monitor"
PERIODIC_LOG = MONITOR_DIR / "periodic.log"
FRAME_PATH = Path("/tmp/vln_calib_frame.bin")
HEARTBEAT_PATH = Path("/tmp/vln_calib_frame.heartbeat")
WATCHDOG_TIMEOUT_S = 5.0


def run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def process_lines(pattern: str) -> list[str]:
    cp = run(["pgrep", "-fl", pattern])
    return [line for line in cp.stdout.splitlines() if line.strip()]


def safety_state() -> str:
    cp = run(["python3", "calib/dmx_open.py", "show"], timeout=5)
    return (cp.stdout or cp.stderr).strip()


def frame_looks_like_desktop(path: Path) -> bool:
    im = Image.open(path).convert("L")
    w, h = im.size
    top = im.crop((0, 0, w, max(1, int(h * 0.08))))
    edges = top.filter(ImageFilter.FIND_EDGES)
    vals = list(edges.getdata())
    edge_density = sum(1 for v in vals if v > 35) / max(1, len(vals))
    top_vals = list(top.getdata())
    top_mean = sum(top_vals) / max(1, len(top_vals))
    return edge_density > 0.11 and 25 <= top_mean <= 130


def latest_stills(limit: int) -> list[Path]:
    if not CAPTURE_ROOT.exists():
        return []
    paths = [
        p for p in CAPTURE_ROOT.rglob("still*.jpg")
        if "_monitor" not in p.parts and p.is_file()
    ]
    return sorted(paths, key=lambda p: p.stat().st_mtime)[-limit:]


def write_contact_sheet(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    thumbs: list[Image.Image] = []
    for path in paths:
        try:
            im = Image.open(path).convert("RGB")
            im.thumbnail((240, 135))
            tile = Image.new("RGB", (240, 168), "white")
            tile.paste(im, (0, 0))
            draw = ImageDraw.Draw(tile)
            rel = str(path.relative_to(CAPTURE_ROOT))
            flag = " DESKTOP?" if frame_looks_like_desktop(path) else ""
            draw.text((3, 138), rel[-54:], fill=(0, 0, 0))
            if flag:
                draw.text((3, 152), flag, fill=(180, 0, 0))
            thumbs.append(tile)
        except OSError:
            continue
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 240, rows * 168), (220, 220, 220))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * 240, (idx // cols) * 168))
    out = MONITOR_DIR / "latest_contact_sheet.jpg"
    try:
        sheet.save(out, quality=90)
    except OSError:
        return None
    return out


def progress_text() -> str:
    cp = run([sys.executable, "calib/fixture_model_progress.py"], timeout=20)
    return (cp.stdout or cp.stderr).strip()


def load_frame_ch1_19() -> list[int]:
    if not FRAME_PATH.exists():
        return [0] * 19
    data = FRAME_PATH.read_bytes()
    frame = (data + bytes(512))[:512]
    return [frame[i] for i in range(19)]


def active_dmx_line() -> str:
    """Always include CH6/CH7 even at 0 so translate sweeps are visible in monitor ticks."""
    frame = load_frame_ch1_19()
    nonzero = [f"CH{i + 1}={frame[i]}" for i in range(19) if frame[i]]
    ch6 = f"CH6={frame[5]}"
    ch7 = f"CH7={frame[6]}"
    if ch6 not in nonzero:
        nonzero.append(ch6)
    if ch7 not in nonzero:
        nonzero.append(ch7)
    nonzero.sort(key=lambda part: int(part.split("=", 1)[0].replace("CH", "")))
    return "ACTIVE_DMX " + (" ".join(nonzero) if nonzero else "(all zero)")


def dmx_frame_text() -> str:
    cp = run([sys.executable, "calib/dmx_pro.py", "show"], timeout=5)
    return (cp.stdout or "(all zero)").strip()


def active_look_line() -> str:
    log_hint = Path("/tmp/vln_run_log_path.txt")
    candidates: list[Path] = []
    if log_hint.exists():
        hinted = Path(log_hint.read_text().strip())
        if hinted.is_file():
            candidates.append(hinted)
    candidates.extend(sorted(CAPTURE_ROOT.glob("final_ch1_19_*.log"), key=lambda p: p.stat().st_mtime, reverse=True))
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in reversed(text.splitlines()):
            if "[phase" in line and "phase3_composition__" in line:
                return f"active_look={line.strip()}"
            if line.startswith("[phase"):
                return f"active_look={line.strip()}"
    return "active_look=(unknown)"


def heartbeat_age_s() -> float | None:
    if not HEARTBEAT_PATH.exists():
        return None
    return time.time() - HEARTBEAT_PATH.stat().st_mtime


def camera_present(name: str = "brandon Camera") -> bool:
    want = name.lower()
    cp = run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        timeout=15,
    )
    in_video = False
    for line in (cp.stderr + cp.stdout).splitlines():
        if "AVFoundation video devices:" in line:
            in_video = True
            continue
        if "AVFoundation audio devices:" in line:
            break
        if not in_video or "] [" not in line or "] " not in line:
            continue
        _idx, dev_name = line.split("] [", 1)[1].split("] ", 1)
        low = dev_name.strip().lower()
        if low == want or want in low:
            if not low.startswith("capture screen") and "desk view" not in low:
                return True
    return False


def storage_text() -> str:
    usage = shutil.disk_usage(CAPTURE_ROOT)
    cp = run(["du", "-sh", str(CAPTURE_ROOT)], timeout=120)
    du = cp.stdout.split()[0] if cp.stdout.strip() else "?"
    rows = 0
    if MANIFEST.exists():
        with MANIFEST.open("r", encoding="utf-8") as fh:
            rows = sum(1 for line in fh if line.strip())
    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    return (
        f"laptop_free_gb={free_gb:.1f} laptop_total_gb={total_gb:.1f} "
        f"captures_dir={du} manifest_rows={rows}"
    )


def output_muted() -> bool:
    cp = run(["osascript", "-e", "output muted of (get volume settings)"], timeout=5)
    return cp.stdout.strip().lower() == "true"


def latest_manifest_row() -> dict[str, Any]:
    if not MANIFEST.exists():
        return {}
    last = ""
    with MANIFEST.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = line
    return json.loads(last) if last else {}


def format_dmx_channels(values: dict[str, Any]) -> str:
    if not values:
        return "(none)"
    parts = [f"{key}={values[key]}" for key in sorted(values, key=lambda k: int(k.replace("CH", "")))]
    return " ".join(parts)


def report(limit: int, *, log_file: Path | None = None) -> None:
    checkpoint = load_json(CHECKPOINT)
    latest = latest_manifest_row()
    analysis = latest.get("analysis") or {}
    ch = latest.get("ch1_19") or {}
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append(active_dmx_line())
    lines.append(active_look_line())
    lines.append(
        "checkpoint "
        f"phase={checkpoint.get('phase')} status={checkpoint.get('status')} "
        f"total={checkpoint.get('running_total') or checkpoint.get('capture_count')} "
        f"last={checkpoint.get('last_capture')}"
    )
    err = checkpoint.get("error")
    if err:
        lines.append(f"checkpoint_error={str(err)[:180]}")
    orch = process_lines("fixture_model_orchestrator.py")
    supervisor = process_lines("run_supervisor.sh")
    daemon = process_lines("dmx_open.py daemon") + process_lines("dmx_pro.py daemon")
    watcher = process_lines("capture_stop_mute_watcher.sh")
    ffmpeg = process_lines("ffmpeg")
    lines.append(
        "processes "
        f"supervisor={len(supervisor)} orchestrator={len(orch)} "
        f"dmx_daemon={len(daemon)} mute_watcher={len(watcher)} ffmpeg={len(ffmpeg)}"
    )
    lines.append(f"camera_present={camera_present(str(checkpoint.get('camera_name') or 'brandon Camera'))}")
    lines.append(f"output_muted={output_muted()}")
    hb_age = heartbeat_age_s()
    hb_fresh = hb_age is not None and hb_age <= WATCHDOG_TIMEOUT_S
    lines.append(
        f"dmx_live_frame={dmx_frame_text()} "
        f"heartbeat_age_s={hb_age if hb_age is not None else 'missing'} "
        f"heartbeat_fresh={hb_fresh}"
    )
    lines.append(f"laptop_storage {storage_text()}")
    if latest:
        lines.append(
            "latest_capture "
            f"id={latest.get('test_id')} phase={latest.get('phase')} "
            f"fps={analysis.get('actual_fps')} blank={analysis.get('blank')} "
            f"geometry_clipped_low={analysis.get('geometry_clipped_low')}"
        )
        lines.append(f"latest_capture_dmx {format_dmx_channels(ch)}")
    lines.append(f"safety_state={safety_state()}")
    lines.append(progress_text())
    stills = latest_stills(limit)
    sheet = write_contact_sheet(stills)
    desktop_flags = [str(p.relative_to(CAPTURE_ROOT)) for p in stills if frame_looks_like_desktop(p)]
    lines.append(f"latest_stills={len(stills)} contact_sheet={sheet}")
    if desktop_flags:
        lines.append("WARNING desktop-like latest stills:")
        for path in desktop_flags:
            lines.append(f"  {path}")
    text = "\n".join(lines)
    print(text, flush=True)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=600, help="seconds between reports")
    ap.add_argument("--latest", type=int, default=16, help="number of latest stills in contact sheet")
    ap.add_argument("--once", action="store_true", help="print one report and exit")
    ap.add_argument("--log-file", type=Path, default=None, help="append each report to this file")
    args = ap.parse_args()
    log_file = args.log_file or (None if args.once else PERIODIC_LOG)
    while True:
        report(args.latest, log_file=log_file)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
