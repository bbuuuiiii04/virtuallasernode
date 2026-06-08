#!/usr/bin/env python3
"""
Capture the CURRENT laser state durably + append to a structured manifest.

Reads the live DMX frame (/tmp/vln_calib_frame.bin), decodes it with the real
decoder (fixtures.py), grabs a camera frame into calib/captures/, and appends a
JSON line to calib/captures/manifest.jsonl recording the DMX values, the decoded
state, the image path, and an observation note. This preserves the full visual
calibration ground truth (DMX value -> what the real laser does -> frame) so a
future rendering refactor can be rebuilt from data, not memory.

Usage:
  caplog.py [--device 2] <name> "<observation note>"
  caplog.py --screen <name> "<observation note>"
"""
import sys, os, json, time, subprocess, tempfile, glob, shutil, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fixtures import FIXTURES, decode_fixture

CAPDIR = os.path.join(ROOT, "calib", "captures")
MANIFEST = os.path.join(CAPDIR, "manifest.jsonl")
FRAME = "/tmp/vln_calib_frame.bin"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default=os.environ.get("VLN_CAMERA_DEVICE", "0"),
                        help="avfoundation video device index")
    parser.add_argument("--size", default=os.environ.get("VLN_CAMERA_SIZE", "1280x720"))
    parser.add_argument("--screen", action="store_true",
                        help="capture the visible macOS screen instead of opening avfoundation")
    parser.add_argument("name")
    parser.add_argument("note", nargs="?", default="")
    args = parser.parse_args()
    name = args.name
    note = args.note
    os.makedirs(CAPDIR, exist_ok=True)

    frame = list(open(FRAME, "rb").read()) if os.path.exists(FRAME) else [0] * 512
    frame = (frame + [0] * 512)[:512]

    png = os.path.join(CAPDIR, name + ".png")
    td = tempfile.mkdtemp(prefix="caplog_")
    try:
        if args.screen:
            result = subprocess.run(["screencapture", "-x", png], check=False)
            if result.returncode != 0 or not os.path.exists(png):
                raise SystemExit("screen capture failed; no manifest entry written")
        else:
            result = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                                     "-f", "avfoundation", "-framerate", "30",
                                     "-pixel_format", "uyvy422", "-video_size", args.size,
                                     "-i", f"{args.device}:none", "-frames:v", "16",
                                     os.path.join(td, "f_%03d.png")], check=False)
            fs = sorted(glob.glob(os.path.join(td, "f_*.png")))
            if result.returncode != 0 or not fs:
                raise SystemExit(f"camera capture failed for device {args.device}; no manifest entry written")
            os.replace(fs[-1], png)
    finally:
        shutil.rmtree(td, ignore_errors=True)

    d0 = decode_fixture(frame, FIXTURES[0])
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "name": name,
        "note": note,
        "png": os.path.relpath(png, ROOT),
        "camera": {"device": "screen" if args.screen else args.device, "size": "screen" if args.screen else args.size},
        "dmx": {str(i + 1): frame[i] for i in range(36) if frame[i]},
        "decoded": {
            "color": d0.get("color", {}).get("label"),
            "pattern_kind": d0.get("pattern", {}).get("kind"),
            "pattern_group": d0.get("pattern", {}).get("group"),
            "pattern_size": d0.get("pattern", {}).get("size"),
            "position": d0.get("position", {}),
        },
    }
    with open(MANIFEST, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(png)


if __name__ == "__main__":
    main()
