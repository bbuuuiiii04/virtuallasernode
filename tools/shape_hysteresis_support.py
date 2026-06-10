"""PR-G1 v6: hysteresis laser support masks."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from tools.shape_extraction import DEFAULT_MIN_CORE_AREA_PX, _connected_components, _percentile
from tools.shape_laser_maps import LaserMaps


@dataclass
class SupportMasks:
    high_core_mask: list[list[bool]]
    low_support_mask: list[list[bool]]
    support_mask: list[list[bool]]
    support_components: list[list[tuple[int, int]]]
    high_core_pixels: list[tuple[int, int]]
    support_pixels: list[tuple[int, int]]


def _mask_from_map(score_map: list[list[float]], thr: float) -> list[list[bool]]:
    h = len(score_map)
    w = len(score_map[0]) if h else 0
    return [[score_map[y][x] >= thr for x in range(w)] for y in range(h)]


def _hysteresis_flood(
    high_mask: list[list[bool]],
    low_mask: list[list[bool]],
) -> list[list[bool]]:
    h = len(high_mask)
    w = len(high_mask[0]) if h else 0
    out = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()
    for y in range(h):
        for x in range(w):
            if high_mask[y][x]:
                out[y][x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and low_mask[ny][nx] and not out[ny][nx]:
                out[ny][nx] = True
                q.append((nx, ny))
    return out


def _erode_mask(mask: list[list[bool]], iterations: int = 1) -> list[list[bool]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    cur = mask
    for _ in range(max(0, iterations)):
        nxt = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if not cur[y][x]:
                    continue
                if all(
                    0 <= y + dy < h and 0 <= x + dx < w and cur[y + dy][x + dx]
                    for dy, dx in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
                ):
                    nxt[y][x] = True
        cur = nxt
    return cur


def _morph_close(mask: list[list[bool]], low_mask: list[list[bool]], *, radius: int = 2) -> list[list[bool]]:
    cur = mask
    for _ in range(max(0, radius)):
        cur = _dilate_mask_once(cur)
    cur = [[cur[y][x] and low_mask[y][x] for x in range(len(mask[0]))] for y in range(len(mask))]
    for _ in range(max(0, radius)):
        cur = _erode_mask(cur, 1)
    return cur


def _dilate_mask_once(mask: list[list[bool]]) -> list[list[bool]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    out = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                out[y][x] = True
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny][nx]:
                        out[y][x] = True
                        break
                if out[y][x]:
                    break
    return out


def merge_per_color_support(
    maps: LaserMaps,
    support_mask: list[list[bool]],
    *,
    bridge_radius: int = 4,
) -> list[list[bool]]:
    """Union per-hue support components into hysteresis support."""
    h, w = maps.h, maps.w
    merged = [row[:] for row in support_mask]
    bridged = support_mask
    for _ in range(max(0, bridge_radius)):
        bridged = _dilate_mask_once(bridged)

    for _name, cmap in maps.color_maps.items():
        vals = [cmap[y][x] for y in range(h) for x in range(w) if cmap[y][x] > maps.med + 0.8 * maps.mad]
        if not vals:
            continue
        thr = max(maps.med + 1.2 * maps.mad, _percentile(vals, 72.0))
        color_mask = _mask_from_map(cmap, thr)
        for y in range(h):
            for x in range(w):
                if color_mask[y][x] and bridged[y][x]:
                    merged[y][x] = True

    low = _mask_from_map(maps.combined_laser_score, maps.med + 1.4 * maps.mad)
    return _hysteresis_flood(merged, low)


def build_hysteresis_support(
    maps: LaserMaps,
    *,
    min_area_px: int = DEFAULT_MIN_CORE_AREA_PX,
) -> SupportMasks:
    high_thr = max(maps.med + 4.2 * maps.mad, _percentile(maps.values, 90.0))
    low_thr = max(maps.med + 1.2 * maps.mad, _percentile(maps.values, 58.0))

    high_core = _mask_from_map(maps.combined_laser_score, high_thr)
    low_support = _mask_from_map(maps.combined_laser_score, low_thr)
    support = _hysteresis_flood(high_core, low_support)
    support = merge_per_color_support(maps, support)
    for _ in range(3):
        dilated = _dilate_mask_once(support)
        support = [
            [dilated[y][x] and low_support[y][x] for x in range(maps.w)] for y in range(maps.h)
        ]

    components = _connected_components(support)
    major = [c for c in components if len(c) >= max(4, min_area_px // 2)]
    if not major:
        major = [c for c in components if len(c) >= DEFAULT_MIN_CORE_AREA_PX]

    high_pixels = [(x, y) for y in range(maps.h) for x in range(maps.w) if high_core[y][x]]
    support_pixels = [(x, y) for y in range(maps.h) for x in range(maps.w) if support[y][x]]

    return SupportMasks(
        high_core_mask=high_core,
        low_support_mask=low_support,
        support_mask=support,
        support_components=major,
        high_core_pixels=high_pixels,
        support_pixels=support_pixels,
    )
