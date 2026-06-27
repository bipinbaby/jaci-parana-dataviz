"""
Generate terrain heightmap from SRTM elevation data.

Downloads and processes SRTM 1-arc-second (~30m) elevation tiles,
crops to the RESEX bbox, and exports as a normalized PNG for WebGL.
"""

import gzip
import struct
import numpy as np
from PIL import Image
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
WEB_ASSETS = PIPELINE_DIR.parent / "web_assets"
TD_ASSETS = PIPELINE_DIR.parent / "td_assets"

# RESEX bounding box (from meta.json)
BBOX_W, BBOX_S, BBOX_E, BBOX_N = -64.47724, -10.16611, -64.00078, -9.37789

# SRTM tile size: 3601 x 3601 samples per 1-degree tile
SRTM_SIZE = 3601


def load_hgt_gz(path):
    """Load a gzipped SRTM .hgt file into a numpy array."""
    with gzip.open(path, 'rb') as f:
        raw = f.read()
    # SRTM .hgt is big-endian signed 16-bit integers
    n_samples = SRTM_SIZE * SRTM_SIZE
    data = np.array(struct.unpack(f'>{n_samples}h', raw[:n_samples * 2]),
                    dtype=np.int16).reshape(SRTM_SIZE, SRTM_SIZE)
    return data


def tile_bounds(name):
    """Get geographic bounds from tile name like 'S10W065'."""
    lat_sign = -1 if name[0] == 'S' else 1
    lon_sign = -1 if name[3] == 'W' else 1
    lat = lat_sign * int(name[1:3])
    lon = lon_sign * int(name[4:7])
    # Tile covers [lat, lat+1] x [lon, lon+1]
    # But SRTM origin is top-left (north), rows go south
    return {
        'south': lat, 'north': lat + 1,
        'west': lon, 'east': lon + 1,
    }


def run():
    WEB_ASSETS.mkdir(parents=True, exist_ok=True)
    TD_ASSETS.mkdir(parents=True, exist_ok=True)

    # Load available tiles
    tile_files = sorted(PIPELINE_DIR.glob('*.hgt.gz'))
    if not tile_files:
        print("No SRTM tiles found! Download them first.")
        return

    print(f"Found {len(tile_files)} SRTM tiles")

    # Build mosaic covering our bbox
    # Figure out the full mosaic extent
    all_south = min(tile_bounds(f.stem.replace('.hgt', ''))['south'] for f in tile_files)
    all_north = max(tile_bounds(f.stem.replace('.hgt', ''))['north'] for f in tile_files)
    all_west = min(tile_bounds(f.stem.replace('.hgt', ''))['west'] for f in tile_files)
    all_east = max(tile_bounds(f.stem.replace('.hgt', ''))['east'] for f in tile_files)

    print(f"Mosaic extent: {all_west} to {all_east} lon, {all_south} to {all_north} lat")

    # Resolution: 1 arcsecond = 1/3600 degrees
    res = 1.0 / 3600.0

    # Mosaic dimensions
    mosaic_w = int(round((all_east - all_west) / res)) + 1
    mosaic_h = int(round((all_north - all_south) / res)) + 1
    mosaic = np.full((mosaic_h, mosaic_w), -32768, dtype=np.int16)

    print(f"Mosaic size: {mosaic_w} x {mosaic_h}")

    # Place each tile into the mosaic
    for f in tile_files:
        name = f.stem.replace('.hgt', '')
        bounds = tile_bounds(name)
        print(f"  Loading {name}: {bounds}")

        data = load_hgt_gz(f)

        # Pixel position in mosaic
        col_start = int(round((bounds['west'] - all_west) / res))
        row_start = int(round((all_north - bounds['north']) / res))

        # Place tile (may overlap by 1 pixel at edges, that's fine)
        r_end = min(row_start + SRTM_SIZE, mosaic_h)
        c_end = min(col_start + SRTM_SIZE, mosaic_w)
        dr = r_end - row_start
        dc = c_end - col_start
        mosaic[row_start:r_end, col_start:c_end] = data[:dr, :dc]

    # Crop to RESEX bounding box
    col_w = int(round((BBOX_W - all_west) / res))
    col_e = int(round((BBOX_E - all_west) / res))
    row_n = int(round((all_north - BBOX_N) / res))
    row_s = int(round((all_north - BBOX_S) / res))

    cropped = mosaic[row_n:row_s, col_w:col_e].astype(np.float32)
    print(f"Cropped to RESEX: {cropped.shape[1]} x {cropped.shape[0]}")

    # Handle voids (-32768)
    void_mask = cropped <= 0
    if void_mask.any():
        # Fill voids with nearest valid value
        from scipy.ndimage import distance_transform_edt
        valid = ~void_mask
        if valid.any():
            _, indices = distance_transform_edt(void_mask, return_distances=True, return_indices=True)
            cropped[void_mask] = cropped[indices[0][void_mask], indices[1][void_mask]]

    # Stats
    print(f"Elevation range: {cropped.min():.0f}m to {cropped.max():.0f}m")
    print(f"Mean elevation: {cropped.mean():.0f}m")

    # Normalize to 0-255 for web (8-bit heightmap)
    elev_min = cropped.min()
    elev_max = cropped.max()
    elev_range = elev_max - elev_min
    if elev_range > 0:
        normalized = ((cropped - elev_min) / elev_range * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(cropped, dtype=np.uint8)

    # Save full-res
    img_full = Image.fromarray(normalized, mode='L')
    img_full.save(TD_ASSETS / "heightmap.png")
    print(f"Saved td_assets/heightmap.png (full-res {normalized.shape[1]}x{normalized.shape[0]})")

    # Resize for web (match forest_loss dimensions: 768x1280)
    img_web = img_full.resize((768, 1280), resample=Image.Resampling.BILINEAR)
    img_web.save(WEB_ASSETS / "heightmap.png")
    print(f"Saved web_assets/heightmap.png (768x1280)")

    # Also save 16-bit for TD
    normalized_16 = ((cropped - elev_min) / elev_range * 65535).astype(np.uint16)
    img_16 = Image.fromarray(normalized_16, mode='I;16')
    img_16.save(TD_ASSETS / "heightmap_16bit.png")
    print(f"Saved td_assets/heightmap_16bit.png")

    # Save elevation metadata
    import json
    elev_meta = {
        "min_elevation_m": float(elev_min),
        "max_elevation_m": float(elev_max),
        "mean_elevation_m": float(cropped.mean()),
        "source": "SRTM 1-arc-second (30m)",
    }
    with open(WEB_ASSETS / "heightmap_meta.json", 'w') as f:
        json.dump(elev_meta, f, indent=2)
    print(f"Elevation metadata: {elev_min:.0f}m - {elev_max:.0f}m")


if __name__ == "__main__":
    run()
