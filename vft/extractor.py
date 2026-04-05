"""
Feature extraction — convert VLM output images into geospatial features.

  extract_lines  : full v6 pipeline (gap-free, straight, continuous lines)
  extract_points : urban/non-agricultural point centroids
"""

import math
import numpy as np
import cv2
from PIL import Image
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union
from skimage.morphology import skeletonize, remove_small_objects, remove_small_holes

from .skeleton import bridge_skeleton_gaps, snap_endpoints
from .tracer   import _agfe_trace_skeleton
from .debug    import save_png


# ═══════════════════════════════════════════════════════════════════════════════
# COORDINATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def px_to_geo(px, py, bounds, tw, th):
    x = bounds.left + (px / tw) * (bounds.right - bounds.left)
    y = bounds.top  - (py / th) * (bounds.top   - bounds.bottom)
    return (x, y)


def geo_to_px_fn(bounds, tw, th):
    def _fn(gx, gy):
        px_ = int((gx - bounds.left) / (bounds.right - bounds.left) * tw)
        py_ = int((bounds.top - gy)  / (bounds.top   - bounds.bottom) * th)
        return (px_, py_)
    return _fn


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACT FIELD LINES — v6: gap-free + straight
# ═══════════════════════════════════════════════════════════════════════════════

def extract_lines(vlm_image, tile_bounds, pixel_size,
                  min_line_length=20, snap_tolerance_geo=0.0,
                  dp_epsilon=3.0, max_gap_px=25,
                  angle_tolerance_deg=8.0, tag=""):
    """
    Full v6 pipeline — gap-free, straight, continuous field boundary lines.

    Steps:
      1.  Resize VLM output to tile pixel size
      2.  Grayscale + Otsu thresholding (adaptive — no fixed 128 cutoff)
      3.  Large morphological CLOSE (7×7, 3 iter) — seals gaps in mask
      4.  Dilation to thicken thin lines before skeletonisation
      5.  Zhang-Suen skeleton → 1px centrelines
      6.  Gap bridging — reconnect broken skeleton endpoints (≤ max_gap_px)
      7.  Contour trace + Douglas-Peucker simplification
      8.  Pixel → geographic coordinate conversion (per vertex)
      9.  shapely linemerge — stitch touching polylines
      10. Straightening pass — collapse staircase runs to straight segments
      11. Endpoint snapping — close junction gaps
      12. Minimum length filter
    """
    tw, th = pixel_size
    b      = tile_bounds

    # ── 1. Resize ─────────────────────────────────────────────────────────
    vlm_r   = vlm_image.resize((tw, th), Image.LANCZOS)
    arr_rgb = np.array(vlm_r)
    save_png("01_vlm_raw", vlm_r, tag)

    # ── 2. Extract thin black lines from VLM output ──────────────────────
    gray = cv2.cvtColor(arr_rgb, cv2.COLOR_RGB2GRAY)
    save_png("02_gray", gray, tag)
    mean_brightness = float(gray.mean())
    print(f"   📊 Brightness: {mean_brightness:.1f}")

    color_mask = cv2.inRange(arr_rgb,
                             np.array([0,   0,   0  ], dtype=np.uint8),
                             np.array([60,  60,  60 ], dtype=np.uint8))
    dark_mask  = (gray < 100).astype(np.uint8) * 255
    thin_mask  = cv2.bitwise_or(color_mask, dark_mask)
    save_png("03_mask_otsu", thin_mask, tag)

    # ── 3. Remove noise ───────────────────────────────────────────────────
    binary = thin_mask > 128
    binary = remove_small_objects(binary, max_size=20)
    binary = remove_small_holes(binary, max_size=10)
    save_png("04_mask_closed", (binary * 255).astype(np.uint8), tag)

    # ── 4. FATTEN thin lines into solid blobs ─────────────────────────────
    fat = cv2.dilate(
        (binary * 255).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)),
        iterations=2
    )
    save_png("05_mask_dilated", fat, tag)

    # ── 5. Skeletonize ────────────────────────────────────────────────────
    skel_bool = skeletonize(fat > 128)
    skeleton  = (skel_bool * 255).astype(np.uint8)
    save_png("06_skeleton", skeleton, tag)

    if cv2.countNonZero(skeleton) == 0:
        print("   ⚠️  Empty skeleton — no lines found")
        return []

    # ── 6. Bridge any remaining small gaps ───────────────────────────────
    skeleton  = bridge_skeleton_gaps(skeleton, max_gap_px=max_gap_px)
    skel_bool = skeleton > 0
    save_png("07_skeleton_bridged", skeleton, tag)

    # ── 7. Trace ──────────────────────────────────────────────────────────
    paths = _agfe_trace_skeleton(skel_bool)
    print(f"   📐 Skeleton paths traced: {len(paths)}")

    # ── 8. Geo conversion + simplify ─────────────────────────────────────
    geo_lines    = []
    debug_raw    = np.ones((th, tw, 3), dtype=np.uint8) * 255
    geo_per_px   = ((abs(b.right - b.left) / tw) + (abs(b.top - b.bottom) / th)) / 2
    min_geo_len  = min_line_length * geo_per_px
    simplify_geo = dp_epsilon * 3.0 * (abs(b.right - b.left) / tw)

    for path_xy in paths:
        if len(path_xy) < 2:
            continue
        px_len = sum(
            math.hypot(path_xy[j+1][0]-path_xy[j][0], path_xy[j+1][1]-path_xy[j][1])
            for j in range(len(path_xy)-1)
        )
        if px_len < min_line_length:
            continue
        for i in range(len(path_xy) - 1):
            cv2.line(debug_raw,
                     (int(path_xy[i][0]),   int(path_xy[i][1])),
                     (int(path_xy[i+1][0]), int(path_xy[i+1][1])),
                     (0, 60, 200), 2)
        geo_coords = [px_to_geo(float(p[0]), float(p[1]), b, tw, th) for p in path_xy]
        try:
            ln = LineString(geo_coords)
            if simplify_geo > 0:
                ln = ln.simplify(simplify_geo, preserve_topology=True)
            if ln.is_valid and not ln.is_empty and ln.length >= min_geo_len:
                geo_lines.append(ln)
        except Exception:
            continue

    save_png("08_contours_raw", debug_raw, tag)
    print(f"   📏 Geo lines before merge: {len(geo_lines)}")

    if not geo_lines:
        return []

    # ── 9. linemerge ─────────────────────────────────────────────────────
    merged = linemerge(unary_union(geo_lines))
    if merged.is_empty:
        return []
    if merged.geom_type == 'LineString':
        merged_lines = [merged]
    elif merged.geom_type == 'MultiLineString':
        merged_lines = list(merged.geoms)
    else:
        merged_lines = [g for g in merged.geoms if g.geom_type == 'LineString']
    print(f"   🔗 After linemerge: {len(merged_lines)} lines")

    # ── 10. Auto snap ─────────────────────────────────────────────────────
    auto_snap = geo_per_px * 5.0
    effective_snap = snap_tolerance_geo if snap_tolerance_geo > 0 else auto_snap
    merged_lines = snap_endpoints(merged_lines, effective_snap)
    print(f"   📍 After snap ({effective_snap:.4f} geo): {len(merged_lines)} lines")

    # ── 11. Final length filter ───────────────────────────────────────────
    final_lines = [ln for ln in merged_lines
                   if ln.is_valid and not ln.is_empty and ln.length >= min_geo_len]
    print(f"   ✅ Final lines: {len(final_lines)}")

    # Debug: draw final lines
    g2p         = geo_to_px_fn(b, tw, th)
    debug_final = np.ones((th, tw, 3), dtype=np.uint8) * 255
    for ln in final_lines:
        coords = list(ln.coords)
        for i in range(len(coords) - 1):
            cv2.line(debug_final, g2p(*coords[i]), g2p(*coords[i+1]),
                     (180, 0, 0), 2)
    save_png("09_lines_final", debug_final, tag)

    return final_lines


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACT POINTS
# ═══════════════════════════════════════════════════════════════════════════════

