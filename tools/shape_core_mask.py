"""V7 CORE/GLOW mask extraction from laser stills (numpy + scikit-image)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from skimage import measure, morphology
from scipy.ndimage import binary_fill_holes

DEFAULT_K_CORE = 8.0
DEFAULT_K_GLOW = 3.5
DEFAULT_SAT_FLOOR = 200
DEFAULT_MIN_CORE_AREA = 4
DEFAULT_DOT_MAX_AREA = 80
DEFAULT_DOT_MAX_ASPECT = 2.0
COORDINATE_SPACE = "wall_norm_per_fixture_calibration_box"


class FixtureBox:
    def __init__(self, label: str, x0: int, y0: int, x1: int, y1: int):
        self.label = label
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    @property
    def width(self) -> int:
        return max(1, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(1, self.y1 - self.y0)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) * 0.5

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) * 0.5

    def contains_pixel(self, px: float, py: float) -> bool:
        return self.x0 <= px < self.x1 and self.y0 <= py < self.y1


def load_analysis_geometry(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def load_fixture_boxes(geom: dict[str, Any]) -> dict[str, FixtureBox]:
    boxes: dict[str, FixtureBox] = {}
    for b in geom.get("boxes", []):
        label = b["label"]
        x0, y0, x1, y1 = b["bbox"]
        boxes[label] = FixtureBox(label, int(x0), int(y0), int(x1), int(y1))
    return boxes


def geometry_source_sha(geom_path: str | Path) -> str:
    data = Path(geom_path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def pixel_to_wall_norm(px: float, py: float, box: FixtureBox) -> tuple[float, float]:
    x_norm = 2.0 * ((px - box.x0) / box.width) - 1.0
    y_norm = 1.0 - 2.0 * ((py - box.y0) / box.height)
    return x_norm, y_norm


def bbox_wall_norm(px0: float, py0: float, px1: float, py1: float, box: FixtureBox) -> list[float]:
    corners = [
        pixel_to_wall_norm(px0, py0, box),
        pixel_to_wall_norm(px1, py0, box),
        pixel_to_wall_norm(px1, py1, box),
        pixel_to_wall_norm(px0, py1, box),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return [min(xs), min(ys), max(xs), max(ys)]


def compute_combined_score(img_rgb: np.ndarray) -> np.ndarray:
    """Compute per-pixel laser score, matching v6 _channel_scores logic in numpy."""
    R = img_rgb[:, :, 0].astype(np.float32)
    G = img_rgb[:, :, 1].astype(np.float32)
    B = img_rgb[:, :, 2].astype(np.float32)

    mx = np.maximum(R, np.maximum(G, B))
    mn = np.minimum(R, np.minimum(G, B))
    sat = mx - mn
    lum = 0.2126 * R + 0.7152 * G + 0.0722 * B

    cand0 = mx + 0.72 * sat

    red_cond = (R >= G) & (R >= B)
    red = np.where(red_cond, np.maximum(0.0, R - np.maximum(G, B) * 0.55) + 0.25 * sat, 0.0)

    green_cond = (G >= R * 0.85) & (G >= B * 0.85)
    green = np.where(green_cond, np.maximum(0.0, G - np.maximum(R, B) * 0.55) + 0.2 * sat, 0.0)

    blue_cond = B >= R * 0.8
    blue = np.where(blue_cond, np.maximum(0.0, B - np.maximum(R, G) * 0.5) + 0.3 * sat, 0.0)

    cyan_cond = (G >= R * 0.9) & (B >= R * 0.9)
    cyan = np.where(cyan_cond, np.maximum(0.0, (G + B) * 0.5 - R * 0.45), 0.0)

    mag_cond = (R >= G * 1.05) & (B >= G * 1.05)
    magenta = np.where(mag_cond, np.maximum(0.0, (R + B) * 0.5 - G * 0.5), 0.0)

    yel_cond = (R >= B * 1.1) & (G >= B * 1.1)
    yellow = np.where(yel_cond, np.maximum(0.0, (R + G) * 0.5 - B * 0.55), 0.0)

    white_cond = (sat < 45) & (mx > 120)
    white = np.where(white_cond, np.minimum(mx, lum + 0.35 * sat), 0.0)

    combined_lum = lum + 0.5 * sat

    # Blue-heavy boost (handles blue/purple/cyan beams)
    bheavy = (B >= R * 0.85) & (B >= G * 0.75)
    blue_boost = np.where(bheavy, B + 0.58 * np.maximum(0.0, B - mn) + 0.22 * G, 0.0)

    # Magenta-heavy boost
    mheavy = (R >= G * 1.05) & (B >= G * 0.9)
    mag_boost = np.where(mheavy, (R + B) * 0.52 + 0.42 * sat, 0.0)

    return np.maximum.reduce([cand0, red, green, blue, cyan, magenta, yellow, white,
                               combined_lum, blue_boost, mag_boost])


def compute_bg_model(score_map: np.ndarray, roi_mask: np.ndarray) -> tuple[float, float]:
    """Return (bg_median, bg_mad) for the ROI, excluding top 1% to avoid laser bias."""
    domain = score_map[roi_mask]
    if len(domain) == 0:
        return 0.0, 1.0
    p99 = float(np.percentile(domain, 99.0))
    bg = domain[domain < p99]
    if len(bg) < 100:
        bg = domain
    bg_median = float(np.median(bg))
    bg_mad = float(np.median(np.abs(bg - bg_median)))
    return bg_median, max(bg_mad, 1.0)


def make_core_mask(
    score_map: np.ndarray,
    roi_mask: np.ndarray,
    img_rgb: np.ndarray,
    bg_median: float,
    bg_mad: float,
    k_core: float = DEFAULT_K_CORE,
    sat_floor: float = DEFAULT_SAT_FLOOR,
    min_core_area: int = DEFAULT_MIN_CORE_AREA,
) -> np.ndarray:
    """Return binary CORE mask restricted to analysis_roi."""
    domain = score_map[roi_mask]
    p99_5 = float(np.percentile(domain, 99.5)) if len(domain) > 0 else 0.0
    core_thresh = max(p99_5, bg_median + k_core * bg_mad)

    core = (score_map >= core_thresh) & roi_mask

    # Saturation test for white cores: min(R,G,B) >= sat_floor
    min_ch = np.minimum(img_rgb[:, :, 0], np.minimum(img_rgb[:, :, 1], img_rgb[:, :, 2])).astype(np.float32)
    core = core | ((min_ch >= sat_floor) & roi_mask)

    # Morphology: remove specks, close 1-px gaps
    # max_size=N removes objects with area <= N (skimage >= 0.26 semantics)
    core = morphology.remove_small_objects(core, max_size=max(0, min_core_area - 1))
    core = morphology.closing(core, morphology.disk(1))
    return core


def make_glow_mask(
    score_map: np.ndarray,
    roi_mask: np.ndarray,
    bg_median: float,
    bg_mad: float,
    k_glow: float = DEFAULT_K_GLOW,
) -> np.ndarray:
    """Return GLOW mask (diagnostics/halo detection only, never geometry source)."""
    glow_thresh = bg_median + k_glow * bg_mad
    return (score_map >= glow_thresh) & roi_mask


def make_roi_mask(img_shape: tuple[int, int], roi: list[int]) -> np.ndarray:
    """Boolean mask for analysis_roi = [x0, y0, x1, y1]."""
    H, W = img_shape[:2]
    x0, y0, x1, y1 = roi
    mask = np.zeros((H, W), dtype=bool)
    mask[y0:y1, x0:x1] = True
    return mask


def label_components(core_mask: np.ndarray) -> tuple[np.ndarray, int]:
    """8-connected component labeling. Returns (labeled, n_components)."""
    labeled = measure.label(core_mask, connectivity=2)
    return labeled, int(labeled.max())


def classify_component(
    comp_mask: np.ndarray,
    dot_max_area: int = DEFAULT_DOT_MAX_AREA,
    dot_max_aspect: float = DEFAULT_DOT_MAX_ASPECT,
) -> str:
    """Classify component as 'dot', 'closed_stroke', or 'open_stroke'.

    dot_max_area is a soft hint for synthetic tests; real laser dots can be much
    larger (k_core p99.5 threshold yields ~500px blobs for actual spots on wall).
    Primary discriminators: aspect ratio + hole fraction + skeleton structure.
    """
    ys, xs = np.where(comp_mask)
    if len(ys) == 0:
        return "open_stroke"
    area = int(len(ys))
    bbox_h = int(ys.max() - ys.min() + 1)
    bbox_w = int(xs.max() - xs.min() + 1)
    aspect = max(bbox_h, bbox_w) / max(1, min(bbox_h, bbox_w))

    filled = binary_fill_holes(comp_mask)
    hole_area = int(np.sum(filled)) - area

    # Closed loop: significant enclosed area (ring/frame shape)
    if hole_area > area * 0.3:
        return "closed_stroke"

    # Closed loop: skeleton has no endpoints (closed cycle)
    skel = morphology.skeletonize(comp_mask)
    if np.any(skel) and _count_skeleton_endpoints(skel) == 0:
        return "closed_stroke"

    # Dot: compact blob (not elongated, no significant hole)
    # area check applies only for the synthetic-test dot_max_area bound;
    # real laser dots are compact but may be large (>> 80 px)
    if aspect < dot_max_aspect and hole_area < area * 0.1:
        return "dot"

    return "open_stroke"


def _count_skeleton_endpoints(skel: np.ndarray) -> int:
    """Count terminal pixels: degree-1 OR isolated (degree-0) using convolution."""
    from scipy.ndimage import convolve
    kernel = np.ones((3, 3), dtype=np.int32)
    kernel[1, 1] = 0
    neighbor_count = convolve(skel.astype(np.int32), kernel, mode="constant", cval=0)
    # degree-0 (isolated) and degree-1 (tip) are both terminal
    return int(np.sum(skel & (neighbor_count <= 1)))


def assign_fixture(
    comp_mask: np.ndarray,
    fixture_boxes: dict[str, FixtureBox],
    out_of_box_margin: int = 20,
) -> tuple[str, str, bool]:
    """
    Returns (assignment_type, box_label, out_of_box_geometry).

    assignment_type: 'contained' | 'nearest' | 'ambiguous'
    box_label: the assigned fixture label
    out_of_box_geometry: True if any component pixels are outside the assigned box
    """
    ys, xs = np.where(comp_mask)
    if len(ys) == 0 or not fixture_boxes:
        label = next(iter(fixture_boxes)) if fixture_boxes else "unknown"
        return "nearest", label, False

    comp_cx = float(xs.mean())
    comp_cy = float(ys.mean())

    # Count fraction of pixels inside each box
    contained_fracs: list[tuple[float, str]] = []
    for box in fixture_boxes.values():
        inside = ((xs >= box.x0) & (xs < box.x1) & (ys >= box.y0) & (ys < box.y1)).sum()
        frac = inside / len(xs)
        if frac > 0.3:
            contained_fracs.append((frac, box.label))

    contained_fracs.sort(reverse=True)

    if len(contained_fracs) == 0:
        # No box contains >30% — assign to nearest by center distance
        dists = [(abs(comp_cx - box.cx) + abs(comp_cy - box.cy), box.label)
                 for box in fixture_boxes.values()]
        dists.sort()
        assigned_label = dists[0][1]
        assignment_type = "nearest"
    elif len(contained_fracs) == 1:
        assigned_label = contained_fracs[0][1]
        assignment_type = "contained"
    else:
        # Multiple boxes — ambiguous if top two are within 30% of each other
        if contained_fracs[0][0] - contained_fracs[1][0] < 0.3:
            assignment_type = "ambiguous"
        else:
            assignment_type = "contained"
        assigned_label = contained_fracs[0][1]

    # Check if any pixels are outside the assigned box
    box = fixture_boxes[assigned_label]
    outside = (~((xs >= box.x0) & (xs < box.x1) & (ys >= box.y0) & (ys < box.y1))).any()
    out_of_box = bool(outside)

    return assignment_type, assigned_label, out_of_box


def rle_encode(mask: np.ndarray) -> dict[str, Any]:
    """Run-length encode a boolean mask in row-major order."""
    flat = mask.flatten().astype(bool)
    runs: list[int] = []
    current = False
    count = 0
    for val in flat:
        if val == current:
            count += 1
        else:
            runs.append(count)
            current = val
            count = 1
    runs.append(count)
    # Ensure starts-with-False (off run)
    if mask.flatten()[0]:
        runs = [0] + runs
    return {
        "shape": list(mask.shape),
        "encoding": "rle_row_major_bool",
        "runs": runs,
    }


def rle_decode(rle: dict[str, Any]) -> np.ndarray:
    """Decode RLE back to boolean mask."""
    shape = rle["shape"]
    runs = rle["runs"]
    flat = np.zeros(shape[0] * shape[1], dtype=bool)
    pos = 0
    for i, count in enumerate(runs):
        if i % 2 == 1:  # odd indices = ones
            flat[pos:pos + count] = True
        pos += count
    return flat.reshape(shape)
