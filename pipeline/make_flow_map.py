"""
Generate flow_map.png from the forest_loss texture.

The gradient of the year-of-loss field points from older clearings toward newer ones.
In the fishbone pattern, this means gradients radiate outward from roads into forest.

Output encoding (RGBA):
  R = flow direction X (128 = zero, 0 = full left, 255 = full right)
  G = flow direction Y (128 = zero, 0 = full up, 255 = full down)
  B = normalized loss time (same as forest_loss values)
  A = forest mask (255 = was ever forest, 0 = never forest)
"""

import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
from pathlib import Path

WEB_ASSETS = Path(__file__).parent.parent / "web_assets"
TD_ASSETS = Path(__file__).parent.parent / "td_assets"


def run():
    # Load the 8-bit forest loss texture
    loss_img = np.array(Image.open(WEB_ASSETS / "forest_loss.png"), dtype=np.float32)
    h, w = loss_img.shape
    print(f"Loaded forest_loss.png: {w}x{h}")

    # Create masks
    never_forest = (loss_img == 0)       # nodata / water / never forest
    stable_forest = (loss_img == 255)    # forest in all years
    has_loss = ~never_forest & ~stable_forest  # pixels with year-of-loss (1-254)
    was_ever_forest = ~never_forest      # includes both lost and stable

    # Build a continuous loss time field for gradient computation
    # Replace never-forest with NaN, stable forest with a high value (beyond the range)
    loss_field = loss_img.copy()
    loss_field[never_forest] = np.nan
    loss_field[stable_forest] = 260.0  # slightly beyond 254, so gradient points toward it

    # Gaussian blur to smooth the loss time field (handles noise, gaps)
    # We need to handle NaN regions — use a weighted blur approach
    weights = np.ones_like(loss_field)
    weights[np.isnan(loss_field)] = 0
    loss_filled = np.where(np.isnan(loss_field), 0, loss_field)

    sigma = 5
    blurred_num = gaussian_filter(loss_filled * weights, sigma=sigma)
    blurred_den = gaussian_filter(weights, sigma=sigma)
    blurred_den[blurred_den == 0] = 1  # avoid division by zero
    smoothed = blurred_num / blurred_den

    # Compute spatial gradient (gy, gx)
    gy, gx = np.gradient(smoothed)

    # Normalize to unit vectors
    magnitude = np.sqrt(gx**2 + gy**2)
    magnitude[magnitude == 0] = 1  # avoid division by zero
    gx_norm = gx / magnitude
    gy_norm = gy / magnitude

    # Zero out gradients in never-forest regions
    gx_norm[never_forest] = 0
    gy_norm[never_forest] = 0

    # Encode to RGBA
    flow_map = np.zeros((h, w, 4), dtype=np.uint8)

    # R = gx: -1..+1 → 0..255 (128 = zero)
    flow_map[:, :, 0] = np.clip((gx_norm * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)

    # G = gy: -1..+1 → 0..255 (128 = zero)
    flow_map[:, :, 1] = np.clip((gy_norm * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)

    # B = normalized loss time (copy from forest_loss, stable→254 for continuity)
    b_channel = loss_img.copy()
    b_channel[stable_forest] = 254
    flow_map[:, :, 2] = b_channel.astype(np.uint8)

    # A = forest mask
    flow_map[:, :, 3] = (was_ever_forest * 255).astype(np.uint8)

    # Save
    img = Image.fromarray(flow_map, mode='RGBA')
    img.save(WEB_ASSETS / "flow_map.png")
    img.save(TD_ASSETS / "flow_map_hires.png")
    print(f"Saved flow_map.png ({w}x{h} RGBA)")

    # Stats
    forest_pixels = was_ever_forest.sum()
    avg_mag = magnitude[was_ever_forest].mean()
    print(f"  Forest pixels: {forest_pixels:,}")
    print(f"  Avg gradient magnitude: {avg_mag:.3f}")


if __name__ == "__main__":
    run()