def extract_points(vlm_image, tile_bounds, pixel_size, min_dot_area=20, tag=""):
    tw, th = pixel_size
    vlm_r  = vlm_image.resize((tw, th), Image.LANCZOS)
    arr    = np.array(vlm_r)
    save_png("10_points_vlm_raw", vlm_r, tag)

    gray  = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    mean_ = float(gray.mean())
    print(f"   📊 Points brightness: {mean_:.1f}")

    gray_inv = cv2.bitwise_not(gray)
    _, dot_mask = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    save_png("11_points_mask", dot_mask, tag)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dot_mask, connectivity=8
    )
    print(f"   🔢 Dot components: {num_labels - 1}")

    b         = tile_bounds
    points    = []
    debug_img = np.ones((th, tw, 3), dtype=np.uint8) * 255

    for lid in range(1, num_labels):
        area = stats[lid, cv2.CC_STAT_AREA]
        if area < min_dot_area:
            continue
        cx, cy = int(centroids[lid][0]), int(centroids[lid][1])
        cv2.circle(debug_img, (cx, cy), 6, (220, 50, 50), -1)
        geo_x, geo_y = px_to_geo(cx, cy, b, tw, th)
        try:
            pt = Point(geo_x, geo_y)
            if pt.is_valid:
                points.append(pt)
        except Exception:
            continue

    save_png("12_points_detected", debug_img, tag)
    print(f"   ✅ {len(points)} points extracted")
    return points
