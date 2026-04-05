"""
Output writers — save lines and points as GeoJSON and ESRI Shapefile.

Outputs per run:
  <stem>_vft_lines.geojson
  <stem>_vft_points.geojson
  <stem>_vft_combined.geojson
  <stem>_vft_lines.shp  (+ .dbf .shx .prj)
  <stem>_vft_points.shp (+ .dbf .shx .prj)
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import geojson
import geopandas as gpd
from shapely.geometry import mapping

from .vlm import MODEL_NAME

__version__ = "6.0.0"


def build_and_save_outputs(all_lines, all_points, epsg, crs_obj,
                           source_file, out_base, stem):
    now_str  = datetime.now(timezone.utc).isoformat()
    crs_name = f"EPSG:{epsg}" if epsg else None

    def make_line_feature(line):
        fid = str(uuid.uuid4())
        f   = geojson.Feature(
            id=fid,
            geometry=mapping(line),
            properties={
                "id":       fid,
                "type":     "field_boundary_line",
                "length":   round(line.length, 4),
                "vertices": len(list(line.coords)),
                "source":   f"vlm-field-tracer v{__version__}",
                "model":    MODEL_NAME,
                "created":  now_str,
            }
        )
        if epsg:
            f.properties["epsg"] = epsg
        return f

    def make_point_feature(pt):
        fid = str(uuid.uuid4())
        f   = geojson.Feature(
            id=fid,
            geometry=mapping(pt),
            properties={
                "id":      fid,
                "type":    "non_agricultural_marker",
                "source":  f"vlm-field-tracer v{__version__}",
                "model":   MODEL_NAME,
                "created": now_str,
            }
        )
        if epsg:
            f.properties["epsg"] = epsg
        return f

    crs_block = {
        "type": "name",
        "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg}"}
    } if epsg else None

    def meta(lc, pc):
        return {
            "generator":   f"vlm-field-tracer v{__version__}",
            "model":       MODEL_NAME,
            "line_count":  lc,
            "point_count": pc,
            "created_at":  now_str,
            "source_file": os.path.basename(source_file),
        }

    line_features  = [make_line_feature(ln) for ln in all_lines]
    point_features = [make_point_feature(pt) for pt in all_points]

    # ── Lines GeoJSON ─────────────────────────────────────────────────────
    lines_geojson_path = out_base / f"{stem}_vft_lines.geojson"
    fc_lines = geojson.FeatureCollection(features=line_features, crs=crs_block)
    fc_lines["metadata"] = meta(len(all_lines), 0)
    with open(lines_geojson_path, 'w') as f:
        geojson.dump(fc_lines, f, indent=2)
    print(f"   💾 Lines GeoJSON  → {lines_geojson_path}  ({len(all_lines)} lines)")

    # ── Points GeoJSON ────────────────────────────────────────────────────
    points_geojson_path = out_base / f"{stem}_vft_points.geojson"
    fc_points = geojson.FeatureCollection(features=point_features, crs=crs_block)
    fc_points["metadata"] = meta(0, len(all_points))
    with open(points_geojson_path, 'w') as f:
        geojson.dump(fc_points, f, indent=2)
    print(f"   💾 Points GeoJSON → {points_geojson_path}  ({len(all_points)} points)")

    # ── Combined GeoJSON (legacy) ─────────────────────────────────────────
    combined_path = out_base / f"{stem}_vft_combined.geojson"
    fc_combined   = geojson.FeatureCollection(
        features=line_features + point_features, crs=crs_block
    )
    fc_combined["metadata"] = meta(len(all_lines), len(all_points))
    with open(combined_path, 'w') as f:
        geojson.dump(fc_combined, f, indent=2)
    print(f"   💾 Combined GeoJSON → {combined_path}")

    # ── Lines SHP ─────────────────────────────────────────────────────────
    if all_lines:
        try:
            lines_gdf = gpd.GeoDataFrame(
                {
                    "id":       [str(uuid.uuid4()) for _ in all_lines],
                    "type":     ["field_boundary_line"] * len(all_lines),
                    "length":   [round(ln.length, 4) for ln in all_lines],
                    "vertices": [len(list(ln.coords)) for ln in all_lines],
                    "source":   [f"vlm-field-tracer v{__version__}"] * len(all_lines),
                    "created":  [now_str] * len(all_lines),
                    "geometry": all_lines,
                },
                crs=crs_name or (str(crs_obj) if crs_obj else "EPSG:4326"),
            )
            lines_shp_path = out_base / f"{stem}_vft_lines.shp"
            lines_gdf.to_file(lines_shp_path, driver="ESRI Shapefile")
            print(f"   💾 Lines SHP      → {lines_shp_path}  ({len(all_lines)} lines)")
        except Exception as e:
            print(f"   ⚠️  Lines SHP failed: {e}")
    else:
        print("   ℹ️  No lines to save as SHP")

    # ── Points SHP ────────────────────────────────────────────────────────
    if all_points:
        try:
            points_gdf = gpd.GeoDataFrame(
                {
                    "id":      [str(uuid.uuid4()) for _ in all_points],
                    "type":    ["non_agricultural_marker"] * len(all_points),
                    "source":  [f"vlm-field-tracer v{__version__}"] * len(all_points),
                    "created": [now_str] * len(all_points),
                    "geometry": all_points,
                },
                crs=crs_name or (str(crs_obj) if crs_obj else "EPSG:4326"),
            )
            points_shp_path = out_base / f"{stem}_vft_points.shp"
            points_gdf.to_file(points_shp_path, driver="ESRI Shapefile")
            print(f"   💾 Points SHP     → {points_shp_path}  ({len(all_points)} points)")
        except Exception as e:
            print(f"   ⚠️  Points SHP failed: {e}")
    else:
        print("   ℹ️  No points to save as SHP")

    return str(combined_path)
