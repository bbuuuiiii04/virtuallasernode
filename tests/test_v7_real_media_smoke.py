"""V7 real-media smoke tests for 3 named captures (skipif no media/no numpy)."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CAPTURE_ROOT = REPO_ROOT

SMOKE_REFS = {
    "sh1_21b9e82ef84b930b": {
        "desc": "row-of-squares",
        "expect_closed_strokes_gte": 4,
        "expect_status_in": {"authority", "provisional", "quarantined"},
        "must_not_status": set(),
    },
    "sh1_41c84ad2ac1f458e": {
        "desc": "dual-dot",
        "expect_dots_exact": 2,
        "expect_status_in": {"authority", "provisional", "quarantined"},
    },
    "sh1_adb58093da473f3e": {
        "desc": "cue_002 red arcs",
        "expect_status_in": {"authority", "provisional", "quarantined"},
        "no_fragment_only": True,
    },
}

# Check prerequisites
_skimage = pytest.importorskip("skimage", reason="scikit-image required")
_numpy = pytest.importorskip("numpy", reason="numpy required")

# Check media presence
_geom_path = CAPTURE_ROOT / "captures/fixture_model/analysis_geometry.json"
_selection_path = CAPTURE_ROOT / "artifacts/renderer/pr-g1-shape-authority/shape_selection.json"

media_available = False
if _geom_path.exists() and _selection_path.exists():
    import json
    try:
        with open(_selection_path) as f:
            data = json.load(f)
        
        # Check if the three specific stills exist
        from tools.shape_extract_v7 import compute_shape_ref
        
        found_stills = 0
        expected_refs = set(SMOKE_REFS.keys())
        for e in data.get("entries", []):
            vk = e.get("vector_key", "")
            cp = e.get("capture_path", "")
            box = e.get("selected_fixture_box", "image_left")
            ref = compute_shape_ref(vk, cp, box)
            if ref in expected_refs:
                still_path = CAPTURE_ROOT / e.get("still_path", "")
                if still_path.exists() or (still_path.parent / "still_color.jpg").exists():
                    found_stills += 1
        
        media_available = found_stills == len(expected_refs)
    except Exception:
        pass

pytestmark = pytest.mark.skipif(not media_available, reason="Local media not available")


def _run_extraction(shape_ref):
    """Run v7 extraction for a single ref, return the record dict."""
    from tools.shape_core_mask import load_analysis_geometry, load_fixture_boxes
    from tools.shape_extract_v7 import extract_record, find_entry_by_ref, load_selection

    entries = load_selection(_selection_path)
    entry = find_entry_by_ref(entries, shape_ref)
    if entry is None:
        pytest.skip(f"ref {shape_ref} not found in selection")

    geom = load_analysis_geometry(_geom_path)

    params = {"k_core": 8.0, "k_glow": 3.5, "sat_floor": 200, "min_core_area_px": 20}
    record = extract_record(entry, shape_ref, CAPTURE_ROOT, geom, _geom_path, params)
    record.pop("_rle_data", None)
    return record


def _path_span_px(pl):
    xs = [p[0] for p in pl["points_px"]]
    ys = [p[1] for p in pl["points_px"]]
    return ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5


def test_row_of_squares_has_four_or_more_closed_strokes():
    ref = "sh1_21b9e82ef84b930b"
    r = _run_extraction(ref)
    topo = r["topology_summary"]
    assert topo["closed_strokes"] >= 4, (
        f"row-of-squares: expected >=4 closed_strokes, got {topo}"
    )


def test_row_of_squares_boxes_are_clean_rectangles():
    """Final render geometry for the squares must be snapped rectangles.

    A wobbly skeleton trace (closed_centerline with many points) as final
    render geometry is the squiggly-box failure mode and must fail here.
    """
    ref = "sh1_21b9e82ef84b930b"
    r = _run_extraction(ref)

    closed_comp_ids = {
        c["component_id"] for c in r["components"] if c["class"] == "closed_stroke"
    }
    assert len(closed_comp_ids) >= 4

    rects = [pl for pl in r["polylines"] if pl["geometry_kind"] == "rect_centerline"]
    assert len(rects) >= 4, (
        f"expected >=4 rect_centerline render polylines, got "
        f"{[pl['geometry_kind'] for pl in r['polylines']]}"
    )
    for pl in rects:
        assert pl["render_role"] == "render"
        assert pl["closed"] is True
        assert len(pl["points_px"]) == 5, "rectangle must be a clean 4-corner loop"
        assert pl["fit_residual_px_p90"] <= 2.0, (
            f"rectangle fit residual too high: {pl['fit_residual_px_p90']}"
        )
    # Every closed-stroke component is represented by a rectangle
    assert closed_comp_ids <= {pl["component_id"] for pl in rects}

    # No squiggly skeleton trace may remain as render geometry
    for pl in r["polylines"]:
        if pl["render_role"] == "render" and pl["geometry_kind"] == "closed_centerline":
            assert len(pl["points_px"]) <= 8, (
                "closed_centerline render geometry with many points — squiggly box"
            )


def test_row_of_squares_sibling_aperture_traced():
    """The sibling aperture shows the same 4 squares; they must be traced
    (rectangles), not just bounding-boxed."""
    ref = "sh1_21b9e82ef84b930b"
    r = _run_extraction(ref)

    assert len(r["sibling_aperture_component_ids"]) > 0
    sib_rects = [
        pl for pl in r["sibling_polylines"]
        if pl["geometry_kind"] == "rect_centerline" and pl["render_role"] == "render"
    ]
    assert len(sib_rects) >= 4, (
        f"sibling squares not traced: {[pl['geometry_kind'] for pl in r['sibling_polylines']]}"
    )
    # Every sibling component must carry render geometry (bbox is not tracing)
    sib_with_render = {
        pl["component_id"] for pl in r["sibling_polylines"]
        if pl["render_role"] == "render"
    }
    assert set(r["sibling_aperture_component_ids"]) <= sib_with_render
    assert r["fixture_output_accounting_complete"] is True
    assert r["status"] == "authority", f"got {r['status']}: {r['status_reasons']}"


def test_dual_dot_exactly_two_dot_anchors():
    ref = "sh1_41c84ad2ac1f458e"
    r = _run_extraction(ref)
    dot_polys = [pl for pl in r["polylines"] if pl["geometry_kind"] == "dot_anchor"]
    assert len(dot_polys) == 2, (
        f"dual-dot: expected exactly 2 dot_anchor polylines, got {len(dot_polys)}"
    )
    # Each dot_anchor has exactly 1 point and is render geometry
    for dp in dot_polys:
        assert len(dp["points_px"]) == 1, f"dot_anchor must have 1 point, got {dp['points_px']}"
        assert dp["render_role"] == "render"
    # Dot anchors ARE the render geometry — no mask fallback
    assert r["render_authority"] == "vector", (
        f"dual-dot must have vector render authority, got {r['render_authority']}"
    )
    # Sibling dots traced as well
    sib_dots = [
        pl for pl in r["sibling_polylines"]
        if pl["geometry_kind"] == "dot_anchor" and pl["render_role"] == "render"
    ]
    assert len(sib_dots) == len(r["sibling_aperture_component_ids"])
    assert r["status"] == "authority", f"got {r['status']}: {r['status_reasons']}"


def test_cue_002_dotted_arcs_traced_as_real_geometry():
    """cue_002: BOTH aperture arcs must be real render geometry.

    The red dotted arc evidence must become an ordered open polyline through
    the dash centers. A tiny partial trace, a sibling bbox, or a mask
    fallback are failure modes and must fail this test.
    """
    ref = "sh1_adb58093da473f3e"
    r = _run_extraction(ref)

    assert len(r["components"]) > 0, "cue_002: no components detected"
    comp_classes = [c["class"] for c in r["components"]]
    assert "closed_stroke" in comp_classes, (
        f"cue_002: expected closed_stroke classification, got {comp_classes}"
    )

    # Selected aperture: one ordered open arc path through the dashes
    arcs = [pl for pl in r["polylines"] if pl["geometry_kind"] == "dotted_arc_path"]
    assert len(arcs) >= 1, (
        f"cue_002: no dotted_arc_path geometry, got "
        f"{[pl['geometry_kind'] for pl in r['polylines']]}"
    )
    for pl in arcs:
        assert pl["render_role"] == "render", "arc demoted to diagnostic — not final geometry"
        assert pl["closed"] is False and pl["ordered"] is True
        assert pl["dash_count"] >= 2
        assert _path_span_px(pl) >= 25.0, (
            f"cue_002: arc span {_path_span_px(pl):.1f}px — tiny partial trace"
        )

    # Sibling aperture arc must ALSO be traced (same fixture, same DMX state)
    assert len(r["sibling_aperture_component_ids"]) > 0
    sib_arcs = [
        pl for pl in r["sibling_polylines"]
        if pl["geometry_kind"] == "dotted_arc_path" and pl["render_role"] == "render"
    ]
    assert len(sib_arcs) >= 1, (
        "cue_002: sibling aperture arc is not traced — a bbox is not tracing"
    )
    for pl in sib_arcs:
        assert _path_span_px(pl) >= 25.0

    # The geometry must reconstruct the laser structure (no partial trace)
    m = r["metrics"]
    assert m["recall_basis"] == "structure_skeleton"
    assert m["core_recall"] >= 0.8, f"cue_002: recall {m['core_recall']} — partial trace"
    assert m["core_precision"] >= 0.9

    # Vector render authority — mask fallback is NOT the final success state
    assert r["render_authority"] == "vector", (
        f"cue_002: render_authority must be 'vector', got {r['render_authority']}"
    )
    assert r["geometry_layers"]["render_vectors"] == "derived_validated"
    assert r["geometry_layers"]["render_fallback"] == "none"
    assert r["fixture_output_accounting_complete"] is True
    assert r["status"] == "authority", f"got {r['status']}: {r['status_reasons']}"
    assert r.get("authority_scope") == "aperture"


def test_no_diagnostic_vectors_promoted_to_render():
    """Diagnostic/debug vectors must never count as render geometry, and
    every render polyline must actually cover its component's structure."""
    for ref in SMOKE_REFS:
        r = _run_extraction(ref)
        for pl in r["polylines"] + r["sibling_polylines"]:
            assert pl.get("render_role") in {"render", "diagnostic"}
            assert pl["geometry_kind"] != "peak_contour" or pl["render_role"] == "diagnostic"
            if pl["render_role"] == "render" and pl["geometry_kind"] != "dot_anchor":
                assert pl["structure_coverage"] >= 0.6, (
                    f"{ref}: render polyline with structure_coverage "
                    f"{pl['structure_coverage']} — debug vector promoted to render"
                )



