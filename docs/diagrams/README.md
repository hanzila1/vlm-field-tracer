# Diagrams

This folder contains visual diagrams, result screenshots, and comparison figures
for the VLM-Field-Tracer project.

## Suggested Content

Place your result images here before pushing to GitHub or presenting.

### Recommended images to add:

| Filename | What to put here |
|---|---|
| `01_input_sentinel2.png` | Raw Sentinel-2 GeoTIFF rendered as RGB |
| `02_vlm_lines_output.png` | Raw VLM output — black lines on white |
| `03_skeleton.png` | Skeleton after gap bridging |
| `04_final_lines.png` | Extracted LineStrings overlaid on image |
| `05_final_points.png` | Urban point markers overlaid on image |
| `06_qgis_result.png` | Final SHP loaded in QGIS |
| `comparison_ftw_vs_vft.png` | Side-by-side with FTW baseline output |

### Pipeline debug stages

The pipeline automatically saves 13 debug PNGs per tile to `outputs/<stem>_debug_pngs/`.
Copy representative examples here for documentation.

```
00_input_fullres.png      ← Original GeoTIFF
01_vlm_raw.png            ← Raw VLM lines response
02_gray.png               ← Grayscale conversion
03_mask_otsu.png          ← Otsu binary mask
04_mask_closed.png        ← After noise removal
05_mask_dilated.png       ← After dilation (fat blobs)
06_skeleton.png           ← Zhang-Suen skeleton
07_skeleton_bridged.png   ← After gap bridging
08_contours_raw.png       ← Traced paths (blue)
09_lines_final.png        ← Final lines (dark red)
10_points_vlm_raw.png     ← Raw VLM points response
11_points_mask.png        ← Points binary mask
12_points_detected.png    ← Detected centroids
13_final_overlay.png      ← All features on original
```
