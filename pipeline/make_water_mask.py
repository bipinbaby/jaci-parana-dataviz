"""
Extract water mask from a MapBiomas TIFF (class 33 = river/lake/ocean).
"""

import numpy as np
import rasterio
from PIL import Image
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
TIFF_DIR = DATA_DIR / "cobertura_tiff" / "tiff"
WEB_ASSETS = DATA_DIR / "web_assets"

WATER_CLASS = 33


def run():
    # Use the most recent TIFF for water (rivers shift slightly over time)
    tiff_path = sorted(TIFF_DIR.glob("cobertua_*.tif"))[-1]
    print(f"Using {tiff_path.name} for water mask")

    with rasterio.open(tiff_path) as src:
        data = src.read(1)

    water = (data == WATER_CLASS).astype(np.uint8) * 255
    water_count = (data == WATER_CLASS).sum()
    print(f"  Water pixels: {water_count:,}")

    img = Image.fromarray(water, mode='L')
    img.save(WEB_ASSETS / "water_mask.png")
    print(f"Saved water_mask.png ({water.shape[1]}x{water.shape[0]})")


if __name__ == "__main__":
    run()