def test_cue_002_out_of_box_geometry_preserved():
    """cue_002: components at box boundary preserved with out_of_box flag."""
    ref = "sh1_adb58093da473f3e"
    r = _run_extraction(ref)
    # At least one component should exist (full ROI detection)
    assert len(r["components"]) >= 1

    # If out_of_box components exist, their wall_norm coords should go beyond [-1,1]
    for comp in r["components"]:
        if comp.get("out_of_box_geometry"):
            bbox_wn = comp.get("bbox_wall_norm", [])
            if bbox_wn:
                # At least one coordinate outside [-1,1]
                outside = any(abs(v) > 1.0 for v in bbox_wn)
                assert outside, (
                    f"out_of_box_geometry component has bbox_wall_norm {bbox_wn} "
                    "fully within [-1,1] — should have values outside"
                )


def test_all_smoke_records_have_valid_schema():
    """All 3 smoke records have required fields."""
    required = ["record_version", "shape_ref", "vector_key", "fixture_box_label",
                "authority_scope", "selected_aperture", "source_frame_accounting_complete",
                "fixture_output_accounting_complete", "geometry_layers", "source_core_components",
                "included_component_ids", "sibling_aperture_component_ids",
                "unaccounted_component_ids", "component_structure_coverage",
                "extraction", "core_mask", "components", "polylines", "sibling_polylines",
                "topology_summary", "metrics", "status", "authority_eligible",
                "status_reasons", "quality_flags", "render_authority"]

    for ref in SMOKE_REFS:
        r = _run_extraction(ref)
        for field in required:
            assert field in r, f"{ref}: missing required field '{field}'"
        assert r["extraction"]["policy_version"] == "v7"
        assert r["record_version"] == "shape-authority-v2"


def test_smoke_metrics_are_in_range():
    for ref in SMOKE_REFS:
        r = _run_extraction(ref)
        m = r["metrics"]
        assert 0.0 <= m["core_precision"] <= 1.0, f"{ref}: precision out of range"
        assert 0.0 <= m["core_recall"] <= 1.0, f"{ref}: recall out of range"
        assert 0.0 <= m["halo_spill"] <= 1.0, f"{ref}: halo_spill out of range"
        assert m["vector_fit_residual_px_p95"] >= 0.0, f"{ref}: negative p95 residual"
