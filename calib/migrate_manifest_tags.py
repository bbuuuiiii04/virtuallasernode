#!/usr/bin/env python3
"""Migrates manifest.jsonl to backfill intent tags based on folder names."""

import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "captures" / "fixture_model" / "manifest.jsonl"
BACKUP = MANIFEST.with_suffix(".jsonl.bak_migration")

def main():
    if not MANIFEST.exists():
        print(f"Manifest not found at {MANIFEST}")
        return

    print(f"Backing up manifest to {BACKUP}")
    shutil.copy2(MANIFEST, BACKUP)

    rows = []
    with MANIFEST.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            folder = row.get("folder", "")
            
            # Derive intent from folder
            intent = ""
            if "gate_CH01_enables_all" in folder:
                intent = "gate_CH1_all"
            elif "gate_CH03_static_dynamic_split" in folder:
                intent = "gate_CH3_split"
            elif "gate_CH08_enables_CH09" in folder:
                intent = "gate_CH8_CH9"
            elif "not_gate_CH08_CH18" in folder:
                intent = "not_gate_CH8_CH18"
            elif "gate_CH03_CH04_shape" in folder:
                intent = "gate_CH3_CH4_shape"
            elif "group_colour_CH8xCH9" in folder:
                intent = "composition_colour_CH8xCH9"
            elif "group_colour_CH8xCH18" in folder:
                intent = "composition_colour_CH8xCH18"
            elif "group_translate_CH6xCH15" in folder:
                intent = "composition_translate_CH6xCH15"
            elif "group_translate_CH7xCH16" in folder:
                intent = "composition_translate_CH7xCH16"
            elif "group_scale_CH5xCH17" in folder:
                intent = "composition_scale_CH5xCH17"
            elif "group_rotation_move_CH12xCH15" in folder:
                intent = "composition_rotation_move_CH12xCH15"
            elif "group_move_wave_CH15xCH19" in folder:
                intent = "composition_move_wave_CH15xCH19"
            elif "orientation_CH12xCH13xCH14" in folder:
                intent = "composition_orientation_CH12xCH13xCH14"
            elif "independent_CH11xCH08" in folder:
                intent = "independent_CH11xCH08"
            elif "independent_CH11xCH12" in folder:
                intent = "independent_CH11xCH12"
            elif "independent_CH11xCH15" in folder:
                intent = "independent_CH11xCH15"
            elif "independent_CH12xCH08" in folder:
                intent = "independent_CH12xCH08"
            elif "independent_CH17xCH08" in folder:
                intent = "independent_CH17xCH08"
            elif "independent_CH19xCH08" in folder:
                intent = "independent_CH19xCH08"
            
            row["intent"] = intent
            rows.append(row)

    print(f"Writing {len(rows)} rows back to {MANIFEST}")
    with MANIFEST.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
            
    print("Migration complete.")

if __name__ == "__main__":
    main()
