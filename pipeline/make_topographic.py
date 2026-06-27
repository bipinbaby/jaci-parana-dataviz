"""
Generate topographic base map from SRTM heightmap:
  - Hillshade (terrain lighting)
  - Hypsometric color (elevation -> color ramp)
  - Combined topographic map
"""

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from pathlib import Path

WEB_ASSETS = Path(__file__).parent.parent / "web_assets"
TD_ASSETS = Path(__file__).parent.parent / "td_assets"


def compute_hillshade(elevation, azimuth=315, altitude=45, z_factor=3.0):
    """Compute hillshade from elevation array. Returns 0-1 float array."""
    az_rad = np.radians(azimuth)
    alt_rad = np.radians(altitude)

    # Gradients (slope in x and y directions)
    dy, dx = np.gradient(elevation * z_factor)

    slope = np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dy, dx)

    hillshade = (
        np.sin(alt_rad) * np.cos(slope) +
        np.cos(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect)
    )

    return np.clip(hillshade, 0, 1)


def hypsometric_color(elevation):
    """Map normalized elevation (0-1) to topographic colors. Returns RGB array."""
    h, w = elevation.shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)

    # Color stops: (elevation_threshold, R, G, B)
    # Low = river valleys (deep green-blue)
    # Mid = forest zone (green)
    # High = ridges (tan/brown)
    stops = [
        (0.00, 0.12, 0.22, 0.14),   # deep valley green
        (0.15, 0.14, 0.28, 0.12),   # low green
        (0.30, 0.18, 0.35, 0.13),   # mid green
        (0.45, 0.28, 0.38, 0.16),   # transitional
        (0.60, 0.42, 0.38, 0.20),   # tan-brown
        (0.75, 0.52, 0.44, 0.26),   # light brown
        (0.90, 0.58, 0.50, 0.32),   # ridge tan
        (1.00, 0.65, 0.56, 0.38),   # peak
    ]

    for i in range(len(stops) - 1):
        e0, r0, g0, b0 = stops[i]
        e1, r1, g1, b1 = stops[i + 1]
        mask = (elevation >= e0) & (elevation < e1)
        t = np.clip((elevation[mask] - e0) / (e1 - e0), 0, 1)
        rgb[mask, 0] = r0 + t * (r1 - r0)
        rgb[mask, 1] = g0 + t * (g1 - g0)
        rgb[mask, 2] = b0 + t * (b1 - b0)

    # Handle exactly 1.0
    mask = elevation >= stops[-1][0]
    rgb[mask] = [stops[-1][1], stops[-1][2], stops[-1][3]]

    return rgb


def run():
    # Load heightmap
    hm_path = WEB_ASSETS / "heightmap.png"
    if not hm_path.exists():
        # Try full-res from td_assets
        hm_path = TD_ASSETS / "heightmap.png"

    hm = np.array(Image.open(hm_path), dtype=np.float32) / 255.0
    print(f"Loaded heightmap: {hm.shape[1]}x{hm.shape[0]}")

    # Smooth slightly for cleaner hillshade
    hm_smooth = gaussian_filter(hm, sigma=0.5)

    # Hillshade
    hs = compute_hillshade(hm_smooth, azimuth=315, altitude=45, z_factor=4.0)
    print(f"Hillshade range: {hs.min():.2f} - {hs.max():.2f}")

    # Save hillshade as grayscale
    hs_img = Image.fromarray((hs * 255).astype(np.uint8), mode='L')
    hs_img.save(WEB_ASSETS / "hillshade.png")
    print("Saved hillshade.png")

    # Hypsometric coloring
    hypso = hypsometric_color(hm_smooth)

    # Combine: multiply hypsometric color by hillshade for shaded relief
    shaded = hypso * hs[:, :, np.newaxis]

    # Boost contrast slightly
    shaded = np.clip(shaded * 1.3 + 0.02, 0, 1)

    # Save combined topographic map
    topo_img = Image.fromarray((shaded * 255).astype(np.uint8), mode='RGB')
    topo_img.save(WEB_ASSETS / "topographic.png")
    print(f"Saved topographic.png ({topo_img.size[0]}x{topo_img.size[1]})")

    # Also save for TD
    topo_img.save(TD_ASSETS / "topographic.png")


if __name__ == "__main__":
    run()
