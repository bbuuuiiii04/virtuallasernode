"""Every selected shape must expose geometry_kind and ordered metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from tools.shape_extraction import FixtureBox, extract_shape_from_image  # noqa: E402

LIBRARY = ROOT / "artifacts/renderer/shape_library_v1.json"
BOX = FixtureBox(label="image_left", x0=0, y0=0, x1=200, y1=200)


def test_extraction_includes_geometry_kind_and_ordered() -> None:
    img = Image.new("RGB", (200, 200), (14, 14, 18))
    px = img.load()
    for x in range(40, 160):
        px[x, 100] = (255, 255, 255)
    out = extract_shape_from_image(img, BOX, min_area_px=6)
    assert out.get("geometry_kind")
    assert "ordered" in out
    assert isinstance(out["ordered"], bool)
    for poly in out.get("polylines") or []:
        assert poly.get("geometry_kind")
        assert "ordered" in poly


@pytest.mark.skipif(not LIBRARY.is_file(), reason="shape library not built")
def test_library_shapes_have_geometry_kind_contract() -> None:
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    for shape in library.get("shapes") or []:
        assert shape.get("geometry_kind"), f"missing geometry_kind on {shape.get('shape_ref')}"
        assert "ordered" in shape, f"missing ordered on {shape.get('shape_ref')}"
        assert "rejection_reasons" in shape
        for poly in shape.get("polylines") or []:
            assert poly.get("geometry_kind"), f"polyline missing geometry_kind on {shape.get('shape_ref')}"
            assert "ordered" in poly
