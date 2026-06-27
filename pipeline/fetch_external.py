"""
fetch_external.py
Fetches open data for the RESEX Jaci-Paraná region (Rondônia, Brazil).

Data sources:
  1. OSM roads via Overpass API  -> roads.geojson
  2. GBIF biodiversity records   -> biodiversity.json
  3. NASA FIRMS fire hotspots    -> fire_hotspots.json  +  fire_by_year.json
"""

import json
import os
import sys
import time
from collections import Counter

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH = -64.47724, -10.16611, -64.00078, -9.37789

OUT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "web_assets")
)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GBIF_URL = "https://api.gbif.org/v1/occurrence/search"
FIRMS_CSV_URL = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "modis-c6.1/csv/MODIS_C6_1_South_America.csv"
)

HEADERS = {
    "User-Agent": "RESEX-JaciParana-DataJam/1.0 (research; contact@example.com)"
}


def ensure_dir():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Output directory: {OUT_DIR}")


# ===================================================================
# 1. OSM Roads
# ===================================================================

def fetch_osm_roads():
    """Query Overpass for highways inside the RESEX bbox, convert to GeoJSON."""
    print("\n--- [1/3] Fetching OSM roads via Overpass API ---")

    # Overpass bbox format: south, west, north, east
    bbox_str = f"{BBOX_SOUTH},{BBOX_WEST},{BBOX_NORTH},{BBOX_EAST}"
    query = (
        f'[out:json][timeout:60];'
        f'way["highway"]({bbox_str});'
        f'(._;>;);'
        f'out body;'
    )

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers=HEADERS,
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"  WARNING: Overpass request failed: {exc}")
        _save_json("roads.geojson", {"type": "FeatureCollection", "features": []})
        return

    # Parse the Overpass JSON into GeoJSON
    # Build a dict of node id -> (lon, lat)
    nodes = {}
    ways = []
    for elem in data.get("elements", []):
        if elem["type"] == "node":
            nodes[elem["id"]] = (elem["lon"], elem["lat"])
        elif elem["type"] == "way":
            ways.append(elem)

    features = []
    for way in ways:
        coords = []
        for nid in way.get("nodes", []):
            if nid in nodes:
                coords.append(list(nodes[nid]))  # [lon, lat]
        if len(coords) < 2:
            continue  # need at least 2 points for a LineString

        tags = way.get("tags", {})
        props = {
            "highway": tags.get("highway", "unknown"),
            "name": tags.get("name", None),
        }
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": props,
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    _save_json("roads.geojson", geojson)
    print(f"  Roads fetched: {len(features)} ways, {len(nodes)} nodes")

    # Quick breakdown by highway type
    highway_types = Counter(f["properties"]["highway"] for f in features)
    for htype, count in highway_types.most_common(10):
        print(f"    {htype}: {count}")


# ===================================================================
# 2. GBIF Biodiversity
# ===================================================================

