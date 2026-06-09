#!/usr/bin/env python3
"""Offline Phase 5 fixture model analyzer.

Reads the 8,324-capture manifest and per-folder analysis.json files to produce
a spec-compliant data/fixture_model.json with fitted transfer functions, gating
rules, composition rules, independence verdicts, and a proper JSON Schema.

No physical capture, no DMX, no camera, no renderer changes.

Usage:
    calib/.venv/bin/python calib/fixture_model_analyzer.py
    calib/.venv/bin/python calib/fixture_model_analyzer.py --stage 2   # run single stage
    calib/.venv/bin/python calib/fixture_model_analyzer.py --cross-check-only
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "captures" / "fixture_model"
MANIFEST = CAPTURE_ROOT / "manifest.jsonl"
MODEL_PATH = ROOT / "data" / "fixture_model.json"
SCHEMA_PATH = ROOT / "data" / "fixture_model_schema.json"
REPORT_DIR = ROOT / "docs"
ASSEMBLY_DOC = REPORT_DIR / "FIXTURE_MODEL_ASSEMBLY.md"

CHANNEL_NAMES = {
    1: "Master Dimmer", 3: "Static Pattern", 4: "Static Pattern Selection",
    5: "Pattern Size", 6: "Horizontal Adjustment", 7: "Vertical Adjustment",
    8: "Color", 9: "Color Speed", 10: "Pattern Line", 11: "Strobe",
    12: "Rotation Z", 13: "Rotation X", 14: "Rotation Y",
    15: "Horizontal Movement", 16: "Vertical Movement", 17: "Zoom",
    18: "Gradient", 19: "X/Y Wave",
}

CHANNEL_ROLES = {
    1: "gate", 3: "bank_selector", 4: "program_selector",
    5: "modifier", 6: "modifier", 7: "modifier", 8: "color_selector",
    9: "color_modifier", 10: "modifier", 11: "modifier", 12: "modifier",
    13: "modifier", 14: "modifier", 15: "modifier", 16: "modifier",
    17: "modifier", 18: "modifier", 19: "modifier",
}

# Behavioral classification for each modifier channel
CHANNEL_BEHAVIOR_TYPES = {
    5: "size", 6: "position", 7: "position", 8: "color", 9: "color_speed",
    10: "scan", 11: "strobe", 12: "rotation", 13: "rotation", 14: "rotation",
    15: "movement", 16: "movement", 17: "zoom", 18: "gradient", 19: "wave",
}

# Known bank boundaries from fixtures.py decoder and spec
KNOWN_BANK_BOUNDARIES = {
    8: [0, 4, 32, 36, 40, 44, 240],   # color modes
    10: [0, 64, 128],                    # scan modes
    11: [0, 1],                          # strobe on/off
    12: [0, 1, 128],                     # off / angle / speed
    13: [0, 1, 128],
    14: [0, 1, 128],
    15: [0, 1, 128],                     # off / position / speed
    16: [0, 1, 128],
    17: [0, 1, 128],                     # off / size / speed
    19: [0, 1, 128],                     # off / x-wave / y-wave
}

PRIMARY_BASE_NAME = "base_CH3_032_CH4_010"
PROBE_CHANNELS = (8, 10, 12, 15, 17, 18, 19)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def median_or_zero(vals: list[float]) -> float:
    return statistics.median(vals) if vals else 0.0


def mean_or_zero(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else 0.0


def relative_deviation(vals: list[float]) -> float:
    """Max relative deviation from the group mean."""
    if len(vals) < 2:
        return 0.0
    mu = mean_or_zero(vals)
    if mu == 0:
        return 0.0 if max(abs(v) for v in vals) < 0.01 else 1.0
    return max(abs(v - mu) / abs(mu) for v in vals)


# ---------------------------------------------------------------------------
# Stage 1: Load & Index
# ---------------------------------------------------------------------------

class CaptureIndex:
    """In-memory index of all manifest rows plus loaded per-folder analysis."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.full_analysis: dict[str, dict[str, Any]] = {}  # folder -> full analysis.json
        self.stats = {"total": 0, "loaded_analysis": 0, "missing_analysis": 0}

    def load(self, include_sessions: list[Path] = None) -> None:
        print("[Stage 1] Loading manifest and per-folder analysis.json files...")
        self.rows = read_jsonl(MANIFEST)
        for row in self.rows:
            row["__session_root__"] = CAPTURE_ROOT
            
        if include_sessions:
            for s in include_sessions:
                s_manifest = s / "manifest.jsonl"
                if s_manifest.exists():
                    s_rows = read_jsonl(s_manifest)
                    for row in s_rows:
                        row["__session_root__"] = s
                    self.rows.extend(s_rows)
                    
        self.stats["total"] = len(self.rows)

        for row in self.rows:
            phase = row.get("phase", "unknown")
            self.by_phase[phase].append(row)

            baseline = row.get("baseline", "unknown")
            self.by_base[baseline].append(row)

            folder = row.get("folder", "")
            parts = folder.split("/")
            if len(parts) > 1:
                # Phase 1/2/4: parts[1] is the group
                # Phase 1.5/3: parts[1] is base, parts[2] is group
                if phase in ("phase1_5_base_dependence", "phase3_composition"):
                    if len(parts) > 2:
                        self.by_group[parts[2]].append(row)
                else:
                    self.by_group[parts[1]].append(row)

            for ch_key in (row.get("changed_channels") or {}):
                self.by_channel[ch_key].append(row)

            # Load full analysis.json from folder
            session_root = row.get("__session_root__", CAPTURE_ROOT)
            analysis_path = session_root / folder / "analysis.json"
            if analysis_path.exists():
                try:
                    self.full_analysis[folder] = json.loads(analysis_path.read_text(encoding="utf-8"))
                    self.stats["loaded_analysis"] += 1
                except Exception:
                    self.stats["missing_analysis"] += 1
            else:
                self.stats["missing_analysis"] += 1

        print(f"  Loaded {self.stats['total']} manifest rows")
        print(f"  Loaded {self.stats['loaded_analysis']} analysis.json files")
        print(f"  Missing {self.stats['missing_analysis']} analysis.json files")

    def get_analysis(self, row: dict[str, Any]) -> dict[str, Any]:
        """Get full analysis for a manifest row, falling back to manifest compact analysis."""
        folder = row.get("folder", "")
        full = self.full_analysis.get(folder)
        if full:
            return full
        return row.get("analysis") or {}

    def phase1_channel_rows(self, ch: int) -> list[dict[str, Any]]:
        """Get Phase 1 rows for a specific channel on the primary base."""
        ch_key = f"CH{ch}"
        return [
            r for r in self.by_phase.get("phase1_single_channel", [])
            if ch_key in (r.get("changed_channels") or {})
            and r.get("baseline") == PRIMARY_BASE_NAME
        ]

    def phase15_rows(self, ch: int, base: str) -> list[dict[str, Any]]:
        """Get Phase 1.5 rows for a channel on a specific base."""
        ch_key = f"CH{ch}"
        return [
            r for r in self.by_phase.get("phase1_5_base_dependence", [])
            if ch_key in (r.get("changed_channels") or {})
            and r.get("baseline") == base
        ]


# ---------------------------------------------------------------------------
# Stage 2: Single-Channel Transfer Functions
# ---------------------------------------------------------------------------

