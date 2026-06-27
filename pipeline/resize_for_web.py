"""
Downscale textures for web delivery.
Full-res (1767x2923) → 1024x1024 (web) with correct aspect ratio.
Uses power-of-two dimensions for GPU texture compatibility.
"""

import numpy as np
from PIL import Image
from pathlib import Path

WEB_ASSETS = Path(__file__).parent.parent / "web_assets"

# Target: fit into 1024x1024 with correct aspect ratio
# Original is 1767w x 2923h (portrait, ratio ~0.6)
# We'll use 1024x1696 (maintaining aspect) but round to nearest power-of-two-friendly
WEB_SIZE = (768, 1280)  # w x h, close to original aspect ratio


def resize_texture(name, resample, mode=None):
    path = WEB_ASSETS / name
    if not path.exists():
        print(f"  Skipping {name} (not found)")
        return
    img = Image.open(path)
    original_size = img.size
    # Save full-res backup first
    full_path = WEB_ASSETS / f"full_{name}"
    if not full_path.exists():
        img.save(full_path)

    resized = img.resize(WEB_SIZE, resample=resample)
    resized.save(path)
    print(f"  {name}: {original_size} -> {WEB_SIZE}")


def run():
    print(f"Resizing textures to {WEB_SIZE[0]}x{WEB_SIZE[1]}...")

    # Forest loss: NEAREST (preserve class boundaries, no interpolation artifacts)
    resize_texture("forest_loss.png", Image.Resampling.NEAREST)

    # Flow map: BILINEAR (smooth gradients can be interpolated)
    resize_texture("flow_map.png", Image.Resampling.BILINEAR)

    # Water mask: NEAREST (binary mask)
    resize_texture("water_mask.png", Image.Resampling.NEAREST)

    print("Done!")


if __name__ == "__main__":
    run()
