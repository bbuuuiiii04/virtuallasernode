#!/usr/bin/env python3
"""
Grab one camera frame to PNG (macOS, via ffmpeg avfoundation) for the
VirtualLaserNode calibration loop.

Captures a short burst and keeps the LAST frame so the webcam's auto-exposure /
white-balance has time to settle on the (very bright, very saturated) laser
output before we read the colour. The agent then views the PNG and records what
the real fixture is doing for the DMX value currently being held.

Usage:
  grab.py --out /tmp/calib/ch8_v12.png                 # default device 0 (FaceTime HD)
  grab.py --device 1 --out shot.png --settle 30        # OBS virtual cam, longer settle
"""
import subprocess, sys, argparse, os, tempfile, glob, shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="0", help="avfoundation video device index")
    ap.add_argument("--out", required=True, help="output PNG path")
    ap.add_argument("--settle", type=int, default=20,
                    help="frames to capture; the last is kept (lets exposure settle)")
    ap.add_argument("--size", default="1280x720")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="vlngrab_")
    try:
        pat = os.path.join(tmpdir, "f_%04d.png")
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "avfoundation", "-framerate", "30", "-video_size", a.size,
               "-i", f"{a.device}:none", "-frames:v", str(a.settle), pat]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(f"ffmpeg failed (device {a.device}?). "
                     f"List devices: ffmpeg -f avfoundation -list_devices true -i \"\"")
        frames = sorted(glob.glob(os.path.join(tmpdir, "f_*.png")))
        if not frames:
            sys.exit("no frame captured")
        os.replace(frames[-1], a.out)
        print(a.out)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
