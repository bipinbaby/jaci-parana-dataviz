"""
Generate colored category map PNGs from MapBiomas TIFFs.
Each pixel colored by its land-cover class using MapBiomas palette.
Output: one PNG per year at web-ready resolution.
"""

import glob
import numpy as np
from PIL import Image
from pathlib import Path

TIFF_DIR = Path(__file__).parent.parent / "cobertura_tiff" / "tiff"
WEB_ASSETS = Path(__file__).parent.parent / "web_assets"

# MapBiomas class -> RGB color (official palette)
CLASS_COLORS = {
    0:  (10, 10, 10),       # NoData / outside
    3:  (31, 141, 73),      # Forest Formation (dark green)
    4:  (146, 186, 69),     # Savanna Formation
    6:  (32, 104, 73),      # Floodable Forest (darker green)
    11: (51, 111, 156),     # Wetland
    12: (183, 219, 116),    # Grassland
    15: (237, 205, 97),     # Pasture (golden tan)
    18: (224, 164, 59),     # Agriculture
    21: (196, 142, 51),     # Mosaic Agriculture
    24: (233, 72, 94),      # Urban
    25: (157, 112, 72),     # Other Non-Vegetated
    31: (109, 171, 209),    # Aquaculture
    33: (35, 88, 171),      # River/Lake/Ocean (blue)
    39: (204, 126, 46),     # Soybean
    41: (163, 120, 52),     # Other Temp Crops
}

WEB_SIZE = (384, 640)  # half of 768x1280 for fast loading


def run():
    (WEB_ASSETS / "category").mkdir(parents=True, exist_ok=True)

    files = sorted(glob.glob(str(TIFF_DIR / "cobertua_*.tif")))
    if not files:
        print("No TIFFs found!")
        return

    import rasterio

    for f in files:
        year = int(Path(f).stem.split("_")[-1])

        with rasterio.open(f) as src:
            data = src.read(1)

        h, w = data.shape
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        rgb[:] = CLASS_COLORS[0]  # default = outside

        for cls, color in CLASS_COLORS.items():
            mask = data == cls
            rgb[mask] = color

        img = Image.fromarray(rgb, mode='RGB')
        img_resized = img.resize(WEB_SIZE, resample=Image.Resampling.NEAREST)
        img_resized.save(WEB_ASSETS / "category" / f"cat_{year}.png")

    years = [int(Path(f).stem.split("_")[-1]) for f in files]
    print(f"Generated {len(years)} category maps: {min(years)}-{max(years)}")
    print(f"Size: {WEB_SIZE[0]}x{WEB_SIZE[1]}")


if __name__ == "__main__":
    run()
