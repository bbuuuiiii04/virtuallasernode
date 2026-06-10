"""PR-G1 v6: per-channel laser probability maps inside fixture crop."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


@dataclass
class LaserMaps:
    w: int
    h: int
    combined_laser_score: list[list[float]]
    red_score: list[list[float]]
    green_score: list[list[float]]
    blue_score: list[list[float]]
    cyan_score: list[list[float]]
    magenta_score: list[list[float]]
    yellow_score: list[list[float]]
    white_score: list[list[float]]
    med: float
    mad: float
    values: list[float]

    @property
    def color_maps(self) -> dict[str, list[list[float]]]:
        return {
            "red": self.red_score,
            "green": self.green_score,
            "blue": self.blue_score,
            "cyan": self.cyan_score,
            "magenta": self.magenta_score,
            "yellow": self.yellow_score,
            "white": self.white_score,
        }


def _luma(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _channel_scores(r: int, g: int, b: int) -> dict[str, float]:
    mx = float(max(r, g, b))
    mn = float(min(r, g, b))
    sat = mx - mn
    lum = _luma(r, g, b)

    red = max(0.0, r - max(g, b) * 0.55) + 0.25 * sat if r >= g and r >= b else 0.0
    green = max(0.0, g - max(r, b) * 0.55) + 0.2 * sat if g >= r * 0.85 and g >= b * 0.85 else 0.0
    blue = max(0.0, b - max(r, g) * 0.5) + 0.3 * sat if b >= r * 0.8 else 0.0
    cyan = max(0.0, (g + b) * 0.5 - r * 0.45) if g >= r * 0.9 and b >= r * 0.9 else 0.0
    magenta = max(0.0, (r + b) * 0.5 - g * 0.5) if r >= g * 1.05 and b >= g * 1.05 else 0.0
    yellow = max(0.0, (r + g) * 0.5 - b * 0.55) if r >= b * 1.1 and g >= b * 1.1 else 0.0
    white = min(mx, lum + 0.35 * sat) if sat < 45 and mx > 120 else 0.0

    combined_candidates = [
        mx + 0.72 * sat,
        red,
        green,
        blue,
        cyan,
        magenta,
        yellow,
        white,
        lum + 0.5 * sat,
    ]
    if b >= r * 0.85 and b >= g * 0.75:
        combined_candidates.append(b + 0.58 * max(0.0, b - min(r, g)) + 0.22 * g)
    if r >= g * 1.05 and b >= g * 0.9:
        combined_candidates.append((r + b) * 0.52 + 0.42 * sat)

    return {
        "combined": max(combined_candidates),
        "red": red,
        "green": green,
        "blue": blue,
        "cyan": cyan,
        "magenta": magenta,
        "yellow": yellow,
        "white": white,
    }


def build_laser_maps(pixels: Any, w: int, h: int) -> LaserMaps:
    combined = [[0.0] * w for _ in range(h)]
    red = [[0.0] * w for _ in range(h)]
    green = [[0.0] * w for _ in range(h)]
    blue = [[0.0] * w for _ in range(h)]
    cyan = [[0.0] * w for _ in range(h)]
    magenta = [[0.0] * w for _ in range(h)]
    yellow = [[0.0] * w for _ in range(h)]
    white = [[0.0] * w for _ in range(h)]
    values: list[float] = []

    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            scores = _channel_scores(r, g, b)
            combined[y][x] = scores["combined"]
            red[y][x] = scores["red"]
            green[y][x] = scores["green"]
            blue[y][x] = scores["blue"]
            cyan[y][x] = scores["cyan"]
            magenta[y][x] = scores["magenta"]
            yellow[y][x] = scores["yellow"]
            white[y][x] = scores["white"]
            values.append(scores["combined"])

    med = statistics.median(values) if values else 0.0
    mad = statistics.median([abs(v - med) for v in values]) if values else 1.0
    if mad <= 0:
        mad = 1.0

    return LaserMaps(
        w=w,
        h=h,
        combined_laser_score=combined,
        red_score=red,
        green_score=green,
        blue_score=blue,
        cyan_score=cyan,
        magenta_score=magenta,
        yellow_score=yellow,
        white_score=white,
        med=med,
        mad=mad,
        values=values,
    )
