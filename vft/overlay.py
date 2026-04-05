"""
Overlay visualisation — draw extracted lines and points over the original image.
"""

import numpy as np
import cv2
from .extractor import geo_to_px_fn
from .debug     import save_png


def save_overlay_png(image, all_lines, all_points, bounds, tag=""):
    try:
        canvas = np.array(image.convert('RGB')).copy()
        bx     = bounds
        tw, th = image.size
        g2p    = geo_to_px_fn(bx, tw, th)

        for line in all_lines:
            try:
                coords = list(line.coords)
                for i in range(len(coords) - 1):
                    cv2.line(canvas, g2p(*coords[i]), g2p(*coords[i+1]), (0, 255, 255), 2)
            except Exception:
                continue

        for pt in all_points:
            try:
                p = g2p(pt.x, pt.y)
                cv2.circle(canvas, p, 8,  (0, 0, 255),    -1)
                cv2.circle(canvas, p, 10, (255, 255, 255),  2)
            except Exception:
                continue

        save_png("13_final_overlay", canvas, tag)
        print("     ✅ Final overlay saved")
    except Exception as e:
        print(f"   ⚠️  Overlay error: {e}")
