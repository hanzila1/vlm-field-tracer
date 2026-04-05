# Architecture

This folder contains architecture diagrams for the VLM-Field-Tracer pipeline.

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        VLM-FIELD-TRACER                         │
│                  VLM Sketch Extraction Pipeline                  │
└─────────────────────────────────────────────────────────────────┘

  Input GeoTIFF (Sentinel-2 or any georeferenced raster)
       │
       ▼
  ┌──────────┐   Full-resolution load, percentile stretch,
  │ loader   │   multi-fallback EPSG/CRS detection
  └────┬─────┘
       │
       ▼
  ┌──────────┐   Split into NxM tiles, clip geo bounds,
  │  tiling  │   resize to Gemini API limit (4096px)
  └────┬─────┘
       │
  ╔════╪══════════════════════════════════════════╗
  ║    │  Per-tile loop                           ║
  ║    ├─────────────────┐                        ║
  ║    ▼                 ▼                        ║
  ║ ┌──────┐         ┌──────┐                     ║
  ║ │ VLM  │ LINES   │ VLM  │ POINTS              ║
  ║ │      │ prompt  │      │ prompt              ║
  ║ └──┬───┘         └──┬───┘                     ║
  ║    │                │                         ║
  ║    ▼                ▼                         ║
  ║ Black lines      Black dots                   ║
  ║ on white PNG     on white PNG                 ║
  ║    │                │                         ║
  ║    ▼                ▼                         ║
  ║ ┌─────────────┐  ┌─────────────┐             ║
  ║ │ extractor   │  │  extractor  │             ║
  ║ │ (lines)     │  │  (points)   │             ║
  ║ │             │  │             │             ║
  ║ │ 1. Resize   │  │ 1. Resize   │             ║
  ║ │ 2. Mask     │  │ 2. Invert   │             ║
  ║ │ 3. Denoise  │  │ 3. Otsu     │             ║
  ║ │ 4. Dilate   │  │ 4. CCA      │             ║
  ║ │ 5. Skeleton │  │ 5. Centroid │             ║
  ║ │ 6. Bridge   │  │ 6. Geo conv │             ║
  ║ │ 7. Trace    │  └──────┬──────┘             ║
  ║ │ 8. Geo conv │         │                    ║
  ║ │ 9. Merge    │         │                    ║
  ║ │ 10. Snap    │         │                    ║
  ║ │ 11. Filter  │         │                    ║
  ║ └──────┬──────┘         │                    ║
  ║        │                │                    ║
  ╚════════╪════════════════╪═══════════════════╝
           │                │
           └────────┬───────┘
                    │
                    ▼
             ┌────────────┐
             │  overlay   │  Draw lines + points over original
             └─────┬──────┘
                    │
                    ▼
             ┌────────────┐
             │   writer   │  GeoJSON + SHP + metadata
             └─────┬──────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
  _vft_lines   _vft_points  _vft_combined
  .geojson     .geojson     .geojson
  .shp                      + debug PNGs
```

## Module Dependency Graph

```
__main__.py
    ├── vft.loader      (GeoTIFFLoader)
    ├── vft.tiling      (parse_grid, create_tiles, prepare_tile_for_api)
    ├── vft.vlm         (call_vlm, PROMPT_LINES, PROMPT_POINTS)
    ├── vft.extractor   (extract_lines, extract_points)
    │       ├── vft.skeleton  (bridge_skeleton_gaps, snap_endpoints)
    │       ├── vft.tracer    (_agfe_trace_skeleton)
    │       └── vft.debug     (save_png)
    ├── vft.overlay     (save_overlay_png)
    │       └── vft.debug
    └── vft.writer      (build_and_save_outputs)
```

## Files in This Folder

| File | Description |
|---|---|
| `pipeline_overview.png` | Full pipeline flowchart (add your own render) |
| `module_graph.png` | Module dependency diagram |
| `skeleton_stages.png` | Visual comparison of skeleton processing stages |
