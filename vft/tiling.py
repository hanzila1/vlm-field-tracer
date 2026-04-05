"""
Tiling utilities — split a full-resolution image into a grid of tiles
and prepare each tile for the Gemini API (resize if needed).
"""

import math
from PIL import Image
from rasterio.coords import BoundingBox

GEMINI_MAX_PX = 4096   # Gemini API hard limit per side


def parse_grid(grid_str):
    try:
        parts = grid_str.lower().split('x')
        cols, rows = int(parts[0]), int(parts[1])
        assert cols >= 1 and rows >= 1
        return cols, rows
    except Exception:
        raise ValueError(f"Invalid --grid value '{grid_str}'. Use format like 2x2 or 3x4.")


def create_tiles(image, geo_bounds, grid_cols, grid_rows):
    w, h = image.size
    gw   = geo_bounds.right - geo_bounds.left
    gh   = geo_bounds.top   - geo_bounds.bottom
    tile_pw = math.ceil(w / grid_cols)
    tile_ph = math.ceil(h / grid_rows)
    tiles = []
    idx   = 0
    for row in range(grid_rows):
        for col in range(grid_cols):
            x1 = col * tile_pw;  y1 = row * tile_ph
            x2 = min(x1 + tile_pw, w);  y2 = min(y1 + tile_ph, h)
            tile_img = image.crop((x1, y1, x2, y2))
            geo_left   = geo_bounds.left + (x1 / w) * gw
            geo_right  = geo_bounds.left + (x2 / w) * gw
            geo_top    = geo_bounds.top  - (y1 / h) * gh
            geo_bottom = geo_bounds.top  - (y2 / h) * gh
            tiles.append({
                'index': idx, 'row': row, 'col': col,
                'image': tile_img,
                'bounds': BoundingBox(geo_left, geo_bottom, geo_right, geo_top),
                'pixel_size': (x2 - x1, y2 - y1),
            })
            print(f"   Tile [{row},{col}]: {x2-x1:,} × {y2-y1:,} px")
            idx += 1
    return tiles


def prepare_tile_for_api(tile_img):
    w, h = tile_img.size
    if w <= GEMINI_MAX_PX and h <= GEMINI_MAX_PX:
        return tile_img, 1.0
    scale = min(GEMINI_MAX_PX / w, GEMINI_MAX_PX / h)
    nw, nh = int(w * scale), int(h * scale)
    print(f"   ⚠️  Tile exceeds Gemini limit → rescaling to {nw}×{nh}")
    return tile_img.resize((nw, nh), Image.LANCZOS), scale
