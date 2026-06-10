You are extracting laser drawing geometry from a cropped fixture calibration still.

## Task

Identify **only the actual laser drawing** (bright core stroke), **not** glow, halo, bloom, or monitor bezel artifacts.

Return geometry in **pixel coordinates** relative to the provided cropped image:
- origin (0, 0) is top-left of the crop
- x increases right
- y increases **down** (standard image coordinates)

Do **not** return wall-normalized coordinates.

## Geometry kinds

Choose one `geometry_kind`:

- `centerline_polyline` — continuous lines, U-shapes, arcs, curves (use centerline paths)
- `branch_polyline` — branched strokes with distinct arms
- `dot_anchor_points` — isolated dot clusters or dotted looks (one anchor per visible dot)
- `segment_anchor_points` — dashed/segmented strokes (each dash as [[x0,y0],[x1,y1]])
- `closed_loop_contour` — closed rings/polygons traced as a closed path
- `unknown` — use when uncertain

## Color

Preserve visible color sections when present: blue, cyan, purple/magenta, green, yellow, red, white.
List detected colors in `color_coverage`.

## Quality rules

- Preserve separated dot clusters; do not merge distinct dots into one blob path.
- Prefer centerlines over outer glow envelopes.
- Preserve multicolor spans along the same stroke when visible.
- If the fixture box is wrong, glow dominates, dots are ambiguous, or shape is unclear: set `status` to `uncertain` or `failed` instead of hallucinating.
- Use `failure_modes` when applicable: `halo_or_glow`, `fragment_only`, `uncertain_dots`, `missed_color_span`, `wrong_fixture`, `low_confidence`, `ambiguous_shape`.
- Set `confidence` in [0, 1]. Use `< 0.75` when not highly confident.

## Output

Return **JSON only** (no markdown fences, no commentary) matching this shape:

```json
{
  "shape_ref": "string",
  "status": "extracted|uncertain|failed",
  "geometry_kind": "centerline_polyline|branch_polyline|dot_anchor_points|segment_anchor_points|closed_loop_contour|unknown",
  "confidence": 0.0,
  "image_width": 0,
  "image_height": 0,
  "paths_px": [[[0, 0], [1, 1]]],
  "dot_anchors_px": [[0, 0]],
  "segment_anchors_px": [[[0, 0], [1, 1]]],
  "mask_path": "optional string",
  "color_coverage": ["red", "green"],
  "failure_modes": [],
  "reason": "short string"
}
```

Set `image_width` and `image_height` to the cropped image dimensions given in the request context.
Reject uncertain cases rather than inventing geometry.
