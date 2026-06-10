"""V7: §15 metric math — shifted geometry fails precision; missing stroke fails recall; halo fails spill."""

import numpy as np
import pytest

pytest.importorskip("skimage", reason="scikit-image required")


def _make_hline_masks(H=32, W=64, row=16, x0=10, x1=54):
    """Returns core_mask and glow_mask for a horizontal stroke."""
    core = np.zeros((H, W), dtype=bool)
    core[row, x0:x1] = True
    glow = np.zeros((H, W), dtype=bool)
    glow[row - 3:row + 4, x0 - 3:x1 + 3] = True
    return core, glow


def _line_polyline(row, x0, x1, comp_id="c0"):
    pts = [[float(x), float(row)] for x in range(x0, x1 + 1, 3)]
    return [{"component_id": comp_id, "geometry_kind": "open_centerline",
             "closed": False, "ordered": True, "points_px": pts,
             "points_wall_norm": pts, "point_count": len(pts)}]


def test_on_core_geometry_passes_all_gates():
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics

    core, glow = _make_hline_masks()
    polys = _line_polyline(16, 10, 54)
    m = compute_metrics(polys, core, glow)
    m["components_detected"] = 1
    m["components_vectorized"] = 1
    assert m["core_precision"] >= 0.90, f"precision={m['core_precision']}"
    assert m["core_recall"] >= 0.80, f"recall={m['core_recall']}"
    assert m["halo_spill"] <= 0.05, f"halo_spill={m['halo_spill']}"
    eligible, status, reasons = compute_authority_gate(m, 1, 1, [])
    assert eligible
    assert status == "authority"
    assert reasons == []


def test_shifted_geometry_fails_precision():
    """Geometry shifted 10 px off-core: precision should fail."""
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics

    core, glow = _make_hline_masks()
    polys = _line_polyline(16 + 10, 10, 54)  # shifted 10px down
    m = compute_metrics(polys, core, glow)
    m["components_detected"] = 1
    m["components_vectorized"] = 1
    assert m["core_precision"] < 0.90, f"Expected precision<0.90 for shifted geom, got {m['core_precision']}"
    eligible, status, _ = compute_authority_gate(m, 1, 1, [])
    assert not eligible
    assert status in ("quarantined", "provisional")


def test_missing_stroke_half_fails_recall():
    """Geometry covers only first half of stroke: recall should fail."""
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics

    core, glow = _make_hline_masks(x0=10, x1=54)
    polys = _line_polyline(16, 10, 30)  # only left half
    m = compute_metrics(polys, core, glow)
    m["components_detected"] = 1
    m["components_vectorized"] = 1
    assert m["core_recall"] < 0.80, f"Expected recall<0.80 for half-coverage, got {m['core_recall']}"
    eligible, status, _ = compute_authority_gate(m, 1, 1, [])
    assert not eligible


def test_halo_trace_fails_spill():
    """Geometry that traces the halo (not the core) should fail halo_spill."""
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics

    core, glow = _make_hline_masks(row=16)
    # Geometry at halo row (3 pixels away from core, still in glow)
    polys = _line_polyline(16 + 5, 10, 54)
    m = compute_metrics(polys, core, glow)
    m["components_detected"] = 1
    m["components_vectorized"] = 1
    # Should fail either precision or spill
    assert m["core_precision"] < 0.90 or m["halo_spill"] > 0.05, (
        f"Halo trace should fail: prec={m['core_precision']:.2f} spill={m['halo_spill']:.2f}"
    )
    eligible, status, _ = compute_authority_gate(m, 1, 1, [])
    assert not eligible


def test_vectorization_incomplete_degrades_to_provisional():
    """components_vectorized < components_detected => provisional (not quarantine)."""
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics

    core, glow = _make_hline_masks()
    polys = _line_polyline(16, 10, 54)
    m = compute_metrics(polys, core, glow)
    m["components_detected"] = 2
    m["components_vectorized"] = 1
    eligible, status, reasons = compute_authority_gate(m, 2, 1, [])
    assert not eligible
    assert status == "provisional"
    assert any("vectorization_incomplete" in r for r in reasons)


def test_fixture_ambiguous_quarantines():
    """fixture_assignment_ambiguous quality flag => quarantined."""
    from tools.shape_validation_v2 import compute_authority_gate, compute_metrics

    core, glow = _make_hline_masks()
    polys = _line_polyline(16, 10, 54)
    m = compute_metrics(polys, core, glow)
    m["components_detected"] = 1
    m["components_vectorized"] = 1
    eligible, status, reasons = compute_authority_gate(m, 1, 1, ["fixture_assignment_ambiguous"])
    assert not eligible
    assert status == "quarantined"
