#!/usr/bin/env python3
"""
virtual_laser_node_poc.py

Virtual Art-Net node + live ArtDMX channel inspector for SoundSwitch.
Covers build-order steps 1-4 (node detection, ArtDMX receive, raw channel
inspector, fixture patch slicing). It does NOT yet decode fixture profiles
or render fixtures (steps 5-6).

What it does:
    - binds UDP 6454 on the wildcard + specific local IPs (see KEY FINDING in
      the README) so it both gets discovered AND actually receives the DMX
    - answers ArtPoll with a spec-shaped ArtPollReply (so SoundSwitch lists us)
    - receives ArtDMX for all universes, deduplicates SoundSwitch's multi-IP
      copies, tracks per-universe state, and logs it (throttled by default)
    - with --web, serves a browser channel inspector (HTTP + SSE) showing a
      live 512-channel heatmap per universe and the fixture patch
    - tells you loudly if NOTHING is arriving (a discovery / firewall problem,
      not a renderer problem)

See the README section at the bottom of this file for setup + the networking
findings that made same-host discovery and DMX delivery work.
"""

import argparse
import json
import select
import socket
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTNET_PORT = 6454
ARTNET_ID = b"Art-Net\x00"          # 8-byte magic header, NUL-terminated

# OpCodes are transmitted little-endian on the wire (Art-Net spec).
OP_POLL = 0x2000        # ArtPoll       (controller -> node, "who is there?")
OP_POLL_REPLY = 0x2100  # ArtPollReply  (node -> controller, "here I am")
OP_DMX = 0x5000         # ArtDmx / OpOutput (controller -> node, channel data)

OPCODE_NAMES = {
    OP_POLL: "ArtPoll (OpPoll)",
    OP_POLL_REPLY: "ArtPollReply",
    OP_DMX: "ArtDmx (OpOutput)",
}

# Identity advertised to controllers.
SHORT_NAME = "VirtualLaserNode"
LONG_NAME = "VirtualLaserNode SoundSwitch Local Renderer"

# Universes we advertise / expect (wire universe numbers). NOTE: this is
# informational only (used in the startup banner). build_art_poll_reply()
# constructs the port/SwOut fields independently — keep them in sync by hand.
ADVERTISED_UNIVERSES = (0,)

# ---------------------------------------------------------------------------
# Fixture patch (step 4: fixture patch slicing)
# ---------------------------------------------------------------------------
# Two identical RGB galvo laser fixtures, both patched in 36CH (Professional)
# mode at DMX address 001, on separate universes (SoundSwitch "Universe One &
# Two"). Channel meanings come from the fixture manual and get decoded at
# step 5. (Confirmed from the manual + patch: 36 channels each, addr 1.)
FIXTURES = [
    {"name": "Laser 1", "universe": 0, "start": 1, "count": 36, "mode": "36ch"},
    {"name": "Laser 2", "universe": 1, "start": 1, "count": 36, "mode": "36ch"},
]

WEB_PUSH_HZ = 30        # SSE snapshot rate to the browser
MAX_SSE_CLIENTS = 16    # cap concurrent /stream connections (each = 1 thread)

STATUS_INTERVAL = 5.0       # seconds between operator status lines
DMX_LOG_MIN_INTERVAL = 0.2  # default mode: at most ~5 DMX log lines/sec/universe
POLL_LOG_INTERVAL = 5.0     # default mode: throttle ArtPoll/reply logging

# Verbosity config, populated from CLI flags in main().
CFG = {
    "dump_all": False,        # log every Art-Net packet, no throttling
    "changes_only": False,    # for ArtDMX, log only when channel values change
    "quiet_poll_replies": False,  # always suppress our own ArtPollReply echoes
}


# ---------------------------------------------------------------------------
# Per-universe state
# ---------------------------------------------------------------------------

