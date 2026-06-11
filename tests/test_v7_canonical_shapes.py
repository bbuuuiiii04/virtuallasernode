"""Synthetic PR-G1 v7 canonical shape tests."""

import numpy as np
import pytest

pytest.importorskip("skimage", reason="scikit-image required")


def _draw_line(mask, p0, p1, radius=1):
    from skimage.draw import line
    from skimage.morphology import dilation, disk

    rr, cc = line(int(round(p0[1])), int(round(p0[0])), int(round(p1[1])), int(round(p1[0])))
    rr = np.clip(rr, 0, mask.shape[0] - 1)
    cc = np.clip(cc, 0, mask.shape[1] - 1)
    local = np.zeros_like(mask, dtype=bool)
    local[rr, cc] = True
    if radius > 0:
        local = dilation(local, disk(radius))
    mask |= local


def _component(mask_shape, segments):
    m = np.zeros(mask_shape, dtype=bool)
    for p0, p1 in segments:
        _draw_line(m, p0, p1, radius=1)
    return m


def test_grouped_dashed_line_snaps_to_line_and_can_earn_vector_authority():
    from skimage.morphology import dilation, disk

    from tools.shape_extract_v7 import _assign_render_roles
    from tools.shape_validation_v2 import component_structure_coverage, compute_authority_gate, compute_metrics
    from tools.shape_vectorize_v7 import vectorize_group

    shape = (80, 140)
    members = [
        _component(shape, [((12, 22), (34, 27))]),
        _component(shape, [((45, 30), (68, 35))]),
        _component(shape, [((80, 38), (112, 45))]),
    ]
    union = np.zeros(shape, dtype=bool)
    for m in members:
        union |= m
    glow = dilation(union, disk(8))
    polys = vectorize_group(members, members, ["open_stroke"] * 3, ["s0", "s1", "s2"], union.astype(float), glow, np.zeros((*shape, 3), dtype=np.uint8))
    assert polys is not None
    assert len(polys) == 1
    assert polys[0]["geometry_kind"] == "line_centerline"
    assert polys[0]["member_component_ids"] == ["s0", "s1", "s2"]

    coverage = {}
    represented = set()
    _assign_render_roles(polys, {"s0": members[0], "s1": members[1], "s2": members[2]},
                         {"s0": "open_stroke", "s1": "open_stroke", "s2": "open_stroke"},
                         component_structure_coverage, coverage, represented)
    assert polys[0]["render_role"] == "render"
    assert represented == {"s0", "s1", "s2"}

    core = np.zeros(shape, dtype=bool)
    _draw_line(core, polys[0]["points_px"][0], polys[0]["points_px"][1], radius=2)
    metrics = compute_metrics(polys, core, glow, [{"component_id": "s0", "class": "open_stroke"}], structure_mask=core)
    eligible, status, reasons = compute_authority_gate(metrics, 1, 1, [], True)
    assert eligible, reasons
    assert status == "authority"


def test_grouped_parallelogram_outline_snaps_to_quad():
    from skimage.morphology import dilation, disk

    from tools.shape_vectorize_v7 import vectorize_group

    shape = (100, 140)
    corners = [(34, 22), (94, 30), (106, 68), (45, 60)]
    members = []
    for i in range(4):
        members.append(_component(shape, [(corners[i], corners[(i + 1) % 4])]))
    union = np.zeros(shape, dtype=bool)
    for m in members:
        union |= m
    glow = dilation(union, disk(6))
    polys = vectorize_group(members, members, ["open_stroke"] * 4, ["s0", "s1", "s2", "s3"], union.astype(float), glow, np.zeros((*shape, 3), dtype=np.uint8))
    assert polys is not None
    assert polys[0]["geometry_kind"] == "quad_centerline"
    assert polys[0]["fit_residual_px_p90"] <= 2.5
    assert polys[0]["closed"] is True
    assert len(polys[0]["points_px"]) == 5


def test_grouped_v_curve_accepts_one_sharp_turn_with_bridge_spans():
    from skimage.morphology import dilation, disk

    from tools.shape_vectorize_v7 import vectorize_group

    shape = (90, 120)
    members = [
        _component(shape, [((14, 20), (32, 38))]),
        _component(shape, [((37, 42), (48, 31))]),
        _component(shape, [((53, 27), (72, 18))]),
    ]
    union = np.zeros(shape, dtype=bool)
    for m in members:
        union |= m
    glow = dilation(union, disk(7))
    polys = vectorize_group(members, members, ["open_stroke"] * 3, ["s0", "s1", "s2"], union.astype(float), glow, np.zeros((*shape, 3), dtype=np.uint8))
    assert polys is not None
    assert polys[0]["geometry_kind"] == "dotted_arc_path"
    assert polys[0].get("bridge_spans")
    assert len([b for b in polys[0].get("bridges", []) if b["glow_coverage"] >= 0.85]) == len(polys[0]["bridges"])


