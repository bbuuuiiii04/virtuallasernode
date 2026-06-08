# Fixture: RGB Galvo Laser — 36CH (Professional) mode

Two identical units. Galvo scanning 15kpps/±25°, RGB (R 660nm / G 532nm /
B 450nm). Supports 16CH (Standard) and 36CH (Professional) DMX modes.

**Patch (as used here):** both fixtures in **36CH mode**, both at **DMX address
001**, on separate universes:
- **Laser 1 → wire universe 0**, ch 1–36
- **Laser 2 → wire universe 1**, ch 1–36

This is what `fixtures.py` encodes (`decode_36ch`). Values are 0–255.

## 36CH channel map (first pattern = CH1–19)
| CH | Function | Values |
|----|----------|--------|
| 1  | ON/OFF (dimmer) | 0=off, 1–255 = 1–100% |
| 2  | Auto/Sound | 0–26 default auto, 27–127 auto speed, 128–255 sound sensitivity |
| 3  | Pattern group | static 0–127 (line folders 0-15/16-31/32-47/48-63, animation 64-127); dynamic 128–255 (line 128-143/144-159/176-255, animation 160-175) |
| 4  | Pattern select | static: 1 per 5 values. dynamic: 0–1 play-all (CH3≥128 only), 2–255 one per 2. **CH4≥1 also enables the 2nd pattern.** |
| 5  | Pattern size | 0–255 |
| 6  | Horizontal position | 128 = centre, out of bounds → beam blanks |
| 7  | Vertical position | 128 = centre, out of bounds → blanks |
| 8  | Colour | 0 white; 1–3 original; 4–31 fixed 7-colour (1 per 4); 32–35 colourful; 36–39 R/G/B change; 40–43 original colourful; 44–239 flowing water (1 per 4); 240–255 gradient (uses CH9) |
| 9  | Colour speed | 0–3 off, 4–127 forward, 128–255 reverse |
| 10 | Line/Dot scan | 0–63 bright line, 64–127 line, 128–255 dot |
| 11 | Strobe | 1–255 speed (0 off) |
| 12 | Rotation Z | 1–127 angle, 128–255 speed |
| 13 | Rotation X | 1–127 angle, 128–255 speed |
| 14 | Rotation Y | 1–127 angle, 128–255 speed |
| 15 | Horizontal movement | 1–127 position, 128–255 speed |
| 16 | Vertical movement | 1–127 position, 128–255 speed |
| 17 | Zoom | 1–127 size, 128–255 speed |
| 18 | Gradient | 1–255 speed |
| 19 | X/Y Wave | 1–127 X-wave, 128–255 Y-wave |

## Second pattern = CH20–36  (STATIC-ONLY; active only when CH4≥1)
CH20 static pattern group (no dynamic), CH21 pattern (1 per 5 values), CH22
size, CH23/24 H/V position, CH25 colour, CH26 colour speed, CH27 line/dot scan,
CH28 strobe, CH29–31 rotation Z/X/Y, CH32/33 H/V movement, CH34 zoom,
CH35 gradient, CH36 X/Y wave. Same value semantics as the first pattern, except
CH20/CH21 are static-only (do NOT apply CH3/CH4 dynamic rules here).

## 16CH (Standard) mode — for reference (not used)
CH1 ON/OFF, CH2 auto/sound, CH3 group, CH4 select, CH5 colour, CH6 colour
speed, CH7 line/dot, CH8 size, CH9–11 rot Z/X/Y, CH12/13 H/V move, CH14 zoom,
CH15 gradient, CH16 X/Y wave. **Note: 16CH has no strobe and no absolute
position** — those exist only in 36CH (CH11 strobe, CH6/7 position).