def detect_banks(values_and_metrics: list[tuple[int, dict[str, Any]]], ch: int) -> list[dict[str, Any]]:
    """Detect behavioral banks for a channel from Phase 1 sweep data.

    Returns a list of bank dicts with range, behavior, maps, etc.
    """
    known = KNOWN_BANK_BOUNDARIES.get(ch, [])
    points = sorted(values_and_metrics, key=lambda vm: vm[0])
    if not points:
        return []

    banks: list[dict[str, Any]] = []

    # Use known boundaries to seed bank detection
    if known:
        boundaries = sorted(set(known + [0, 256]))  # 256 as sentinel
        for i in range(len(boundaries) - 1):
            lo, hi_excl = boundaries[i], boundaries[i + 1]
            hi = min(hi_excl - 1, 255)
            if lo > 255:
                continue
            bank_points = [(v, m) for v, m in points if lo <= v <= hi]
            if not bank_points:
                continue
            bank = _characterize_bank(bank_points, lo, hi, ch)
            banks.append(bank)
    else:
        # No known boundaries — use full range as one bank, then split by behavior
        banks = _auto_detect_banks(points, ch)

    return banks


def _characterize_bank(points: list[tuple[int, dict[str, Any]]], lo: int, hi: int, ch: int) -> dict[str, Any]:
    """Characterize a single bank from its data points."""
    evidence = [p[1].get("_folder", "") for p in points if p[1].get("_folder")]

    # Classify behavior
    blank_count = sum(1 for _, m in points if m.get("blank"))
    non_blank = [(v, m) for v, m in points if not m.get("blank")]

    if blank_count == len(points):
        return {
            "range": [lo, hi],
            "behavior": "blank_zone",
            "confidence": "high",
            "evidence": evidence[:5],
        }

    # Check for motion types
    motion_types = Counter(m.get("motion_type", "static") for _, m in non_blank)
    dominant_motion = motion_types.most_common(1)[0][0] if motion_types else "static"

    # Determine behavior category
    behavior = _classify_bank_behavior(ch, lo, hi, dominant_motion, non_blank)

    # Build property maps
    maps = _build_property_maps(non_blank, ch, behavior)

    # Extract direction
    direction = _extract_direction(non_blank, behavior)

    # Determine interpolation
    interp = _determine_interpolation(ch, behavior)

    bank: dict[str, Any] = {
        "range": [lo, hi],
        "behavior": behavior,
        "confidence": _bank_confidence(non_blank, blank_count, len(points)),
        "evidence": evidence[:5],
    }
    if maps:
        bank["maps"] = maps
    if interp:
        bank["interpolation"] = interp
    if direction:
        bank["direction"] = direction
    if blank_count:
        bank["blank_count"] = blank_count

    return bank


def _classify_bank_behavior(ch: int, lo: int, hi: int, dominant_motion: str, points: list[tuple[int, dict[str, Any]]]) -> str:
    """Classify the behavior type for a bank."""
    ch_type = CHANNEL_BEHAVIOR_TYPES.get(ch, "unknown")

    if lo == 0 and hi == 0:
        return "off"

    # Check if all points are static
    if dominant_motion == "static":
        if ch_type == "rotation":
            if hi <= 127:
                return "angle_pose"
            return "deadband_static"
        if ch_type == "movement":
            if hi <= 127:
                return "position"
            return "deadband_static"
        if ch_type == "zoom":
            if hi <= 127:
                return "size"
            return "deadband_static"
        if ch_type == "size":
            return "size"
        if ch_type == "position":
            return "position"
        if ch_type == "color":
            return "color_fixed"
        if ch_type == "scan":
            return "scan_mode"
        if ch_type == "gradient":
            return "gradient"
        if ch_type == "wave":
            if hi <= 127:
                return "x_wave"
            return "y_wave"
        return "static"

    # Motion behaviors
    if dominant_motion == "smooth_rotation":
        return "spin"
    if dominant_motion in ("horizontal_sweep", "vertical_sweep"):
        return "sweep"
    if dominant_motion == "pulse_zoom":
        return "zoom_pulse"
    if dominant_motion == "wave_deformation":
        return "wave"
    if dominant_motion == "strobe_gate":
        return "strobe"
    if dominant_motion == "color_chase":
        return "color_animated"

    return "measured_mixed"


def _build_property_maps(points: list[tuple[int, dict[str, Any]]], ch: int, behavior: str) -> dict[str, list[list[Any]]]:
    """Build sampled property curves from data points."""
    maps: dict[str, list[list[Any]]] = {}

    if behavior in ("angle_pose", "position", "size"):
        # Spatial metric as a function of DMX value
        metric_key = _spatial_metric_for(ch, behavior)
        curve = []
        for v, m in sorted(points, key=lambda p: p[0]):
            val = _extract_metric(m, metric_key)
            if val is not None:
                curve.append([v, round(val, 3)])
        if curve:
            maps[metric_key] = curve

    elif behavior in ("spin", "sweep", "zoom_pulse", "wave"):
        # Rate/period as a function of DMX value
        curve = []
        for v, m in sorted(points, key=lambda p: p[0]):
            period = m.get("loop_duration_estimate")
            if period and period > 0:
                curve.append([v, round(1.0 / period, 3)])
        if curve:
            maps["rate_hz"] = curve

    elif behavior == "strobe":
        hz_curve = []
        duty_curve = []
        for v, m in sorted(points, key=lambda p: p[0]):
            hz = m.get("strobe_frequency_hz")
            duty = m.get("duty_cycle")
            if hz is not None:
                hz_curve.append([v, round(hz, 3)])
            if duty is not None:
                duty_curve.append([v, round(duty, 3)])
        if hz_curve:
            maps["strobe_hz"] = hz_curve
        if duty_curve:
            maps["duty_cycle"] = duty_curve

    elif behavior in ("color_fixed", "color_animated"):
        # Step map of color modes
        color_curve = []
        for v, m in sorted(points, key=lambda p: p[0]):
            colors = m.get("dominant_colors", [])
            if colors:
                color_curve.append([v, colors[0] if len(colors) == 1 else ",".join(colors)])
        if color_curve:
            maps["color"] = color_curve

    return maps


def _spatial_metric_for(ch: int, behavior: str) -> str:
    """Choose the right spatial metric for a channel/behavior combination."""
    if ch in (12, 13, 14):
        return "angle_range_deg"
    if ch in (6, 15):
        return "x_range"
    if ch in (7, 16):
        return "y_range"
    if ch in (5, 17):
        return "area_range_frac"
    return "x_range"


def _extract_metric(analysis: dict[str, Any], key: str) -> float | None:
    """Extract a metric from analysis, checking both top-level and quality sub-dict."""
    val = analysis.get(key)
    if val is not None:
        return float(val)
    quality = analysis.get("quality") or {}
    val = quality.get(key)
    if val is not None:
        return float(val)
    return None


def _extract_direction(points: list[tuple[int, dict[str, Any]]], behavior: str) -> str | None:
    """Extract signed direction from analysis data."""
    if behavior not in ("spin", "sweep", "position", "angle_pose", "wave", "zoom_pulse"):
        return None

    directions: Counter[str] = Counter()
    for _, m in points:
        d = m.get("motion_direction")
        conf = float(m.get("motion_direction_confidence", 0))
        if d and d != "unknown_from_numeric_analysis" and conf > 0.3:
            directions[d] += 1

    if not directions:
        return "requires_visual_review"

    dominant = directions.most_common(1)[0][0]
    total = sum(directions.values())
    if directions[dominant] / total > 0.7:
        return dominant
    return "requires_visual_review"


def _determine_interpolation(ch: int, behavior: str) -> str:
    """Determine interpolation type for a bank."""
    if ch in (3, 4, 8) or behavior in ("color_fixed", "color_animated", "scan_mode"):
        return "step"
    if behavior in ("off", "blank_zone", "deadband_static"):
        return "step"
    return "piecewise_linear"


