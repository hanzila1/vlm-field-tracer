# Changelog

## v6.0.0 — Current

### Fixed
- **FIX 3 — No more gaps in lines**
  - Root cause: VLM draws lines with slight brightness fade at junctions and corners. Hard threshold at 128 drops faint pixels → holes in mask → gaps in skeleton → breaks in output lines.
  - Solution: Adaptive Otsu thresholding instead of fixed 128; dilation before skeletonisation to bridge micro-gaps; large morphological CLOSE kernel (7×7, 3 iterations); post-skeleton gap bridging to reconnect nearby endpoints.

- **FIX 4 — Straight smooth lines (no more jagged staircase edges)**
  - Root cause: Contour tracing follows pixel diagonals producing staircase artefacts. Douglas-Peucker alone cannot straighten these.
  - Solution: Bearing-based straightening pass collapses collinear-ish point runs to their two endpoints; increased DP epsilon default (3.0).

### Added
- **FIX 5 — SHP output alongside GeoJSON**
  - `<stem>_ftw_lines.geojson` — LineStrings only
  - `<stem>_ftw_points.geojson` — Points only
  - `<stem>_ftw_lines.shp` — Shapefile (lines)
  - `<stem>_ftw_points.shp` — Shapefile (points)
  - `<stem>_ftw_combined.geojson` — all features combined (legacy)

---

## v5.0.0

- Dual VLM call per tile (lines + points)
- Graph-walk skeleton tracer with proper junction handling
- Auto snap tolerance (5px geo units)

## v4.0.0

- Grid tiling support (`--grid NxM`)
- Gemini API integration
- GeoJSON output with UUID per feature

## v3.0.0

- Endpoint snapping
- Douglas-Peucker simplification

## v2.0.0

- Skeleton-based line extraction
- Geographic coordinate conversion

## v1.0.0

- Initial release — single-tile VLM pipeline
