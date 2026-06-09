#!/usr/bin/env python3
"""Targeted CH16 / CH7xCH16 Recapture workflow."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "calib"))

import fixture_model_orchestrator as orch

SESSION_NAME = "recapture_CH16_CH7xCH16_distance_adjusted_2026_06_08"
CAPTURE_ROOT = ROOT / "captures" / SESSION_NAME

# EXACT DEFAULT 36CH NEUTRAL VECTOR
# 36CH Professional Mode defaults.
DEFAULT_36CH_VECTOR = {
    1: 220,  # master dimmer
    2: 0,    # mode
    3: 0,    # pattern group (overridden per capture)
    4: 195,  # pattern (overridden per capture)
    5: 90,   # pattern size
    6: 128,  # h pos
    7: 128,  # v pos
    8: 20,   # color
    9: 0,    # color speed
    10: 0,   # pattern line
    11: 0,   # strobe
    12: 0,   # rot z
    13: 0,   # rot x
    14: 0,   # rot y
    15: 0,   # h move
    16: 0,   # v move
    17: 0,   # zoom
    18: 0,   # gradient
    19: 0,   # wave
    **{ch: 0 for ch in range(20, 37)}
}

def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")

def capture_target(name: str, rel_path: str, overrides: dict, reason: str, duration: float = 3.0, **manifest_fields) -> dict:
    dmx = dict(DEFAULT_36CH_VECTOR)
    dmx.update(overrides)
    
    outdir = CAPTURE_ROOT / rel_path
    video = outdir / "video.mp4"
    metadata_path = outdir / "metadata.json"
    analysis_path = outdir / "analysis.json"
    
    # 1. Output DMX
    orch.set_dmx(dmx)
    time.sleep(0.65)
    
    # 2. Capture
    orch.capture_video(video, duration)
    fps = orch.ffprobe_fps(video)
    
    # 3. Analyze immediately at 60 FPS
    import dense_cue_breakpoints as dense
    dense_entry = {
        "test_id": name,
        "capture": str(video),
        "capture_dir": str(outdir),
        "full_ch1_19_dmx": {str(ch): dmx[ch] for ch in range(1, 20)},
        "duration": duration,
        "family": "targeted_recapture"
    }
    
    # We must explicitly call 60fps instead of orch.analyze_with_dense which hardcodes 30fps
    analysis = dense.analyze_existing_entry(dense_entry, 60, orch.LASER_CORE_THRESHOLD_FLOOR)["analysis"]
    write_json(analysis_path, analysis)
    
    # 4. Write Metadata
    metadata = {
        "test_id": name,
        "ch1_19": {f"CH{ch}": dmx.get(ch, 0) for ch in range(1, 20)},
        "full_36ch_vector": {f"CH{ch}": dmx.get(ch, 0) for ch in range(1, 37)},
        "changed_channels": {f"CH{ch}": val for ch, val in overrides.items()},
        "override_reason": reason,
        "camera_session_id": SESSION_NAME,
        "framing_changed_from_original": False,
        "camera_distance_changed_cm": 0.5,
        "framing_change_severity": "negligible",
        "purpose": "CH16_reclean_and_CH7xCH16_targeted_recapture",
        "registration_check_required": True,
        "requires_registration_to_original_model": False,
        "fps": fps,
        "duration": duration,
        "timestamp": orch.now(),
        "folder": rel_path
    }
    write_json(metadata_path, metadata)
    
    
    # 5. Write to session manifest
    manifest_path = CAPTURE_ROOT / "manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**metadata, **manifest_fields, "analysis": analysis}) + "\n")
        
    return analysis

def run_preflight():
    print("=== STARTING PREFLIGHT ===")
    preflight_overrides = [
        *[({"CH3": 0, "CH4": 195, "CH7": 128, "CH16": v}, f"preflight_CH16_{v}") for v in [32, 64, 96, 120, 128, 160, 192, 224]],
        *[({"CH3": 0, "CH4": 195, "CH7": v, "CH16": 0}, f"preflight_CH7_{v}") for v in [64, 128, 192]],
        ({"CH3": 0, "CH4": 195, "CH7": 128, "CH16": 128}, "preflight_CH7_128_CH16_128")
    ]
    
    for overrides_names, name in preflight_overrides:
        num_overrides = {int(k.replace("CH", "")): v for k, v in overrides_names.items()}
        print(f"Running preflight: {name}")
        manifest_fields = {
            "phase": "preflight_targeted",
            "baseline": "base_CH3_000_CH4_195",
            "family": "targeted_recapture_preflight"
        }
        analysis = capture_target(name, f"preflight/{name}", num_overrides, "preflight_sanity_check", **manifest_fields)
        
        clipped = analysis.get("clipped", False)
        geo_clipped = analysis.get("geometry_clipped_low", False)
        
        if clipped or geo_clipped:
            print(f"HALT: Preflight capture {name} caused clipping! (clipped={clipped}, geo_clipped={geo_clipped})")
            print("Please adjust camera to avoid clipping before continuing.")
            orch.blackout()
            sys.exit(1)
            
    print("Preflight passed! No clipping detected.")

def run_ch16_sweep():
    print("=== STARTING CH16 RE-SWEEP ===")
    vals = list(range(0, 253, 4))
    if 255 not in vals: vals.append(255)
    for v in vals:
        overrides = {3: 0, 4: 195, 7: 128, 16: v}
        name = f"CH16_{v:03d}"
        path = f"phase1_single_channel/CH16_vertical_movement/{name}"
        manifest_fields = {
            "phase": "phase1_single_channel",
            "baseline": "base_CH3_000_CH4_195",
            "group": "CH16_vertical_movement",
            "family": "targeted_recapture_CH16_reclean"
        }
        capture_target(name, path, overrides, "Priority 1: CH16 clean re-sweep", **manifest_fields)

def run_ch7xch16_matrix():
    print("=== STARTING CH7xCH16 MATRIX ===")
    bases = [
        ("base_CH3_000_CH4_195", {3: 0, 4: 195}),
        ("base_CH3_032_CH4_010", {3: 32, 4: 10})
    ]
    
    ch7_vals = [32, 64, 96, 128, 160, 192]
    
    for base_name, base_overrides in bases:
        print(f"\n--- Running Base: {base_name} ---")
        
        # 1. Reference rows
        ch7_refs = [32, 64, 96, 128, 160, 192]
        for ch7 in ch7_refs:
            overrides = {**base_overrides, 7: ch7, 16: 0}
            name = f"CH07_{ch7:03d}_CH16_000_reference"
            path = f"phase3_composition/{base_name}/group_translate_CH7xCH16/{name}"
            manifest_fields = {
                "phase": "phase3_composition",
                "baseline": base_name,
                "group": "group_translate_CH7xCH16",
                "family": "targeted_recapture_CH7xCH16_reference",
                "temporal_classification": "static_reference"
            }
            capture_target(name, path, overrides, "Priority 1: CH7xCH16 reference row", **manifest_fields)
            
        ch16_refs = [32, 64, 96, 120]
        for ch16 in ch16_refs:
            overrides = {**base_overrides, 7: 128, 16: ch16}
            name = f"CH07_128_CH16_{ch16:03d}_reference"
            path = f"phase3_composition/{base_name}/group_translate_CH7xCH16/{name}"
            manifest_fields = {
                "phase": "phase3_composition",
                "baseline": base_name,
                "group": "group_translate_CH7xCH16",
                "family": "targeted_recapture_CH7xCH16_reference",
                "temporal_classification": "static_reference"
            }
            capture_target(name, path, overrides, "Priority 1: CH7xCH16 reference row", **manifest_fields)
        
        # 2. Static matrix
        ch16_static = [32, 64, 96, 120]
        for ch7 in ch7_vals:
            if ch7 == 128: continue
            for ch16 in ch16_static:
                overrides = {**base_overrides, 7: ch7, 16: ch16}
                name = f"CH07_{ch7:03d}_CH16_{ch16:03d}"
                path = f"phase3_composition/{base_name}/group_translate_CH7xCH16/{name}"
                manifest_fields = {
                    "phase": "phase3_composition",
                    "baseline": base_name,
                    "group": "group_translate_CH7xCH16",
                    "family": "targeted_recapture_CH7xCH16_static",
                    "temporal_classification": "static_geometry"
                }
                capture_target(name, path, overrides, "Priority 1: CH7xCH16 static interaction matrix", **manifest_fields)
        
        # Temporal matrix
        ch16_temporal = [128, 160, 192]
        ch7_temp_vals = [64, 128, 192]
        for ch7 in ch7_temp_vals:
            for ch16 in ch16_temporal:
                overrides = {**base_overrides, 7: ch7, 16: ch16}
                name = f"CH07_{ch7:03d}_CH16_{ch16:03d}_temporal"
                path = f"phase3_composition/{base_name}/group_translate_CH7xCH16/{name}"
                manifest_fields = {
                    "phase": "phase3_composition",
                    "baseline": base_name,
                    "group": "group_translate_CH7xCH16",
                    "family": "targeted_recapture_CH7xCH16_temporal",
                    "temporal_classification": "temporal_estimated"
                }
                capture_target(name, path, overrides, "Priority 1: CH7xCH16 temporal interaction matrix (estimated)", duration=8.0, **manifest_fields)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rig-confirmed", action="store_true")
    args = parser.parse_args()
    
    if not args.rig_confirmed:
        print("Dry run only. Use --rig-confirmed to output DMX and capture video.")
        return
        
    daemon = orch.start_daemon()
    watchdog_stop, watchdog_thread = orch.start_watchdog_heartbeat()
    
    try:
        run_preflight()
        run_ch16_sweep()
        run_ch7xch16_matrix()
    finally:
        orch.stop_watchdog_heartbeat(watchdog_stop, watchdog_thread)
        orch.stop_daemon(daemon)
        orch.blackout()

if __name__ == "__main__":
    main()