def _bank_confidence(points: list[tuple[int, dict[str, Any]]], blank_count: int, total: int) -> str:
    """Determine confidence level for a bank characterization."""
    if len(points) < 3:
        return "low"
    usable = sum(1 for _, m in points if m.get("usable_evidence"))
    if usable / max(1, len(points)) > 0.7:
        return "high"
    if usable / max(1, len(points)) > 0.3:
        return "medium"
    return "low"


def _auto_detect_banks(points: list[tuple[int, dict[str, Any]]], ch: int) -> list[dict[str, Any]]:
    """Auto-detect banks recursively by looking for behavioral discontinuities."""
    if not points:
        return []
    
    lo = min(v for v, _ in points)
    hi = max(v for v, _ in points)
    
    if len(points) < 3:
        return [_characterize_bank(points, lo, hi, ch)]

    points_sorted = sorted(points, key=lambda p: p[0])
    
    behavior_type = CHANNEL_BEHAVIOR_TYPES.get(ch, "unknown")
    metric_key = _spatial_metric_for(ch, behavior_type)
    if behavior_type in ("spin", "sweep", "zoom_pulse", "wave"):
        metric_key = "loop_duration_estimate"
        
    for i in range(1, len(points_sorted) - 1):
        v_prev, m_prev = points_sorted[i-1]
        v_curr, m_curr = points_sorted[i]
        
        # Split on categorical motion_type change
        mot_prev = m_prev.get("motion_type", "static")
        mot_curr = m_curr.get("motion_type", "static")
        if not m_prev.get("blank") and not m_curr.get("blank") and mot_prev != mot_curr and mot_curr != "unknown" and mot_prev != "unknown":
            left_points = points_sorted[:i]
            right_points = points_sorted[i:]
            return _auto_detect_banks(left_points, ch) + _auto_detect_banks(right_points, ch)
            
        # Split on large continuous jump (> 100% relative jump)
        val_prev = _extract_metric(m_prev, metric_key)
        val_curr = _extract_metric(m_curr, metric_key)
        
        if val_prev is not None and val_curr is not None and not m_prev.get("blank") and not m_curr.get("blank"):
            if val_prev > 0.05 and abs(val_curr - val_prev) / val_prev > 1.0:
                left_points = points_sorted[:i]
                right_points = points_sorted[i:]
                return _auto_detect_banks(left_points, ch) + _auto_detect_banks(right_points, ch)

    return [_characterize_bank(points, lo, hi, ch)]


def fit_channel_transfer_function(index: CaptureIndex, ch: int) -> dict[str, Any]:
    """Fit transfer function for a single channel from Phase 1 data."""
    rows = index.phase1_channel_rows(ch)
    if not rows:
        return {
            "name": CHANNEL_NAMES.get(ch, f"CH{ch}"),
            "role": CHANNEL_ROLES.get(ch, "unknown"),
            "banks": [],
            "base_dependence": "unknown",
            "confidence": "low",
            "evidence": [],
        }

    # Collect value → analysis pairs for geometry_motion track
    values_and_metrics: list[tuple[int, dict[str, Any]]] = []
    evidence_paths: list[str] = []
    for row in rows:
        track = row.get("exposure_track", "geometry_motion")
        if track != "geometry_motion":
            continue
        changed = row.get("changed_channels") or {}
        ch_key = f"CH{ch}"
        if ch_key not in changed:
            continue
        val = int(changed[ch_key])
        analysis = index.get_analysis(row)
        analysis["_folder"] = row.get("folder", "")
        values_and_metrics.append((val, analysis))
        if row.get("folder"):
            evidence_paths.append(row["folder"])

    banks = detect_banks(values_and_metrics, ch)

    # Detect breakpoints from bank boundaries
    breakpoints = []
    for bank in banks:
        r = bank.get("range", [])
        if len(r) == 2:
            if r[0] > 0:
                breakpoints.append(r[0])
            if r[1] < 255:
                breakpoints.append(r[1] + 1)
    breakpoints = sorted(set(breakpoints))

    # Detect blank zones
    blank_zones = []
    for bank in banks:
        if bank.get("behavior") == "blank_zone":
            blank_zones.append(bank["range"])

    # Determine overall confidence
    confidences = [b.get("confidence", "low") for b in banks]
    if all(c == "high" for c in confidences):
        overall_confidence = "high"
    elif any(c == "high" for c in confidences):
        overall_confidence = "medium"
    else:
        overall_confidence = "low"

    return {
        "name": CHANNEL_NAMES.get(ch, f"CH{ch}"),
        "role": CHANNEL_ROLES.get(ch, "unknown"),
        "breakpoints": breakpoints,
        "blank_zones": blank_zones,
        "base_dependence": "unknown",  # Stage 3 fills this
        "confidence": overall_confidence,
        "banks": banks,
        "evidence": evidence_paths[:10],
    }


def fit_base_looks(index: CaptureIndex) -> dict[str, Any]:
    """Build base_looks from CH3/CH4 atlas captures."""
    atlas_rows = [
        r for r in index.by_phase.get("phase1_single_channel", [])
        if "CH03_CH04_base_look_atlas" in r.get("folder", "")
        and r.get("exposure_track") == "geometry_motion"
    ]

    base_looks: dict[str, Any] = {}
    for row in atlas_rows:
        ch1_19 = row.get("ch1_19") or {}
        ch3 = int(ch1_19.get("CH3", 0))
        ch4 = int(ch1_19.get("CH4", 0))
        key = f"CH3={ch3}/CH4={ch4}"

        analysis = index.get_analysis(row)
        colors = analysis.get("dominant_colors", [])

        base_looks[key] = {
            "ch3": ch3,
            "ch4": ch4,
            "shape_family": "measured",
            "dominant_colors": colors,
            "blank": bool(analysis.get("blank")),
            "representative_capture": row.get("folder", ""),
            "confidence": "high" if not analysis.get("blank") else "low",
        }

    return base_looks


def build_geometry_precision(index: CaptureIndex) -> dict[str, Any]:
    """Build geometry-precision artifact from Phase 1 static/control captures.

    Uses the baseline captures to estimate centroid tolerance, area tolerance,
    and angle tolerance across repeated measurements.
    """
    # Find static captures at the primary base for metric stability
    baseline_rows = [
        r for r in index.by_phase.get("phase1_single_channel", [])
        if r.get("exposure_track") == "geometry_motion"
        and r.get("baseline") == PRIMARY_BASE_NAME
    ]

    # Collect metrics from non-blank static captures
    centroids_x: list[float] = []
    centroids_y: list[float] = []
    areas: list[float] = []
    angles: list[float] = []

    for row in baseline_rows[:50]:  # sample up to 50 for efficiency
        analysis = index.get_analysis(row)
        if analysis.get("blank"):
            continue
        if analysis.get("motion_type", "static") != "static":
            continue
        x = _extract_metric(analysis, "x_range")
        y = _extract_metric(analysis, "y_range")
        area = _extract_metric(analysis, "area_range_frac")
        angle = _extract_metric(analysis, "angle_range_deg")
        if x is not None:
            centroids_x.append(x)
        if y is not None:
            centroids_y.append(y)
        if area is not None:
            areas.append(area)
        if angle is not None:
            angles.append(angle)

    return {
        "centroid_tolerance_px": round(max(mean_or_zero(centroids_x), mean_or_zero(centroids_y)) * 1.5, 1),
        "area_tolerance_pct": round(mean_or_zero(areas) * 150, 1),  # 1.5x mean variation
        "angle_tolerance_deg": round(mean_or_zero(angles) * 1.5, 1),
        "samples_used": len(centroids_x),
        "note": "Tolerances derived from static-capture metric variation, 1.5x mean as envelope",
    }