@dataclass
class UniverseState:
    """Live state for one observed Art-Net universe."""
    universe: int
    buffer: bytearray = field(default_factory=lambda: bytearray(512))
    packet_count: int = 0
    locked_src: str = ""          # universe is pinned to one source IP
    dup_count: int = 0            # frames dropped as duplicates from other src
    last_ts: float = 0.0          # monotonic time of last packet
    recv_times: deque = field(default_factory=deque)  # timestamps in last ~1s
    last_log_ts: float = 0.0      # for default-mode rate limiting

    @property
    def fps(self):
        """
        Frames in the last second — burst-immune, unlike a 1/dt estimate.

        The deque is pruned only by the writer thread in update(), so if DMX
        stops it would otherwise report the last active rate forever. Guard on
        last_ts: if the most recent frame is >1s old, zero frames arrived in
        the last second by definition. This reads only atomic fields (len /
        float load) — no cross-thread deque mutation or iteration.
        """
        if not self.recv_times or (time.monotonic() - self.last_ts) > 1.0:
            return 0
        return len(self.recv_times)

    def update(self, channels, now):
        """Fold a new ArtDMX payload into this universe. Returns changed list."""
        # FPS via a 1-second sliding window (robust to bursty arrival).
        self.recv_times.append(now)
        cutoff = now - 1.0
        while self.recv_times and self.recv_times[0] < cutoff:
            self.recv_times.popleft()
        self.last_ts = now

        # Diff against previous frame (1-based channel numbers for humans).
        # Only the first n channels are overwritten; channels above a short
        # frame's length intentionally HOLD their last value — that is correct
        # DMX semantics (a fixture holds its last commanded level). SoundSwitch
        # sends full 512-channel frames in practice, so this rarely matters.
        n = len(channels)
        changed = [i + 1 for i in range(n) if self.buffer[i] != channels[i]]
        self.buffer[0:n] = channels
        self.packet_count += 1
        return changed


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Local IP detection
# ---------------------------------------------------------------------------

