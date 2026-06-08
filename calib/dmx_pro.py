#!/usr/bin/env python3
"""
Enttec DMX USB PRO driver — for VirtualLaserNode calibration.

Drop-in CLI sibling of dmx_open.py. Same contract (daemon/base/set/blackout/
keepalive/show), same frame file (/tmp/vln_calib_frame.bin), same watchdog
heartbeat — so the orchestrator can drive either backend through the identical
subprocess + frame-file boundary. The frame/IO/stdout code below is copied
verbatim from dmx_open.py on purpose: the orchestrator string-matches `show`
output ("(all zero)") and parses `_fmt`, so the grammar MUST NOT drift.

PRO vs OPEN — the differences that matter:
  * The Open is a dumb FTDI chip: the host bit-bangs BREAK + 513 bytes at 250000
    baud, every frame, forever. Stop banging and the line goes quiet.
  * The Pro has onboard firmware. The host sends a framed "Send DMX" packet
    (label 6) ONCE and the widget AUTONOMOUSLY retransmits that frame on the DMX
    line at its own rate (measured 40 pps on this unit, firmware 300). We send
    over the FTDI VCP via pyserial; host baud is irrelevant (FT245 framing
    carries the meaning) — we open at 115200 only because the port wants a value.

  * SAFETY CONSEQUENCE (the important one): because the widget keeps outputting
    the last frame on its own, a HARD-KILLED daemon leaves the lasers stuck at
    the last frame — NOT dark. The watchdog-stale blackout below only covers the
    "orchestrator died while this daemon lives" case. A `kill -9` of THIS process
    cannot be caught; DMX-side power / the physical kill switch is the true
    failsafe. On every catchable exit (SIGTERM/SIGINT/normal) we push a real zero
    packet to the wire before closing.

Protocol (confirmed against this unit via a label-3 round-trip):
  packet = 0x7E | label | len_lsb | len_msb | payload | 0xE7   (len little-endian)
  Send DMX (label 6): payload = start_code(0x00) + 512 channel bytes => len 513
    => blackout = 7E 06 01 02 00 <512x00> E7   (518 bytes)

Channels are 1-based DMX addresses (CH1..CH512); byte index = ch-1.

Usage:
  dmx_pro.py daemon --port /dev/cu.usbserial-XXXX   # push loop (background)
  dmx_pro.py base                                   # neutral base frame
  dmx_pro.py set 8=12 5=128                          # set channel(s)
  dmx_pro.py blackout                               # all channels -> 0
  dmx_pro.py keepalive                              # touch watchdog
  dmx_pro.py show                                   # print non-zero channels
"""
import sys, os, time, argparse, signal

FRAME_PATH = "/tmp/vln_calib_frame.bin"   # 512 bytes; ch1 -> index 0
WATCHDOG_PATH = "/tmp/vln_calib_frame.heartbeat"
WATCHDOG_TIMEOUT_S = 5.0

# ENTTEC Pro framing
MSG_START = 0x7E
MSG_END = 0xE7
LABEL_GET_WIDGET_PARAMS = 3
LABEL_SEND_DMX = 6
DMX_START_CODE = 0x00
REFRESH_S = 1.0       # defensive re-push cadence (widget self-refreshes anyway)
POLL_S = 0.02         # frame-file responsiveness


# --- frame/IO/format: copied verbatim from dmx_open.py (grammar must match) ---
def load_frame():
    try:
        with open(FRAME_PATH, "rb") as f:
            b = bytearray(f.read())
    except FileNotFoundError:
        b = bytearray(512)
    if len(b) < 512:
        b.extend(bytes(512 - len(b)))
    return b[:512]


def write_frame_file(b):
    tmp = FRAME_PATH + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bytes(b))
    os.replace(tmp, FRAME_PATH)        # atomic: daemon never reads a half-write


def save_frame(b):
    write_frame_file(b)
    touch_watchdog()


def persist_blackout_frame():
    """Persist an all-zero frame without refreshing the orchestrator heartbeat."""
    write_frame_file(bytearray(512))