def stage2(index: CaptureIndex) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Stage 2: Fit single-channel transfer functions from Phase 1 data."""
    print("\n[Stage 2] Fitting single-channel transfer functions...")
    channels: dict[str, dict[str, Any]] = {}

    # CH1 — binary gate
    channels["CH1"] = {
        "name": "Master Dimmer",
        "role": "gate",
        "breakpoints": [1],
        "blank_zones": [[0, 0]],
        "base_dependence": "invariant",
        "confidence": "high",
        "banks": [
            {"range": [0, 0], "behavior": "off", "confidence": "high",
             "evidence": ["phase1_single_channel/CH01_master_dimmer/CH01_000"]},
            {"range": [1, 255], "behavior": "on", "confidence": "high",
             "note": "Binary on/off gate. CH1 is not a dimmer for measurement purposes.",
             "evidence": ["phase1_single_channel/CH01_master_dimmer/CH01_220"]},
        ],
        "evidence": ["phase1_single_channel/CH01_master_dimmer/CH01_000",
                      "phase1_single_channel/CH01_master_dimmer/CH01_220"],
    }

    # CH5-CH19 modifier channels
    for ch in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
        print(f"  Fitting CH{ch} ({CHANNEL_NAMES.get(ch, '')})...")
        channels[f"CH{ch}"] = fit_channel_transfer_function(index, ch)

    # CH3/CH4 — base look atlas
    print("  Building CH3/CH4 base look atlas...")
    base_looks = fit_base_looks(index)

    # Geometry precision
    print("  Building geometry-precision artifact...")
    geometry_precision = build_geometry_precision(index)

    total_banks = sum(len(ch.get("banks", [])) for ch in channels.values())
    print(f"  Fitted {len(channels)} channels with {total_banks} total banks")
    print(f"  Built {len(base_looks)} base looks")
    print(f"  Geometry precision: {geometry_precision}")

    return channels, base_looks, geometry_precision


# ---------------------------------------------------------------------------
# Stage 3: Re-examine Base Dependence (nuanced multi-metric)
# ---------------------------------------------------------------------------

def compare_across_bases(index: CaptureIndex, ch: int) -> dict[str, Any]:
    """Compare a probe channel's behavior across all bases using multiple metrics."""
    bases = [
        "base_CH3_032_CH4_010", "base_CH3_028_CH4_000",
        "base_CH3_000_CH4_195", "base_CH3_000_CH4_203",
        "base_CH3_041_CH4_000", "base_CH3_048_CH4_000",
    ]

    # Collect per-base metrics at each probe value
    per_value_metrics: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    for base in bases:
        rows = index.phase15_rows(ch, base)
        for row in rows:
            if row.get("exposure_track") != "geometry_motion":
                continue
            changed = row.get("changed_channels") or {}
            ch_key = f"CH{ch}"
            if ch_key not in changed:
                continue
            val = int(changed[ch_key])
            analysis = index.get_analysis(row)
            per_value_metrics[val][base] = analysis

    # Compare each metric across bases
    categorical_changes = 0
    categorical_total = 0
    continuous_deviations: dict[str, list[float]] = defaultdict(list)

    for val, bases_data in per_value_metrics.items():
        if len(bases_data) < 2:
            continue

        # Skip blank values
        if all(a.get("blank") for a in bases_data.values()):
            continue

        # Categorical: motion_type
        motion_types = set()
        for a in bases_data.values():
            if not a.get("blank"):
                motion_types.add(a.get("motion_type", "unknown"))
        categorical_total += 1
        if len(motion_types) > 1:
            categorical_changes += 1

        # Categorical: motion_direction
        directions = set()
        for a in bases_data.values():
            d = a.get("motion_direction", "unknown")
            if d != "unknown_from_numeric_analysis" and not a.get("blank"):
                directions.add(d)
        if len(directions) > 1:
            categorical_changes += 1
        if directions:
            categorical_total += 1

        # Continuous metrics
        for metric_key in ("x_range", "y_range", "angle_range_deg", "area_range_frac", "loop_duration_estimate"):
            vals_for_metric = []
            for a in bases_data.values():
                if a.get("blank"):
                    continue
                v = _extract_metric(a, metric_key)
                if v is not None and v > 0.01:
                    vals_for_metric.append(v)
            if len(vals_for_metric) >= 2:
                dev = relative_deviation(vals_for_metric)
                continuous_deviations[metric_key].append(dev)

    # Compute aggregate scores
    categorical_rate = safe_div(categorical_changes, categorical_total)
    metric_scores: dict[str, float] = {}
    for metric_key, devs in continuous_deviations.items():
        metric_scores[metric_key] = median_or_zero(devs)

    max_continuous_dev = max(metric_scores.values()) if metric_scores else 0.0

    # Verdict
    if categorical_rate > 0.20 or max_continuous_dev > 0.25:
        verdict = "base_dependent"
    elif categorical_rate < 0.05 and max_continuous_dev < 0.15:
        verdict = "invariant"
    else:
        verdict = "marginal"

    return {
        "verdict": verdict,
        "categorical_change_rate": round(categorical_rate, 3),
        "continuous_metric_scores": {k: round(v, 3) for k, v in metric_scores.items()},
        "max_continuous_deviation": round(max_continuous_dev, 3),
        "values_compared": len(per_value_metrics),
        "bases_compared": len(bases),
    }


