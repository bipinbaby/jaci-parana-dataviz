"""
Generate forest_loss control texture from MapBiomas yearly TIFFs.

Output encoding (8-bit grayscale):
  0   = never forest (water, outside boundary, nodata)
  1-254 = normalized year-of-loss (1=earliest loss, 254=latest loss)
  255 = stable forest (forest in all available years)
"""

import glob
import numpy as np
import rasterio
from pathlib import Path

TIFF_DIR = Path(__file__).parent.parent / "cobertura_tiff" / "tiff"
OUT_DIR_WEB = Path(__file__).parent.parent / "web_assets"
OUT_DIR_TD = Path(__file__).parent.parent / "td_assets"

# MapBiomas classes that count as "forest"
FOREST_CLASSES = {3, 6}  # Forest Formation + Floodable Forest


def load_all_years():
    """Load all yearly TIFFs into a dict {year: 2D array} and return profile."""
    files = sorted(glob.glob(str(TIFF_DIR / "cobertua_*.tif")))
    if not files:
        raise FileNotFoundError(f"No TIFFs found in {TIFF_DIR}")

    data = {}
    profile = None
    for f in files:
        year = int(Path(f).stem.split("_")[-1])
        with rasterio.open(f) as src:
            data[year] = src.read(1)
            if profile is None:
                profile = src.profile.copy()

    years = sorted(data.keys())
    print(f"Loaded {len(years)} years: {years[0]}-{years[-1]}")
    print(f"  Raster size: {data[years[0]].shape}")
    return data, years, profile


def compute_forest_loss(data, years):
    """
    For each pixel, find the first year it transitions from forest to non-forest.

    Returns:
        loss_year: 2D array of loss year (0=never forest, -1=stable forest)
        was_ever_forest: boolean mask
    """
    h, w = data[years[0]].shape
    stack = np.zeros((len(years), h, w), dtype=np.uint8)
    for i, y in enumerate(years):
        stack[i] = data[y]

    # Boolean: is this pixel forest in each year?
    is_forest = np.isin(stack, list(FOREST_CLASSES))

    # Was this pixel ever forest?
    was_ever_forest = np.any(is_forest, axis=0)

    # Is this pixel still forest in the last year?
    still_forest = is_forest[-1]

    # For each pixel, find the first year where forest transitions to non-forest
    # and stays non-forest for at least 1 more year (to filter noise)
    loss_year = np.zeros((h, w), dtype=np.int32)

    for i in range(len(years) - 1):
        # Pixel was forest in year i but not in year i+1
        transition = is_forest[i] & ~is_forest[i + 1]
        # Only record first transition (where loss_year is still 0 and pixel was forest)
        first_loss = transition & (loss_year == 0) & was_ever_forest
        loss_year[first_loss] = years[i + 1]  # The year the loss appeared

    # Pixels that are forest in all years: stable
    # Pixels that lost forest only in the very last year
    last_year_loss = is_forest[-2] & ~is_forest[-1] & (loss_year == 0) & was_ever_forest if len(years) > 1 else np.zeros_like(still_forest)
    loss_year[last_year_loss] = years[-1]

    return loss_year, was_ever_forest, still_forest


def encode_8bit(loss_year, was_ever_forest, still_forest, years):
    """Encode to 8-bit: 0=never forest, 1-254=year-of-loss, 255=stable."""
    result = np.zeros(loss_year.shape, dtype=np.uint8)

    min_year = years[0]
    max_year = years[-1]
    year_range = max_year - min_year

    # Pixels with a loss year: map to 1-254
    has_loss = (loss_year > 0)
    if year_range > 0:
        normalized = ((loss_year[has_loss] - min_year) / year_range * 253).astype(np.uint8) + 1
    else:
        normalized = np.ones(has_loss.sum(), dtype=np.uint8) * 128
    result[has_loss] = normalized

    # Stable forest (was forest and still is): 255
    result[was_ever_forest & still_forest & ~has_loss] = 255

    # Never forest: stays 0
    # This includes nodata (class 0), water, grassland that was never forest

    return result


def encode_16bit(loss_year, was_ever_forest, still_forest):
    """Encode to 16-bit: 0=never forest, actual year values, 65535=stable."""
    result = np.zeros(loss_year.shape, dtype=np.uint16)
    has_loss = (loss_year > 0)
    result[has_loss] = loss_year[has_loss].astype(np.uint16)
    result[was_ever_forest & still_forest & ~has_loss] = 65535
    return result


def run():
    OUT_DIR_WEB.mkdir(parents=True, exist_ok=True)
    OUT_DIR_TD.mkdir(parents=True, exist_ok=True)

    data, years, profile = load_all_years()
    loss_year, was_ever_forest, still_forest = compute_forest_loss(data, years)

    # Stats
    total_valid = was_ever_forest.sum()
    lost = (loss_year > 0).sum()
    stable = (was_ever_forest & still_forest & (loss_year == 0)).sum()
    print(f"\nForest stats:")
    print(f"  Pixels ever forest: {total_valid:,}")
    print(f"  Pixels lost:        {lost:,} ({lost/total_valid*100:.1f}%)")
    print(f"  Pixels stable:      {stable:,} ({stable/total_valid*100:.1f}%)")

    # 8-bit for web
    img_8bit = encode_8bit(loss_year, was_ever_forest, still_forest, years)
    from PIL import Image
    img = Image.fromarray(img_8bit, mode='L')
    img.save(OUT_DIR_WEB / "forest_loss.png")
    img.save(OUT_DIR_TD / "forest_loss.png")  # Full-res for TD too
    print(f"\nSaved forest_loss.png ({img_8bit.shape[1]}x{img_8bit.shape[0]})")

    # 16-bit TIFF for TD
    img_16bit = encode_16bit(loss_year, was_ever_forest, still_forest)
    td_profile = profile.copy()
    td_profile.update(dtype='uint16', count=1, nodata=0)
    with rasterio.open(OUT_DIR_TD / "forest_loss_16bit.tif", 'w', **td_profile) as dst:
        dst.write(img_16bit, 1)
    print(f"Saved forest_loss_16bit.tif")

    return loss_year, was_ever_forest, still_forest, years, profile


if __name__ == "__main__":
    run()