def test_zigzag_dot_constellation_rejects_chain_and_falls_back_to_anchors():
    from skimage.morphology import dilation, disk

    from tools.shape_vectorize_v7 import group_chain_rejection_reasons, vectorize_component, vectorize_group

    shape = (100, 120)
    members = [
        _component(shape, [((10, 20), (30, 20))]),
        _component(shape, [((33, 23), (33, 50))]),
        _component(shape, [((36, 53), (36, 25))]),
        _component(shape, [((39, 22), (70, 22))]),
    ]
    union = np.zeros(shape, dtype=bool)
    for m in members:
        union |= m
    glow = dilation(union, disk(18))
    assert vectorize_group(members, members, ["dot"] * 4, ["s0", "s1", "s2", "s3"], union.astype(float), glow, np.zeros((*shape, 3), dtype=np.uint8)) is None
    reasons = group_chain_rejection_reasons(members, glow)
    assert "chain_sharp_turns_above_threshold" in reasons or "chain_mean_turn_above_threshold" in reasons
    anchors = []
    for i, m in enumerate(members):
        anchors.extend(vectorize_component(m, "dot", union.astype(float), f"s{i}", structure_mask=m))
    assert [p["geometry_kind"] for p in anchors] == ["dot_anchor", "dot_anchor", "dot_anchor", "dot_anchor"]


def test_two_compact_dots_sharing_glow_stay_anchors():
    from skimage.morphology import dilation, disk

    from tools.shape_vectorize_v7 import vectorize_component, vectorize_group

    shape = (60, 80)
    members = [
        _component(shape, [((24, 30), (24, 30))]),
        _component(shape, [((38, 30), (38, 30))]),
    ]
    glow = dilation(members[0] | members[1], disk(10))
    assert vectorize_group(members, members, ["dot", "dot"], ["s0", "s1"], np.zeros(shape), glow, np.zeros((*shape, 3), dtype=np.uint8)) is None
    anchors = []
    for i, m in enumerate(members):
        anchors.extend(vectorize_component(m, "dot", np.ones(shape), f"s{i}", structure_mask=m))
    assert [p["geometry_kind"] for p in anchors] == ["dot_anchor", "dot_anchor"]


def test_artifact_rejection_marks_tiny_dim_far_speck():
    from tools.shape_extract_v7 import _find_artifact_rejections
    from tools.shape_vectorize_v7 import sample_geometry_points

    shape = (50, 80)
    speck = np.zeros(shape, dtype=bool)
    speck[5:8, 5:8] = True
    main = np.zeros(shape, dtype=bool)
    _draw_line(main, (42, 25), (64, 25), radius=1)
    comp_infos = [
        {"component_id": "s0", "area_px": int(speck.sum()), "aperture_label": "image_left",
         "centroid_px": [6.0, 6.0], "peak_score": 10.0},
        {"component_id": "s1", "area_px": int(main.sum()), "aperture_label": "image_left",
         "centroid_px": [53.0, 25.0], "peak_score": 100.0},
    ]
    polylines = [{"component_id": "s1", "geometry_kind": "line_centerline", "render_role": "render",
                  "aperture": "image_left", "points_px": [[42.0, 25.0], [64.0, 25.0]]}]
    reasons = _find_artifact_rejections(comp_infos, polylines, {"s1"}, sample_geometry_points)
    assert set(reasons) == {"s0"}
    assert reasons["s0"].startswith("tiny_dim_far_artifact:")


def test_bridge_metrics_exclude_bridge_samples_from_precision_halo_and_residual():
    from tools.shape_validation_v2 import compute_metrics

    shape = (40, 70)
    core = np.zeros(shape, dtype=bool)
    _draw_line(core, (10, 20), (24, 20), radius=1)
    _draw_line(core, (36, 20), (50, 20), radius=1)
    glow = np.zeros(shape, dtype=bool)
    _draw_line(glow, (10, 20), (50, 20), radius=3)
    polys = [{
        "component_id": "s0",
        "geometry_kind": "dotted_arc_path",
        "closed": False,
        "ordered": True,
        "points_px": [[10.0, 20.0], [24.0, 20.0], [36.0, 20.0], [50.0, 20.0]],
        "bridge_spans": [[1, 2]],
    }]
    metrics = compute_metrics(polys, core, glow, structure_mask=core)
    assert metrics["core_precision"] == 1.0
    assert metrics["halo_spill"] == 0.0
    assert metrics["vector_fit_residual_px_p95"] == 0.0


def test_status_cap_prevents_core_mask_authority_conflict():
    from tools.shape_extract_v7 import _cap_status_for_render_authority

    status, reasons = _cap_status_for_render_authority("authority", [], "core_mask")
    assert status == "provisional"
    assert reasons == ["render_authority_core_mask"]
