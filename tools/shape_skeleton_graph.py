"""PR-G1 v6: pure-Python skeleton thinning and graph path tracing."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class SkeletonGraph:
    nodes: set[tuple[int, int]] = field(default_factory=set)
    neighbors: dict[tuple[int, int], list[tuple[int, int]]] = field(default_factory=dict)

    def degree(self, node: tuple[int, int]) -> int:
        return len(self.neighbors.get(node, []))

    def endpoints(self) -> list[tuple[int, int]]:
        return [n for n in self.nodes if self.degree(n) <= 1]

    def branch_points(self) -> list[tuple[int, int]]:
        return [n for n in self.nodes if self.degree(n) >= 3]


def _neighbors8(mask: list[list[bool]], x: int, y: int) -> list[tuple[int, int]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    out: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx]:
                out.append((nx, ny))
    return out


def _zhang_suen_iteration(mask: list[list[bool]], subiter: int) -> tuple[list[list[bool]], bool]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    to_remove: list[tuple[int, int]] = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if not mask[y][x]:
                continue
            p = [
                mask[y - 1][x],
                mask[y - 1][x + 1],
                mask[y][x + 1],
                mask[y + 1][x + 1],
                mask[y + 1][x],
                mask[y + 1][x - 1],
                mask[y][x - 1],
                mask[y - 1][x - 1],
            ]
            b = sum(int(v) for v in p)
            if b < 2 or b > 6:
                continue
            seq = p + [p[0]]
            a = sum(1 for i in range(8) if not seq[i] and seq[i + 1])
            if a != 1:
                continue
            if subiter == 0:
                if p[0] * p[2] * p[4] != 0:
                    continue
                if p[2] * p[4] * p[6] != 0:
                    continue
            else:
                if p[0] * p[2] * p[6] != 0:
                    continue
                if p[0] * p[4] * p[6] != 0:
                    continue
            to_remove.append((x, y))
    if not to_remove:
        return mask, False
    nxt = [row[:] for row in mask]
    for x, y in to_remove:
        nxt[y][x] = False
    return nxt, True


def skeletonize_support_mask(mask: list[list[bool]], *, max_iter: int = 80) -> list[list[bool]]:
    """Reduce support mask to 1-pixel-wide skeleton."""
    skel = [row[:] for row in mask]
    for _ in range(max_iter):
        skel, changed0 = _zhang_suen_iteration(skel, 0)
        skel, changed1 = _zhang_suen_iteration(skel, 1)
        if not (changed0 or changed1):
            break
    return skel


def build_skeleton_graph(skel_mask: list[list[bool]]) -> SkeletonGraph:
    h = len(skel_mask)
    w = len(skel_mask[0]) if h else 0
    nodes: set[tuple[int, int]] = set()
    neighbors: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for y in range(h):
        for x in range(w):
            if not skel_mask[y][x]:
                continue
            nodes.add((x, y))
            neighbors[(x, y)] = _neighbors8(skel_mask, x, y)
    return SkeletonGraph(nodes=nodes, neighbors=neighbors)


def _bfs_farthest(graph: SkeletonGraph, start: tuple[int, int]) -> tuple[tuple[int, int], dict[tuple[int, int], tuple[int, int] | None]]:
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    q: deque[tuple[int, int]] = deque([start])
    farthest = start
    while q:
        cur = q.popleft()
        farthest = cur
        for nxt in graph.neighbors.get(cur, []):
            if nxt in parent:
                continue
            parent[nxt] = cur
            q.append(nxt)
    return farthest, parent


def _reconstruct_path(parent: dict[tuple[int, int], tuple[int, int] | None], end: tuple[int, int]) -> list[tuple[int, int]]:
    path: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = end
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def longest_geodesic_path(graph: SkeletonGraph) -> list[tuple[int, int]]:
    if not graph.nodes:
        return []
    start = min(graph.nodes, key=lambda p: (p[1], p[0]))
    far_a, _ = _bfs_farthest(graph, start)
    far_b, parent = _bfs_farthest(graph, far_a)
    return _reconstruct_path(parent, far_b)


def _walk_branch(
    graph: SkeletonGraph,
    start: tuple[int, int],
    forbidden: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    path = [start]
    visited = {start}
    cur = start
    while True:
        nbrs = [n for n in graph.neighbors.get(cur, []) if n not in forbidden and n not in visited]
        if not nbrs:
            break
        if len(nbrs) > 1:
            break
        nxt = nbrs[0]
        path.append(nxt)
        visited.add(nxt)
        cur = nxt
    return path


def split_skeleton_paths(graph: SkeletonGraph) -> list[list[tuple[int, int]]]:
    """Emit ordered path segments: longest geodesic plus branch arms."""
    if not graph.nodes:
        return []
    paths: list[list[tuple[int, int]]] = []
    main = longest_geodesic_path(graph)
    if len(main) >= 2:
        paths.append(main)

    used: set[tuple[int, int]] = set(main)
    branches = graph.branch_points()
    for bp in branches:
        for nbr in graph.neighbors.get(bp, []):
            if nbr in used:
                continue
            seg = _walk_branch(graph, nbr, used | {bp})
            if len(seg) >= 2:
                paths.append([bp] + seg)
                used.update(seg)

    if not paths:
        paths.append(sorted(graph.nodes, key=lambda p: (p[0], p[1])))
    return paths


def trace_skeleton_from_mask(mask: list[list[bool]]) -> list[list[tuple[int, int]]]:
    skel = skeletonize_support_mask(mask)
    graph = build_skeleton_graph(skel)
    return split_skeleton_paths(graph)


def path_length_px(path: list[tuple[int, int]]) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(path, path[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    return total
