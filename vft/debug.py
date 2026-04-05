"""
Debug PNG utilities — save intermediate pipeline images for inspection.
Set _png_dir to None to disable all debug output.
"""

from pathlib import Path
import numpy as np
from PIL import Image

_png_dir: Path = None


def set_debug_dir(path: Path):
    global _png_dir
    _png_dir = path


def save_png(name: str, img, tag: str = ""):
    global _png_dir
    if _png_dir is None:
        return
    prefix   = f"{tag}_" if tag else ""
    out_path = _png_dir / f"{prefix}{name}.png"
    if isinstance(img, np.ndarray):
        arr = img.copy()
        if arr.dtype != np.uint8:
            mn, mx = arr.min(), arr.max()
            arr = ((arr - mn) / (mx - mn) * 255).astype(np.uint8) if mx > mn \
                  else np.zeros_like(arr, dtype=np.uint8)
        pil = Image.fromarray(arr) if arr.ndim == 3 else Image.fromarray(arr, 'L')
    elif isinstance(img, Image.Image):
        pil = img.convert('RGB')
    else:
        return
    pil.save(out_path, format='PNG')
    print(f"     📸 {out_path.name}")