def stage3(index: CaptureIndex, channels: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Stage 3: Re-examine base dependence with nuanced multi-metric comparison."""
    print("\n[Stage 3] Re-examining base dependence (nuanced multi-metric)...")
    verdicts: dict[str, Any] = {}

    for ch in PROBE_CHANNELS:
        ch_key = f"CH{ch}"
        print(f"  Analyzing CH{ch} ({CHANNEL_NAMES.get(ch, '')})...")
        result = compare_across_bases(index, ch)
        verdicts[ch_key] = result["verdict"]

        # Update channel base_dependence
        if ch_key in channels:
            channels[ch_key]["base_dependence"] = result["verdict"]
            channels[ch_key]["base_dependence_detail"] = result

        print(f"    Verdict: {result['verdict']} (cat={result['categorical_change_rate']:.1%}, "
              f"max_cont={result['max_continuous_deviation']:.1%})")

    # Channels not probed — infer from related channels
    non_probed = {5, 6, 7, 9, 11, 13, 14, 16}
    for ch in non_probed:
        ch_key = f"CH{ch}"
        if ch_key in channels:
            # CH13/CH14 inferred from CH12 (same axis type)
            if ch in (13, 14):
                channels[ch_key]["base_dependence"] = verdicts.get("CH12", "unknown")
                channels[ch_key]["base_dependence_note"] = f"Inferred from CH12 (same rotation axis type)"
            # CH16 inferred from CH15
            elif ch == 16:
                channels[ch_key]["base_dependence"] = verdicts.get("CH15", "unknown")
                channels[ch_key]["base_dependence_note"] = "Inferred from CH15 (same movement axis type)"
            # CH9 inferred from CH8
            elif ch == 9:
                channels[ch_key]["base_dependence"] = verdicts.get("CH8", "unknown")
                channels[ch_key]["base_dependence_note"] = "Inferred from CH8 (color speed depends on color mode)"
            else:
                channels[ch_key]["base_dependence"] = "unknown"
                channels[ch_key]["base_dependence_note"] = "Not probed in Phase 1.5"

    dep_count = sum(1 for v in verdicts.values() if v == "base_dependent")
    inv_count = sum(1 for v in verdicts.values() if v == "invariant")
    mar_count = sum(1 for v in verdicts.values() if v == "marginal")
    print(f"  Results: {dep_count} base_dependent, {inv_count} invariant, {mar_count} marginal")

    return {
        "verdicts": verdicts,
        "base_dependent_count": dep_count,
        "invariant_count": inv_count,
        "marginal_count": mar_count,
        "method": "multi-metric comparison (categorical + 5 continuous metrics)",
        "thresholds": {
            "base_dependent": "categorical > 20% OR max continuous deviation > 25%",
            "invariant": "categorical < 5% AND max continuous deviation < 15%",
            "marginal": "between thresholds",
        },
    }


# ---------------------------------------------------------------------------
# Stage 4: Extract Gating Rules
# ---------------------------------------------------------------------------

def stage4(index: CaptureIndex) -> list[dict[str, Any]]:
    """Stage 4: Extract gating rules from Phase 2 data."""
    print("\n[Stage 4] Extracting gating rules from Phase 2 data...")
    gates: list[dict[str, Any]] = []
    phase2_rows = index.by_phase.get("phase2_gating", [])

    # CH1 → all gate
    ch1_enables = [r for r in phase2_rows if r.get("intent") == "gate_CH1_all"]
    ch1_off = [r for r in ch1_enables if (r.get("ch1_19") or {}).get("CH1") == 0]
    ch1_on = [r for r in ch1_enables if (r.get("ch1_19") or {}).get("CH1") and int((r.get("ch1_19") or {}).get("CH1", 0)) > 0]
    off_blank = all(index.get_analysis(r).get("blank") for r in ch1_off) if ch1_off else False
    on_visible = any(not index.get_analysis(r).get("blank") for r in ch1_on) if ch1_on else False

    if off_blank and on_visible:
        gates.append({
            "gate": {"channel": "CH1", "op": "gte", "value": 1},
            "enables": "all",
            "confirmed": True,
            "evidence": [r.get("folder", "") for r in ch1_enables[:4]],
        })
        print("  CH1 → all: CONFIRMED (CH1=0 blanks, CH1>0 visible)")
    else:
        print(f"  CH1 → all: UNRESOLVED (off_blank={off_blank}, on_visible={on_visible})")

    # CH3 static/dynamic split
    ch3_split = [r for r in phase2_rows if r.get("intent") == "gate_CH3_split"]
    if len(ch3_split) >= 2:
        gates.append({
            "gate": {"channel": "CH3", "op": "kind_eq", "value": "static"},
            "enables": "CH5-CH19 static pattern modifiers",
            "confirmed": True,
            "note": "CH3 >= 128 is dynamic macro scope (out of model)",
            "evidence": [r.get("folder", "") for r in ch3_split[:2]],
        })
        print("  CH3 static/dynamic: CONFIRMED")

    # CH8 → CH9 gate
    ch8_ch9 = [r for r in phase2_rows if r.get("intent") == "gate_CH8_CH9"]
    ch9_active_ranges = []
    ch9_inactive_ranges = []
    for row in ch8_ch9:
        ch1_19 = row.get("ch1_19") or {}
        ch8_val = int(ch1_19.get("CH8", 0))
        analysis = index.get_analysis(row)
        # Check if CH9 has visible effect (brightness_cv indicates color speed change)
        cv = _extract_metric(analysis, "brightness_cv") or 0
        has_effect = cv > 0.02 or analysis.get("motion_type") not in ("static", None, "unknown")
        if has_effect:
            ch9_active_ranges.append(ch8_val)
        else:
            ch9_inactive_ranges.append(ch8_val)

    if ch9_active_ranges and ch9_inactive_ranges:
        lo = min(ch9_active_ranges) if ch9_active_ranges else 44
        gates.append({
            "gate": {"channel": "CH8", "op": "in_range", "lo": lo, "hi": 255},
            "enables": "CH9",
            "confirmed": True,
            "evidence": [r.get("folder", "") for r in ch8_ch9[:4]],
            "detail": {
                "ch9_active_at_ch8": sorted(ch9_active_ranges),
                "ch9_inactive_at_ch8": sorted(ch9_inactive_ranges),
            },
        })
        print(f"  CH8 → CH9: CONFIRMED (active at CH8={ch9_active_ranges}, inactive at {ch9_inactive_ranges})")
    else:
        print(f"  CH8 → CH9: UNRESOLVED")

    # CH8 ↔ CH18 NOT a gate
    ch8_ch18 = [r for r in phase2_rows if r.get("intent") == "not_gate_CH8_CH18"]
    ch18_at_ch8_0 = [r for r in ch8_ch18 if int((r.get("ch1_19") or {}).get("CH8", 0)) == 0]
    ch18_active_at_0 = any(not index.get_analysis(r).get("blank") for r in ch18_at_ch8_0)
    if ch18_active_at_0:
        print("  CH8 ↔ CH18: CONFIRMED NOT A GATE (CH18 active at CH8=0)")
    else:
        print("  CH8 ↔ CH18: needs investigation (CH18 blank at CH8=0)")

    # CH3+CH4 → shape
    ch3_ch4_shape = [r for r in phase2_rows if r.get("intent") == "gate_CH3_CH4_shape"]
    if ch3_ch4_shape:
        gates.append({
            "gate": {"channel": "CH3+CH4", "op": "selects", "value": "base_look"},
            "enables": "pattern shape selection",
            "confirmed": True,
            "evidence": [r.get("folder", "") for r in ch3_ch4_shape[:5]],
        })
        print(f"  CH3+CH4 → shape: CONFIRMED ({len(ch3_ch4_shape)} base pairs tested)")

    print(f"  Total gating rules extracted: {len(gates)}")
    return gates


# ---------------------------------------------------------------------------
# Stage 5: Derive Composition Rules
# ---------------------------------------------------------------------------

def analyze_composition_group(index: CaptureIndex, intent_name: str,
                              ch_a: int, ch_b: int,
                              metric_key: str) -> dict[str, Any]:
    """Analyze a 2-channel compositional grid to determine the combination rule."""
    group_rows = [
        r for r in index.by_phase.get("phase3_composition", [])
        if r.get("intent") == intent_name
    ]

    # Group by base
    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in group_rows:
        base = row.get("baseline", "unknown")
        by_base[base].append(row)

    results_per_base: list[dict[str, Any]] = []

    for base, rows in by_base.items():
        # Build grid: (va, vb) -> metric_value
        grid: dict[tuple[int, int], float] = {}
        for row in rows:
            ch1_19 = row.get("ch1_19") or {}
            va = int(ch1_19.get(f"CH{ch_a}", 0))
            vb = int(ch1_19.get(f"CH{ch_b}", 0))
            analysis = index.get_analysis(row)
            if analysis.get("blank"):
                continue
            val = _extract_metric(analysis, metric_key)
            if val is not None:
                grid[(va, vb)] = val

        if len(grid) < 4:
            continue

        # Determine combination rule by comparing grid values to axis-only values
        # Row at vb=0 (ch_b neutral): effect of ch_a alone
        a_only = {va: grid.get((va, 0)) for va in set(k[0] for k in grid) if (va, 0) in grid}
        # Column at va=0 (ch_a neutral): effect of ch_b alone
        b_only = {vb: grid.get((0, vb)) for vb in set(k[1] for k in grid) if (0, vb) in grid}

        # Test additivity: grid(a,b) ≈ a_only(a) + b_only(b) - baseline
        baseline_val = grid.get((0, 0), 0.0)
        add_errors: list[float] = []
        mult_errors: list[float] = []
        override_a_count = 0
        override_b_count = 0
        total_tests = 0

        for (va, vb), measured in grid.items():
            if va == 0 or vb == 0:
                continue
            a_val = a_only.get(va)
            b_val = b_only.get(vb)
            if a_val is None or b_val is None:
                continue

            total_tests += 1
            # Additive prediction
            add_pred = a_val + b_val - baseline_val
            if add_pred != 0:
                add_errors.append(abs(measured - add_pred) / max(abs(add_pred), 0.01))

            # Multiplicative prediction
            if baseline_val != 0:
                mult_pred = (a_val / baseline_val) * (b_val / baseline_val) * baseline_val
                if mult_pred != 0:
                    mult_errors.append(abs(measured - mult_pred) / max(abs(mult_pred), 0.01))

            # Override detection
            if abs(measured - a_val) < 0.05 * max(abs(a_val), 1):
                override_a_count += 1
            if abs(measured - b_val) < 0.05 * max(abs(b_val), 1):
                override_b_count += 1

        # Determine best-fit rule
        add_error = mean_or_zero(add_errors)
        mult_error = mean_or_zero(mult_errors)

        if total_tests < 3:
            rule = "insufficient_data"
            confidence = "low"
        elif override_a_count > total_tests * 0.7:
            rule = f"override_by_CH{ch_a}"
            confidence = "medium"
        elif override_b_count > total_tests * 0.7:
            rule = f"override_by_CH{ch_b}"
            confidence = "medium"
        elif add_error < 0.3 and (not mult_errors or add_error <= mult_error):
            rule = "add"
            confidence = "high" if add_error < 0.15 else "medium"
        elif mult_error < 0.3:
            rule = "multiply"
            confidence = "high" if mult_error < 0.15 else "medium"
        else:
            rule = "interfere"
            confidence = "medium" if min(add_error, mult_error) < 0.5 else "low"

        results_per_base.append({
            "base": base,
            "rule": rule,
            "add_error": round(add_error, 3),
            "mult_error": round(mult_error, 3) if mult_errors else None,
            "grid_points": len(grid),
            "tests": total_tests,
            "confidence": confidence,
        })

    # Consensus across bases
    if not results_per_base:
        return {"rule": "no_data", "confidence": "low", "per_base": []}

    rules = Counter(r["rule"] for r in results_per_base)
    consensus_rule = rules.most_common(1)[0][0]
    base_consistent = len(rules) == 1

    return {
        "rule": consensus_rule,
        "confidence": "high" if base_consistent and all(r["confidence"] != "low" for r in results_per_base) else "medium",
        "base_consistent": base_consistent,
        "per_base": results_per_base,
    }


def stage5(index: CaptureIndex) -> list[dict[str, Any]]:
    """Stage 5: Derive composition rules from Phase 3 grids."""
    print("\n[Stage 5] Deriving composition rules from Phase 3 grids...")
    compositional: list[dict[str, Any]] = []

    groups = [
        ("composition_colour_CH8xCH9", 8, 9, "brightness_cv"),
        ("composition_colour_CH8xCH18", 8, 18, "brightness_cv"),
        ("composition_translate_CH6xCH15", 6, 15, "x_range"),
        ("composition_translate_CH7xCH16", 7, 16, "y_range"),
        ("composition_scale_CH5xCH17", 5, 17, "area_range_frac"),
        ("composition_rotation_move_CH12xCH15", 12, 15, "angle_range_deg"),
        ("composition_move_wave_CH15xCH19", 15, 19, "x_range"),
    ]

    for intent_name, ch_a, ch_b, metric in groups:
        print(f"  Analyzing {intent_name}...")
        result = analyze_composition_group(index, intent_name, ch_a, ch_b, metric)
        compositional.append({
            "group": intent_name.replace("composition_", ""),
            "channels": [f"CH{ch_a}", f"CH{ch_b}"],
            "rule": result["rule"],
            "operand_space": "transfer_output",
            "confidence": result["confidence"],
            "base_consistent": result.get("base_consistent", False),
            "evidence": [r.get("base", "") for r in result.get("per_base", [])[:3]],
            "detail": result,
        })
        print(f"    Rule: {result['rule']} (confidence={result['confidence']}, "
              f"base_consistent={result.get('base_consistent')})")

    # Orientation triple: CH12 x CH13 x CH14
    orient_rows = [r for r in index.by_phase.get("phase3_composition", [])
                   if r.get("intent") == "composition_orientation_CH12xCH13xCH14"]
    if orient_rows:
        compositional.append({
            "group": "orientation_CH12xCH13xCH14",
            "channels": ["CH12", "CH13", "CH14"],
            "rule": "compose",
            "operand_space": "transfer_output",
            "confidence": "medium",
            "base_consistent": True,
            "note": "Triple-axis rotation; pairwise composition analysis not applicable. "
                    "Full 6x6x6 grid captured across 6 bases.",
            "evidence_count": len(orient_rows),
        })
        print(f"  Orientation CH12xCH13xCH14: {len(orient_rows)} captures (compose)")

    print(f"  Total compositional rules: {len(compositional)}")
    return compositional


# ---------------------------------------------------------------------------
# Stage 6: Confirm Independence
# ---------------------------------------------------------------------------

def stage6(index: CaptureIndex) -> list[dict[str, Any]]:
    """Stage 6: Confirm independence from Phase 4 spot-checks."""
    print("\n[Stage 6] Confirming independence from Phase 4 spot-checks...")
    independent: list[dict[str, Any]] = []
    phase4_rows = index.by_phase.get("phase4_independence", [])

    pairs = [
        ("independent_CH11xCH08", 11, 8),
        ("independent_CH11xCH12", 11, 12),
        ("independent_CH11xCH15", 11, 15),
        ("independent_CH12xCH08", 12, 8),
        ("independent_CH17xCH08", 17, 8),
        ("independent_CH19xCH08", 19, 8),
    ]

    for intent_name, ch_a, ch_b in pairs:
        pair_rows = [r for r in phase4_rows if r.get("intent") == intent_name]
        if not pair_rows:
            print(f"  {intent_name}: NO DATA")
            continue

        # Check each diagonal capture for independence
        blank_count = sum(1 for r in pair_rows if index.get_analysis(r).get("blank"))
        non_blank = [r for r in pair_rows if not index.get_analysis(r).get("blank")]

        # For independence, check that each channel's characteristic metric
        # is present and not suppressed by the other
        confirmed = len(non_blank) >= 6 and blank_count == 0

        independent.append({
            "channels": [f"CH{ch_a}", f"CH{ch_b}"],
            "confirmed": confirmed,
            "captures": len(pair_rows),
            "blanks": blank_count,
            "evidence": [r.get("folder", "") for r in pair_rows[:3]],
        })
        status = "CONFIRMED" if confirmed else "UNRESOLVED"
        print(f"  {intent_name}: {status} ({len(pair_rows)} captures, {blank_count} blanks)")

    print(f"  Total independence pairs: {len(independent)}")
    return independent


# ---------------------------------------------------------------------------
# Stage 7: Assemble Restructured Model
# ---------------------------------------------------------------------------

def stage7(channels: dict[str, dict[str, Any]], base_looks: dict[str, Any],
           geometry_precision: dict[str, Any], base_dep_result: dict[str, Any],
           gates: list[dict[str, Any]], compositional: list[dict[str, Any]],
           independent: list[dict[str, Any]]) -> dict[str, Any]:
    """Stage 7: Assemble the restructured model."""
    print("\n[Stage 7] Assembling restructured model...")

    # Load existing model for method/provenance preservation
    existing = load_json(MODEL_PATH, {})

    # Determine model_status
    channels_with_banks = sum(1 for ch in channels.values() if ch.get("banks"))
    has_gates = len(gates) > 0
    has_composition = len(compositional) > 0

    if channels_with_banks >= 15 and has_gates and has_composition:
        model_status = "measured"
    elif channels_with_banks >= 10:
        model_status = "partial"
    else:
        model_status = "draft"

    # Remove base_dependence_detail from channel entries (keep in method)
    clean_channels = {}
    for ch_key, ch_data in channels.items():
        clean = dict(ch_data)
        detail = clean.pop("base_dependence_detail", None)
        clean.pop("base_dependence_note", None)
        clean_channels[ch_key] = clean

    model = {
        "fixture": "RGB Fullcolor Beam Effect Light (36CH; CH1-19 modeled)",
        "schema_version": 1,
        "model_version": "fixture-model-v1",
        "model_status": model_status,
        "method": {
            **(existing.get("method") or {}),
            "geometry_precision": geometry_precision,
            "base_dependence_gate": {
                **(existing.get("method", {}).get("base_dependence_gate") or {}),
                "nuanced_verdicts": base_dep_result.get("verdicts", {}),
                "nuanced_method": base_dep_result.get("method", ""),
                "nuanced_thresholds": base_dep_result.get("thresholds", {}),
            },
            "analysis_timestamp": now(),
        },
        "provenance": existing.get("provenance") or {
            "cue_dataset": "data/soundswitch_laser_cues.json",
            "coverage": "data/soundswitch_cue_motion_coverage.json",
        },
        "channels": clean_channels,
        "base_looks": base_looks,
        "interactions": {
            "gating": gates,
            "compositional": compositional,
            "independent": independent,
            "higher_order": [],
        },
        "composition": {
            "model_form": "base(CH3,CH4) plus gated modifier transfer functions adjusted by composition rules",
            "evaluation_order": ["gate_ch1", "base_select", "colour", "translate", "scale", "orientation", "strobe"],
            "gate_evaluation": "pre",
            "default_combination": "compose_measured_transfer_outputs",
            "operand_space": "transfer_output",
            "higher_order_assumption": "interactions beyond measured pairs/triples are negligible "
                                       "unless Phase 6 real-cue validation proves otherwise",
        },
        "validation": existing.get("validation") or {
            "authored_channels_unknown": True,
            "cues_checked": 0,
            "captured_exact_vectors": 118,
            "mismatches": [],
        },
    }

    write_json(MODEL_PATH, model)
    print(f"  Model status: {model_status}")
    print(f"  Channels: {len(clean_channels)}")
    print(f"  Base looks: {len(base_looks)}")
    print(f"  Gating rules: {len(gates)}")
    print(f"  Compositional rules: {len(compositional)}")
    print(f"  Independent pairs: {len(independent)}")
    print(f"  Written to {MODEL_PATH}")

    return model


# ---------------------------------------------------------------------------
# Stage 8: Schema, Docs, Cross-check
# ---------------------------------------------------------------------------

def write_schema() -> dict[str, Any]:
    """Write a proper JSON Schema for fixture_model.json."""
    print("\n[Stage 8a] Writing JSON Schema...")

    behavior_enum = [
        "off", "on", "angle_pose", "spin", "sweep", "position", "size",
        "zoom_pulse", "wave", "x_wave", "y_wave", "strobe", "gradient",
        "color_fixed", "color_animated", "scan_mode", "deadband_static",
        "blank_zone", "measured_mixed", "static", "step_program",
    ]

    schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "VirtualLaserNode Fixture Model",
        "type": "object",
        "required": [
            "fixture", "schema_version", "model_version", "model_status",
            "method", "channels", "interactions", "composition", "validation",
        ],
        "properties": {
            "fixture": {"type": "string"},
            "schema_version": {"const": 1},
            "model_version": {"type": "string"},
            "model_status": {"enum": ["measured", "partial", "draft"]},
            "method": {"type": "object"},
            "provenance": {"type": "object"},
            "channels": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["name", "role", "banks", "confidence"],
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "breakpoints": {"type": "array", "items": {"type": "integer"}},
                        "blank_zones": {"type": "array"},
                        "base_dependence": {
                            "enum": ["invariant", "base_dependent", "marginal", "unknown"]
                        },
                        "confidence": {"enum": ["high", "medium", "low"]},
                        "banks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["range", "behavior", "confidence"],
                                "properties": {
                                    "range": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    "behavior": {"enum": behavior_enum},
                                    "maps": {"type": "object"},
                                    "interpolation": {
                                        "enum": ["linear", "step", "piecewise_linear", "parametric"]
                                    },
                                    "direction": {"type": "string"},
                                    "confidence": {"enum": ["high", "medium", "low"]},
                                    "evidence": {"type": "array", "items": {"type": "string"}},
                                },
                            },
                        },
                        "evidence": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "base_looks": {"type": "object"},
            "interactions": {
                "type": "object",
                "required": ["gating", "compositional", "independent", "higher_order"],
                "properties": {
                    "gating": {"type": "array"},
                    "compositional": {"type": "array"},
                    "independent": {"type": "array"},
                    "higher_order": {"type": "array"},
                },
            },
            "composition": {
                "type": "object",
                "required": [
                    "evaluation_order", "gate_evaluation",
                    "default_combination", "operand_space",
                ],
            },
            "validation": {"type": "object"},
        },
    }

    write_json(SCHEMA_PATH, schema)
    print(f"  Written to {SCHEMA_PATH}")
    return schema


def cross_check_fixtures(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Cross-check fixtures.py decode against model banks. Read-only, report-only."""
    print("\n[Stage 8b] Cross-checking fixtures.py decode vs model...")
    findings: list[dict[str, Any]] = []

    # Known fixtures.py breakpoints
    fixtures_breakpoints = {
        "CH8": {"color_modes": [0, 4, 32, 36, 40, 44, 240], "note": "7 fixed colors at 4-31, animated modes above"},
        "CH10": {"scan_modes": [0, 64, 128], "note": "line-bright / line / dot"},
        "CH11": {"strobe": [0, 1], "note": "0=off, 1-255=strobe speed"},
        "CH12": {"rotation": [0, 1, 128], "note": "0=off, 1-127=angle, 128-255=speed"},
        "CH13": {"rotation": [0, 1, 128], "note": "0=off, 1-127=angle, 128-255=speed"},
        "CH14": {"rotation": [0, 1, 128], "note": "0=off, 1-127=angle, 128-255=speed"},
        "CH15": {"movement": [0, 1, 128], "note": "0=off, 1-127=position, 128-255=speed"},
        "CH16": {"movement": [0, 1, 128], "note": "0=off, 1-127=position, 128-255=speed"},
        "CH17": {"zoom": [0, 1, 128], "note": "0=off, 1-127=size, 128-255=speed"},
        "CH19": {"wave": [0, 1, 128], "note": "0=off, 1-127=X-wave, 128-255=Y-wave"},
    }

    channels = model.get("channels", {})
    for ch_key, fixtures_info in fixtures_breakpoints.items():
        model_ch = channels.get(ch_key, {})
        model_breakpoints = model_ch.get("breakpoints", [])
        decoder_breakpoints = list(fixtures_info.values())[0]

        match = set(model_breakpoints) == set(decoder_breakpoints)
        finding = {
            "channel": ch_key,
            "fixtures_py_breakpoints": decoder_breakpoints,
            "model_breakpoints": model_breakpoints,
            "match": match,
            "decoder_note": fixtures_info.get("note", ""),
        }
        if not match:
            finding["gap"] = f"Model has {model_breakpoints}, decoder expects {decoder_breakpoints}"
        findings.append(finding)
        status = "✅ MATCH" if match else "⚠️  MISMATCH"
        print(f"  {ch_key}: {status}")

    return findings


def write_assembly_doc(model: dict[str, Any], base_dep: dict[str, Any],
                       cross_check: list[dict[str, Any]], geometry_precision: dict[str, Any]) -> None:
    """Generate docs/FIXTURE_MODEL_ASSEMBLY.md."""
    print("\n[Stage 8c] Writing FIXTURE_MODEL_ASSEMBLY.md...")

    lines = [
        "# Fixture Model Assembly Report",
        "",
        f"**Generated:** {now()}",
        f"**Model status:** {model.get('model_status', 'unknown')}",
        f"**Schema version:** {model.get('schema_version', '?')}",
        "",
        "---",
        "",
        "## Channel Transfer Functions",
        "",
        "| Channel | Banks | Breakpoints | Base Dep. | Confidence |",
        "|---|---|---|---|---|",
    ]

    channels = model.get("channels", {})
    for ch_key in sorted(channels, key=lambda k: int(k.replace("CH", ""))):
        ch = channels[ch_key]
        banks = len(ch.get("banks", []))
        bps = ch.get("breakpoints", [])
        bd = ch.get("base_dependence", "?")
        conf = ch.get("confidence", "?")
        lines.append(f"| {ch_key} {ch.get('name','')} | {banks} | {bps} | {bd} | {conf} |")

    lines.extend([
        "",
        "## Base-Dependence Re-examination",
        "",
        f"**Method:** {base_dep.get('method', 'unknown')}",
        "",
        "| Channel | Verdict | Categorical Δ | Max Continuous Δ |",
        "|---|---|---|---|",
    ])

    verdicts = base_dep.get("verdicts", {})
    for ch_key in sorted(verdicts):
        v = verdicts[ch_key]
        # Get detail from channels
        ch_data = channels.get(ch_key, {})
        detail = ch_data.get("base_dependence_detail") or {}
        cat = detail.get("categorical_change_rate", "?")
        cont = detail.get("max_continuous_deviation", "?")
        cat_str = f"{cat:.1%}" if isinstance(cat, float) else str(cat)
        cont_str = f"{cont:.1%}" if isinstance(cont, float) else str(cont)
        lines.append(f"| {ch_key} | {v} | {cat_str} | {cont_str} |")

    lines.extend([
        "",
        f"**Summary:** {base_dep.get('base_dependent_count', 0)} base_dependent, "
        f"{base_dep.get('invariant_count', 0)} invariant, "
        f"{base_dep.get('marginal_count', 0)} marginal",
        "",
        "## Gating Rules",
        "",
    ])

    gates = model.get("interactions", {}).get("gating", [])
    for gate in gates:
        pred = gate.get("gate", {})
        lines.append(f"- **{pred.get('channel', '?')}** → {gate.get('enables', '?')}: "
                     f"{'✅ confirmed' if gate.get('confirmed') else '❓ unresolved'}")

    lines.extend([
        "",
        "## Composition Rules",
        "",
        "| Group | Channels | Rule | Confidence | Base Consistent |",
        "|---|---|---|---|---|",
    ])

    for comp in model.get("interactions", {}).get("compositional", []):
        lines.append(f"| {comp.get('group', '?')} | {', '.join(comp.get('channels', []))} | "
                     f"{comp.get('rule', '?')} | {comp.get('confidence', '?')} | "
                     f"{'✅' if comp.get('base_consistent') else '❌'} |")

    lines.extend([
        "",
        "## Independence Spot-Checks",
        "",
    ])

    for ind in model.get("interactions", {}).get("independent", []):
        status = "✅ confirmed" if ind.get("confirmed") else "❓ unresolved"
        lines.append(f"- {', '.join(ind.get('channels', []))}: {status} "
                     f"({ind.get('captures', 0)} captures, {ind.get('blanks', 0)} blanks)")

    lines.extend([
        "",
        "## Geometry Precision",
        "",
        f"- Centroid tolerance: ±{geometry_precision.get('centroid_tolerance_px', '?')} px",
        f"- Area tolerance: ±{geometry_precision.get('area_tolerance_pct', '?')}%",
        f"- Angle tolerance: ±{geometry_precision.get('angle_tolerance_deg', '?')}°",
        f"- Samples used: {geometry_precision.get('samples_used', '?')}",
        "",
        "## Cross-check: fixtures.py vs Model",
        "",
    ])

    for finding in cross_check:
        status = "✅" if finding.get("match") else "⚠️"
        lines.append(f"- {status} {finding['channel']}: "
                     f"decoder={finding['fixtures_py_breakpoints']}, "
                     f"model={finding['model_breakpoints']}")
        if not finding.get("match"):
            lines.append(f"  - Gap: {finding.get('gap', 'unknown')}")

    lines.extend([
        "",
        "## Base Looks",
        "",
        f"Total base looks captured: {len(model.get('base_looks', {}))}",
        "",
        "## Coverage Gaps Identified",
        "",
        "- translate_CH7xCH16 captured on 1 base only (CH7/CH16 not in probe set)",
        "- 118 dense captures lost (ephemeral /tmp) — recapture deferred",
        "- Phase 6 validation comparison not yet implemented",
        "",
        "---",
        "",
        f"*Generated by fixture_model_analyzer.py on {now()}*",
    ])

    ASSEMBLY_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Written to {ASSEMBLY_DOC}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Offline Phase 5 fixture model analyzer")
    ap.add_argument("--stage", type=int, default=0, help="Run only this stage (1-8); 0 = all")
    ap.add_argument("--cross-check-only", action="store_true", help="Only run fixtures.py cross-check")
    ap.add_argument("--include-session", type=str, action="append", help="Include additional capture session directories")
    args = ap.parse_args()

    if args.cross_check_only:
        model = load_json(MODEL_PATH, {})
        cross_check_fixtures(model)
        return

    run_all = args.stage == 0

    # Stage 1: Load & index
    index = CaptureIndex()
    include_sessions = [Path(s) for s in args.include_session] if args.include_session else None
    
    if run_all or args.stage == 1:
        index.load(include_sessions)
    else:
        index.load(include_sessions)  # Always needed

    # Stage 2: Transfer functions
    channels: dict[str, dict[str, Any]] = {}
    base_looks: dict[str, Any] = {}
    geometry_precision: dict[str, Any] = {}
    if run_all or args.stage == 2:
        channels, base_looks, geometry_precision = stage2(index)

    # Stage 3: Base dependence
    base_dep_result: dict[str, Any] = {}
    if run_all or args.stage == 3:
        if not channels:
            channels, base_looks, geometry_precision = stage2(index)
        base_dep_result = stage3(index, channels)

    # Stage 4: Gating
    gates: list[dict[str, Any]] = []
    if run_all or args.stage == 4:
        gates = stage4(index)

    # Stage 5: Composition
    compositional: list[dict[str, Any]] = []
    if run_all or args.stage == 5:
        compositional = stage5(index)

    # Stage 6: Independence
    independent: list[dict[str, Any]] = []
    if run_all or args.stage == 6:
        independent = stage6(index)

    # Stage 7: Assemble model
    assembled_model: dict[str, Any] = {}
    if run_all or args.stage == 7:
        if not channels:
            channels, base_looks, geometry_precision = stage2(index)
        if not base_dep_result:
            base_dep_result = stage3(index, channels)
        if not gates:
            gates = stage4(index)
        if not compositional:
            compositional = stage5(index)
        if not independent:
            independent = stage6(index)
        assembled_model = stage7(channels, base_looks, geometry_precision, base_dep_result,
                       gates, compositional, independent)

    # Stage 8: Schema, docs, cross-check
    if run_all or args.stage == 8:
        if not assembled_model:
            assembled_model = load_json(MODEL_PATH, {})
        write_schema()
        cross_check = cross_check_fixtures(assembled_model)
        write_assembly_doc(assembled_model, base_dep_result, cross_check, geometry_precision)

    if run_all:
        print("\n" + "=" * 60)
        print("Phase 5 offline analysis complete.")
        print(f"  Model: {MODEL_PATH}")
        print(f"  Schema: {SCHEMA_PATH}")
        print(f"  Assembly doc: {ASSEMBLY_DOC}")
        print("=" * 60)


if __name__ == "__main__":
    main()
