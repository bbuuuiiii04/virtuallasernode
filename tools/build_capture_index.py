#!/usr/bin/env python3
"""CLI entrypoint for PR1 capture index generation."""

from __future__ import annotations

from pathlib import Path

from capture_index_builder import build_capture_index, write_capture_index_artifacts


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = root / "captures" / "fixture_model" / "manifest.jsonl"
    capture_root = root / "captures" / "fixture_model"
    analysis_geometry = capture_root / "analysis_geometry.json"
    output_dir = root / "artifacts" / "renderer" / "renderer-capture-index-pr1"

    index, report = build_capture_index(
        manifest_path=manifest,
        capture_root=capture_root,
        analysis_geometry_path=analysis_geometry,
    )
    paths = write_capture_index_artifacts(index=index, report=report, output_dir=output_dir)

    print("Capture index generated:")
    print(f"- index: {paths['index']}")
    print(f"- report_json: {paths['report_json']}")
    print(f"- report_md: {paths['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

