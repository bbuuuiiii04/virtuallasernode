"""
Fixture patch + 36CH profile decoding (build steps 4-5).

FIXTURES describes how the physical lasers are patched in SoundSwitch: two
identical RGB galvo lasers, both 36CH (Professional) mode at DMX address 001,
on the same universe ("Universe 1").

decode_fixture() turns the raw DMX channel bytes into a readable per-fixture
state object — the data contract the renderer (step 6) consumes, so it never
has to touch raw DMX. Channel meanings are encoded from the fixture manual
(36CH / PRO mode). Values are 0-255; channels are 1-based DMX addresses.
"""

# Both physical lasers are patched on the SAME universe + DMX address (001),
# as they connect to the same DMX Enttec Pro on Universe 1 (Art-Net 0).
FIXTURES = [
    {"name": "Laser 1", "universe": 0, "start": 1, "count": 36, "mode": "36ch"},
    {"name": "Laser 2", "universe": 0, "start": 1, "count": 36, "mode": "36ch"},
]

# Calibration loader works both as a package import and as a top-level module
# (the calib/ render harnesses add the package root to sys.path and `import
# fixtures` directly, so a relative import alone would fail there).
try:
    from .calibration import get as _cal_get
except ImportError:  # imported as top-level module (calib harnesses)
    from calibration import get as _cal_get

# RGB laser fixed-colour palette (CH8 / CH25 values 4-31, one per 4 values).
# Order CALIBRATED 2026-06-05 against the real lasers (camera sweep CH8=4..31,
# white-balanced to the CH8=0 white reference): W, R, Y, G, C, B, M.
# (The earlier R,G,B,Y,C,M,W was a guess and was wrong — caused the colour
# mismatch.) idx = (CH8-4)//4 maps each 4-value band to one entry.
# Values live in calibration.json (single source of truth); the literals below
# are the fallback when that file is absent — identical to the calibrated order.
SEVEN_COLORS = [tuple(c) for c in _cal_get("color", "sevenColors", [
    [255, 255, 255],  # band 4-7    white
    [255, 0, 0],      # band 8-11   red
    [255, 255, 0],    # band 12-15  yellow
    [0, 255, 0],      # band 16-19  green
    [0, 255, 255],    # band 20-23  cyan
    [0, 0, 255],      # band 24-27  blue
    [255, 0, 255],    # band 28-31  magenta
])]
SEVEN_COLOR_NAMES = _cal_get("color", "sevenColorNames",
    ["white", "red", "yellow", "green", "cyan", "blue", "magenta"])

# Position blank window (CH6/7, CH23/24) — the fixture closes the light outside
# this band. Calibrated thresholds in calibration.json; 50/254 = fallback.
_BLANK_LO = _cal_get("position", "blankLow", 50)
_BLANK_HI = _cal_get("position", "blankHigh", 254)


# ---------------------------------------------------------------------------
# Small per-channel decoders
# ---------------------------------------------------------------------------

def _angle_or_speed(v):
    """Rotation channels (CH12-14): 0 off, 1-127 angle, 128-255 speed."""
    if v == 0:
        return {"mode": "off", "val": 0}
    if v <= 127:
        return {"mode": "angle", "val": v}
    return {"mode": "speed", "val": v - 127}


def _pos_or_speed(v):
    """Movement channels (CH15-16): 0 off, 1-127 position, 128-255 speed."""
    if v == 0:
        return {"mode": "off", "val": 0}
    if v <= 127:
        return {"mode": "position", "val": v}
    return {"mode": "speed", "val": v - 127}


def _zoom(v):
    """Zoom (CH17): 0 off, 1-127 size, 128-255 speed."""
    if v == 0:
        return {"mode": "off", "val": 0}
    if v <= 127:
        return {"mode": "size", "val": v}
    return {"mode": "speed", "val": v - 127}


def _wave(v):
    """Wave (CH19/36): 0 off, 1-127 X-wave speed, 128-255 Y-wave speed."""
    if v == 0:
        return {"axis": "off", "speed": 0}
    if v <= 127:
        return {"axis": "x", "speed": v}
    return {"axis": "y", "speed": v - 127}


def _scan(v):
    """Pattern line/dot scan (CH10/27)."""
    if v <= 63:
        return {"mode": "line-bright", "speed": v}
    if v <= 127:
        return {"mode": "line", "speed": v - 64}
    return {"mode": "dot", "speed": v - 128}


