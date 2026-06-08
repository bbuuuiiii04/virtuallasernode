#!/usr/bin/env python3
"""
Enttec DMX USB Open driver — for VirtualLaserNode calibration.

Drives the physical lasers DIRECTLY (bypassing SoundSwitch) so the calibration
loop can set any channel to any value, hold it steady, and a camera captures how
the real fixture responds. We then map that observation into the decoder
(fixtures.py) and renderer (renderer.js) — replacing guesses with ground truth.

The Open is host-timed ("bit-banged") DMX: open the FTDI serial port at 250000
baud 8N2, emit a BREAK + mark-after-break, then a start code (0x00) followed by
512 channel bytes, and repeat continuously so the fixture stays refreshed. The
Open's show-time weakness is timing JITTER under fast updates — irrelevant for
calibration, where every value is held static for seconds.

Frame state lives in a 512-byte file (FRAME_PATH). The daemon re-reads it every
frame, so `base` / `set` / `blackout` update the live output without a restart —
which lets an agent drive the rig one channel at a time across tool calls.

Channels are 1-based DMX addresses (CH1..CH512); byte index = ch-1.

Usage:
  dmx_open.py daemon --port /dev/cu.usbserial-XXXX   # run blast loop (background)
  dmx_open.py base                                   # neutral: ON, centred, 1 static pattern, no motion
  dmx_open.py set 8=12 5=128                          # set channel(s)
  dmx_open.py blackout                               # all channels -> 0
  dmx_open.py show                                   # print non-zero channels
"""
import sys, os, time, argparse

FRAME_PATH = "/tmp/vln_calib_frame.bin"   # 512 bytes; ch1 -> index 0
WATCHDOG_PATH = "/tmp/vln_calib_frame.heartbeat"
WATCHDOG_TIMEOUT_S = 5.0


def load_frame():
    try:
        with open(FRAME_PATH, "rb") as f:
            b = bytearray(f.read())
    except FileNotFoundError:
        b = bytearray(512)
    if len(b) < 512:
        b.extend(bytes(512 - len(b)))
    return b[:512]


def save_frame(b):
    tmp = FRAME_PATH + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bytes(b))
    os.replace(tmp, FRAME_PATH)        # atomic: daemon never reads a half-write
    touch_watchdog()


def touch_watchdog():
    with open(WATCHDOG_PATH, "a", encoding="utf-8"):
        os.utime(WATCHDOG_PATH, None)


def watchdog_fresh():
    try:
        return time.time() - os.path.getmtime(WATCHDOG_PATH) <= WATCHDOG_TIMEOUT_S
    except FileNotFoundError:
        return False


def _ftdi_url(prefer_serial=None):
    """Build the pyftdi URL for the Enttec Open (FT232R). Auto-pick if only one."""
    from pyftdi.ftdi import Ftdi
    devs = Ftdi.list_devices()           # [(UsbDeviceDescriptor, interface), ...]
    if not devs:
        raise SystemExit("no FTDI device found (is the Enttec Open plugged in?)")
    for desc, _iface in devs:
        sn = getattr(desc, "sn", None)
        if prefer_serial is None or sn == prefer_serial:
            return f"ftdi://ftdi:0x{desc.pid:x}:{sn}/1" if sn else \
                   f"ftdi://ftdi:0x{desc.pid:x}/1"
    raise SystemExit(f"FTDI with serial {prefer_serial} not found")


def cmd_daemon(serial_hint):
    # serial_hint may be a /dev/cu.usbserial-XXXX path, a bare serial, or None.
    sn = None
    if serial_hint:
        sn = serial_hint.rsplit("-", 1)[-1] if "usbserial-" in serial_hint else serial_hint
    from pyftdi.ftdi import Ftdi
    url = _ftdi_url(sn)
    ftdi = Ftdi()
    ftdi.open_from_url(url)
    ftdi.set_baudrate(250000)
    ftdi.set_line_property(8, 2, "N")    # 8 data bits, 2 stop, no parity
    ftdi.set_latency_timer(1)            # 1ms — THE fix the VCP path can't do
    ftdi.purge_buffers()
    if not os.path.exists(FRAME_PATH):
        save_frame(bytearray(512))
    print(f"[dmx] Enttec Open via pyftdi {url}; latency=1ms; frame={FRAME_PATH}",
          flush=True)
    try:
        watchdog_tripped = False
        while True:
            if watchdog_fresh():
                frame = load_frame()
                watchdog_tripped = False
            else:
                frame = bytearray(512)
                if not watchdog_tripped:
                    save_frame(frame)
                    watchdog_tripped = True
                    print("[dmx] watchdog stale; blackout frame written", flush=True)
            data = bytes([0x00]) + bytes(frame)        # start code + 512 channels
            # DMX BREAK via libftdi line-break (reliable, unlike VCP TIOCSBRK):
            ftdi.set_line_property(8, 2, "N", break_=True)
            time.sleep(0.0001)                          # break (coarse sleep -> ~1ms, valid)
            ftdi.set_line_property(8, 2, "N", break_=False)
            ftdi.write_data(data)                       # MAB = USB transfer latency
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ftdi.close()
        except Exception:
            pass
        print("[dmx] daemon stopped", flush=True)


# Neutral base: light ON, one static pattern, centred, NO motion / NO colour
# animation — the clean starting point every sweep returns to. Per the manual,
# static patterns only show when H/V position (CH6/CH7) are near centre (128).
BASE = {1: 255, 3: 0, 4: 10, 5: 128, 6: 128, 7: 128, 8: 8, 9: 0}


def cmd_base():
    b = bytearray(512)
    for ch, v in BASE.items():
        b[ch - 1] = v
    save_frame(b)
    print("[dmx] base neutral frame written:", _fmt(b))


def cmd_set(pairs):
    b = load_frame()
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"bad arg {p!r}; expected CH=VAL")
        ch, val = p.split("=", 1)
        ch, val = int(ch), int(val)
        if not (1 <= ch <= 512):
            raise SystemExit(f"channel {ch} out of range 1..512")
        if not (0 <= val <= 255):
            raise SystemExit(f"value {val} out of range 0..255")
        b[ch - 1] = val
    save_frame(b)
    print("[dmx] set", " ".join(pairs), "->", _fmt(b))


def cmd_blackout():
    save_frame(bytearray(512))
    print("[dmx] blackout (all 0)")


def cmd_keepalive():
    touch_watchdog()
    print("[dmx] keepalive")


def cmd_show():
    print(_fmt(load_frame()) or "(all zero)")


def _fmt(b):
    return " ".join(f"CH{i+1}={v}" for i, v in enumerate(b) if v)


def main():
    ap = argparse.ArgumentParser(description="Enttec DMX USB Open driver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("daemon"); d.add_argument("--port", required=True)
    sub.add_parser("base")
    s = sub.add_parser("set"); s.add_argument("pairs", nargs="+")
    sub.add_parser("blackout")
    sub.add_parser("keepalive")
    sub.add_parser("show")
    a = ap.parse_args()
    if a.cmd == "daemon":   cmd_daemon(a.port)
    elif a.cmd == "base":   cmd_base()
    elif a.cmd == "set":    cmd_set(a.pairs)
    elif a.cmd == "blackout": cmd_blackout()
    elif a.cmd == "keepalive": cmd_keepalive()
    elif a.cmd == "show":   cmd_show()


if __name__ == "__main__":
    main()
