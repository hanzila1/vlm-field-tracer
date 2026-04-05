"""
Skeleton processing — gap bridging, line straightening, and endpoint snapping.
"""

import math
import numpy as np
import cv2
from shapely.geometry import LineString


# ═══════════════════════════════════════════════════════════════════════════════
# SKELETONISATION
# ═══════════════════════════════════════════════════════════════════════════════

def skeletonise(binary_mask):
    try:
        import cv2.ximgproc as xip
        skel = xip.thinning(binary_mask, thinningType=xip.THINNING_ZHANGSUEN)
        print("   🦴 Zhang-Suen thinning (ximgproc)")
        return skel
    except (ImportError, AttributeError):
        pass
    print("   🦴 Morphological skeleton fallback")
    img    = binary_mask.copy()
    skel   = np.zeros_like(img)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while True:
        eroded = cv2.erode(img, kernel)
        opened = cv2.dilate(eroded, kernel)
        diff   = cv2.subtract(img, opened)
        skel   = cv2.bitwise_or(skel, diff)
        img    = eroded.copy()
        if cv2.countNonZero(img) == 0:
            break
    return skel


# ═══════════════════════════════════════════════════════════════════════════════
# GAP BRIDGING — reconnect broken skeleton endpoints
# ═══════════════════════════════════════════════════════════════════════════════

def find_skeleton_endpoints(skeleton):
    """
    Find pixels in the skeleton that have exactly 1 neighbour (endpoints).
    These are where breaks/gaps start and end.
    """
    kernel = np.ones((3, 3), dtype=np.uint8)
    neighbour_count = cv2.filter2D(
        (skeleton > 0).astype(np.uint8), -1, kernel
    )
    endpoints = np.argwhere((skeleton > 0) & (neighbour_count == 2))
    return endpoints  # array of [row, col]


def bridge_skeleton_gaps(skeleton, max_gap_px=25):
    """
    Find pairs of skeleton endpoints that are close together (broken line)
    and draw a straight line between them to close the gap.

    max_gap_px: maximum distance in pixels to bridge. Tune this to match
    the typical gap size in the VLM output — 25px is a good default.
    """
    endpoints = find_skeleton_endpoints(skeleton)
    if len(endpoints) < 2:
        return skeleton

    bridged = skeleton.copy()
    used    = set()

    for i in range(len(endpoints)):
        if i in used:
            continue
        r1, c1 = endpoints[i]
        best_dist = max_gap_px + 1
        best_j    = -1

        for j in range(i + 1, len(endpoints)):
            if j in used:
                continue
            r2, c2 = endpoints[j]
            dist = math.hypot(r2 - r1, c2 - c1)
            if dist < best_dist:
                best_dist = dist
                best_j    = j

        if best_j >= 0 and best_dist <= max_gap_px:
            r2, c2 = endpoints[best_j]
            cv2.line(bridged, (c1, r1), (c2, r2), 255, 1)
            used.add(i)
            used.add(best_j)

    n_bridged = len(used) // 2
    if n_bridged > 0:
        print(f"   🔗 Bridged {n_bridged} skeleton gaps")
    return bridged


# ═══════════════════════════════════════════════════════════════════════════════
# STRAIGHTEN LINES — collapse near-collinear runs to straight segments
# ═══════════════════════════════════════════════════════════════════════════════

def straighten_linestring(line, angle_tolerance_deg=8.0):
    """
    Collapse runs of nearly-collinear points in a LineString into straight
    segments. This eliminates the pixel-staircase artefact from skeleton
    tracing where a diagonal line is represented as many tiny horizontal
    and vertical steps.

    angle_tolerance_deg: how far a point's bearing can deviate from the
    current segment direction before we consider it a real corner.
    Lower = straighter lines but may lose slight curves.
    Higher = preserves more shape detail.
    """
    coords = list(line.coords)
    if len(coords) <= 2:
        return line

    tol_rad = math.radians(angle_tolerance_deg)

    def bearing(p1, p2):
        return math.atan2(p2[1] - p1[1], p2[0] - p1[0])

    def angle_diff(a, b):
        d = abs(a - b) % (2 * math.pi)
        return min(d, 2 * math.pi - d)

    simplified = [coords[0]]
    seg_start   = coords[0]
    seg_bearing = bearing(coords[0], coords[1])

    for i in range(1, len(coords) - 1):
        new_bearing = bearing(seg_start, coords[i + 1])
        if angle_diff(seg_bearing, new_bearing) > tol_rad:
            simplified.append(coords[i])
            seg_start   = coords[i]
            seg_bearing = bearing(coords[i], coords[i + 1])

    simplified.append(coords[-1])

    if len(simplified) < 2:
        return line

    try:
        straight = LineString(simplified)
        return straight if straight.is_valid and straight.length > 0 else line
    except Exception:
        return line


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT SNAPPING
# ═══════════════════════════════════════════════════════════════════════════════

def snap_endpoints(lines, snap_tolerance_geo):
    if snap_tolerance_geo <= 0 or not lines:
        return lines

    coords_list = [list(ln.coords) for ln in lines]
    tol2        = snap_tolerance_geo ** 2

    def dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    endpoints = {}
    for i, coords in enumerate(coords_list):
        endpoints[(i, 0)] = coords[0]
        endpoints[(i, 1)] = coords[-1]

    keys    = list(endpoints.keys())
    snapped = set()

    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            ka, kb = keys[a], keys[b]
            if ka[0] == kb[0]:
                continue
            ca, cb = endpoints[ka], endpoints[kb]
            if dist2(ca, cb) <= tol2 and (ka, kb) not in snapped:
                mid = ((ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2)
                if ka[1] == 0:
                    coords_list[ka[0]][0]  = mid
                else:
                    coords_list[ka[0]][-1] = mid
                if kb[1] == 0:
                    coords_list[kb[0]][0]  = mid
                else:
                    coords_list[kb[0]][-1] = mid
                endpoints[ka] = mid
                endpoints[kb] = mid
                snapped.add((ka, kb))

    result = []
    for coords in coords_list:
        if len(coords) >= 2:
            try:
                ln = LineString(coords)
                if ln.is_valid and ln.length > 0:
                    result.append(ln)
            except Exception:
                pass
    return result
