"""
Fetch Landsat annual composites for RESEX Jaci-Paraná via Microsoft Planetary Computer.
No API key needed — completely free.

Output: web_assets/landsat/landsat_YYYY.png (768x1280, true-color RGB)
"""

import numpy as np
from PIL import Image
from pathlib import Path
import pystac_client
import planetary_computer
import odc.stac
import warnings
warnings.filterwarnings("ignore")

BBOX = [-64.47724, -10.16611, -64.00078, -9.37789]  # W, S, E, N
YEARS = range(1996, 2025)
OUT_DIR = Path(__file__).parent.parent / "web_assets" / "landsat"
OUT_SIZE = (768, 1280)  # width, height

# Landsat Collection 2 Surface Reflectance scale: DN * 0.0000275 - 0.2
SCALE = 0.0000275
OFFSET = -0.2


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    for year in YEARS:
        out_path = OUT_DIR / f"landsat_{year}.png"
        if out_path.exists():
            print(f"{year}: already exists, skipping")
            continue

        print(f"\n{year}: searching...")

        # Search for scenes — prefer dry season (Jun-Oct) for less cloud
        # Fall back to full year if not enough scenes
        items = catalog.search(
            collections=["landsat-c2-l2"],
            bbox=BBOX,
            datetime=f"{year}-06-01/{year}-10-31",
            query={"eo:cloud_cover": {"lt": 30}},
        ).item_collection()

        if len(items) < 3:
            # Try full year with higher cloud tolerance
            items = catalog.search(
                collections=["landsat-c2-l2"],
                bbox=BBOX,
                datetime=f"{year}-01-01/{year}-12-31",
                query={"eo:cloud_cover": {"lt": 50}},
            ).item_collection()

        if not items:
            print(f"{year}: no scenes found, skipping")
            continue

        print(f"{year}: {len(items)} scenes found, loading...")

        try:
            ds = odc.stac.load(
                items,
                bands=["red", "green", "blue"],
                bbox=BBOX,
                resolution=30,
                groupby="solar_day",
            )

            # Median composite — removes clouds and Landsat 7 SLC-off gaps
            composite = ds.median(dim="time", skipna=True)

            r = composite["red"].values * SCALE + OFFSET
            g = composite["green"].values * SCALE + OFFSET
            b = composite["blue"].values * SCALE + OFFSET

            # Stack and normalize
            rgb = np.stack([r, g, b], axis=-1)
            rgb = np.clip(rgb, 0.0, 0.3) / 0.3  # stretch reflectance to 0-1
            rgb = (rgb ** (1 / 2.2) * 255).astype(np.uint8)  # gamma correction

            img = Image.fromarray(rgb)
            img = img.resize(OUT_SIZE, Image.LANCZOS)
            img.save(out_path)
            print(f"{year}: saved {out_path.name} ({len(items)} scenes composited)")

        except Exception as e:
            print(f"{year}: ERROR — {e}")
            continue

    print(f"\nDone. Files in {OUT_DIR}")


if __name__ == "__main__":
    run()
