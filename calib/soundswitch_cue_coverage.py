#!/usr/bin/env python3
"""
Bridge real SoundSwitch laser cue states to timed CH1-19 capture evidence.

This is an evidence integration pass only. It validates the extracted
SoundSwitch cue dataset, compares each cue's CH1-19 vector against the timed
motion scaffold, and writes a machine-readable coverage map plus a markdown
summary. It does not change renderer behavior or calibration values.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / "vln_ss_analysis" / "soundswitch_laser_cues.json"
DEFAULT_LOCAL = ROOT / "data" / "soundswitch_laser_cues.json"
DEFAULT_TIMED_ROOT = Path("/tmp/vln_timed_motion_ch1_19_fine_ch4bank_20260605_1855")
DEFAULT_OUTPUT = ROOT / "data" / "soundswitch_cue_motion_coverage.json"
DEFAULT_REPORT = ROOT / "docs" / "SOUNDSWITCH_CUE_MOTION_COVERAGE.md"

CHS = tuple(range(1, 20))
TIMED_SCAFFOLD_CH3_BASES = {0, 32, 48, 96}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def cue_dmx(cue: dict[str, Any]) -> dict[int, int]:
    dmx = cue.get("dmx", {})
    return {ch: int(dmx[f"CH{ch}"]) for ch in CHS}


def capture_dmx(entry: dict[str, Any]) -> dict[int, int]:
    dmx = entry.get("full_ch1_19_dmx", {})
    return {ch: int(dmx[str(ch)]) for ch in CHS}


def vector(dmx: dict[int, int]) -> tuple[int, ...]:
    return tuple(dmx[ch] for ch in CHS)


def validate_cues(cues: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(cues) != 184:
        errors.append(f"expected 184 cues, loaded {len(cues)}")
    for idx, cue in enumerate(cues):
        prefix = f"cue[{idx}]"
        for key in ("cue_id", "cue_name", "calibration_type", "is_motion", "confidence"):
            if key not in cue:
                errors.append(f"{prefix} missing {key}")
        dmx = cue.get("dmx")
        if not isinstance(dmx, dict):
            errors.append(f"{prefix} missing dmx object")
            continue
        for ch in CHS:
            key = f"CH{ch}"
            if key not in dmx:
                errors.append(f"{prefix} missing {key}")
                continue
            try:
                val = int(dmx[key])
            except (TypeError, ValueError):
                errors.append(f"{prefix} {key} is not an integer")
                continue
            if not 0 <= val <= 255:
                errors.append(f"{prefix} {key} out of range: {val}")
    return errors


def ch3_family(value: int) -> str:
    ranges = [
        (0, 8, "ring_circle_static"),
        (16, 40, "horizontal_line_static"),
        (48, 56, "dual_dot_static"),
        (64, 120, "static_arc_swirl_bank"),
        (128, 136, "dynamic_u_wave"),
        (144, 152, "dynamic_three_star"),
        (160, 168, "dynamic_compact_swirl"),
        (176, 176, "dynamic_star_polygon"),
        (184, 216, "dynamic_line_row_variants"),
        (224, 224, "dynamic_point_dot"),
        (232, 255, "late_dynamic_variants"),
    ]
    for lo, hi, name in ranges:
        if lo <= value <= hi:
            return name
    return f"ch3_unsampled_bin_{(value // 8) * 8:03d}_{min((value // 8) * 8 + 7, 255):03d}"


def ch4_program(value: int) -> str:
    return f"ch4_program_{(value // 5) * 5:03d}_{min((value // 5) * 5 + 4, 255):03d}"


def color_family(value: int) -> str:
    if value <= 3:
        return "white_or_original"
    if value <= 31:
        return f"fixed_7_color_{(value - 4) // 4}"
    if value <= 35:
        return "colorful_change"
    if value <= 39:
        return "rgb_change"
    if value <= 43:
        return "original_colorful_change"
    if value <= 239:
        return f"flowing_water_{(value - 44) // 4}"
    return "gradient_effect"


def color_speed_family(value: int) -> str:
    if value <= 3:
        return "color_speed_off"
    if value <= 127:
        return f"color_speed_positive_{speed_bucket(value, 4, 127)}"
    return f"color_speed_reverse_{speed_bucket(value, 128, 255)}"


def strobe_family(value: int) -> str:
    if value == 0:
        return "strobe_off"
    if value <= 63:
        return "strobe_slow"
    if value <= 127:
        return "strobe_mid"
    if value <= 191:
        return "strobe_fast"
    return "strobe_very_fast"


def angle_speed_family(value: int, axis: str) -> str:
    if value == 0:
        return f"{axis}_neutral"
    if value <= 127:
        return f"{axis}_angle_{position_bucket(value)}"
    if axis == "z_rot" and value < 144:
        return f"{axis}_speed_deadband_128_143"
    return f"{axis}_speed_{speed_bucket(value, 128, 255)}"


def movement_family(value: int, axis: str) -> str:
    if value == 0:
        return f"{axis}_neutral"
    if value <= 127:
        return f"{axis}_position_{position_bucket(value)}"
    return f"{axis}_speed_{speed_bucket(value, 128, 255)}"


def zoom_family(value: int) -> str:
    if value == 0:
        return "zoom_neutral"
    if value <= 127:
        return f"zoom_size_{position_bucket(value)}"
    if value < 152:
        return "zoom_speed_deadband_128_151"
    return f"zoom_speed_{speed_bucket(value, 128, 255)}"


def gradient_family(value: int) -> str:
    if value == 0:
        return "gradient_off"
    return f"gradient_speed_{speed_bucket(value, 1, 255)}"


def wave_family(value: int) -> str:
    if value == 0:
        return "wave_off"
    if value <= 127:
        return f"x_wave_{speed_bucket(value, 1, 127)}"
    if value < 136:
        return "y_wave_deadband_128_135"
    return f"y_wave_{speed_bucket(value, 128, 255)}"


def pattern_size_family(value: int) -> str:
    if value == 0:
        return "pattern_size_default_or_max"
    return f"pattern_size_{position_bucket(value)}"


def position_family(value: int, axis: str) -> str:
    if value < 32 or value > 224:
        return f"{axis}_edge_or_blank"
    if 112 <= value <= 144:
        return f"{axis}_center"
    if value < 112:
        return f"{axis}_low"
    return f"{axis}_high"


def line_dot_family(value: int) -> str:
    if value <= 63:
        return f"brightening_line_scan_{speed_bucket(value, 0, 63)}"
    if value <= 127:
        return f"line_scan_{speed_bucket(value, 64, 127)}"
    return f"dot_scan_{speed_bucket(value, 128, 255)}"


def speed_bucket(value: int, lo: int, hi: int) -> str:
    if value <= lo:
        return "min"
    span = max(1, hi - lo)
    frac = (value - lo) / span
    if frac < 0.25:
        return "low"
    if frac < 0.5:
        return "mid_low"
    if frac < 0.75:
        return "mid_high"
    return "high"


def position_bucket(value: int) -> str:
    if value <= 31:
        return "min"
    if value <= 63:
        return "low"
    if value <= 95:
        return "mid_low"
    if value <= 127:
        return "high"
    if value <= 159:
        return "center_high"
    if value <= 191:
        return "high_mid"
    if value <= 223:
        return "very_high"
    return "max"


def families(dmx: dict[int, int]) -> dict[str, str]:
    return {
        "base": f"{ch3_family(dmx[3])}|{ch4_program(dmx[4])}",
        "ch3_family": ch3_family(dmx[3]),
        "ch4_program": ch4_program(dmx[4]),
        "ch5_size": pattern_size_family(dmx[5]),
        "ch6_x": position_family(dmx[6], "x"),
        "ch7_y": position_family(dmx[7], "y"),
        "ch8_color": color_family(dmx[8]),
        "ch9_color_speed": color_speed_family(dmx[9]),
        "ch10_scan": line_dot_family(dmx[10]),
        "ch11_strobe": strobe_family(dmx[11]),
        "ch12_z": angle_speed_family(dmx[12], "z_rot"),
        "ch13_xrot": angle_speed_family(dmx[13], "x_rot"),
        "ch14_yrot": angle_speed_family(dmx[14], "y_rot"),
        "ch15_xmove": movement_family(dmx[15], "x_move"),
        "ch16_ymove": movement_family(dmx[16], "y_move"),
        "ch17_zoom": zoom_family(dmx[17]),
        "ch18_gradient": gradient_family(dmx[18]),
        "ch19_wave": wave_family(dmx[19]),
    }


WEIGHTS = {
    "base": 10,
    "ch3_family": 18,
    "ch4_program": 4,
    "ch5_size": 4,
    "ch6_x": 4,
    "ch7_y": 4,
    "ch8_color": 8,
    "ch9_color_speed": 5,
    "ch10_scan": 3,
    "ch11_strobe": 10,
    "ch12_z": 8,
    "ch13_xrot": 6,
    "ch14_yrot": 6,
    "ch15_xmove": 8,
    "ch16_ymove": 8,
    "ch17_zoom": 7,
    "ch18_gradient": 5,
    "ch19_wave": 5,
}

ONSET_WEIGHTS = {
    "strobe": 22,
    "z_spin": 14,
    "x_rotation": 8,
    "y_rotation": 8,
    "x_move": 12,
    "y_move": 12,
    "zoom_pulse": 10,
    "zoom_static": 6,
    "color_timing": 8,
    "gradient": 5,
    "wave": 10,
    "wave_low_bank": 5,
}


def motion_signature(fam: dict[str, str]) -> tuple[str, ...]:
    keys = ("ch11_strobe", "ch12_z", "ch13_xrot", "ch14_yrot", "ch15_xmove", "ch16_ymove", "ch17_zoom", "ch18_gradient", "ch19_wave")
    neutral = ("off", "neutral", "center")
    sig: list[str] = []
    for key in keys:
        value = fam[key]
        if not any(part in value for part in neutral):
            sig.append(value)
    return tuple(sig)


def modifier_onsets(dmx: dict[int, int]) -> dict[str, bool]:
    return {
        "strobe": dmx[11] > 0,
        "z_spin": dmx[12] >= 144,
        "x_rotation": dmx[13] >= 128 or 1 <= dmx[13] <= 127,
        "y_rotation": dmx[14] >= 128 or 1 <= dmx[14] <= 127,
        "x_move": dmx[15] > 0,
        "y_move": dmx[16] > 0,
        "zoom_pulse": dmx[17] >= 152,
        "zoom_static": 1 <= dmx[17] <= 127,
        "color_timing": dmx[8] >= 32 or dmx[9] > 0,
        "gradient": dmx[18] > 0,
        "wave": dmx[19] >= 136,
        "wave_low_bank": 1 <= dmx[19] <= 127,
    }


def sampled_timed_base(fam: dict[str, str]) -> bool:
    return fam["ch3_family"] in {
        "ring_circle_static",
        "horizontal_line_static",
        "dual_dot_static",
        "static_arc_swirl_bank",
    }


def dynamic_out_of_scope(dmx: dict[int, int]) -> bool:
    return dmx[3] >= 128


def capture_usable(capture: dict[str, Any]) -> bool:
    analysis = capture.get("analysis", {})
    if analysis.get("blank"):
        return False
    return float(analysis.get("loop_confidence") or 0.0) >= 0.35


def timing_reliability(dmx: dict[int, int]) -> str:
    if dmx[11] > 0:
        return "reliable_strobe_timing"
    if any((dmx[12] >= 144, dmx[15] >= 128, dmx[16] >= 128, dmx[17] >= 152, dmx[19] >= 136)):
        return "aliased_non_strobe_timing"
    return "static_or_not_timed"


def ch18_low_evidence(dmx: dict[int, int]) -> bool:
    return dmx[18] > 0


def preset_family(fam: dict[str, str], is_motion: bool) -> str:
    parts = [fam["ch3_family"], fam["ch4_program"]]
    if "strobe_off" not in fam["ch11_strobe"]:
        parts.append("strobe")
    for key, label in (("ch12_z", "zrot"), ("ch13_xrot", "xrot"), ("ch14_yrot", "yrot"), ("ch15_xmove", "xmove"), ("ch16_ymove", "ymove")):
        if "neutral" not in fam[key] and "center" not in fam[key]:
            parts.append(label)
    if "zoom_neutral" not in fam["ch17_zoom"]:
        parts.append("zoom")
    if "gradient_off" not in fam["ch18_gradient"]:
        parts.append("gradient")
    if "wave_off" not in fam["ch19_wave"]:
        parts.append("wave")
    if is_motion and len(parts) == 2:
        parts.append("motion_macro")
    return "+".join(parts)


def compare(cue: dict[str, Any], capture: dict[str, Any]) -> tuple[int, list[str]]:
    cue_fam = cue["families"]
    cap_fam = capture["families"]
    score = 0
    matched: list[str] = []
    for key, weight in WEIGHTS.items():
        if cue_fam[key] == cap_fam[key]:
            score += weight
            matched.append(key)
    for key, weight in ONSET_WEIGHTS.items():
        if cue["modifier_onsets"][key] and cue["modifier_onsets"][key] == capture["modifier_onsets"][key]:
            score += weight
            matched.append(f"onset:{key}")
    if cue["vector"] == capture["vector"]:
        return 130, ["exact_ch1_19"]
    return score, matched


def match_type_for(cue: dict[str, Any], capture: dict[str, Any] | None, score: int, matched: list[str]) -> str:
    if capture is None:
        return "no_match"
    if "exact_ch1_19" in matched:
        return "exact_ch1_19_match"
    same_base = cue["families"]["base"] == capture["families"]["base"]
    key_modifiers = ("ch8_color", "ch11_strobe", "ch12_z", "ch13_xrot", "ch14_yrot", "ch15_xmove", "ch16_ymove", "ch17_zoom", "ch18_gradient", "ch19_wave")
    same_key_mods = all(cue["families"][k] == capture["families"][k] for k in key_modifiers)
    if same_base and same_key_mods:
        return "same_ch3_ch4_base_same_key_modifiers"
    if same_base:
        return "same_base_different_modifier_values"
    shared_onsets = {
        key for key, active in cue["modifier_onsets"].items()
        if active and active == capture["modifier_onsets"].get(key)
    }
    if shared_onsets or set(cue["motion_signature"]) & set(capture["motion_signature"]):
        return "similar_motion_family"
    if score >= 35:
        return "same_ch3_family_or_modifier_family"
    return "no_match"


def next_action(cue: dict[str, Any], match_type: str) -> str:
    fam = cue["families"]
    dmx = cue["dmx"]
    if dynamic_out_of_scope(dmx):
        return "defer"
    if ch18_low_evidence(dmx):
        return "needs_dense_breakpoint_capture"
    if dmx[11] > 0 and cue.get("has_usable_strobe_evidence"):
        return "ready_motion_mapping"
    dynamic_ch3 = fam["ch3_family"].startswith("dynamic") or fam["ch3_family"].startswith("late_dynamic")
    has_motion = bool(cue["motion_signature"]) or bool(cue["is_motion"]) or dynamic_ch3
    has_fine = any(
        "speed" in fam[key] or "flowing" in fam[key] or "gradient" in fam[key] or "wave" in fam[key]
        for key in ("ch8_color", "ch9_color_speed", "ch11_strobe", "ch12_z", "ch13_xrot", "ch14_yrot", "ch15_xmove", "ch16_ymove", "ch17_zoom", "ch18_gradient", "ch19_wave")
    )
    if match_type in {"exact_ch1_19_match", "same_ch3_ch4_base_same_key_modifiers"}:
        return "ready_motion_mapping" if has_motion else "ready_static_validation"
    if match_type == "same_base_different_modifier_values" and not has_motion:
        return "ready_static_validation"
    if has_fine:
        return "needs_dense_breakpoint_capture"
    if has_motion:
        return "needs_timed_capture"
    return "defer"


def evidence_gap_reason(cue: dict[str, Any], match_type: str, action: str) -> str:
    if action in {"ready_static_validation", "ready_motion_mapping"}:
        return ""
    if dynamic_out_of_scope(cue["dmx"]):
        return "dynamic macro - out of CH1-19 timed scope"
    if ch18_low_evidence(cue["dmx"]):
        return "CH18-driven gradient evidence is weak in the timed pass; needs dedicated dense capture"
    if match_type != "no_match":
        if action == "needs_dense_breakpoint_capture":
            return "partial scaffold match only; dense CH3-CH19 breakpoint evidence is missing for this exact cue state"
        if action == "needs_timed_capture":
            return "base/static evidence exists but timed capture is missing for this motion combination"
        return "covered only by low-priority or deferred evidence"
    fam = cue["families"]
    if not any(cap["families"]["base"] == fam["base"] for cap in cue["all_captures"]):
        return "no timed capture with same CH3 family plus CH4 program bin"
    if cue["motion_signature"]:
        return "base family exists but motion modifier combination was not captured"
    return "base family exists but exact static modifier values were not captured"


def build_report(
    report_path: Path,
    mapping: dict[str, Any],
    local_cue_path: Path,
    timed_root: Path,
    manifest_path: Path,
    analysis_path: Path,
) -> None:
    stats = mapping["statistics"]
    cue_entries = mapping["cues"]
    families_list = mapping["families"]

    lines: list[str] = [
        "# SoundSwitch cue motion coverage",
        "",
        "Evidence bridge between the extracted SoundSwitch Attribute Cue library and the timed CH1-19 motion capture scaffold.",
        "",
        "This report does not tune renderer behavior. The timed pass remains representative scaffolding; CH3-CH19 still need dense breakpoint discovery before value-by-value calibration.",
        "",
        "Quality correction: clipped captures are treated as usable when they are nonblank. The `recapture_needed` flag from the timed pass is ignored for coverage because wall-edge clipping is expected in this ROI. Usability is gated by blank=false and loop_confidence >= 0.35. Non-strobe loop-duration estimates are treated as aliased timing; CH11 strobe timing is the reliable timed family.",
        "",
        "## Inputs",
        f"- Project-local cue dataset: `{local_cue_path}`",
        f"- Timed capture root: `{timed_root}`",
        f"- Timed manifest: `{manifest_path}`",
        f"- Timed analysis manifest: `{analysis_path}`",
        "",
        "## Validation",
        f"- Cues loaded: {stats['total_cues']}",
        f"- Timed captures loaded: {stats['total_captures']}",
        f"- Usable timed captures after corrected quality gate: {stats['usable_timed_captures']}",
        f"- Blank timed captures rejected: {stats['blank_timed_captures']}",
        f"- Sampled-base cues: {stats['sampled_base_cues']}",
        f"- Unsampled-base cues: {stats['unsampled_base_cues']}",
        f"- Dynamic CH3>=128 cues deferred by design: {stats['dynamic_deferred_cues']}",
        f"- Cue dataset validation errors: {stats['validation_error_count']}",
        "",
        "## Match Statistics",
    ]
    lines.extend([
        f"- exact CH1-19 matches: {stats['match_summary']['exact']}",
        f"- partial matches: {stats['match_summary']['partial']}",
        f"- unmatched cues: {stats['match_summary']['unmatched']}",
        "",
        "Detailed match categories:",
    ])
    for key, value in stats["match_types"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Coverage Buckets",
        f"- Static cues ready for still validation: {stats['next_actions'].get('ready_static_validation', 0)}",
        f"- Motion cues strictly ready for timed renderer mapping: {stats['next_actions'].get('ready_motion_mapping', 0)}",
        f"- Motion cues with partial family evidence but not ready: {stats['motion_partial_evidence_not_ready']}",
        f"- Cues needing dense breakpoint capture: {stats['next_actions'].get('needs_dense_breakpoint_capture', 0)}",
        f"- Cues needing timed capture: {stats['next_actions'].get('needs_timed_capture', 0)}",
        f"- Deferred cues: {stats['next_actions'].get('defer', 0)}",
        "",
        "## Strobe / Color / Motion Evidence",
        f"- Strobe cues with usable evidence: {stats['special_coverage']['strobe_with_evidence']}",
        f"- Strobe cues lacking evidence: {stats['special_coverage']['strobe_without_evidence']}",
        "- Strobe is the highest-confidence timed family in this evidence set.",
        f"- Color timing cues with usable evidence: {stats['special_coverage']['color_with_evidence']}",
        f"- Color timing cues lacking evidence: {stats['special_coverage']['color_without_evidence']}",
        f"- Rotation cues with usable evidence: {stats['special_coverage']['rotation_with_evidence']}",
        f"- Rotation cues lacking evidence: {stats['special_coverage']['rotation_without_evidence']}",
        f"- Sweep/path cues with usable evidence: {stats['special_coverage']['sweep_with_evidence']}",
        f"- Sweep/path cues lacking evidence: {stats['special_coverage']['sweep_without_evidence']}",
        f"- Wave cues with usable onset evidence: {stats['special_coverage']['wave_with_evidence']}",
        f"- Wave cues lacking evidence: {stats['special_coverage']['wave_without_evidence']}",
        f"- CH18 gradient cues with strong evidence: {stats['special_coverage']['ch18_with_strong_evidence']}",
        f"- CH18 gradient cues marked low-evidence: {stats['special_coverage']['ch18_low_evidence']}",
        "",
        "## Top Cue Families",
        "",
        "| family | cues | representative cue | dominant next action | usable evidence |",
        "|---|---:|---|---|---:|",
    ])
    for fam in families_list[:20]:
        lines.append(
            f"| `{fam['family_key']}` | {fam['cue_count']} | {fam['representative_cue_name']} | "
            f"{fam['dominant_next_action']} | {fam['usable_evidence_count']} |"
        )

    ready = [c for c in cue_entries if c["recommended_next_action"] in {"ready_static_validation", "ready_motion_mapping"}]
    needs = [c for c in cue_entries if c["recommended_next_action"] in {"needs_dense_breakpoint_capture", "needs_timed_capture"}]
    color_only = [fam for fam in families_list if "+strobe" not in fam["family_key"] and "+xmove" not in fam["family_key"] and "+ymove" not in fam["family_key"] and "+zrot" not in fam["family_key"] and "+xrot" not in fam["family_key"] and "+yrot" not in fam["family_key"] and "+wave" not in fam["family_key"] and "+gradient" not in fam["family_key"]]
    motion_preset = [fam for fam in families_list if any(token in fam["family_key"] for token in ("+strobe", "+xmove", "+ymove", "+zrot", "+xrot", "+yrot", "+zoom", "+wave", "+gradient"))]
    unsupported = [fam for fam in families_list if fam["usable_evidence_count"] == 0 and fam["cue_count"] >= 2]
    lines.extend([
        "",
        "## Cues Ready For Renderer Mapping",
        "",
        "| cue | type | match | preset family | capture |",
        "|---|---|---|---|---|",
    ])
    for cue in ready[:30]:
        lines.append(
            f"| {cue['cue_name']} | {cue['calibration_type']} | {cue['match_type']} | "
            f"`{cue['recommended_renderer_preset_family']}` | `{cue.get('best_capture_match_id') or ''}` |"
        )

    lines.extend([
        "",
        "## Cues Needing More Capture",
        "",
        "| cue | type | next action | missing evidence | preset family |",
        "|---|---|---|---|---|",
    ])
    for cue in needs[:40]:
        lines.append(
            f"| {cue['cue_name']} | {cue['calibration_type']} | {cue['recommended_next_action']} | "
            f"{cue['missing_evidence_reason']} | `{cue['recommended_renderer_preset_family']}` |"
        )

    lines.extend([
        "",
        "## Family Classification",
        "",
        f"- Families with many members: {sum(1 for fam in families_list if fam['cue_count'] >= 3)}",
        f"- Families likely needing only base/color/static validation: {len(color_only)}",
        f"- Families needing motion or timing presets: {len(motion_preset)}",
        f"- Repeated families unsupported by strict current evidence: {len(unsupported)}",
        "",
        "Top repeated unsupported families:",
        "",
        "| family | cues | representative cue |",
        "|---|---:|---|",
    ])
    for fam in unsupported[:15]:
        lines.append(f"| `{fam['family_key']}` | {fam['cue_count']} | {fam['representative_cue_name']} |")

    lines.extend([
        "",
        "## Cue Simulation Mode Plan",
        "",
        "- Cue browser backed by `data/soundswitch_cue_motion_coverage.json`.",
        "- Cue detail panel showing cue name, cue id, calibration type, confidence, and raw CH1-19 values.",
        "- Match status panel showing exact/partial/no-match coverage and linked timed capture evidence.",
        "- Calibration status badges: ready static validation, ready motion mapping, needs dense breakpoint capture, needs timed capture, defer.",
        "- Capture recommendation panel showing which CH3+CH4 base or CH5-CH19 modifier range should be captured next.",
        "- Render preset preview field using the recommended preset family, but without changing renderer behavior until evidence-backed tuning begins.",
        "",
        "## Evidence Priority",
        "",
        "1. CH11 strobe timing: highest-confidence timed evidence. Use this family first for timing implementation.",
        "2. Static/base look families with sampled CH3 bank evidence: useful for still validation, but CH4 values remain sparse.",
        "3. Modifier-onset motion families: useful for deciding which motion preset is needed, but non-strobe rate estimates are aliased.",
        "4. CH18 gradient families: low evidence in this pass; require dedicated dense capture.",
        "5. CH3>=128 dynamic macro cues: deferred because they were intentionally excluded from this deterministic timed pass.",
        "",
        "## Recommended Renderer Work Order",
        "",
        "1. Static cues with exact or near capture evidence.",
        "2. Gradient/static-color cue families.",
        "3. Strobe timing families.",
        "4. Rotation/spin families.",
        "5. Sweep/path motion families.",
        "6. Wave, gradient-speed, and color-speed families.",
        "7. Haze/volumetric tuning last.",
        "",
        "## Exact Next Step",
        "",
        "Run dense breakpoint discovery for CH3-CH19 using the top cue families above as the sampling guide. Prioritize repeated SoundSwitch cue families over theoretical channel coverage, then add timed captures only for representative ranges and combinations that the current scaffold cannot explain.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(args: argparse.Namespace) -> None:
    source = Path(args.source).expanduser()
    local = Path(args.local).expanduser()
    timed_root = Path(args.timed_root).expanduser()
    output = Path(args.output).expanduser()
    report = Path(args.report).expanduser()

    local.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != local.resolve():
        shutil.copyfile(source, local)

    cues_raw = load_json(local)
    if not isinstance(cues_raw, list):
        raise SystemExit(f"cue dataset must be a list: {local}")
    validation_errors = validate_cues(cues_raw)

    manifest_path = timed_root / "manifest.jsonl"
    analysis_path = timed_root / "analysis_manifest.jsonl"
    captures_raw = load_jsonl(analysis_path)
    manifest_count = len(load_jsonl(manifest_path))

    captures: list[dict[str, Any]] = []
    for entry in captures_raw:
        dmx = capture_dmx(entry)
        fam = families(dmx)
        captures.append({
            "test_id": entry["test_id"],
            "test_name": entry.get("test_name", ""),
            "group": entry.get("group", ""),
            "capture_path": entry.get("capture", ""),
            "strip_path": entry.get("strip", ""),
            "dmx": dmx,
            "vector": vector(dmx),
            "families": fam,
            "modifier_onsets": modifier_onsets(dmx),
            "motion_signature": motion_signature(fam),
            "analysis": entry.get("analysis", {}),
            "capture_quality_usable": capture_usable(entry),
            "timing_reliability": timing_reliability(dmx),
            "active_channels": entry.get("active_channels_changed_from_baseline", {}),
        })

    usable_captures = [cap for cap in captures if cap["capture_quality_usable"]]
    exact = {cap["vector"]: cap for cap in usable_captures}
    usable_strobe_captures = [cap for cap in usable_captures if cap["dmx"][11] > 0]
    cue_entries: list[dict[str, Any]] = []

    for cue in cues_raw:
        dmx = cue_dmx(cue)
        fam = families(dmx)
        prepared = {
            "vector": vector(dmx),
            "dmx": dmx,
            "families": fam,
            "modifier_onsets": modifier_onsets(dmx),
            "motion_signature": motion_signature(fam),
            "is_motion": bool(cue.get("is_motion")),
            "has_usable_strobe_evidence": bool(usable_strobe_captures),
            "all_captures": captures,
        }
        best = exact.get(prepared["vector"])
        best_score = 130 if best else -1
        best_matched = ["exact_ch1_19"] if best else []
        if best is None:
            for cap in usable_captures:
                score, matched = compare(prepared, cap)
                if score > best_score:
                    best = cap
                    best_score = score
                    best_matched = matched
        match_type = match_type_for(prepared, best, best_score, best_matched)
        if match_type == "no_match":
            best_for_output = None
            confidence = 0.0
        else:
            best_for_output = best
            base_confidence = min(1.0, best_score / 100.0)
            if dmx[11] > 0 and usable_strobe_captures:
                base_confidence = max(base_confidence, 0.82)
            elif timing_reliability(dmx) == "aliased_non_strobe_timing":
                base_confidence = min(base_confidence, 0.62)
            if ch18_low_evidence(dmx):
                base_confidence = min(base_confidence, 0.45)
            confidence = round(base_confidence, 3)
        action = next_action(prepared, match_type)
        reliability = timing_reliability(dmx)
        if dynamic_out_of_scope(dmx):
            evidence_quality = "defer_dynamic_macro"
        elif ch18_low_evidence(dmx):
            evidence_quality = "low_ch18_evidence"
        elif dmx[11] > 0 and usable_strobe_captures:
            evidence_quality = "high_strobe_timing_evidence"
        elif reliability == "aliased_non_strobe_timing":
            evidence_quality = "medium_onset_evidence_aliased_timing"
        elif match_type != "no_match":
            evidence_quality = "medium_family_evidence"
        else:
            evidence_quality = "no_evidence"
        entry = {
            "cue_id": cue["cue_id"],
            "cue_name": cue["cue_name"],
            "ch1_19": {f"CH{ch}": dmx[ch] for ch in CHS},
            "calibration_type": cue["calibration_type"],
            "is_motion": bool(cue["is_motion"]),
            "confidence": cue["confidence"],
            "best_capture_match_id": best_for_output["test_id"] if best_for_output else None,
            "best_capture_path": best_for_output["capture_path"] if best_for_output else None,
            "best_capture_motion_type": (best_for_output.get("analysis", {}).get("motion_type") if best_for_output else None),
            "best_capture_quality_usable": (best_for_output.get("capture_quality_usable") if best_for_output else None),
            "best_capture_loop_confidence": (best_for_output.get("analysis", {}).get("loop_confidence") if best_for_output else None),
            "match_type": match_type,
            "match_confidence": confidence,
            "evidence_quality": evidence_quality,
            "timing_reliability": reliability,
            "strobe_timing_evidence_usable": bool(dmx[11] > 0 and usable_strobe_captures),
            "modifier_onsets": prepared["modifier_onsets"],
            "matched_family_keys": best_matched if best_for_output else [],
            "missing_evidence_reason": evidence_gap_reason(prepared, match_type, action),
            "recommended_renderer_preset_family": preset_family(fam, bool(cue["is_motion"])),
            "recommended_next_action": action,
            "family_key": preset_family(fam, bool(cue["is_motion"])),
            "base_family": fam["base"],
            "motion_signature": list(prepared["motion_signature"]),
        }
        cue_entries.append(entry)

    match_counts = Counter(c["match_type"] for c in cue_entries)
    ordered_match_counts = {
        "exact_ch1_19_match": match_counts.get("exact_ch1_19_match", 0),
        "same_ch3_ch4_base_same_key_modifiers": match_counts.get("same_ch3_ch4_base_same_key_modifiers", 0),
        "same_base_different_modifier_values": match_counts.get("same_base_different_modifier_values", 0),
        "similar_motion_family": match_counts.get("similar_motion_family", 0),
        "same_ch3_family_or_modifier_family": match_counts.get("same_ch3_family_or_modifier_family", 0),
        "no_match": match_counts.get("no_match", 0),
    }
    action_counts = Counter(c["recommended_next_action"] for c in cue_entries)
    sampled_base_cues = sum(1 for cue in cue_entries if cue["ch1_19"]["CH3"] in TIMED_SCAFFOLD_CH3_BASES)
    usable_timed_captures = sum(1 for cap in captures if cap["capture_quality_usable"])
    blank_timed_captures = sum(1 for cap in captures if cap["analysis"].get("blank"))

    def has_evidence(cue: dict[str, Any]) -> bool:
        return cue["evidence_quality"] in {
            "high_strobe_timing_evidence",
            "medium_onset_evidence_aliased_timing",
            "medium_family_evidence",
        }

    special = {
        "strobe_with_evidence": 0,
        "strobe_without_evidence": 0,
        "color_with_evidence": 0,
        "color_without_evidence": 0,
        "rotation_with_evidence": 0,
        "rotation_without_evidence": 0,
        "sweep_with_evidence": 0,
        "sweep_without_evidence": 0,
        "wave_with_evidence": 0,
        "wave_without_evidence": 0,
        "ch18_with_strong_evidence": 0,
        "ch18_low_evidence": 0,
    }
    for cue in cue_entries:
        d = {int(k[2:]): v for k, v in cue["ch1_19"].items()}
        evidence = has_evidence(cue)
        checks = [
            ("color", d[8] >= 32 or d[9] != 0),
            ("rotation", any(d[ch] != 0 for ch in (12, 13, 14))),
            ("sweep", any(d[ch] != 0 for ch in (15, 16))),
            ("wave", d[19] != 0),
        ]
        if d[11] != 0:
            special[f"strobe_{'with' if cue['strobe_timing_evidence_usable'] else 'without'}_evidence"] += 1
        for name, active in checks:
            if active:
                special[f"{name}_{'with' if evidence else 'without'}_evidence"] += 1
        if d[18] != 0:
            if cue["evidence_quality"] == "low_ch18_evidence":
                special["ch18_low_evidence"] += 1
            else:
                special["ch18_with_strong_evidence"] += 1

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cue in cue_entries:
        grouped[cue["family_key"]].append(cue)
    family_rows = []
    for key, rows in grouped.items():
        actions = Counter(row["recommended_next_action"] for row in rows)
        family_rows.append({
            "family_key": key,
            "cue_count": len(rows),
            "representative_cue_id": rows[0]["cue_id"],
            "representative_cue_name": rows[0]["cue_name"],
            "dominant_next_action": actions.most_common(1)[0][0],
            "usable_evidence_count": sum(1 for row in rows if has_evidence(row)),
            "high_confidence_strobe_count": sum(1 for row in rows if row["evidence_quality"] == "high_strobe_timing_evidence"),
            "match_types": dict(Counter(row["match_type"] for row in rows)),
        })
    family_rows.sort(key=lambda row: (-row["cue_count"], row["dominant_next_action"], row["family_key"]))

    mapping = {
        "inputs": {
            "project_local_cue_dataset": str(local),
            "timed_capture_root": str(timed_root),
            "timed_manifest": str(manifest_path),
            "timed_analysis_manifest": str(analysis_path),
        },
        "statistics": {
            "total_cues": len(cues_raw),
            "total_captures": len(captures),
            "timed_manifest_entries": manifest_count,
            "usable_timed_captures": usable_timed_captures,
            "blank_timed_captures": blank_timed_captures,
            "sampled_base_cues": sampled_base_cues,
            "unsampled_base_cues": len(cue_entries) - sampled_base_cues,
            "dynamic_deferred_cues": sum(1 for cue in cue_entries if cue["recommended_next_action"] == "defer" and cue["missing_evidence_reason"].startswith("dynamic macro")),
            "validation_error_count": len(validation_errors),
            "validation_errors": validation_errors[:20],
            "match_summary": {
                "exact": ordered_match_counts["exact_ch1_19_match"],
                "partial": len(cue_entries) - ordered_match_counts["exact_ch1_19_match"] - ordered_match_counts["no_match"],
                "unmatched": ordered_match_counts["no_match"],
            },
            "match_types": ordered_match_counts,
            "next_actions": dict(action_counts),
            "motion_partial_evidence_not_ready": sum(
                1 for cue in cue_entries
                if cue["is_motion"] and cue["match_type"] != "no_match" and cue["recommended_next_action"] != "ready_motion_mapping"
            ),
            "special_coverage": special,
        },
        "families": family_rows,
        "cues": cue_entries,
    }
    output.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    build_report(report, mapping, local, timed_root, manifest_path, analysis_path)

    print(local)
    print(output)
    print(report)
    print(json.dumps(mapping["statistics"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--local", default=str(DEFAULT_LOCAL))
    parser.add_argument("--timed-root", default=str(DEFAULT_TIMED_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    analyze(args)


if __name__ == "__main__":
    main()
