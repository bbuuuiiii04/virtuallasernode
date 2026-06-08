Please review a Python package + its browser frontend:
  /Users/bbui/virtuallasernode/
    __init__.py, __main__.py, util.py, artnet.py, fixtures.py, webserver.py
    static/index.html, static/app.js, static/style.css

CONTEXT
"VirtualLaserNode" is a virtual Art-Net (DMX-over-UDP) node that runs on the
SAME machine as SoundSwitch (lighting software). It gets discovered by
SoundSwitch, receives the live ArtDMX it emits, decodes two laser fixtures,
and serves a browser inspector (HTTP + Server-Sent Events). Build steps 1-5 of
6 are done; the step-6 on-screen renderer is NOT built yet.

WHAT CHANGED IN THIS REVIEW SCOPE (review these)
1. Refactor from a single 900-line file into the package above (stdlib only,
   no pip deps). The Art-Net networking logic was moved into an ArtNetNode
   class in artnet.py; the embedded HTML/JS/CSS string was split into static/
   files served from disk by webserver.py.
2. NEW: a 36CH fixture decoder in fixtures.py (decode_fixture / decode_36ch +
   per-channel helpers) that turns raw DMX bytes into a semantic state dict.
   This is the riskiest new logic — verify it against the channel map below.
3. The SSE snapshot now computes decode for each fixture every push (~30Hz)
   and adds a "decoded" key; static/app.js renders a "Decoded fixture state"
   panel from it.

HARD CONSTRAINTS (requirements, not smells)
- Standard library only. SSE over http.server is deliberate (no websockets lib).
- Must coexist with SoundSwitch, which already holds UDP 6454.

INTENTIONAL DESIGN DECISIONS — do NOT flag these; they're from prior live
debugging and are documented in artnet.py:
- Multiple bound sockets (0.0.0.0 + 127.0.0.1 + LAN IP): a more-specific bind
  beats SoundSwitch's wildcard so we win the unicast ArtDMX on a shared
  SO_REUSEPORT port.
- BROADCASTING the ArtPollReply (unicast got misrouted back to our own socket).
- Per-universe source lock preferring 127.0.0.1 (SoundSwitch sends each
  universe to both 127.0.0.1 and the LAN IP; we dedup).
- Advertising one output port / universe 0; fps via a 1s sliding window;
  inspector bound to 127.0.0.1 only.

FIXTURE FACTS
Two identical RGB galvo lasers, BOTH 36CH (Professional) mode at DMX addr 001,
on separate universes: Laser 1 = wire universe 0 ch1-36, Laser 2 = wire
universe 1 ch1-36.

36CH CHANNEL MAP (verify decode_36ch against this):
  CH1 ON/OFF: 0=off, 1-255=dimmer 1-100%
  CH2: 0-26 default auto, 27-127 auto speed, 128-255 sound sensitivity
  CH3 pattern group: static 0-127 (line folders 0-15/16-31/32-47/48-63,
      animation 64-127); dynamic 128-255 (line 128-143/144-159/176-255,
      animation 160-175)
  CH4 pattern select: static = one pattern per 5 values; dynamic = 0-1 play
      all (only when CH3>=128), 2-255 one per 2 values. ALSO: CH4>=1 enables
      the 2nd pattern (CH20-36).
  CH5 pattern size 0-255
  CH6 horizontal position (128=centre, out of bounds = beam blanks)
  CH7 vertical position (128=centre, out of bounds = blanks)
  CH8 colour: 0 white; 1-3 original; 4-31 fixed 7-colour (one per 4 values);
      32-35 colourful change; 36-39 R/G/B change; 40-43 original colourful;
      44-239 flowing water (one per 4 values); 240-255 gradient (uses CH9)
  CH9 colour speed: 0-3 off, 4-127 forward, 128-255 reverse
  CH10 line/dot scan: 0-63 bright line, 64-127 line, 128-255 dot
  CH11 strobe: 1-255 speed (0 off)
  CH12 rotation Z / CH13 X / CH14 Y: 1-127 angle, 128-255 speed
  CH15 horizontal move / CH16 vertical move: 1-127 position, 128-255 speed
  CH17 zoom: 1-127 size, 128-255 speed
  CH18 gradient 1-255
  CH19 X-wave 1-127 / Y-wave 128-255
  CH20-36 = second pattern (group, pattern, size, H/V pos, colour, colour
      speed, scan, strobe, rot Z/X/Y, H/V move, zoom, gradient, X/Y wave),
      same value semantics as the first pattern.

PLEASE FOCUS ON
1. Decoder correctness vs the map above: angle/speed and position/speed splits,
   the colour sub-ranges + 7-colour palette index math, pattern group/folder
   boundaries, the CH4>=1 second-pattern gate, off-by-one and edge values
   (0, 1, 127, 128, 255). Flag any boundary that's wrong or ambiguous.
2. Refactor parity: did any behaviour get dropped/changed vs a faithful port?
   (poll throttling, dedup/source-lock, status logging, ArtPollReply bytes.)
3. Thread-safety: the UDP receiver thread mutates ArtNetNode.universes /
   UniverseState while SSE handler threads read them AND run the decoder over a
   copied 512-list each push. Any race, torn read, or dict-changed-size risk?
   Is computing decode for every fixture at 30Hz per client a concern?
4. webserver.py static file serving: path-traversal safety, content types,
   the SSE BoundedSemaphore(16) cap / 503 path, exception handling.
5. static/app.js: correctness of renderDecoded + the canvas heatmap, any DOM
   or escaping issue (fixture names use textContent; decoded values come only
   from our own decoder).
6. Package hygiene: imports, __main__ wiring, anything that won't run as
   `python3 -m virtuallasernode`.

OUTPUT
- Group findings by severity (High / Medium / Low) with file:line and a
  concrete fix for each.
- Call out any decoder value-range that contradicts the channel map.
- It's fine to confirm the intentional decisions above are sound rather than
  re-litigating them.
