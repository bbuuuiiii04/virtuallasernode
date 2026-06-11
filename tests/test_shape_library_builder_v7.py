"""PR-G1 v7 shape-library builder integration tests."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture_index_runtime import vector_key_from_ch1_19  # noqa: E402
from tools.shape_extraction import ARTIFACT_VERSION  # noqa: E402
from tools.shape_library_builder import (  # noqa: E402
    DEFAULT_FIXTURE_BOX,
    build_pr_g1_artifacts,
    compute_shape_ref,
    merge_v7_shape_refs_into_index,
)
import tools.shape_library_builder as builder  # noqa: E402


def _entry(name: str, *, ch3: int = 32, capture_path: str | None = None) -> dict:
    ch1_19 = {f"CH{i}": 0 for i in range(1, 20)}
    ch1_19.update({"CH1": 220, "CH3": ch3, "CH5": 90, "CH6": 128, "CH7": 128})
    capture_path = capture_path or f"phase_test/{name}"
    return {
        "selection_lane": "phase6_cue",
        "family_or_checkpoint": name,
        "capture_path": capture_path,
        "still_path": f"captures/fixture_model/{capture_path}/still.jpg",
        "metadata_path": f"captures/fixture_model/{capture_path}/metadata.json",
        "analysis_path": f"captures/fixture_model/{capture_path}/analysis.json",
        "vector_key": vector_key_from_ch1_19(ch1_19),
        "ch1_19": ch1_19,
        "phase": "phase_test",
        "exposure_track": "geometry_motion",
        "quality_flags": [],
        "selected_fixture_box": DEFAULT_FIXTURE_BOX,
        "selection_reason": "test fixture",
        "selection_tier": "phase6_cue",
        "local_media_exists": True,
    }


def _shape_ref(entry: dict) -> str:
    return compute_shape_ref(
        ARTIFACT_VERSION,
        entry["vector_key"],
        entry["capture_path"],
        entry.get("selected_fixture_box", DEFAULT_FIXTURE_BOX),
    )


def _poly(kind: str = "centerline_polyline", *, role: str = "render", prefix: str = "p") -> dict:
    return {
        "polyline_id": f"{prefix}0",
        "component_id": "s0",
        "geometry_kind": kind,
        "closed": False,
        "ordered": True,
        "points_px": [[10.0, 10.0], [20.0, 20.0]],
        "points_wall_norm": [[-0.1, -0.1], [0.1, 0.1]],
        "point_count": 2,
        "render_role": role,
        "structure_coverage": 1.0,
        "aperture": "image_left" if prefix == "p" else "image_right",
    }


def _record(entry: dict, *, status: str = "authority", render_authority: str = "vector", render_fallback: str = "none", render_role: str = "render") -> dict:
    ref = _shape_ref(entry)
    return {
        "record_version": "shape-authority-v2",
        "shape_ref": ref,
        "vector_key": entry["vector_key"],
        "ch1_19": entry["ch1_19"],
        "capture_path": entry["capture_path"],
        "source_still": entry["still_path"],
        "test_id": entry["family_or_checkpoint"],
        "phase": entry["phase"],
        "exposure_track": entry["exposure_track"],
        "fixture_box_label": "image_left",
        "selected_aperture": "image_left",
        "aperture_boxes": {"image_left": [0, 0, 100, 100], "image_right": [110, 0, 210, 100]},
        "core_mask": {
            "bbox_px": [10, 10, 20, 20],
            "bbox_wall_norm": [-0.1, -0.1, 0.1, 0.1],
            "centroid_wall_norm": [0.0, 0.0],
        },
        "components": [{"component_id": "s0", "class": "open_stroke"}],
        "polylines": [_poly(role=render_role)],
        "sibling_polylines": [_poly(role=render_role, prefix="sp")],
        "topology_summary": {"dots": 0, "closed_strokes": 0, "open_strokes": 1},
        "metrics": {},
        "status": status,
        "quality_flags": [],
        "render_authority": render_authority,
        "geometry_layers": {
            "core_mask": "primary_evidence_authority",
            "raw_debug_vectors": "diagnostic_only",
            "render_vectors": "derived_validated" if render_authority == "vector" else None,
            "render_fallback": render_fallback,
        },
    }


def _write_root(tmp_path: Path, entries: list[dict], records: list[dict]) -> Path:
    root = tmp_path / "repo"
    (root / "captures/fixture_model").mkdir(parents=True)
    (root / "captures/fixture_model/analysis_geometry.json").write_text(
        json.dumps({"version": 1, "created_at": "test"}) + "\n",
        encoding="utf-8",
    )
    selection_dir = root / "artifacts/renderer/pr-g1-shape-authority"
    selection_dir.mkdir(parents=True)
    (selection_dir / "shape_selection.json").write_text(
        json.dumps(
            {
                "artifact_version": "pr-g1-shape-selection-v1",
                "generated_at": "test",
                "entries": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    v7_dir = root / "artifacts/renderer/shape_authority_v2"
    records_dir = v7_dir / "records"
    records_dir.mkdir(parents=True)
    (v7_dir / "manifest.json").write_text(
        json.dumps(
            {
                "policy_version": "v7",
                "record_version": "shape-authority-v2",
                "generated_at": "2026-01-01T00:00:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for record in records:
        (records_dir / f"{record['shape_ref']}.json").write_text(
            json.dumps(record, indent=2) + "\n",
            encoding="utf-8",
        )
    return root


def test_v7_builder_reads_records_and_marks_missing_records(tmp_path: Path) -> None:
    authority = _entry("authority", ch3=32)
    missing = _entry("missing", ch3=48)
    root = _write_root(tmp_path, [authority, missing], [_record(authority)])

    stats = build_pr_g1_artifacts(root, extractor="v7", merge_index=False)

    library = json.loads((root / "artifacts/renderer/shape_library_v1.json").read_text())
    assert stats["extractor"] == "v7"
    assert stats["v7_record_count"] == 1
    assert stats["v7_subset_count"] == 2
    assert stats["authority_counts"] == {
        "authority": 1,
        "provisional": 0,
        "quarantined": 0,
        "missing": 1,
        "conflicts": 0,
    }
    assert [shape["shape_ref"] for shape in library["shapes"]] == [_shape_ref(authority)]
    missing_row = next(row for row in library["v7_authority_accounting"] if row["shape_ref"] == _shape_ref(missing))
    assert missing_row["shape_authority"] is False
    assert missing_row["reason"] == "missing_v7_record"


def test_default_extractor_stays_v6(monkeypatch, tmp_path: Path) -> None:
    def fail_v7(*args, **kwargs):
        raise AssertionError("default builder path unexpectedly invoked v7")

    monkeypatch.setattr(builder, "build_pr_g1_v7_artifacts", fail_v7)

    try:
        build_pr_g1_artifacts(tmp_path)
    except FileNotFoundError as exc:
        assert "captures/fixture_model" in str(exc)


def test_v7_rejects_provisional_core_mask_and_diagnostic_geometry(tmp_path: Path) -> None:
    provisional = _entry("provisional", ch3=32)
    core_mask = _entry("core_mask", ch3=48)
    diagnostic = _entry("diagnostic", ch3=96)
    root = _write_root(
        tmp_path,
        [provisional, core_mask, diagnostic],
        [
            _record(provisional, status="provisional"),
            _record(core_mask, render_authority="core_mask", render_fallback="core_mask"),
            _record(diagnostic, render_role="diagnostic"),
        ],
    )

    build_pr_g1_artifacts(root, extractor="v7", merge_index=False)

    library = json.loads((root / "artifacts/renderer/shape_library_v1.json").read_text())
    assert library["shapes"] == []
    reasons = {row["family_or_checkpoint"]: row["reason"] for row in library["v7_authority_accounting"]}
    assert reasons == {
        "provisional": "v7_status_provisional",
        "core_mask": "render_authority_core_mask",
        "diagnostic": "empty_selected_render_geometry",
    }


def test_v7_does_not_promote_exact_vector_match_without_expected_shape_ref(tmp_path: Path) -> None:
    entry = _entry("selected", ch3=32)
    other = _entry("other", ch3=32, capture_path="phase_test/other")
    record = _record(other)
    record["vector_key"] = entry["vector_key"]
    root = _write_root(tmp_path, [entry], [record])

    build_pr_g1_artifacts(root, extractor="v7", merge_index=False)

    library = json.loads((root / "artifacts/renderer/shape_library_v1.json").read_text())
    assert library["shapes"] == []
    assert library["v7_authority_accounting"][0]["reason"] == "missing_v7_record"


def test_v7_builder_output_is_deterministic(tmp_path: Path) -> None:
    entry = _entry("authority", ch3=32)
    root = _write_root(tmp_path, [entry], [_record(entry)])

    build_pr_g1_artifacts(root, extractor="v7", merge_index=False)
    first_library = (root / "artifacts/renderer/shape_library_v1.json").read_bytes()
    first_selection = (root / "artifacts/renderer/pr-g1-shape-authority/shape_selection.json").read_bytes()

    build_pr_g1_artifacts(root, extractor="v7", merge_index=False)

    assert (root / "artifacts/renderer/shape_library_v1.json").read_bytes() == first_library
    assert (root / "artifacts/renderer/pr-g1-shape-authority/shape_selection.json").read_bytes() == first_selection


def test_v7_merge_index_keeps_false_authority_machine_reason(tmp_path: Path) -> None:
    authority = _entry("authority", ch3=32)
    missing = _entry("missing", ch3=48)
    authority_shape = {
        "shape_ref": _shape_ref(authority),
        "shape_point_count": 2,
        "topology_class": "line",
        "quality_flags": [],
        "capture_path": authority["capture_path"],
    }
    index_path = tmp_path / "capture_index_v1.json"
    index_path.write_text(
        json.dumps(
            {
                "captures": [],
                "vector_index": {
                    authority["vector_key"]: {"preferred_capture_id": 0, "capture_ids": [0]},
                    missing["vector_key"]: {"preferred_capture_id": 1, "capture_ids": [1]},
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    accounting = [
        {
            "shape_ref": _shape_ref(authority),
            "vector_key": authority["vector_key"],
            "capture_path": authority["capture_path"],
            "v7_status": "authority",
            "shape_authority": True,
            "reason": None,
            "record_path": "records/authority.json",
            "sibling_render_polyline_count": 1,
        },
        {
            "shape_ref": _shape_ref(missing),
            "vector_key": missing["vector_key"],
            "capture_path": missing["capture_path"],
            "v7_status": "missing",
            "shape_authority": False,
            "reason": "missing_v7_record",
            "record_path": None,
            "sibling_render_polyline_count": 0,
        },
    ]

    stats = merge_v7_shape_refs_into_index(index_path, [authority_shape], accounting)

    merged = json.loads(index_path.read_text())
    authority_bucket = merged["vector_index"][authority["vector_key"]]
    missing_bucket = merged["vector_index"][missing["vector_key"]]
    assert stats == {"selected_vectors": 2, "authority_vectors": 1, "rejected_vectors": 1}
    assert authority_bucket["shape_authority"] is True
    assert authority_bucket["shape_status"] == "authority"
    assert missing_bucket["shape_authority"] is False
    assert missing_bucket["shape_ref"] is None
    assert missing_bucket["shape_fallback_reason"] == "missing_v7_record"


def test_cue_002_dotted_arc_and_sibling_geometry_survive_v7_join(tmp_path: Path) -> None:
    record_path = ROOT / "artifacts/renderer/shape_authority_v2/records/sh1_adb58093da473f3e.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    entry = {
        "selection_lane": "phase6_cue",
        "family_or_checkpoint": "cue_002_green",
        "capture_path": record["capture_path"],
        "still_path": record["source_still"],
        "metadata_path": "",
        "analysis_path": "",
        "vector_key": record["vector_key"],
        "ch1_19": record["ch1_19"],
        "phase": record["phase"],
        "exposure_track": record["exposure_track"],
        "quality_flags": [],
        "selected_fixture_box": record["fixture_box_label"],
        "selection_reason": "real v7 record fixture",
        "selection_tier": "phase6_cue",
        "local_media_exists": True,
    }
    root = _write_root(tmp_path, [entry], [])
    dst = root / "artifacts/renderer/shape_authority_v2/records/sh1_adb58093da473f3e.json"
    shutil.copyfile(record_path, dst)

    build_pr_g1_artifacts(root, extractor="v7", merge_index=False)

    library = json.loads((root / "artifacts/renderer/shape_library_v1.json").read_text())
    shape = library["shapes"][0]
    assert shape["shape_ref"] == "sh1_adb58093da473f3e"
    assert {poly["geometry_kind"] for poly in shape["polylines"]} == {"dotted_arc_path"}
    assert {poly["geometry_kind"] for poly in shape["sibling_polylines"]} == {"dotted_arc_path"}
    assert all(poly["render_role"] == "render" for poly in shape["polylines"])
    assert all(poly["render_role"] == "render" for poly in shape["sibling_polylines"])
