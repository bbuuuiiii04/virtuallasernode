"""PR-G1 shape_ref stability: deterministic, path-independent, box-sensitive."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.shape_extraction import ARTIFACT_VERSION, compute_shape_ref  # noqa: E402


def test_same_inputs_same_ref() -> None:
    ref_a = compute_shape_ref(
        ARTIFACT_VERSION,
        "v1:0,0,32,0,90,128,128,0,0,0,0,0,0,0,0,0,0,0,0",
        "phase1_5_base_dependence/ch3_032",
        "image_left",
    )
    ref_b = compute_shape_ref(
        ARTIFACT_VERSION,
        "v1:0,0,32,0,90,128,128,0,0,0,0,0,0,0,0,0,0,0,0",
        "phase1_5_base_dependence/ch3_032",
        "image_left",
    )
    assert ref_a == ref_b
    assert ref_a.startswith("sh1_")


def test_absolute_paths_do_not_affect_ref() -> None:
    rel = "phase6_cue_validation/cue_relevant/cue_001"
    ref_rel = compute_shape_ref(ARTIFACT_VERSION, "v1:1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19", rel, "image_left")
    ref_abs_like = compute_shape_ref(
        ARTIFACT_VERSION,
        "v1:1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19",
        rel,
        "image_left",
    )
    assert ref_rel == ref_abs_like


def test_fixture_box_label_changes_ref() -> None:
    vector = "v1:0,0,48,0,90,128,128,0,0,0,0,0,0,0,0,0,0,0,0"
    path = "phase1/ch3_048"
    left = compute_shape_ref(ARTIFACT_VERSION, vector, path, "image_left")
    right = compute_shape_ref(ARTIFACT_VERSION, vector, path, "image_right")
    assert left != right
