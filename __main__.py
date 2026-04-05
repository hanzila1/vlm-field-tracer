#!/usr/bin/env python3
"""
VLM-Field-Tracer — Field Boundary & Non-Agricultural Point Extractor
Version 6.0.0

Pipeline:
  1. Load GeoTIFF at full resolution → auto-tile
  2. Send tile to VLM → field boundary lines image
  3. Extract smooth gap-free straight lines
  4. Send tile to VLM → non-agricultural point markers
  5. Extract point centroids
  6. Save GeoJSON + SHP + debug PNGs

Usage:
  python -m vft <input.tif> -k <GEMINI_API_KEY>
  python -m vft <input.tif> -k <KEY> --grid 2x2
  python -m vft <input.tif> -k <KEY> --grid 3x3 --epsg 32643
  python -m vft <input.tif> -k <KEY> --snap-tolerance 3.0
"""

import os
import sys
import argparse
from pathlib import Path

from google import genai

from vft          import __version__
from vft.loader   import GeoTIFFLoader
from vft.tiling   import parse_grid, create_tiles, prepare_tile_for_api
from vft.vlm      import call_vlm, PROMPT_LINES, PROMPT_POINTS, MODEL_NAME
from vft.extractor import extract_lines, extract_points
from vft.overlay  import save_overlay_png
from vft.writer   import build_and_save_outputs
from vft.debug    import set_debug_dir, save_png


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(args):
    print("\n" + "═" * 65)
    print(f"  VLM-Field-Tracer v{__version__}  —  Field Lines + Non-Ag Points")
    print(f"  Model: {MODEL_NAME}")
    print("═" * 65)

    stem     = Path(args.input).stem
    out_base = Path(args.output).parent if args.output else Path('.')
    out_base.mkdir(parents=True, exist_ok=True)

    debug_dir = out_base / f"{stem}_debug_pngs"
    debug_dir.mkdir(exist_ok=True)
    set_debug_dir(debug_dir)
    print(f"  📸 Debug PNGs → {debug_dir}")

    loader = GeoTIFFLoader(args.input)
    if args.epsg:
        loader.epsg = args.epsg
        print(f"  ℹ️  EPSG forced to {args.epsg}")
    loader.print_info()

    image = loader.load_full_resolution()
    save_png("00_input_fullres", image)

    client = genai.Client(api_key=args.api_key)

    # Build work units
    if args.grid:
        grid_cols, grid_rows = parse_grid(args.grid)
        print(f"\n🔲 Grid: {grid_cols}×{grid_rows} = {grid_cols*grid_rows} tiles (full resolution)")
        work_units = create_tiles(image, loader.bounds, grid_cols, grid_rows)
    else:
        print(f"\n🔲 Single image mode ({image.size[0]:,}×{image.size[1]:,} px)")
        work_units = [{
            'index': 0, 'row': 0, 'col': 0,
            'image': image,
            'bounds': loader.bounds,
            'pixel_size': image.size,
        }]

    all_lines  = []
    all_points = []

    for unit in work_units:
        row   = unit['row']
        col   = unit['col']
        tag   = f"r{row}c{col}" if args.grid else ""
        label = f"Tile [{row},{col}]" if args.grid else "Image"

        print(f"\n{'─' * 55}")
        print(f"  {label}  ({unit['pixel_size'][0]:,}×{unit['pixel_size'][1]:,} px)")

        api_img, api_scale = prepare_tile_for_api(unit['image'])
        if api_scale < 1.0:
            print(f"   ℹ️  API image: {api_img.size[0]}×{api_img.size[1]} px")
        else:
            print(f"   ✅ Full resolution to API")

        # ── Lines ───────────────────────────────────────────────────────
        print(f"\n  [1/2] Field boundary lines → VLM...")
        lines_result = call_vlm(client, api_img, PROMPT_LINES)

        if lines_result is None:
            print(f"  ⚠️  Lines call failed — skipping {label}")
        else:
            print(f"     ✅ VLM output received")
            lines = extract_lines(
                lines_result,
                unit['bounds'],
                unit['pixel_size'],
                min_line_length=args.min_line,
                snap_tolerance_geo=args.snap_tolerance,
                dp_epsilon=args.dp_epsilon,
                max_gap_px=args.max_gap,
                angle_tolerance_deg=args.angle_tolerance,
                tag=tag,
            )
            all_lines.extend(lines)

        # ── Points ──────────────────────────────────────────────────────
        print(f"\n  [2/2] Non-agricultural markers → VLM...")
        points_result = call_vlm(client, api_img, PROMPT_POINTS)

        if points_result is None:
            print(f"  ⚠️  Points call failed — skipping {label}")
        else:
            print(f"     ✅ VLM output received")
            points = extract_points(
                points_result,
                unit['bounds'],
                unit['pixel_size'],
                min_dot_area=args.min_dot,
                tag=tag,
            )
            all_points.extend(points)

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'═' * 65}")
    print(f"  ✅ Total smooth lines  : {len(all_lines)}")
    print(f"  ✅ Total non-ag points : {len(all_points)}")

    if all_lines:
        lengths = [ln.length for ln in all_lines]
        print(f"  📏 Length min/max/mean : {min(lengths):.1f} / {max(lengths):.1f} / {sum(lengths)/len(lengths):.1f}")
        verts = sum(len(list(ln.coords)) for ln in all_lines)
        print(f"  🔢 Total vertices      : {verts:,}")

    if not all_lines and not all_points:
        print("  ⚠️  No features detected. Check debug PNGs.")
        return

    # ── Overlay ───────────────────────────────────────────────────────────
    print(f"\n📸 Saving overlay PNG...")
    save_overlay_png(image, all_lines, all_points, loader.bounds)

    # ── Save outputs ──────────────────────────────────────────────────────
    print(f"\n💾 Saving outputs...")
    build_and_save_outputs(
        all_lines, all_points,
        loader.epsg, loader.crs,
        args.input, out_base, stem
    )

    print(f"\n{'═' * 65}")
    print(f"  🌾 Done!")
    print(f"  📂 Outputs:    {out_base}/")
    print(f"  📂 Debug PNGs: {debug_dir}/")
    print(f"{'═' * 65}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"VLM-Field-Tracer v{__version__} — Gap-free straight field boundary lines, GeoJSON + SHP output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m vft field.tif -k YOUR_KEY
  python -m vft field.tif -k KEY --grid 2x2
  python -m vft field.tif -k KEY --grid 3x3 --epsg 32643
  python -m vft field.tif -k KEY --snap-tolerance 3.0 --max-gap 30
  python -m vft field.tif -k KEY --angle-tolerance 5.0   # stricter straight lines
  python -m vft field.tif -k KEY --angle-tolerance 15.0  # allow more curves

Parameters for tuning line quality:
  --max-gap          Max pixel gap to bridge in skeleton (default 25).
                     Increase if lines still have breaks.
  --dp-epsilon       Douglas-Peucker simplification in pixels (default 3.0).
                     Lower = more vertices. Higher = smoother/straighter.
  --angle-tolerance  Degrees before a direction change becomes a corner (default 8).
                     Lower = straighter lines. Higher = follows curves better.
  --snap-tolerance   Geo-unit distance to snap endpoints (default 0 = off).
                     Set to ~1-3x your pixel ground resolution in metres.

Install opencv-contrib for best skeleton quality:
  pip install opencv-contrib-python
        """
    )
    parser.add_argument('input',                   help='Input GeoTIFF')
    parser.add_argument('-k', '--api-key',         required=True)
    parser.add_argument('-o', '--output',          default=None,   help='Output path (optional)')
    parser.add_argument('--grid',                  default=None,   help='NxM tile grid e.g. 2x2')
    parser.add_argument('--epsg',                  type=int,       default=None)
    parser.add_argument('--min-line',              type=int,       default=20,   help='Min line length px (default 20)')
    parser.add_argument('--min-dot',               type=int,       default=30,   help='Min dot area px² (default 30)')
    parser.add_argument('--snap-tolerance',        type=float,     default=0.0,  help='Endpoint snap in geo units (default 0=off)')
    parser.add_argument('--dp-epsilon',            type=float,     default=3.0,  help='Douglas-Peucker epsilon px (default 3.0)')
    parser.add_argument('--max-gap',               type=int,       default=25,   help='Max skeleton gap to bridge in px (default 25)')
    parser.add_argument('--angle-tolerance',       type=float,     default=8.0,  help='Straightening angle tolerance degrees (default 8.0)')
    parser.add_argument('--version',               action='version', version=f'vlm-field-tracer {__version__}')
    parser.add_argument('--tiles',                 action='store_true', help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.tiles and not args.grid:
        args.grid = '2x2'
        print("  ℹ️  --tiles → --grid 2x2")

    if not os.path.exists(args.input):
        print(f"❌ Not found: {args.input}")
        sys.exit(1)

    run_pipeline(args)


if __name__ == '__main__':
    main()