def detect_local_ip():
    """
    Find the IP of the interface that would be used to reach the LAN.

    We open a throwaway UDP socket and "connect" it to a remote address.
    No packets are sent by connect() on a UDP socket; the OS just picks the
    egress interface, and getsockname() then reveals that interface's IP.
    Falls back to 127.0.0.1 if detection fails (e.g. fully offline).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def broadcast_ip_for(local_ip):
    """
    Derive a /24 directed-broadcast address for the local subnet
    (e.g. 192.168.1.42 -> 192.168.1.255). This is a best-effort guess used
    only for the unsolicited startup ArtPollReply; we also send to the global
    255.255.255.255 broadcast as a backstop.
    """
    parts = local_ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["255"])
    return "255.255.255.255"


# ---------------------------------------------------------------------------
# ArtPollReply construction
# ---------------------------------------------------------------------------

def build_art_poll_reply(local_ip):
    """
    Build a minimal but spec-shaped ArtPollReply (239 bytes).

    Only the fields a controller actually inspects to list us as a usable
    output node are filled meaningfully; everything else is zeroed.

    We advertise a single DMX-capable OUTPUT port on wire universe 0. The
    advertised port count does NOT gate whether SoundSwitch emits ArtDMX —
    once the node is assigned to a universe, SoundSwitch sends DMX to it
    regardless. The MVP only needs Universe 0 channel data, so we keep the
    reply minimal and let the ArtDMX receiver below handle whatever universe
    actually arrives.
    """
    pkt = bytearray()

    # ID[8] — "Art-Net\0"
    pkt += ARTNET_ID

    # OpCode[2] — little-endian
    pkt += struct.pack("<H", OP_POLL_REPLY)

    # IP Address[4] — our node IP, raw bytes in network order
    try:
        pkt += socket.inet_aton(local_ip)
    except OSError:
        pkt += socket.inet_aton("127.0.0.1")

    # Port[2] — little-endian (Art-Net is unusual here: this one field is LE)
    pkt += struct.pack("<H", ARTNET_PORT)

    # VersInfoH / VersInfoL — firmware version (big-endian-ish, byte pair)
    pkt += bytes([0x00, 0x01])

    # NetSwitch / SubSwitch — top bits of the 15-bit Port-Address. 0 => net 0.
    pkt += bytes([0x00, 0x00])

    # OemHi / OemLo — 0x00FF = "unknown / generic" OEM code
    pkt += bytes([0x00, 0xFF])

    # Ubea version
    pkt += bytes([0x00])

    # Status1 — bit7..6 ind: 0b11 = indicators in normal mode; rest 0
    pkt += bytes([0xC0])

    # EstaMan[2] — ESTA manufacturer code, 0x0000 (none) is fine for a POC
    pkt += struct.pack("<H", 0x0000)

    # ShortName[18] — NUL-padded, last byte must be NUL
    short = SHORT_NAME.encode("ascii", "ignore")[:17]
    pkt += short + b"\x00" * (18 - len(short))

    # LongName[64] — NUL-padded, last byte must be NUL
    long_ = LONG_NAME.encode("ascii", "ignore")[:63]
    pkt += long_ + b"\x00" * (64 - len(long_))

    # NodeReport[64] — human-readable status string, NUL-padded
    report = b"#0001 [0000] VirtualLaserNode POC OK"
    report = report[:63]
    pkt += report + b"\x00" * (64 - len(report))

    # NumPortsHi / NumPortsLo — we expose 1 port
    pkt += bytes([0x00, 0x01])

    # PortTypes[4] — bit7=output capable, low bits=protocol(0=DMX512).
    # 0x80 => port 0 can OUTPUT DMX512. Remaining ports unused.
    pkt += bytes([0x80, 0x00, 0x00, 0x00])

    # GoodInput[4] — input status flags (we are output-only); zeroed
    pkt += bytes([0x00, 0x00, 0x00, 0x00])

    # GoodOutput[4] — bit7 set => data is being output / port enabled.
    pkt += bytes([0x80, 0x00, 0x00, 0x00])

    # SwIn[4] — low nibble of Port-Address for each input port (unused)
    pkt += bytes([0x00, 0x00, 0x00, 0x00])

    # SwOut[4] — low nibble of Port-Address per output port.
    # Port 0 => wire universe 0 (with Net=0, Sub=0).
    pkt += bytes([0x00, 0x00, 0x00, 0x00])

    # SwVideo, SwMacro, SwRemote
    pkt += bytes([0x00, 0x00, 0x00])

    # Spare1..3
    pkt += bytes([0x00, 0x00, 0x00])

    # Style — 0x00 = StNode (a DMX-to/from-Art-Net device)
    pkt += bytes([0x00])

    # MAC[6] — zeroed (optional for a POC)
    pkt += bytes([0x00] * 6)

    # BindIp[4]
    pkt += socket.inet_aton("0.0.0.0")

    # BindIndex
    pkt += bytes([0x01])

    # Status2 — bit3 set => supports 15-bit Port-Address (ArtNet 3+); harmless
    pkt += bytes([0x08])

    # Filler[26] — pad to the canonical 239-byte length
    pkt += bytes([0x00] * 26)

    return bytes(pkt)


# ---------------------------------------------------------------------------
# Packet parsing
# ---------------------------------------------------------------------------

def _fmt_changed(changed, limit=12):
    """Compact rendering of a changed-channel list."""
    if not changed:
        return "[none]"
    if len(changed) <= limit:
        return "[" + ",".join(str(c) for c in changed) + "]"
    head = ",".join(str(c) for c in changed[:limit])
    return f"[{head},...(+{len(changed) - limit})]"


def parse_artdmx(data, src_ip, universes, now):
    """
    Parse an ArtDmx packet, update UniverseState, and log per the active
    verbosity. Returns True if the packet was a valid ArtDmx.

    Works for ALL universes (no universe-0-only filter).
    """
    if len(data) < 18:
        log(f"  ArtDmx too short ({len(data)} bytes) from {src_ip} — ignored")
        return False

    # bytes 10-11 protocol version and byte 13 physical are unused here.
    sequence = data[12]                             # byte 12
    # bytes 14-15, little-endian. The Port-Address is 15-bit; bit 15 is
    # reserved, so mask it off rather than trust a bogus high universe number.
    universe = struct.unpack("<H", data[14:16])[0] & 0x7FFF
    length = struct.unpack(">H", data[16:18])[0]    # bytes 16-17, big-endian

    if not (2 <= length <= 512):
        log(f"  ArtDmx invalid length {length} (must be 2-512) "
            f"from {src_ip} univ={universe} — ignored")
        return False

    channels = data[18:18 + length]
    if len(channels) != length:
        log(f"  ArtDmx truncated: declared len={length} but only "
            f"{len(channels)} payload bytes from {src_ip} univ={universe} "
            f"— ignored")
        return False

    state = universes.get(universe)
    if state is None:
        state = UniverseState(universe=universe)
        universes[universe] = state
        state.locked_src = src_ip
        log(f"[DMX] NEW universe {universe} locked to source {src_ip}")
    elif src_ip != state.locked_src:
        # SoundSwitch sends each universe to MULTIPLE local IPs (127.0.0.1 AND
        # the LAN IP), so the same frame reaches us on two sockets. Pin each
        # universe to one source to avoid double-counting / FPS inflation.
        # Prefer the loopback path: "Localhost Art-Net Node" delivers a clean
        # ~30fps stream on 127.0.0.1, whereas the LAN-IP path carries extra
        # duplicate copies. Otherwise only fail over if the lock goes stale.
        loop_now = src_ip.startswith("127.")
        loop_locked = state.locked_src.startswith("127.")
        if loop_now and not loop_locked:
            log(f"[DMX] universe {universe} re-locking {state.locked_src} -> "
                f"{src_ip} (prefer loopback)")
            state.locked_src = src_ip
        elif state.last_ts and (now - state.last_ts) <= 2.0:
            state.dup_count += 1
            return True
        else:
            log(f"[DMX] universe {universe} re-locking {state.locked_src} -> "
                f"{src_ip} (previous source went stale)")
            state.locked_src = src_ip

    changed = state.update(channels, now)

    # ---- decide whether to log this frame --------------------------------
    if CFG["changes_only"] and not changed:
        return True
    if not CFG["dump_all"] and not CFG["changes_only"]:
        # Default mode: rate-limit to ~5 lines/sec/universe regardless of
        # whether anything changed (idle shows are all-zero every frame).
        if now - state.last_log_ts < DMX_LOG_MIN_INTERVAL:
            return True
    state.last_log_ts = now

    first32 = " ".join(f"{c}" for c in state.buffer[:32])
    log(f"[DMX] U{universe} fps={state.fps:3d} seq={sequence} "
        f"len={length} pkts={state.packet_count} "
        f"changed={_fmt_changed(changed)} src={src_ip}")
    log(f"      first32=[{first32}]")
    return True


# ---------------------------------------------------------------------------
# Browser channel inspector (step 3: raw channel inspector)
# ---------------------------------------------------------------------------

INSPECTOR_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>VirtualLaserNode — Channel Inspector</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0b0d12; color:#cdd3de;
         font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; }
  header { padding:10px 14px; border-bottom:1px solid #1d2230;
           display:flex; gap:18px; align-items:baseline; flex-wrap:wrap; }
  h1 { font-size:14px; margin:0; color:#7aa2ff; letter-spacing:.5px; }
  .stat { color:#8b93a7; }
  .stat b { color:#e8edf6; font-weight:600; }
  .dot { width:9px;height:9px;border-radius:50%;display:inline-block;
         background:#444;margin-right:5px;vertical-align:middle; }
  .dot.live { background:#36d399; box-shadow:0 0 7px #36d399; }
  section { padding:14px; }
  h2 { font-size:12px; text-transform:uppercase; letter-spacing:1px;
       color:#8b93a7; margin:0 0 8px; }
  .uni { margin-bottom:18px; }
  canvas { image-rendering:pixelated; border:1px solid #1d2230; border-radius:4px;
           width:100%; max-width:680px; height:auto; }
  .fixtures { display:flex; gap:14px; flex-wrap:wrap; }
  .fx { background:#11141c; border:1px solid #1d2230; border-radius:6px;
        padding:10px 12px; min-width:230px; }
  .fx h3 { margin:0 0 8px; font-size:12px; color:#e8edf6; }
  .ch { display:grid; grid-template-columns:42px 1fr 34px; gap:6px;
        align-items:center; margin:2px 0; }
  .ch .n { color:#737b8f; }
  .bar { height:10px; background:#1b2030; border-radius:3px; overflow:hidden; }
  .bar > i { display:block; height:100%; background:linear-gradient(90deg,#3b82f6,#22d3ee); }
  .v { text-align:right; color:#cdd3de; }
  .muted { color:#5a6072; }
</style></head>
<body>
<header>
  <h1>◢ VirtualLaserNode</h1>
  <span class="stat"><span id="dot" class="dot"></span><span id="conn">connecting…</span></span>
  <span class="stat">universes <b id="nuni">0</b></span>
  <span class="stat">polls <b id="polls">0</b></span>
</header>
<section>
  <h2>Universes — raw 512 channels (brighter = higher value)</h2>
  <div id="unis"></div>
  <h2 style="margin-top:18px">Fixture patch</h2>
  <div id="fixtures" class="fixtures"></div>
</section>
<script>
const COLS=32, ROWS=16, CELL=20;
const uniEls={}; // universe -> {canvas, ctx, meta}
const fxEls={};

function ensureUni(u){
  if(uniEls[u]) return uniEls[u];
  const wrap=document.createElement('div'); wrap.className='uni';
  const lbl=document.createElement('div'); lbl.innerHTML=
    '<b style="color:#e8edf6">Universe '+u+'</b> <span class="muted" id="um'+u+'"></span>';
  const cv=document.createElement('canvas'); cv.width=COLS*CELL; cv.height=ROWS*CELL;
  wrap.appendChild(lbl); wrap.appendChild(cv);
  document.getElementById('unis').appendChild(wrap);
  uniEls[u]={canvas:cv, ctx:cv.getContext('2d'), meta:document.getElementById('um'+u)};
  return uniEls[u];
}

function drawUni(u, values){
  const o=ensureUni(u), ctx=o.ctx;
  for(let i=0;i<512;i++){
    const v=values[i]||0, x=(i%COLS)*CELL, y=Math.floor(i/COLS)*CELL;
    // heat ramp: dark blue -> cyan -> white
    const t=v/255;
    const r=Math.round(20+t*t*235), g=Math.round(30+t*200), b=Math.round(50+t*150);
    ctx.fillStyle = v? 'rgb('+r+','+g+','+b+')' : '#0e1118';
    ctx.fillRect(x,y,CELL-1,CELL-1);
  }
}

function ensureFx(f, idx){
  if(fxEls[idx]) return fxEls[idx];
  const box=document.createElement('div'); box.className='fx';
  // Build the title with textContent (not innerHTML) so fixture names that
  // become external at step 5 (from SoundSwitch) can't inject markup.
  const h3=document.createElement('h3');
  h3.textContent=f.name+' ';
  const meta=document.createElement('span'); meta.className='muted';
  meta.textContent='U'+f.universe+' · ch '+f.start+'–'+(f.start+f.count-1);
  h3.appendChild(meta); box.appendChild(h3);
  const rows=[];
  for(let c=0;c<f.count;c++){
    const row=document.createElement('div'); row.className='ch';
    row.innerHTML='<span class="n muted">ch'+(f.start+c)+'</span>'+
      '<span class="bar"><i style="width:0%"></i></span><span class="v">0</span>';
    box.appendChild(row);
    rows.push({bar:row.querySelector('i'), v:row.querySelector('.v')});
  }
  document.getElementById('fixtures').appendChild(box);
  fxEls[idx]={rows, f}; return fxEls[idx];
}

function drawFx(f, idx, values){
  const o=ensureFx(f, idx);
  for(let c=0;c<f.count;c++){
    const v=values[f.start-1+c]||0;
    o.rows[c].bar.style.width=(v/255*100).toFixed(0)+'%';
    o.rows[c].v.textContent=v;
  }
}

const es=new EventSource('/stream');
es.onopen=()=>{document.getElementById('dot').className='dot live';
  document.getElementById('conn').textContent='live';};
es.onerror=()=>{document.getElementById('dot').className='dot';
  document.getElementById('conn').textContent='reconnecting…';};
es.onmessage=(e)=>{
  const d=JSON.parse(e.data);
  document.getElementById('nuni').textContent=Object.keys(d.universes).length;
  document.getElementById('polls').textContent=d.polls;
  for(const u in d.universes){
    const us=d.universes[u];
    drawUni(u, us.values);
    ensureUni(u).meta.textContent='fps '+us.fps+' · src '+us.src+' · pkts '+us.pkts;
  }
  d.fixtures.forEach((f,i)=>{
    const vals=(d.universes[f.universe]||{}).values;
    if(vals) drawFx(f, i, vals);
  });
};
</script>
</body></html>"""