def touch_watchdog():
    with open(WATCHDOG_PATH, "a", encoding="utf-8"):
        os.utime(WATCHDOG_PATH, None)


def watchdog_fresh():
    try:
        return time.time() - os.path.getmtime(WATCHDOG_PATH) <= WATCHDOG_TIMEOUT_S
    except FileNotFoundError:
        return False


def _fmt(b):
    return " ".join(f"CH{i+1}={v}" for i, v in enumerate(b) if v)


# --- Pro packet ---
def build_dmx_packet(frame):
    """Label-6 Send-DMX packet for a 512-byte frame. Pure; unit-tested."""
    body = bytes([DMX_START_CODE]) + bytes(frame[:512]).ljust(512, b"\x00")
    n = len(body)                       # 513
    return bytes([MSG_START, LABEL_SEND_DMX, n & 0xFF, (n >> 8) & 0xFF]) + body + bytes([MSG_END])


_ZERO_PACKET = build_dmx_packet(bytearray(512))
_GET_WIDGET_PARAMS_PACKET = bytes([MSG_START, LABEL_GET_WIDGET_PARAMS, 0x02, 0x00, 0x00, 0x00, MSG_END])


def find_enttec_frame(raw, expected_label=None):
    """Return (label, payload, full_frame) from raw bytes, tolerating leading junk."""
    data = bytes(raw)
    for i, byte in enumerate(data):
        if byte != MSG_START:
            continue
        if len(data) < i + 5:
            return None
        label = data[i + 1]
        n = data[i + 2] | (data[i + 3] << 8)
        end = i + 4 + n
        if len(data) <= end:
            return None
        if data[end] != MSG_END:
            continue
        if expected_label is not None and label != expected_label:
            continue
        payload = data[i + 4:end]
        return label, payload, data[i:end + 1]
    return None


def _open_port(port, *, timeout=1.0, write_timeout=2.0):
    import serial
    # baud irrelevant for the FT245-based Pro; framing carries meaning.
    return serial.Serial(port, baudrate=115200, timeout=timeout, write_timeout=write_timeout)


def read_enttec_frame(ser, *, expected_label=None, timeout_s=1.5):
    raw = bytearray()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        chunk = ser.read(64)
        if chunk:
            raw.extend(chunk)
            parsed = find_enttec_frame(raw, expected_label=expected_label)
            if parsed is not None:
                return parsed
        else:
            time.sleep(0.01)
    raise TimeoutError(f"no complete Enttec frame in reply: {bytes(raw).hex(' ') or '(empty)'}")


def pro_identity_ok(port):
    """Read-only Pro probe. Sends no DMX output."""
    ser = None
    try:
        ser = _open_port(port, timeout=0.05, write_timeout=1.0)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        ser.write(_GET_WIDGET_PARAMS_PACKET)
        ser.flush()
        _label, payload, frame = read_enttec_frame(
            ser,
            expected_label=LABEL_GET_WIDGET_PARAMS,
            timeout_s=1.5,
        )
    except Exception as e:
        return False, f"Enttec Pro identity probe failed: {e}"
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
    if len(payload) < 2:
        return False, f"Enttec Pro identity reply too short: {frame.hex(' ')}"
    fw = payload[0] | (payload[1] << 8)
    return True, f"pro firmware={fw} reply={frame.hex(' ')}"


def push_blackout_best_effort(port, existing_ser=None, reopen_attempts=1):
    """Persist zero, then try to push a hardware blackout packet.

    The frame-file write is always attempted first so a live daemon can pick up
    black immediately. Direct serial output can fail when the daemon already owns
    the port; callers decide whether that is fatal.
    """
    persist_blackout_frame()
    errors = []
    if existing_ser is not None:
        try:
            existing_ser.write(_ZERO_PACKET)
            existing_ser.flush()
            return True, "blackout pushed on existing serial handle"
        except Exception as e:
            errors.append(f"existing handle: {e}")
            try:
                existing_ser.close()
            except Exception:
                pass
    for attempt in range(1, reopen_attempts + 1):
        ser = None
        try:
            ser = _open_port(port, timeout=0.2, write_timeout=1.0)
            ser.write(_ZERO_PACKET)
            ser.flush()
            return True, f"blackout pushed after reopen attempt {attempt}"
        except Exception as e:
            errors.append(f"reopen {attempt}: {e}")
            time.sleep(0.1 * attempt)
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
    return False, "; ".join(errors) if errors else "no serial handle available"


