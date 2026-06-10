"""PR-G1 rejects historical/forbidden input paths in selection artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_library_builder import FORBIDDEN_PATH_FRAGMENTS, _path_forbidden  # noqa: E402

SELECTION_PATH = ROOT / "artifacts" / "renderer" / "pr-g1-shape-authority" / "shape_selection.json"

FORBIDDEN = (
    "calib/captures",
    "archive/pre_corpus",
    "/tmp/",
    "vln_wall_ch3_atlas",
    "wall_atlas_ch3",
    "docs/_archive",
)


def test_forbidden_fragments_registered() -> None:
    for frag in FORBIDDEN:
        assert frag in FORBIDDEN_PATH_FRAGMENTS


def test_path_forbidden_helper() -> None:
    assert _path_forbidden("calib/captures/foo/still.jpg") is True
    assert _path_forbidden("captures/fixture_model/phase1/still.jpg") is False
    assert _path_forbidden("/tmp/vln_wall_ch3_atlas/x.png") is True


def test_selection_artifact_rejects_historical_paths() -> None:
    if not SELECTION_PATH.is_file():
        return
    data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    for entry in data.get("entries") or []:
        for field in ("capture_path", "still_path", "metadata_path", "analysis_path"):
            val = str(entry.get(field) or "")
            if not val:
                continue
            lower = val.replace("\\", "/").lower()
            for frag in FORBIDDEN:
                assert frag not in lower, f"forbidden {frag!r} in {field}: {val}"