def _web_snapshot(universes, poll_count_ref):
    """Build a JSON-serializable snapshot of all universes + the fixture patch.

    Per-field reads are individually GIL-atomic (single writer thread), but the
    snapshot is not transactionally consistent — buffer, fps, and pkts may come
    from adjacent frames. Cosmetic for a visualizer; if the renderer ever needs
    a coherent frame, add a per-UniverseState lock and copy all fields under it.
    """
    unis = {}
    # list() materializes the items atomically under the GIL — the receiver
    # thread may insert a new universe mid-iteration, which would otherwise
    # raise "dictionary changed size during iteration".
    for u, st in list(universes.items()):
        unis[str(u)] = {
            "values": list(st.buffer),   # 512 ints (atomic copy under GIL)
            "fps": st.fps,
            "src": st.locked_src,
            "pkts": st.packet_count,
        }
    return {
        "universes": unis,
        "fixtures": FIXTURES,
        "polls": poll_count_ref[0],
    }


def start_web_server(universes, poll_count_ref, port):
    """Start the HTTP + SSE inspector in a daemon thread. Returns the server."""
    html_bytes = INSPECTOR_HTML.encode("utf-8")
    # Bound the number of live /stream threads so runaway reconnects or many
    # open tabs can't spawn unbounded daemon threads.
    sse_slots = threading.BoundedSemaphore(MAX_SSE_CLIENTS)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # silence default per-request logging

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.end_headers()
                self.wfile.write(html_bytes)
            elif self.path == "/stream":
                if not sse_slots.acquire(blocking=False):
                    self.send_response(503)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"too many SSE clients")
                    return
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    period = 1.0 / WEB_PUSH_HZ
                    while True:
                        snap = _web_snapshot(universes, poll_count_ref)
                        payload = "data: " + json.dumps(snap) + "\n\n"
                        self.wfile.write(payload.encode("utf-8"))
                        self.wfile.flush()
                        time.sleep(period)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return  # browser tab closed
                finally:
                    sse_slots.release()
            else:
                self.send_response(404)
                self.end_headers()

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="VirtualLaserNode POC — virtual Art-Net node / ArtDMX "
                    "receiver for SoundSwitch.")
    p.add_argument("--dump-all", action="store_true",
                   help="log EVERY Art-Net packet (polls, replies, echoes, "
                        "every ArtDMX frame) with no throttling")
    p.add_argument("--changes-only", action="store_true",
                   help="for ArtDMX, log only frames where channel values "
                        "changed since the previous frame")
    p.add_argument("--quiet-poll-replies", action="store_true",
                   help="always suppress logging of our own ArtPollReply "
                        "echoes (even under --dump-all)")
    p.add_argument("--web", action="store_true",
                   help="start the browser channel inspector (HTTP + SSE)")
    p.add_argument("--web-port", type=int, default=8137,
                   help="port for the web inspector (default 8137)")
    p.add_argument("--bind-ip", action="append", default=[], metavar="IP",
                   help="extra specific local IP to bind for ArtDMX receive "
                        "(repeatable; use on multi-homed machines where the "
                        "auto-detected route isn't the one SoundSwitch targets)")
    return p.parse_args(argv)


