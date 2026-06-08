# Calibration — agent-driven visual mapping of EVERY channel

Goal: replace every guessed channel→behaviour mapping with ground truth observed
from the real lasers. The agent drives DMX directly (Enttec Open), a camera
watches, the agent views each frame and records what the fixture actually does,
then bakes it into `fixtures.py` (decode) and `static/renderer.js` (visual map).

## Rig (one-time)
- **DMX out:** Enttec DMX USB **Open** plugged in. Find its port: `ls /dev/cu.usbserial-*`.
- **SoundSwitch CLOSED** (it can't share the DMX interface while we drive it).
- **Lasers** powered, aimed at a **white wall/surface** (colour/pattern phases) and
  with **haze + dark** available (motion/beam phases).
- **Camera** pointed at the output. Default ffmpeg device `0` = FaceTime HD;
  device `1` = OBS Virtual Cam (use to feed a phone for a better angle).
- **SAFETY:** never aim a beam straight into the camera lens at close range
  (can kill the sensor) or at anyone's eyes. Point at a surface.

## Driver
```
# 1. start the blast loop in the background (keeps the fixture refreshed):
calib/.venv/bin/python calib/dmx_open.py daemon --port /dev/cu.usbserial-XXXX
# 2. set the neutral base, then sweep one channel at a time:
python calib/dmx_open.py base
python calib/dmx_open.py set 8=12
# 3. capture + the agent reads the PNG:
python calib/grab.py --out /tmp/calib/ch8_12.png
```

## Sweep protocol (what the agent runs)
Each row: hold the value(s) ~2s, grab, observe, record. Always return to `base`
between channels so only ONE variable changes.

### Phase A — Brightness & colour  (surface, low/no haze)
| Ch | Values to hold | Recording |
|----|----------------|-----------|
| CH1 dimmer | 0, 64, 128, 255 | brightness curve (linear? gamma?) |
| CH8 colour | 0, 1, 4, 8, 12, 16, 20, 24, 28 | white / "original" + the **7 fixed-colour ORDER** |
| CH8 effects | 32, 36, 40, 100, 250 (+CH9=64) | what each animated mode looks like |
| CH9 speed | CH8=100 then CH9 = 0, 64, 200 | speed + direction of colour animation |

### Phase B — Pattern shapes  (surface) — also feeds the renderer pattern library
| Ch | Values | Recording |
|----|--------|-----------|
| CH3 static + CH4 | CH3=0, CH4 = 0,10,…,255 | capture each static figure |
| CH3 anim + CH4 | CH3=64, CH4 sweep | animation figures |
| CH3 dynamic + CH4 | CH3=128, CH4 sweep | dynamic effects |
| CH5 size | 30, 128, 220 | size large→small direction |
| CH10 scan | 30, 100, 200 | bright-line / line / dot look |

### Phase C — Motion & geometry  (HAZE + dark, beams in air)
| Ch | Values | Recording |
|----|--------|-----------|
| CH6 H pos | 64, 128, 192 | which screen direction; where it blanks |
| CH7 V pos | 64, 128, 192 | vertical direction; blank bounds |
| CH12 rot Z | 30, 60, 90 (angle); 180, 255 (speed) | **which screen axis** + CW/CCW |
| CH13 rot X | same | which axis it really tilts |
| CH14 rot Y | same | which axis it really swings |
| CH15 H move | 40, 127 (pos); 200 (speed) | direction + range |
| CH16 V move | 40, 127 (pos); 200 (speed) | direction + range |
| CH17 zoom | 30, 127 (size); 200 (speed) | in/out direction |
| CH18 gradient | 80, 200 | what "gradient" does to colour |
| CH19 waves | 60 (X), 200 (Y) | wave axis + feel |

### Phase D — Second pattern  CH20–36
Set `CH4>=1` to enable, then spot-check CH20/21 (group/select), CH25 colour,
CH29–31 rotation, CH32/33 movement mirror Phase A–C semantics.

## Output
Findings go to `docs/CALIBRATION_RESULTS.md` (per-channel, with the frame paths),
then get applied to `fixtures.py` + `renderer.js` and verified by re-rendering the
VLN against the captured frames.
