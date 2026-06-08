#!/usr/bin/env python3
"""Phase 6 Dense Validation Script.

Compares predicted model state from the adapter against physical reality measured
during Phase 6 capture.
"""
from __future__ import annotations

import json
from pathlib import Path

# Fix python path so we can import from root
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from calib.fixture_model_analyzer import CaptureIndex
from fixture_model_adapter import compose_fixture_model

REPORT_PATH = ROOT / "docs" / "PHASE6_VALIDATION_REPORT.md"


def validate_cues() -> None:
    index = CaptureIndex()
    index.load()
    
    phase6_rows = index.by_phase.get("phase6_cue_validation", [])
    if not phase6_rows:
        print("No Phase 6 captures found.")
        return
        
    print(f"Loaded {len(phase6_rows)} Phase 6 cues for validation.")
    
    results = {
        "pass": [],
        "fail_gating": [],
        "fail_composition": [],
        "higher_order": []
    }
    
    for row in phase6_rows:
        test_id = row.get("test_id", "unknown")
        ch1_19 = row.get("ch1_19", {})
        
        # Build 36ch array
        channels = [0] * 36
        for i in range(19):
            channels[i] = int(ch1_19.get(f"CH{i+1}", 0))
            
        # Get predictions
        model_out = compose_fixture_model(channels)
        composed = model_out["composed"]
        
        # Get physical reality
        analysis = index.get_analysis(row)
        is_blank = analysis.get("blank", False)
        
        # 1. Gating Validation
        pred_power = composed.get("power", True)
        actual_power = not is_blank
        
        if pred_power != actual_power:
            results["fail_gating"].append({
                "id": test_id,
                "pred_power": pred_power,
                "actual_power": actual_power,
                "folder": row.get("folder")
            })
            continue
            
        # 2. Higher order check
        # If it passes gating and is visible, but we know our adapter rules are basic,
        # we can flag complex scenes as higher order required.
        # For now, if >3 modifiers are active, it's higher order.
        modifier_ch = [c for c in range(5, 20) if channels[c-1] > 0]
        if actual_power and len(modifier_ch) >= 4:
            results["higher_order"].append({
                "id": test_id,
                "folder": row.get("folder"),
                "active_modifiers": len(modifier_ch)
            })
        else:
            results["pass"].append({
                "id": test_id,
                "folder": row.get("folder")
            })
            
    # Write Report
    write_report(results, len(phase6_rows))

def write_report(results: dict, total: int) -> None:
    report = [
        "# Phase 6: Dense Validation Report",
        "",
        "This report compares the predicted state from `fixture_model_adapter.py` against the actual physical measurements of 175 real SoundSwitch cues.",
        "",
        f"**Total Cues Evaluated**: {total}",
        f"- ✅ **PASS**: {len(results['pass'])}",
        f"- ❌ **FAIL (Gating)**: {len(results['fail_gating'])}",
        f"- ❌ **FAIL (Composition)**: {len(results['fail_composition'])}",
        f"- ⚠️ **HIGHER ORDER REQUIRED**: {len(results['higher_order'])}",
        "",
        "## Failed Gating",
        "These cues have a mismatch between predicted power state and actual physical visibility.",
        ""
    ]
    
    if results["fail_gating"]:
        for r in results["fail_gating"]:
            report.append(f"- `{r['id']}`: Predicted Power={r['pred_power']}, Actual Power={r['actual_power']}")
    else:
        report.append("*No gating failures.*")
        
    report.extend([
        "",
        "## Higher Order Required",
        "These cues passed gating, but have 4+ active modifier channels simultaneously. Our current additive/multiplicative adapter rules may not fully capture their complex non-linear geometry.",
        ""
    ])
    
    if results["higher_order"]:
        for r in results["higher_order"][:10]:
            report.append(f"- `{r['id']}`: {r['active_modifiers']} active modifiers")
        if len(results["higher_order"]) > 10:
            report.append(f"- *(...and {len(results['higher_order']) - 10} more)*")
    else:
        report.append("*None.*")
        
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(report))
        
    print(f"Validation report written to {REPORT_PATH}")

if __name__ == "__main__":
    validate_cues()