def open_socket(bind_ip, broadcast=False):
    """
    Open a UDP socket on bind_ip:ARTNET_PORT with the shared-port options.

    Returns the socket, or None if the bind failed (e.g. an interface IP that
    no longer exists). SO_REUSEADDR + SO_REUSEPORT are required so we can
    coexist with SoundSwitch, which already holds port 6454.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    if broadcast:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.bind((bind_ip, ARTNET_PORT))
    except OSError as e:
        log(f"  Could not bind {bind_ip}:{ARTNET_PORT} — {e}")
        s.close()
        return None
    return s


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main(argv=None):
    args = parse_args(argv)
    CFG["dump_all"] = args.dump_all
    CFG["changes_only"] = args.changes_only
    CFG["quiet_poll_replies"] = args.quiet_poll_replies

    local_ip = detect_local_ip()
    bcast_targets = sorted({"255.255.255.255", broadcast_ip_for(local_ip)})

    # The WILDCARD socket receives broadcast ArtPoll and is used to SEND the
    # broadcast ArtPollReply. (Discovery path.)
    sock = open_socket("0.0.0.0", broadcast=True)
    if sock is None:
        log(f"FATAL: could not bind 0.0.0.0:{ARTNET_PORT}. Another Art-Net app "
            f"(or a previous instance) may hold the port. Close it and retry.")
        sys.exit(1)

    # SPECIFIC-IP sockets win the unicast demux for ArtDMX. SoundSwitch sends
    # DMX as unicast to its own addresses (127.0.0.1 and the LAN IP) over
    # loopback. On a shared SO_REUSEPORT port, unicast goes to only ONE socket
    # in the group; a socket bound to the *specific* destination IP beats
    # SoundSwitch's wildcard socket, so WE receive the DMX. (Data path.)
    recv_socks = [("0.0.0.0", sock)]
    # 127.0.0.1 + auto-detected LAN IP + any user --bind-ip overrides.
    for ip in dict.fromkeys(["127.0.0.1", local_ip, *args.bind_ip]):
        if ip == "0.0.0.0":
            continue
        s = open_socket(ip)
        if s is not None:
            recv_socks.append((ip, s))

    bound_ips = [ip for ip, _ in recv_socks]

    # ---- startup banner ---------------------------------------------------
    log("VirtualLaserNode POC starting")
    log(f"Receive sockets bound: {bound_ips}  (port {ARTNET_PORT})")
    log(f"Local detected IP: {local_ip}")
    log(f"Broadcast targets: {bcast_targets}")
    log(f"Advertised ports: {len(ADVERTISED_UNIVERSES)}")
    log(f"Advertised universes: {', '.join(str(u) for u in ADVERTISED_UNIVERSES)}")
    mode = ("dump-all" if CFG["dump_all"]
            else "changes-only" if CFG["changes_only"] else "default")
    log(f"Log mode: {mode}")
    log("Waiting for ArtPoll / ArtDMX")

    reply = build_art_poll_reply(local_ip)

    def send_reply(reason, force_log=False):
        """
        Broadcast the ArtPollReply.

        IMPORTANT: we BROADCAST rather than unicast back to the poller. On a
        single machine, SoundSwitch and this node both bind UDP 6454 (via
        SO_REUSEPORT). A *unicast* datagram to that shared host:port is handed
        to only ONE of the two sockets (chosen by the kernel's hash) — in
        practice it kept landing back on OUR socket, so SoundSwitch never saw
        it. A *broadcast* datagram is delivered to ALL sockets bound to the
        port, guaranteeing SoundSwitch's socket receives the reply too. This
        is also exactly what the Art-Net spec prescribes for ArtPollReply.
        """
        for bcast in bcast_targets:
            try:
                sock.sendto(reply, (bcast, ARTNET_PORT))
            except OSError as e:
                log(f"  Could not broadcast ArtPollReply to {bcast}: {e}")
        if force_log or CFG["dump_all"]:
            log(f"  ArtPollReply broadcast to {bcast_targets} "
                f"({len(reply)} bytes) [{reason}]")

    # Unsolicited startup ArtPollReply — announce ourselves before any poll.
    send_reply("startup announce", force_log=True)

    universes = {}
    poll_count = [0]   # 1-element list so the web thread can read it live

    if args.web:
        try:
            start_web_server(universes, poll_count, args.web_port)
            log(f"Web inspector: http://127.0.0.1:{args.web_port}/")
        except OSError as e:
            log(f"Web inspector failed to start on port {args.web_port}: {e}")

    now0 = time.monotonic()
    last_poll_time = 0.0
    last_dmx_time = 0.0
    last_poll_log = 0.0
    last_status = now0

    all_socks = [s for _ip, s in recv_socks]

    while True:
        # select() across all bound sockets; 0.5s timeout so the periodic
        # status tick fires even when idle.
        try:
            ready, _, _ = select.select(all_socks, [], [], 0.5)
        except KeyboardInterrupt:
            raise
        except OSError:
            ready = []

        now = time.monotonic()

        for s in ready:
            try:
                data, addr = s.recvfrom(2048)
            except OSError:
                continue

            src_ip, src_port = addr

            if len(data) < 10:
                if CFG["dump_all"]:
                    log(f"Runt packet ({len(data)} bytes) from "
                        f"{src_ip}:{src_port} — not Art-Net")
                continue
            if data[:8] != ARTNET_ID:
                if CFG["dump_all"]:
                    log(f"Non-Art-Net UDP from {src_ip}:{src_port} "
                        f"(first 8 bytes: {data[:8]!r}) — ignored")
                continue

            opcode = struct.unpack("<H", data[8:10])[0]  # bytes 8-9, LE

            if opcode == OP_POLL:
                poll_count[0] += 1
                last_poll_time = now
                # Throttle poll logging in default/changes-only modes.
                if CFG["dump_all"] or (now - last_poll_log
                                       >= POLL_LOG_INTERVAL):
                    last_poll_log = now
                    log(f"ArtPoll received from {src_ip} "
                        f"(#{poll_count[0]}) -> broadcasting ArtPollReply")
                send_reply(f"answering poll from {src_ip}")

            elif opcode == OP_DMX:
                # Only count it as "DMX flowing" if it was a VALID ArtDmx —
                # malformed OpDmx shouldn't make the status claim DMX activity.
                if parse_artdmx(data, src_ip, universes, now):
                    last_dmx_time = now

            elif opcode == OP_POLL_REPLY:
                # Our own announcement echoed back via broadcast, or another
                # real node. Suppressed unless --dump-all and not quieted.
                if CFG["dump_all"] and not CFG["quiet_poll_replies"]:
                    log(f"  (ArtPollReply from {src_ip} — node or echo)")

            else:
                name = OPCODE_NAMES.get(opcode, f"0x{opcode:04X}")
                if CFG["dump_all"]:
                    log(f"Unhandled opcode 0x{opcode:04X} [{name}] from "
                        f"{src_ip} — ignored")

        # ---- periodic operator status ------------------------------------
        if now - last_status >= STATUS_INTERVAL:
            last_status = now
            dmx_recent = last_dmx_time > 0 and (now - last_dmx_time) < \
                STATUS_INTERVAL
            poll_recent = last_poll_time > 0 and (now - last_poll_time) < \
                STATUS_INTERVAL

            if dmx_recent or universes:
                log(f"[STATUS] ArtDMX flowing — {len(universes)} universe(s), "
                    f"{poll_count[0]} polls answered")
                for u in sorted(universes):
                    st = universes[u]
                    age = now - st.last_ts if st.last_ts else 0.0
                    log(f"[STATUS]   U{u}: pkts={st.packet_count} "
                        f"fps={st.fps:3d} last={age:4.1f}s ago "
                        f"src={st.locked_src} dups_dropped={st.dup_count}")
            elif poll_recent:
                log("[STATUS] Discovery active: ArtPoll received, replies "
                    "sent, but NO ArtDMX yet.")
                log("         Check SoundSwitch: fixture patched to a "
                    "universe, universe assigned to VirtualLaserNode, active "
                    "show output, or click the 'Test' button.")
            else:
                log("[STATUS] No Art-Net packets received. Check macOS "
                    "firewall, SoundSwitch 'Enable Art-Net', and UDP port "
                    "6454.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Shutting down (KeyboardInterrupt).")
        sys.exit(0)


# ===========================================================================
# README — Virtual Laser Node POC
# ===========================================================================
#
# WHAT THIS IS
#   A standalone proof-of-concept that pretends to be an Art-Net DMX node on
#   the local machine. Its only job at this stage is to PROVE that SoundSwitch
#   can find it (via ArtPoll/ArtPollReply) and/or send it raw ArtDMX channel
#   data. No fixtures are decoded and nothing is rendered yet.
#
# HOW TO RUN
#   $ python3 virtual_laser_node_poc.py            # terminal logging only
#   $ python3 virtual_laser_node_poc.py --web      # + browser inspector
#
#   At startup you should see the banner:
#     - "VirtualLaserNode POC starting"
#     - "Receive sockets bound: ['0.0.0.0', '127.0.0.1', '<LAN IP>'] ..."
#     - "Local detected IP: ..."  /  "Waiting for ArtPoll / ArtDMX"
#     - with --web: "Web inspector: http://127.0.0.1:8137/"
#
#   Then, with SoundSwitch configured (below):
#     - "ArtPoll received ... -> broadcasting ArtPollReply" (discovery), and
#     - "[DMX] U0 fps=.. seq=.. changed=[..]" lines once a show outputs.
#   The [STATUS] line every 5s tells you which state you're in (no packets /
#   discovery-only / ArtDMX flowing).
#
#   Flags: --dump-all, --changes-only, --quiet-poll-replies, --web,
#          --web-port N (inspector default port 8137).
#
#   Open the inspector at http://127.0.0.1:8137/ for a live 512-channel
#   heatmap per universe plus the fixture patch (Laser 1 = ch 1-10,
#   Laser 2 = ch 11-20).
#
# ENABLE ART-NET IN SOUNDSWITCH
#   1. Open SoundSwitch > Preferences/Settings > DMX (or Lighting/Output).
#   2. Enable "Art-Net".
#   3. Enable "Localhost Art-Net Node" (sends Art-Net to 127.0.0.1 / local).
#   4. If a universe/output mapping is shown, make sure at least Universe 0 is
#      assigned to an output. Save/apply.
#   5. SoundSwitch may still say "No device found" until it receives our
#      ArtPollReply — keep this script running; some versions list the node
#      only after the next poll cycle, others stream ArtDMX regardless of
#      whether a node was discovered.
#
# CHECK THE macOS FIREWALL
#   System Settings > Network > Firewall.
#     - If the firewall is ON, click "Options..." and ensure that incoming
#       connections to "Python" (or your python3 binary) are allowed. macOS
#       usually prompts on first bind — click "Allow".
#     - Quick test: temporarily turn the firewall OFF and re-run. If packets
#       suddenly appear, the firewall was blocking inbound UDP.
#
# USE WIRESHARK (or tcpdump) TO CONFIRM TRAFFIC
#   Wireshark capture filter / display filter:
#       udp.port == 6454
#   Command-line equivalent (no Wireshark needed):
#       sudo tcpdump -i any -n udp port 6454
#   If you see packets here but NOT in this script's logs, it's a bind/
#   interface issue. If you see nothing at all, SoundSwitch isn't sending —
#   recheck the SoundSwitch Art-Net settings above.
#
# WHY MULTIPLE SOCKETS (0.0.0.0 + 127.0.0.1 + LAN IP)  *** KEY FINDING ***
#   SoundSwitch and this node both run on the same machine and both bind UDP
#   6454 with SO_REUSEPORT. That creates two different delivery rules:
#     - BROADCAST/multicast (the ArtPoll) is delivered to ALL sockets in the
#       reuse group -> our 0.0.0.0 socket receives discovery fine, and we
#       BROADCAST the ArtPollReply so SoundSwitch's socket receives it too.
#     - UNICAST (the ArtDMX) is delivered to only ONE socket in the group,
#       chosen by a fixed 4-tuple hash. SoundSwitch's "Localhost Art-Net Node"
#       sends ArtDMX as UNICAST to its own addresses (127.0.0.1 AND the LAN IP)
#       over loopback. With only a 0.0.0.0 socket, that hash consistently hands
#       the DMX to SoundSwitch's OWN socket and we receive NOTHING — even though
#       tcpdump clearly shows ~530-byte ArtDMX flowing.
#   Fix: also bind sockets to the SPECIFIC destination IPs (127.0.0.1 and the
#   LAN IP). On BSD/macOS a more-specific bind beats a wildcard bind for that
#   address, so OUR specific socket wins the unicast and receives the DMX.
#   Confirm with:  sudo tcpdump -ni lo0 udp port 6454   (look for length 530).
#
# WHY LOOPBACK IS PREFERRED PER UNIVERSE
#   SoundSwitch sends every universe to BOTH 127.0.0.1 and the LAN IP, so each
#   frame reaches us twice. We pin each universe to a single source IP (and
#   prefer 127.0.0.1, which carries a clean ~30fps stream; the LAN-IP path
#   carries extra duplicate copies). Duplicates from the non-locked source are
#   counted as dups_dropped and discarded. FPS is measured with a 1-second
#   sliding window so bursty arrival doesn't inflate it.
#
# ===========================================================================
