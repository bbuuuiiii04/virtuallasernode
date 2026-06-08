#!/usr/bin/env python3
"""Delete superseded pre-base-keying Phase 1.5 captures.

Default mode is a dry run. Apply mode deletes only orphaned Phase 1.5 capture
directories whose base-keyed replacement already exists and is valid.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "captures" / "fixture_model"
PHASE15_ROOT = CAPTURE_ROOT / "phase1_5_base_dependence"
MANIFEST = CAPTURE_ROOT / "manifest.jsonl"


@dataclass(frozen=True)
class Decision:
    source: Path
    folder: str
    target: Path | None
    target_status: str
    decision: str
    reason: str
    bytes_on_disk: int


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    tmp.replace(path)


def rel(path: Path) -> str:
    return str(path.relative_to(CAPTURE_ROOT))


def tree_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def is_orphan_capture_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        relative = path.relative_to(PHASE15_ROOT)
    except ValueError:
        return False
    parts = relative.parts
    return len(parts) == 2 and not parts[0].startswith("base_CH3_")


def video_for_track(path: Path, track: str) -> Path:
    if track == "color" or path.name.endswith("_color"):
        return path / "video_color.mp4"
    return path / "video.mp4"


def target_valid(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if not path.is_dir():
        return False, "target_not_directory"
    metadata_path = path / "metadata.json"
    analysis_path = path / "analysis.json"
    if not metadata_path.exists():
        return False, "missing_metadata"
    if not analysis_path.exists():
        return False, "missing_analysis"
    try:
        metadata = read_json(metadata_path)
        analysis = read_json(analysis_path)
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid_json:{exc}"
    video = video_for_track(path, str(metadata.get("exposure_track") or "geometry_motion"))
    if not video.exists() or video.stat().st_size <= 0:
        return False, "missing_video"
    if analysis.get("recapture_pending"):
        return False, "recapture_pending"
    if analysis.get("blank") or (analysis.get("quality") or {}).get("blank"):
        return False, "blank"
    return True, "valid"


def corrected_target(source: Path) -> tuple[Path | None, str]:
    metadata_path = source / "metadata.json"
    if not metadata_path.exists():
        return None, "missing_source_metadata"
    try:
        metadata = read_json(metadata_path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid_source_metadata:{exc}"
    baseline = str(metadata.get("baseline") or "")
    if not baseline.startswith("base_CH3_"):
        return None, "missing_or_invalid_baseline"
    try:
        relative = source.relative_to(PHASE15_ROOT)
    except ValueError:
        return None, "not_under_phase15_root"
    group, state = relative.parts
    return PHASE15_ROOT / baseline / group / state, "mapped"


def collect_decisions() -> list[Decision]:
    decisions: list[Decision] = []
    for source in sorted(PHASE15_ROOT.glob("*/*")):
        if not is_orphan_capture_dir(source):
            continue
        target, map_status = corrected_target(source)
        bytes_on_disk = tree_size(source)
        if target is None:
            decisions.append(Decision(source, rel(source), None, map_status, "KEEP", map_status, bytes_on_disk))
            continue
        ok, status = target_valid(target)
        decision = "DELETE" if ok else "KEEP"
        reason = "superseded_by_valid_base_keyed_capture" if ok else status
        decisions.append(Decision(source, rel(source), target, status, decision, reason, bytes_on_disk))
    return decisions


def prune_manifest(pruned_folders: set[str]) -> tuple[int, Path]:
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = MANIFEST.with_name(MANIFEST.name + f".bak.{ts}")
    shutil.copy2(MANIFEST, backup)
    for _ in range(20):
        before = MANIFEST.stat()
        rows = read_jsonl(MANIFEST)
        kept = [row for row in rows if str(row.get("folder") or "") not in pruned_folders]
        after = MANIFEST.stat()
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            time.sleep(0.25)
            continue
        write_jsonl(MANIFEST, kept)
        return len(rows) - len(kept), backup
    raise RuntimeError("manifest changed continuously; refused to rewrite while live appends were racing")


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="delete safely superseded orphan captures")
    args = ap.parse_args()
    decisions = collect_decisions()
    delete = [item for item in decisions if item.decision == "DELETE"]
    keep = [item for item in decisions if item.decision == "KEEP"]
    freed = sum(item.bytes_on_disk for item in delete)
    print(f"mode: {'apply' if args.apply else 'dry-run'}")
    print(f"orphan_dirs: {len(decisions)} delete: {len(delete)} keep: {len(keep)}")
    print(f"bytes_to_free: {freed} ({format_bytes(freed)})")
    for item in decisions:
        target = rel(item.target) if item.target else "-"
        print(f"{item.decision:6} {item.folder} -> {target} status={item.target_status} reason={item.reason} size={format_bytes(item.bytes_on_disk)}")
    if not args.apply:
        return 0
    deleted_folders: set[str] = set()
    for item in delete:
        if not is_orphan_capture_dir(item.source):
            raise RuntimeError(f"refusing non-orphan path: {item.source}")
        shutil.rmtree(item.source)
        deleted_folders.add(item.folder)
    pruned, backup = prune_manifest(deleted_folders)
    print(f"deleted_dirs: {len(deleted_folders)}")
    print(f"manifest_rows_pruned: {pruned}")
    print(f"manifest_backup: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
