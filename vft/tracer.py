"""
Skeleton graph tracers — walk the 1-px skeleton into polyline paths.

Two implementations are provided:
  - trace_skeleton_to_polylines : full graph-walk with proper junction handling
  - _agfe_trace_skeleton         : ported from agfe_pro, known-good on
                                   roads/waterlines; used as the primary tracer
                                   in extract_lines.
"""

import math
import numpy as np
import cv2


# ═══════════════════════════════════════════════════════════════════════════════
# FULL GRAPH-WALK TRACER
# ═══════════════════════════════════════════════════════════════════════════════

def trace_skeleton_to_polylines(skeleton, min_px=20):
    """
    Walk the 1px skeleton as a graph:
      - Nodes  = junction pixels (3+ neighbours) and endpoint pixels (1 neighbour)
      - Edges  = pixel chains between nodes

    For each edge we collect all pixels along the chain and return them as a
    polyline.  This avoids the fragmentation that cv2.findContours produces
    at every junction.

    Returns a list of [(x, y), ...] pixel-coordinate paths.
    """
    skel = (skeleton > 0).astype(np.uint8)
    h, w = skel.shape

    kernel = np.ones((3, 3), dtype=np.uint8)
    kernel[1, 1] = 0
    nbr_count = cv2.filter2D(skel, -1, kernel)
    nbr_count  = nbr_count * skel

    node_mask = skel & ((nbr_count == 1) | (nbr_count >= 3)).astype(np.uint8)

    visited    = np.zeros((h, w), dtype=bool)
    is_junction = (nbr_count >= 3) & (skel > 0)

    offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

    def neighbours_of(r, c):
        return [(r+dr, c+dc) for dr,dc in offsets
                if 0 <= r+dr < h and 0 <= c+dc < w and skel[r+dr,c+dc]]

    def walk_edge(r0, c0, r1, c1):
        path = [(c0, r0)]
        visited[r0, c0] = True
        pr, pc = r0, c0
        cr, cc = r1, c1

        while True:
            path.append((cc, cr))
            if node_mask[cr, cc] and (cr != r0 or cc != c0):
                break
            if not is_junction[cr, cc]:
                visited[cr, cc] = True
            nxt = [(nr, nc) for nr, nc in neighbours_of(cr, cc)
                   if (nr, nc) != (pr, pc)
                   and (not visited[nr, nc] or is_junction[nr, nc])]
            if not nxt:
                break
            pr, pc = cr, cc
            cr, cc = nxt[0]

        return path

    paths = []

    node_ys, node_xs = np.where(node_mask > 0)

    for r0, c0 in zip(node_ys.tolist(), node_xs.tolist()):
        for (rn, cn) in neighbours_of(r0, c0):
            if visited[rn, cn] and not is_junction[rn, cn]:
                continue
            path = walk_edge(r0, c0, rn, cn)
            if len(path) < 2:
                continue
            px_len = sum(
                math.hypot(path[i+1][0]-path[i][0], path[i+1][1]-path[i][1])
                for i in range(len(path)-1)
            )
            if px_len >= min_px:
                paths.append(path)

    unvisited_ys, unvisited_xs = np.where((skel > 0) & ~visited & ~is_junction)
    for r0, c0 in zip(unvisited_ys.tolist(), unvisited_xs.tolist()):
        if visited[r0, c0]:
            continue
        nbrs = neighbours_of(r0, c0)
        if not nbrs:
            continue
        path = walk_edge(r0, c0, nbrs[0][0], nbrs[0][1])
        if len(path) < 2:
            continue
        px_len = sum(
            math.hypot(path[i+1][0]-path[i][0], path[i+1][1]-path[i][1])
            for i in range(len(path)-1)
        )
        if px_len >= min_px:
            paths.append(path)

    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# AGFE-PRO SKELETON TRACER — ported directly, known-good on roads/waterlines
# ═══════════════════════════════════════════════════════════════════════════════

def _agfe_trace_skeleton(skeleton_bool):
    """
    Trace a boolean skeleton into a list of (x,y) pixel polylines.
    Ported verbatim from agfe_pro.trace_skeleton_lines — the same function
    that produces clean road/waterline results in that codebase.
    """
    skeleton = skeleton_bool.astype(bool)
    lines    = []
    visited  = np.zeros_like(skeleton, dtype=bool)
    h, w     = skeleton.shape

    kernel        = np.ones((3, 3), dtype=np.uint8)
    neighbor_count = cv2.filter2D(skeleton.astype(np.uint8), -1, kernel) - skeleton.astype(np.uint8)
    endpoints  = (neighbor_count == 1) & skeleton
    junctions  = (neighbor_count >= 3) & skeleton

    start_points = np.column_stack(np.where(endpoints | junctions))
    if len(start_points) == 0:
        start_points = np.column_stack(np.where(skeleton))
        if len(start_points) == 0:
            return []
        start_points = start_points[:1]

    def get_neighbors(y, x):
        neighbors = []
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    if skeleton[ny, nx] and not visited[ny, nx]:
                        neighbors.append((ny, nx))
        return neighbors

    def trace_line(start_y, start_x):
        line = [(start_x, start_y)]
        visited[start_y, start_x] = True
        current = (start_y, start_x)
        while True:
            neighbors = get_neighbors(current[0], current[1])
            if not neighbors:
                break
            next_pt = neighbors[0]
            line.append((next_pt[1], next_pt[0]))
            visited[next_pt[0], next_pt[1]] = True
            current = next_pt
            if junctions[current[0], current[1]]:
                break
        return line

    for y, x in start_points:
        if not visited[y, x]:
            line = trace_line(y, x)
            if len(line) >= 2:
                lines.append(line)

    remaining = skeleton & ~visited
    while remaining.any():
        pts = np.column_stack(np.where(remaining))
        if len(pts) == 0:
            break
        y, x = pts[0]
        line = trace_line(y, x)
        if len(line) >= 2:
            lines.append(line)
        remaining = skeleton & ~visited

    return lines
