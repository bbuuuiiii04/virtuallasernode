"""
Art-Net node + ArtDMX receiver (build steps 1-2).

Why the multi-socket binding and broadcast reply look unusual: SoundSwitch and
this node run on the same machine and both bind UDP 6454 with SO_REUSEPORT.
Broadcast (ArtPoll / our ArtPollReply) reaches ALL sockets in the reuse group;
unicast (ArtDMX, which SoundSwitch sends to 127.0.0.1 AND the LAN IP) reaches
only ONE, chosen by a 4-tuple hash. So we BROADCAST the reply, and we bind the
SPECIFIC destination IPs (127.0.0.1 + LAN IP) — a more-specific bind beats
SoundSwitch's wildcard, which is the only way we actually receive the DMX.
"""

import select
import socket
import struct
import time
from collections import deque
from dataclasses import dataclass, field

from .util import log

ARTNET_PORT = 6454
ARTNET_ID = b"Art-Net\x00"          # 8-byte magic header, NUL-terminated

# OpCodes are transmitted little-endian on the wire (Art-Net spec).
OP_POLL = 0x2000        # ArtPoll       (controller -> node)
OP_POLL_REPLY = 0x2100  # ArtPollReply  (node -> controller)
OP_DMX = 0x5000         # ArtDmx / OpOutput (controller -> node, channel data)

OPCODE_NAMES = {
    OP_POLL: "ArtPoll (OpPoll)",
    OP_POLL_REPLY: "ArtPollReply",
    OP_DMX: "ArtDmx (OpOutput)",
}

SHORT_NAME = "VirtualLaserNode"
LONG_NAME = "VirtualLaserNode SoundSwitch Local Renderer"
ADVERTISED_UNIVERSES = (0,)   # informational (banner); reply built independently

