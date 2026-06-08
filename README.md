# VirtualLaserNode

Render SoundSwitch's DMX laser output on screen — **no Enttec hardware, no
physical lasers**. A virtual Art-Net node that SoundSwitch discovers, receives
the live ArtDMX it emits, decodes the laser fixtures, and (soon) draws them in
the browser.

```
Rekordbox -> rb_ss_bridge_v2 -> SoundSwitch -> Localhost Art-Net
          -> VirtualLaserNode -> rendered lasers on screen
```

Stdlib only — **no pip dependencies**. Does not touch `rb_ss_bridge_v2`.

## Run
From the **parent** directory (`/Users/bbui`), like the bridge:
```bash
python3 -m virtuallasernode --web      # node + browser inspector
python3 -m virtuallasernode            # terminal logging only
```
Then open **http://127.0.0.1:8137/**. Logs: `/tmp/vln.log` when backgrounded.

Flags: `--web`, `--web-port N` (default 8137), `--dump-all`, `--changes-only`,
`--quiet-poll-replies`, `--bind-ip IP` (repeatable, multi-homed machines).

**Restart safety:** kill with `pkill -f virtuallasernode` (NOT
`pkill -f "python3 -m…"` — argv0 is the full python path). Confirm exactly one
instance: `pgrep -f 'virtuallasernode --web' | wc -l` → `1`. A stale instance
holds port 8137 and serves old code.

## Layout
```
virtuallasernode/
├── __main__.py     CLI + wiring        (run: python3 -m virtuallasernode)
├── artnet.py       Art-Net node, UDP receiver, UniverseState, ArtPollReply
├── fixtures.py     fixture patch + 36CH decoder (decode_fixture)
├── webserver.py    HTTP + SSE inspector server
├── util.py         logging helper
├── static/         browser inspector (index.html / app.js / style.css)
└── docs/
    ├── PLANNING.md            north-star + build order + renderer plan
    ├── FIXTURE_36CH.md        the laser's 36CH DMX channel map
    ├── CODEX_REVIEW.md        review prompt (Codex + sub-agent reviews)
    └── reference/virtual_laser_node_poc.py   frozen single-file POC
```

## Status (build order — see docs/PLANNING.md)
- ✅ 1 node detection · ✅ 2 ArtDMX receive · ✅ 3 channel inspector
- ✅ 4 fixture patch slicing · ✅ 5 fixture decoding
- ⬜ **6 2D renderer ← next** · ⬜ 7 bridge overlay · ⬜ 8 3D

Steps 1–5 are live-validated and have been through a 3-way review (Codex + two
sub-agents).

## Key finding (why the sockets look unusual)
SoundSwitch and this node share UDP 6454 on one machine via `SO_REUSEPORT`.
Broadcast (ArtPoll / our ArtPollReply) reaches all sockets; **unicast (ArtDMX)
reaches only one**, chosen by hash. So we **broadcast** the reply and **bind the
specific destination IPs** (127.0.0.1 + LAN IP) — a more-specific bind beats
SoundSwitch's wildcard, which is the only way we receive the DMX. Each universe
is pinned to one source (loopback preferred) to dedup SoundSwitch's multi-IP
copies. See `artnet.py` for the full notes.