def _strobe(v):
    """Strobe (CH11/28): 0 off, 1-255 strobe speed."""
    return {"on": v >= 1, "speed": v}


def _color(c, speed):
    """
    Colour (CH8/25) + colour speed (CH9/26). Returns a representative rgb for
    solid/fixed colours, or rgb=None + animated=True for effect modes (the
    renderer animates those at the given speed).
    """
    if speed <= 3:
        sp = "off"
    elif speed <= 127:
        sp = "forward"
    else:
        sp = "reverse"

    if c == 0:
        return {"mode": "white", "rgb": [255, 255, 255], "label": "white",
                "speed": sp, "animated": False, "raw": c}
    if c <= 3:
        # "Original colour" = the pattern's native colour, not white. CALIBRATED
        # 2026-06-05: rendered RED on the real lasers (pattern-dependent, but red
        # is the observed/common native). Was wrongly mapped to white.
        return {"mode": "original", "rgb": [255, 0, 0],
                "label": "original colour", "speed": sp, "animated": False,
                "raw": c}
    if c <= 31:
        idx = (c - 4) // 4 % 7
        return {"mode": "fixed7", "rgb": list(SEVEN_COLORS[idx]),
                "label": SEVEN_COLOR_NAMES[idx], "speed": sp,
                "animated": False, "raw": c}
    if c <= 35:
        return {"mode": "colorful", "rgb": None, "label": "colourful change",
                "speed": sp, "animated": True, "raw": c}
    if c <= 39:
        return {"mode": "rgb_change", "rgb": None, "label": "R/G/B change",
                "speed": sp, "animated": True, "raw": c}
    if c <= 43:
        return {"mode": "original_colorful", "rgb": None,
                "label": "original colourful change", "speed": sp,
                "animated": True, "raw": c}
    if c <= 239:
        idx = (c - 44) // 4
        return {"mode": "flowing", "rgb": None,
                "label": f"flowing water #{idx}", "speed": sp,
                "animated": True, "raw": c}
    return {"mode": "gradient", "rgb": None, "label": "gradient", "speed": sp,
            "animated": True, "raw": c}


def _position(h, v):
    """
    Coarse H/V position (CH6/7, CH23/24): 128 = centre. Normalised to -1..+1.
    The manual notes static patterns need ~centre to be visible and the beam
    blanks ("closed light") out of bounds — flag the near-extremes case.
    """
    def norm(x):
        # 128 = centre. Asymmetric divisor (128 steps below, 127 above) keeps
        # the result in a clean [-1, 1] instead of underflowing to -1.008.
        return round((x - 128) / (128 if x < 128 else 127), 3)

    return {
        "h": h, "v": v,
        "x": norm(h), "y": norm(v),
        "centered": abs(h - 128) <= 2 and abs(v - 128) <= 2,
        # CALIBRATED 2026-06-05: the usable window is ~[55, 254] — the real
        # fixture "closes the light" below ~50 (CH6/7=0/3/40 are dark, 64 shows),
        # much wider than the old [2, 253] guess on the low end. Thresholds live
        # in calibration.json (position.blankLow/blankHigh); 50/254 = fallback.
        "blanked": (h <= _BLANK_LO or h >= _BLANK_HI
                    or v <= _BLANK_LO or v >= _BLANK_HI),
    }


def _auto_sound(v):
    """CH2: 0-26 default auto, 27-127 auto speed, 128-255 sound sensitivity.

    CALIBRATED 2026-06-05: sound mode (128-254) GATES output on audio — a silent
    room goes dark; it pulses with music. `sound_gated` flags that for consumers.
    """
    if v <= 26:
        return {"mode": "auto", "detail": "default auto speed", "sound_gated": False}
    if v <= 127:
        return {"mode": "auto", "detail": f"auto speed {v - 26}", "sound_gated": False}
    return {"mode": "sound", "detail": f"sound sensitivity {v - 127}",
            "sound_gated": True}


def _pattern_group(ch3):
    """CH3: static (0-127) vs dynamic (128-255) pattern groups + folder."""
    if ch3 <= 127:
        folder = f"line set {ch3 // 16 + 1}" if ch3 <= 63 else "animation"
        return {"kind": "static", "group": ch3, "folder": folder}
    if ch3 <= 143:
        folder = "line set 1"
    elif ch3 <= 159:
        folder = "line set 2"
    elif ch3 <= 175:
        folder = "animation"
    else:
        folder = "line set 3"
    return {"kind": "dynamic", "group": ch3, "folder": folder}