STATUS_INTERVAL = 5.0       # seconds between operator status lines
DMX_LOG_MIN_INTERVAL = 0.2  # default mode: ~5 DMX log lines/sec/universe
POLL_LOG_INTERVAL = 5.0     # default mode: throttle ArtPoll/reply logging


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
        the last second by definition. Reads only atomic fields.
        """
        n = len(self.recv_times)   # single read — avoid a TOCTOU double-read
        if not n or (time.monotonic() - self.last_ts) > 1.0:
            return 0
        return n

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
        # frame's length intentionally HOLD their last value — correct DMX
        # semantics. SoundSwitch sends full 512-channel frames in practice.
        n = len(channels)
        changed = [i + 1 for i in range(n) if self.buffer[i] != channels[i]]
        self.buffer[0:n] = channels
        self.packet_count += 1
        return changed


def _fmt_changed(changed, limit=12):
    """Compact rendering of a changed-channel list."""
    if not changed:
        return "[none]"
    if len(changed) <= limit:
        return "[" + ",".join(str(c) for c in changed) + "]"
    head = ",".join(str(c) for c in changed[:limit])
    return f"[{head},...(+{len(changed) - limit})]"


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------

def detect_local_ip():
    """IP of the interface that would reach the LAN (no packets sent)."""
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
    """Best-effort /24 directed-broadcast address for the local subnet."""
    parts = local_ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["255"])
    return "255.255.255.255"


def open_socket(bind_ip, broadcast=False):
    """Open a UDP socket on bind_ip:ARTNET_PORT. Returns it, or None on failure."""
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


def build_art_poll_reply(local_ip):
    """
    Build a spec-shaped ArtPollReply (239 bytes) advertising one DMX output
    port on universe 0. The advertised port count does NOT gate whether
    SoundSwitch emits ArtDMX — confirmed empirically.
    """
    pkt = bytearray()
    pkt += ARTNET_ID                                  # ID[8]
    pkt += struct.pack("<H", OP_POLL_REPLY)           # OpCode[2], little-endian
    try:
        pkt += socket.inet_aton(local_ip)             # IP[4]
    except OSError:
        pkt += socket.inet_aton("127.0.0.1")
    pkt += struct.pack("<H", ARTNET_PORT)             # Port[2], little-endian
    pkt += bytes([0x00, 0x01])                        # VersInfo
    pkt += bytes([0x00, 0x00])                        # NetSwitch / SubSwitch
    pkt += bytes([0x00, 0xFF])                        # Oem (generic)
    pkt += bytes([0x00])                              # Ubea
    pkt += bytes([0xC0])                              # Status1
    pkt += struct.pack("<H", 0x0000)                  # EstaMan
    short = SHORT_NAME.encode("ascii", "ignore")[:17]
    pkt += short + b"\x00" * (18 - len(short))        # ShortName[18]
    long_ = LONG_NAME.encode("ascii", "ignore")[:63]
    pkt += long_ + b"\x00" * (64 - len(long_))        # LongName[64]
    report = b"#0001 [0000] VirtualLaserNode OK"[:63]
    pkt += report + b"\x00" * (64 - len(report))      # NodeReport[64]
    pkt += bytes([0x00, 0x01])                        # NumPorts = 1
    pkt += bytes([0x80, 0x00, 0x00, 0x00])            # PortTypes: port0 = DMX out
    pkt += bytes([0x00, 0x00, 0x00, 0x00])            # GoodInput
    pkt += bytes([0x80, 0x00, 0x00, 0x00])            # GoodOutput
    pkt += bytes([0x00, 0x00, 0x00, 0x00])            # SwIn
    pkt += bytes([0x00, 0x00, 0x00, 0x00])            # SwOut: port0 => universe 0
    pkt += bytes([0x00, 0x00, 0x00])                  # SwVideo/Macro/Remote
    pkt += bytes([0x00, 0x00, 0x00])                  # Spare1..3
    pkt += bytes([0x00])                              # Style = StNode
    pkt += bytes([0x00] * 6)                          # MAC
    pkt += socket.inet_aton("0.0.0.0")               # BindIp
    pkt += bytes([0x01])                              # BindIndex
    pkt += bytes([0x08])                              # Status2 (15-bit addr)
    pkt += bytes([0x00] * 26)                         # Filler -> 239 bytes total
    return bytes(pkt)


# ---------------------------------------------------------------------------
# The node
# ---------------------------------------------------------------------------

class ArtNetNode:
    """Owns the sockets, answers discovery, and receives/dedups ArtDMX."""

    def __init__(self, local_ip, bcast_targets, send_sock, recv_socks,
                 dump_all=False, changes_only=False, quiet_poll_replies=False):
        self.local_ip = local_ip
        self.bcast_targets = bcast_targets
        self.send_sock = send_sock
        self.recv_socks = recv_socks            # list of (ip, socket)
        self.all_socks = [s for _ip, s in recv_socks]
        self.reply = build_art_poll_reply(local_ip)
        self.dump_all = dump_all
        self.changes_only = changes_only
        self.quiet_poll_replies = quiet_poll_replies
        self.universes = {}                     # read by the web thread too
        self.poll_count = 0                      # atomic int read by web thread

    def send_reply(self, reason, force_log=False):
        """Broadcast the ArtPollReply (see module docstring for why broadcast)."""
        for bcast in self.bcast_targets:
            try:
                self.send_sock.sendto(self.reply, (bcast, ARTNET_PORT))
            except OSError as e:
                log(f"  Could not broadcast ArtPollReply to {bcast}: {e}")
        if force_log or self.dump_all:
            log(f"  ArtPollReply broadcast to {self.bcast_targets} "
                f"({len(self.reply)} bytes) [{reason}]")

    def parse_artdmx(self, data, src_ip, now):
        """Parse + dedup + log an ArtDmx packet. Returns True if it was valid."""
        if len(data) < 18:
            log(f"  ArtDmx too short ({len(data)} bytes) from {src_ip} — ignored")
            return False

        sequence = data[12]                                     # byte 12
        # bytes 14-15 little-endian; Port-Address is 15-bit, mask the high bit.
        universe = struct.unpack("<H", data[14:16])[0] & 0x7FFF
        length = struct.unpack(">H", data[16:18])[0]            # bytes 16-17, BE

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

        state = self.universes.get(universe)
        if state is None:
            state = UniverseState(universe=universe)
            state.locked_src = src_ip
            self.universes[universe] = state  # insert fully-constructed so a
            #                                   reader never sees locked_src=""
            log(f"[DMX] NEW universe {universe} locked to source {src_ip}")
        elif src_ip != state.locked_src:
            # SoundSwitch sends each universe to multiple local IPs; pin each
            # universe to one source (prefer loopback, which is the clean
            # stream) to avoid double-counting / FPS inflation.
            loop_now = src_ip.startswith("127.")
            loop_locked = state.locked_src.startswith("127.")
            if loop_now and not loop_locked:
                log(f"[DMX] universe {universe} re-locking {state.locked_src} "
                    f"-> {src_ip} (prefer loopback)")
                state.locked_src = src_ip
            elif state.last_ts and (now - state.last_ts) <= 2.0:
                state.dup_count += 1
                return True
            else:
                log(f"[DMX] universe {universe} re-locking {state.locked_src} "
                    f"-> {src_ip} (previous source went stale)")
                state.locked_src = src_ip

        changed = state.update(channels, now)

        # ---- decide whether to log this frame ----
        if self.changes_only and not changed:
            return True
        if not self.dump_all and not self.changes_only:
            if now - state.last_log_ts < DMX_LOG_MIN_INTERVAL:
                return True
        state.last_log_ts = now

        first32 = " ".join(f"{c}" for c in state.buffer[:32])
        log(f"[DMX] U{universe} fps={state.fps:3d} seq={sequence} "
            f"len={length} pkts={state.packet_count} "
            f"changed={_fmt_changed(changed)} src={src_ip}")
        log(f"      first32=[{first32}]")
        return True

    def run(self):
        """The receive loop: dispatch packets and emit periodic status."""
        now0 = time.monotonic()
        last_poll_time = 0.0
        last_dmx_time = 0.0
        last_poll_log = 0.0
        last_status = now0

        while True:
            try:
                ready, _, _ = select.select(self.all_socks, [], [], 0.5)
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
                    if self.dump_all:
                        log(f"Runt packet ({len(data)} bytes) from "
                            f"{src_ip}:{src_port} — not Art-Net")
                    continue
                if data[:8] != ARTNET_ID:
                    if self.dump_all:
                        log(f"Non-Art-Net UDP from {src_ip}:{src_port} "
                            f"(first 8 bytes: {data[:8]!r}) — ignored")
                    continue

                opcode = struct.unpack("<H", data[8:10])[0]  # bytes 8-9, LE

                if opcode == OP_POLL:
                    self.poll_count += 1
                    last_poll_time = now
                    if self.dump_all or (now - last_poll_log >= POLL_LOG_INTERVAL):
                        last_poll_log = now
                        log(f"ArtPoll received from {src_ip} "
                            f"(#{self.poll_count}) -> broadcasting ArtPollReply")
                    self.send_reply(f"answering poll from {src_ip}")

                elif opcode == OP_DMX:
                    # Only mark "DMX flowing" if it was a VALID ArtDmx.
                    if self.parse_artdmx(data, src_ip, now):
                        last_dmx_time = now

                elif opcode == OP_POLL_REPLY:
                    if self.dump_all and not self.quiet_poll_replies:
                        log(f"  (ArtPollReply from {src_ip} — node or echo)")

                else:
                    if self.dump_all:
                        name = OPCODE_NAMES.get(opcode, f"0x{opcode:04X}")
                        log(f"Unhandled opcode 0x{opcode:04X} [{name}] from "
                            f"{src_ip} — ignored")

            # ---- periodic operator status ----
            if now - last_status >= STATUS_INTERVAL:
                last_status = now
                dmx_recent = last_dmx_time > 0 and (now - last_dmx_time) < STATUS_INTERVAL
                poll_recent = last_poll_time > 0 and (now - last_poll_time) < STATUS_INTERVAL

                if dmx_recent or self.universes:
                    log(f"[STATUS] ArtDMX flowing — {len(self.universes)} "
                        f"universe(s), {self.poll_count} polls answered")
                    for u in sorted(self.universes):
                        st = self.universes[u]
                        age = now - st.last_ts if st.last_ts else 0.0
                        log(f"[STATUS]   U{u}: pkts={st.packet_count} "
                            f"fps={st.fps:3d} last={age:4.1f}s ago "
                            f"src={st.locked_src} dups_dropped={st.dup_count}")
                elif poll_recent:
                    log("[STATUS] Discovery active: ArtPoll received, replies "
                        "sent, but NO ArtDMX yet.")
                    log("         Check SoundSwitch: fixture patched to a "
                        "universe, universe assigned to VirtualLaserNode, "
                        "active show output, or click the 'Test' button.")
                else:
                    log("[STATUS] No Art-Net packets received. Check macOS "
                        "firewall, SoundSwitch 'Enable Art-Net', and UDP "
                        "port 6454.")