def fetch_gbif_biodiversity():
    """Fetch biodiversity occurrence records from GBIF."""
    print("\n--- [2/3] Fetching GBIF biodiversity records ---")

    params = {
        "decimalLatitude": f"{BBOX_SOUTH},{BBOX_NORTH}",
        "decimalLongitude": f"{BBOX_WEST},{BBOX_EAST}",
        "limit": 300,
        "hasCoordinate": "true",
    }

    all_records = []
    try:
        resp = requests.get(
            GBIF_URL,
            params=params,
            headers=HEADERS,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        for r in data.get("results", []):
            all_records.append({
                "species": r.get("species", r.get("scientificName", "Unknown")),
                "lat": r.get("decimalLatitude"),
                "lon": r.get("decimalLongitude"),
                "year": r.get("year"),
                "kingdom": r.get("kingdom"),
                "phylum": r.get("phylum"),
                "class": r.get("class"),
            })

    except requests.RequestException as exc:
        print(f"  WARNING: GBIF request failed: {exc}")
        _save_json("biodiversity.json", [])
        return

    _save_json("biodiversity.json", all_records)
    print(f"  Biodiversity records: {len(all_records)}")

    # Stats
    kingdoms = Counter(r["kingdom"] for r in all_records if r["kingdom"])
    for k, c in kingdoms.most_common():
        print(f"    {k}: {c}")

    species_set = set(r["species"] for r in all_records if r["species"])
    print(f"  Unique species: {len(species_set)}")


# ===================================================================
# 3. NASA FIRMS Fire Data
# ===================================================================

def fetch_firms_fire():
    """
    Attempt to fetch FIRMS MODIS active-fire data for South America,
    filter to our bbox.  The public CSV only carries recent 24-48h data,
    so we may get zero points inside the RESEX.
    """
    print("\n--- [3/3] Fetching NASA FIRMS fire hotspots ---")

    fire_points = []
    try:
        resp = requests.get(
            FIRMS_CSV_URL,
            headers=HEADERS,
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()

        # Parse CSV line-by-line to avoid loading huge file entirely
        lines = resp.iter_lines(decode_unicode=True)
        header_line = next(lines, None)
        if header_line is None:
            raise ValueError("Empty CSV response")

        headers_list = header_line.strip().split(",")
        lat_idx = headers_list.index("latitude")
        lon_idx = headers_list.index("longitude")
        # acq_date format: YYYY-MM-DD
        date_idx = headers_list.index("acq_date")
        confidence_idx = headers_list.index("confidence") if "confidence" in headers_list else None
        brightness_idx = headers_list.index("brightness") if "brightness" in headers_list else None

        total_rows = 0
        for line in lines:
            total_rows += 1
            cols = line.strip().split(",")
            try:
                lat = float(cols[lat_idx])
                lon = float(cols[lon_idx])
            except (ValueError, IndexError):
                continue

            # Filter to our bbox
            if BBOX_SOUTH <= lat <= BBOX_NORTH and BBOX_WEST <= lon <= BBOX_EAST:
                acq_date = cols[date_idx] if date_idx < len(cols) else ""
                year = acq_date[:4] if len(acq_date) >= 4 else None
                point = {
                    "lat": lat,
                    "lon": lon,
                    "acq_date": acq_date,
                    "year": int(year) if year and year.isdigit() else None,
                }
                if confidence_idx is not None and confidence_idx < len(cols):
                    point["confidence"] = cols[confidence_idx]
                if brightness_idx is not None and brightness_idx < len(cols):
                    try:
                        point["brightness"] = float(cols[brightness_idx])
                    except ValueError:
                        pass
                fire_points.append(point)

        print(f"  Scanned {total_rows:,} rows from FIRMS CSV")

    except requests.RequestException as exc:
        print(f"  WARNING: FIRMS CSV download failed: {exc}")
        print("  The public FIRMS CSV only contains recent 24-48h data.")
        print("  For historical data, get an API key at:")
        print("    https://firms.modaps.eosdis.nasa.gov/api/area/")
        print("  Then download with:")
        print("    https://firms.modaps.eosdis.nasa.gov/api/area/csv/<YOUR_KEY>/MODIS_NRT/")
        print(f"    world/{BBOX_WEST},{BBOX_SOUTH},{BBOX_EAST},{BBOX_NORTH}/1/2012-01-01")
    except Exception as exc:
        print(f"  WARNING: Failed to parse FIRMS CSV: {exc}")

    _save_json("fire_hotspots.json", fire_points)
    print(f"  Fire hotspots in RESEX bbox: {len(fire_points)}")

    if len(fire_points) == 0:
        print("  NOTE: Zero fire points found in the recent FIRMS data.")
        print("  To get historical fire data, register for a free FIRMS API key:")
        print("    https://firms.modaps.eosdis.nasa.gov/api/area/")
        print("  Then download CSV for the bbox and place it at:")
        print(f"    {os.path.join(OUT_DIR, 'fire_hotspots.json')}")

    # Aggregate by year
    year_counts = Counter(p["year"] for p in fire_points if p.get("year"))
    fire_by_year = {str(y): c for y, c in sorted(year_counts.items())}

    _save_json("fire_by_year.json", fire_by_year)
    print(f"  fire_by_year.json: {len(fire_by_year)} years")
    for y, c in sorted(fire_by_year.items()):
        print(f"    {y}: {c}")


# ===================================================================
# Helpers
# ===================================================================

def _save_json(filename, data):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {filename} ({size_kb:.1f} KB)")


# ===================================================================
# Main
# ===================================================================

def main():
    print("=" * 60)
    print("RESEX Jaci-Paraná  --  External Data Fetcher")
    print("=" * 60)
    print(f"Bounding box: W={BBOX_WEST} S={BBOX_SOUTH} E={BBOX_EAST} N={BBOX_NORTH}")

    ensure_dir()

    t0 = time.time()
    fetch_osm_roads()
    fetch_gbif_biodiversity()
    fetch_firms_fire()
    elapsed = time.time() - t0

    print(f"\nDone in {elapsed:.1f}s")
    print(f"Files saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
