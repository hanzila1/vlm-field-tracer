"""
GeoTIFF loader — reads full-resolution raster and detects CRS/EPSG.
"""

import os
import re
import numpy as np
from pathlib import Path
from PIL import Image

import rasterio


class GeoTIFFLoader:
    def __init__(self, path):
        self.path = path
        self._load_meta()

    def _load_meta(self):
        with rasterio.open(self.path) as src:
            self.width      = src.width
            self.height     = src.height
            self.bounds     = src.bounds
            self.crs        = src.crs
            self.transform  = src.transform
            self.band_count = src.count
            self.epsg       = self._detect_epsg(src)
        self.file_size_gb = os.path.getsize(self.path) / (1024 ** 3)

    def _detect_epsg(self, src):
        try:
            e = src.crs.to_epsg()
            if e:
                return e
        except Exception:
            pass
        try:
            s = str(src.crs)
            if 'EPSG:' in s:
                return int(s.split('EPSG:')[1].split()[0])
        except Exception:
            pass
        try:
            wkt = src.crs.to_wkt()
            m = re.search(r'UTM[_ ]zone[_ ](\d+)([NS])', wkt)
            if m:
                z, h = int(m.group(1)), m.group(2)
                return 32600 + z if h == 'N' else 32700 + z
        except Exception:
            pass
        try:
            l, b, r, t = self.bounds
            if 100000 < l < 900000 and 2500000 < b < 4500000:
                print("  ℹ️  Auto-detected UTM Zone 43N")
                return 32643
        except Exception:
            pass
        return None

    def load_full_resolution(self):
        print(f"\n📖 Loading at FULL resolution...")
        print(f"   Size: {self.width:,} × {self.height:,} px  |  {self.file_size_gb:.2f} GB")
        with rasterio.open(self.path) as src:
            if self.band_count >= 3:
                arr = np.dstack((src.read(1), src.read(2), src.read(3)))
            else:
                g   = src.read(1)
                arr = np.dstack((g, g, g))
        if arr.dtype != np.uint8:
            if arr.max() <= 1.0:
                arr = (arr * 255).astype(np.uint8)
            elif arr.max() > 255:
                p2, p98 = np.percentile(arr, (2, 98))
                arr = np.clip((arr - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
            else:
                arr = arr.astype(np.uint8)
        image = Image.fromarray(arr)
        print(f"   ✅ Loaded — {image.size[0]:,} × {image.size[1]:,} px")
        return image

    def print_info(self):
        print(f"\n📁 {os.path.basename(self.path)}")
        print(f"   {self.width:,} × {self.height:,} px  |  {self.file_size_gb:.2f} GB")
        print(f"   CRS: {'EPSG:' + str(self.epsg) if self.epsg else str(self.crs)}")
        b = self.bounds
        print(f"   Bounds: ({b.left:.4f}, {b.bottom:.4f}) → ({b.right:.4f}, {b.top:.4f})")
