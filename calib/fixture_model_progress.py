#!/usr/bin/env python3
"""Progress summary for the fixture model capture run."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ORCH_PATH = ROOT / "calib" / "fixture_model_orchestrator.py"
MANIFEST = ROOT / "captures" / "fixture_model" / "manifest.jsonl"
CHECKPOINT = ROOT / "captures" / "fixture_model" / "checkpoint.json"


def load_orchestrator() -> Any:
    spec = importlib.util.spec_from_file_location("fixture_model_orchestrator", ORCH_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ORCH_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


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


def bar(done: int, total: int, width: int = 28) -> str:
    pct = 1.0 if total == 0 else min(1.0, done / total)
    filled = round(pct * width)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {done:5d}/{total:<5d} {pct * 100:5.1f}%"


def valid_done_ids(rows: list[dict[str, Any]], orch: Any) -> set[str]:
    superseded = orch.superseded_capture_folders()
    done: set[str] = set()
    for row in rows:
        folder = str(row.get("folder") or "")
        test_id = row.get("test_id")
        if not folder or not test_id or folder in superseded:
            continue
        if row.get("phase") == "phase1_5_base_dependence" and not folder.startswith("phase1_5_base_dependence/base_CH3_"):
            continue
        analysis = row.get("analysis") or {}
        if analysis.get("recapture_pending") and folder != "phase1_single_channel/CH01_master_dimmer/CH01_000":
            continue
        done.add(str(test_id))
    return done


def main() -> None:
    orch = load_orchestrator()
    checkpoint = read_json(CHECKPOINT, {})
    rows = read_jsonl(MANIFEST)
    done = valid_done_ids(rows, orch)
    phases = [
        ("Phase 1", orch.phase1_cases()),
        ("Phase 1.5", orch.phase15_cases()),
        ("Phase 2", orch.phase2_cases()),
        ("Phase 3", orch.phase3_cases()),
        ("Phase 4", orch.phase4_cases()),
        ("Phase 6", orch.cue_validation_cases()),
    ]
    print(f"checkpoint: phase={checkpoint.get('phase')} status={checkpoint.get('status')} total={checkpoint.get('running_total') or len(rows)} last={checkpoint.get('last_capture')}")
    for label, cases in phases:
        ids = {case.test_id for case in cases}
        print(f"{label:<9} {bar(len(ids & done), len(ids))}")
    fps = [float((row.get("analysis") or {}).get("actual_fps") or 0) for row in rows if (row.get("analysis") or {}).get("actual_fps")]
    if fps:
        low = sum(1 for value in fps if value < 55)
        print(f"fps: n={len(fps)} min={min(fps):.3f} max={max(fps):.3f} <55={low}")
    stats = checkpoint.get("run_stats") or {}
    if stats:
        print(f"run_stats: {json.dumps(stats, sort_keys=True)}")


if __name__ == "__main__":
    main()
