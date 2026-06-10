"""PR-G1 v6 compatibility shim — typed stroke-vectorization supersedes v5 candidates."""

from __future__ import annotations

from tools.shape_stroke_vectorization import (  # noqa: F401
    SHAPE_TYPES,
    VECTORIZER_NAMES,
    classify_visual_status,
    classify_shape_type,
    run_typed_vectorization,
    score_geometry_fit,
)

# Legacy names kept for tests referencing v5 candidate list migration.
CANDIDATE_NAMES = VECTORIZER_NAMES