def _pattern_select(ch4, kind):
    """CH4: static = pattern every 5 values; dynamic = play-all (0-1) or every 2."""
    if kind == "static":
        return {"raw": ch4, "index": ch4 // 5, "play_all": False}
    if ch4 <= 1:
        return {"raw": ch4, "index": None, "play_all": True}
    # Dynamic selectable range is 2-255 ("one per 2 values") -> 0-based index.
    return {"raw": ch4, "index": (ch4 - 2) // 2, "play_all": False}


# ---------------------------------------------------------------------------
# Full-fixture decode
# ---------------------------------------------------------------------------

def _decode_second_pattern(ch):
    """
    Second pattern block CH20-36. Per the manual this block is STATIC-ONLY:
    CH20 is a static pattern group and CH21 selects a pattern every 5 values
    (there is no dynamic group/select here, unlike CH3/CH4). Shaped like the
    first pattern's `pattern` dict for renderer parity.
    """
    g = ch(20)
    folder = ("animation" if 64 <= g <= 127
              else f"line set {g // 16 + 1}" if g <= 63 else "extended")
    return {
        "kind": "static",
        "group": g,
        "folder": folder,
        "selection": {"raw": ch(21), "index": ch(21) // 5, "play_all": False},
        "size": ch(22),
        "position": _position(ch(23), ch(24)),
        "color": _color(ch(25), ch(26)),
        "scan": _scan(ch(27)),
        "strobe": _strobe(ch(28)),
        "rotation": {"z": _angle_or_speed(ch(29)),
                     "x": _angle_or_speed(ch(30)),
                     "y": _angle_or_speed(ch(31))},
        "movement": {"h": _pos_or_speed(ch(32)), "v": _pos_or_speed(ch(33))},
        "zoom": _zoom(ch(34)),
        "gradient": ch(35),
        "waves": _wave(ch(36)),
    }


def decode_36ch(ch):
    """Decode a 36CH fixture given ch(n) -> value for 1-based channel n."""
    # CH1 is a BINARY on/off gate, NOT a master dimmer: CH1=0 is off, any
    # CH1>0 is fully ON. Confirmed by the fixture model + measurement docs
    # (docs/FIXTURE_MODEL_READINESS_AND_KNOWLEDGE.md "CH1: binary on/off ...
    # Do not use CH1 as a dimmer"). Treating it as a 0-255 dimmer crushed
    # low-CH1 cues to faint output and washed out their measured colours.
    ch1 = ch(1)
    power = ch1 > 0
    group = _pattern_group(ch(3))
    state = {
        "power": power,
        "dimmer": 1.0 if power else 0.0,
        "control": _auto_sound(ch(2)),
        "pattern": {**group,
                    "selection": _pattern_select(ch(4), group["kind"]),
                    "size": ch(5)},
        "position": _position(ch(6), ch(7)),
        "color": _color(ch(8), ch(9)),
        "scan": _scan(ch(10)),
        "strobe": _strobe(ch(11)),
        "rotation": {"z": _angle_or_speed(ch(12)),
                     "x": _angle_or_speed(ch(13)),
                     "y": _angle_or_speed(ch(14))},
        "movement": {"h": _pos_or_speed(ch(15)), "v": _pos_or_speed(ch(16))},
        "zoom": _zoom(ch(17)),
        "gradient": ch(18),
        "waves": _wave(ch(19)),
        # Per the manual the second pattern operates only when CH4 >= 1; we
        # also require some real CH20-36 data, so second_pattern != None means
        # "there is actually a visible second pattern" (a clean renderer
        # contract), not just "CH4 happened to be >= 1".
        "second_pattern": (_decode_second_pattern(ch)
                           if ch(4) >= 1 and any(ch(n) for n in range(20, 37))
                           else None),
    }
    return state


def decode_fixture(values, fixture):
    """
    Decode one fixture from a 512-channel list (for its universe).

    Returns {name, universe, ...semantic state}. Channels outside the buffer
    read as 0, so a partially-patched or empty universe decodes cleanly.
    """
    base = fixture["start"] - 1

    def ch(n):
        idx = base + (n - 1)
        return values[idx] if 0 <= idx < len(values) else 0

    if fixture.get("mode") == "36ch":
        data = decode_36ch(ch)
    else:
        data = {}  # 16CH profile can be added here later
    return {"name": fixture["name"], "universe": fixture["universe"], **data}