def cmd_daemon(port):
    import serial
    ok, msg = pro_identity_ok(port)
    if not ok:
        raise SystemExit(msg)
    print(f"[dmx] {msg}", flush=True)
    ser = _open_port(port)
    if not os.path.exists(FRAME_PATH):
        save_frame(bytearray(512))

    stopping = {"flag": False}

    def _stop(signum, _frame):
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    def _push(packet):
        """Write a packet; on serial error try one reopen, else re-raise."""
        nonlocal ser
        try:
            ser.write(packet)
            ser.flush()
        except serial.SerialException:
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(0.5)
            ser = _open_port(port)       # may raise — let it bubble to finally
            ser.write(packet)
            ser.flush()

    print(f"[dmx] Enttec Pro via pyserial {port}; label6 send-dmx; frame={FRAME_PATH}",
          flush=True)
    last_push = None
    last_refresh = 0.0
    watchdog_tripped = False
    try:
        while not stopping["flag"]:
            now = time.time()
            if watchdog_fresh():
                frame = load_frame()
                watchdog_tripped = False
            else:
                frame = bytearray(512)
                if not watchdog_tripped:
                    persist_blackout_frame()
                    watchdog_tripped = True
                    print("[dmx] watchdog stale; blackout frame persisted and pushed to widget", flush=True)
            packet = build_dmx_packet(frame)
            if packet != last_push or (now - last_refresh) >= REFRESH_S:
                _push(packet)
                last_push = packet
                last_refresh = now
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        pass
    finally:
        # Catchable-exit failsafe: leave the wire dark before releasing the port.
        ok, msg = push_blackout_best_effort(port, existing_ser=ser, reopen_attempts=1)
        try:
            ser.close()
        except Exception:
            pass
        suffix = "blackout pushed" if ok else f"blackout frame persisted; hardware push failed: {msg}"
        print(f"[dmx] daemon stopped ({suffix})", flush=True)


# Neutral base — identical to dmx_open.py BASE.
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


def cmd_blackout(port=None, require_hardware=False):
    save_frame(bytearray(512))
    if port:
        ok, msg = push_blackout_best_effort(port, reopen_attempts=1)
        if ok:
            print(f"[dmx] blackout hardware push: {msg}", file=sys.stderr)
        else:
            text = f"[dmx] blackout hardware push failed: {msg}"
            if require_hardware:
                raise SystemExit(text)
            print(text, file=sys.stderr)
    print("[dmx] blackout (all 0)")


def cmd_keepalive():
    touch_watchdog()
    print("[dmx] keepalive")


def cmd_show():
    print(_fmt(load_frame()) or "(all zero)")


def main():
    ap = argparse.ArgumentParser(description="Enttec DMX USB Pro driver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("daemon"); d.add_argument("--port", required=True)
    sub.add_parser("base")
    s = sub.add_parser("set"); s.add_argument("pairs", nargs="+")
    b = sub.add_parser("blackout")
    b.add_argument("--port", default=None, help="Best-effort direct Pro hardware blackout, useful if daemon is dead.")
    b.add_argument("--require-hardware", action="store_true", help="Fail if --port cannot be opened and zeroed.")
    sub.add_parser("keepalive")
    sub.add_parser("show")
    a = ap.parse_args()
    if a.cmd == "daemon":   cmd_daemon(a.port)
    elif a.cmd == "base":   cmd_base()
    elif a.cmd == "set":    cmd_set(a.pairs)
    elif a.cmd == "blackout": cmd_blackout(a.port, a.require_hardware)
    elif a.cmd == "keepalive": cmd_keepalive()
    elif a.cmd == "show":   cmd_show()


if __name__ == "__main__":
    main()
