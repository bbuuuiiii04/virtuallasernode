# VirtualLaserNode — Planning / North Star

> Text of the planning blueprint. Original PDF lives at
> `~/Downloads/VirtualLaserNode Planning Document.pdf` (macOS blocks copying it
> out of Downloads from the terminal).

**Project:** Virtual DMX Laser Visualizer for rb_ss_bridge_v2 + SoundSwitch
**Primary goal:** Render actual SoundSwitch DMX laser output on the laptop
screen without requiring Enttec Open DMX hardware or physical laser fixtures.

## Core runtime flow
```
Rekordbox -> rb_ss_bridge_v2 -> SoundSwitch -> Localhost Art-Net
          -> VirtualLaserNode -> rendered laser fixtures on laptop screen
```

## MVP done means
- SoundSwitch detects VirtualLaserNode as an Art-Net node.
- VirtualLaserNode receives live ArtDMX packets.
- Universe 0 raw channel values update in the browser.
- Two 10-channel laser fixtures are patched. *(Correction: the real fixtures
  are 36CH, both at addr 001 on separate universes — see FIXTURE_36CH.md.)*
- Fixture channel values decode into readable state.
- A 2D renderer displays color, brightness, strobe, and movement.
- No Enttec hardware / no physical lasers required.
- rb_ss_bridge_v2 remains untouched (optional overlay only).

## Build order  (✅ = done)
1. ✅ Art-Net node detection
2. ✅ ArtDMX raw receive
3. ✅ raw channel inspector
4. ✅ fixture patch slicing
5. ✅ fixture profile decoding
6. ⬜ 2D renderer            ← NEXT
7. ⬜ optional bridge overlay
8. ⬜ 3D renderer

## Renderer plan (step 6) — agreed approach
A galvo laser *is* a vector display, so render as vector polylines on an HTML5
canvas with additive blending + glow. Render at 60fps interpolating the ~37fps
DMX stream (so smoothness is decoupled from the DMX rate). Stages:
- **v0**: each laser = colored glyph + brightness + strobe + position.
- **v1 (MVP target)**: representative pattern library (~16–24 laser-typical
  vector shapes) keyed to decoded pattern IDs; full color/rotation/movement/
  zoom/strobe; additive glow.
- **v2**: flowing-water color gradients, pseudo-3D rotation, 2nd-pattern layer.
- **v3 (optional)**: capture the *real* patterns by photographing each value.

The hard/open-ended part is only the exact pattern *shapes* (the manufacturer
doesn't publish them); everything else (color/brightness/strobe/movement) is
fully determined by the decoder and is squarely achievable.
