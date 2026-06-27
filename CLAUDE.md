# DISSOLVE — RESEX Jaci-Paraná Data Art

## What This Is
Data-art project for Eric Terena's "Izikoxovoti — Sonic Future Spaces" immersive-sound event. Two outputs:
1. **Interactive web page** — scrollytelling / data visualization
2. **Audio-reactive TouchDesigner installation** — three layered concepts (Chainsaw Granular, Sonification of Loss, Fishbone Resonance)

**Subject:** RESEX Jaci-Paraná, Rondônia, Brazil. Extractive reserve where forest fell from ~197,000 ha (1996) to ~44,775 ha (2024) — 77% loss, replaced by cattle pasture in a classic "fishbone" road pattern.

## Serving the Web Page
```bash
cd "C:/Users/bipin/Desktop/26_June_Work/DATA JAM"
python -m http.server 8090
# Open http://localhost:8090/web/index.html
```
Server must run from `DATA JAM/` root (not `web/`) so `../web_assets/` paths resolve.

## Source Data
- `cobertura_tiff/tiff/cobertua_*.tif` — 27 MapBiomas rasters (1996-2024, missing 1997 & 2016), uint8, 1767x2923, EPSG:4326
  - Key classes: 3=Forest, 6=Floodable Forest, 15=Pasture, 33=Water
  - Note the filename typo: "cobertua" not "cobertura"
- `evolucao_cobertura.xlsx` — per-class hectares 1985-2024
- `RESEX_Jaci_parana/ucs.shp` — reserve boundary (SIRGAS 2000)
- RESEX bbox: W=-64.47724, S=-10.16611, E=-64.00078, N=-9.37789
- RESEX center: -64.25, -9.76

## Pipeline (all completed)
All scripts in `pipeline/`, run via `python pipeline/<script>.py`:

| Script | Output | Status |
|--------|--------|--------|
| `make_forest_loss.py` | `forest_loss.png` (8-bit: 0=never forest, 1-254=loss year, 255=stable) | Done |
| `make_flow_map.py` | `flow_map.png` (RGBA: gradient direction + loss time + forest mask) | Done |
| `extract_boundary.py` | `resex_boundary.geojson`, `meta.json` (yearly stats) | Done |
| `make_water_mask.py` | `water_mask.png` | Done |
| `resize_for_web.py` | Resized textures to 768x1280 | Done |
| `make_category_maps.py` | `category/cat_YYYY.png` (27 PNGs at 384x640, MapBiomas palette) | Done |
| `make_heightmap.py` | `heightmap.png` (SRTM 30m, 57-301m elevation) | Done |
| `make_topographic.py` | `topographic.png`, `hillshade.png` | Done |
| `fetch_external.py` | `biodiversity.json` (8300 GBIF records), `roads.geojson`, `rivers.geojson`, `fire_hotspots.json` (empty—URL changed) | Done |

## Generated Assets

### `web_assets/` (web-resolution)
- `forest_loss.png` (768x1280), `flow_map.png` (768x1280 RGBA)
- `water_mask.png` (768x1280, dilated from full-res MapBiomas class 33), `heightmap.png`, `hillshade.png`, `topographic.png`
- `resex_boundary.geojson` (40KB), `meta.json` (6KB)
- `biodiversity.json` — **8,300 GBIF records, 1,150 unique species** (1953–2026), fetched 2026-06-27
  - 6,293 birds, 944 flowering plants, 622 insects, 56 monocots, 54 amphibians, 37 ferns, 7 reptiles, 5 mammals, + parasites
  - Historical: 91 plant records from 1984 botanical survey, 53 fish from 1994 river survey
  - Zero overlap between pre-2000 and post-2020 species — no resurveys have occurred
- `rivers.geojson` — 27 OSM waterway segments (Rio Jaci-Paraná, Rio Formoso, Rio Branco, Rio São Francisco)
- `roads.geojson` — 603 OSM road segments (removed from viz — inaccurate elevation, but data still available)
- `land_mask.png` (718x360) — equirectangular world land mask from Natural Earth 110m, used for the globe dot map
- `category/cat_1996.png` through `cat_2024.png` — 27 colored maps using MapBiomas palette
- `fire_hotspots.json`, `fire_by_year.json` — empty (API issues)
- `heightmap_meta.json` — elevation range metadata

### `td_assets/` (full-resolution for TouchDesigner)
- `forest_loss.png`, `heightmap.png`, `heightmap_16bit.png`, `topographic.png`

## Web Page — Current State

### What's Built (web/index.html)
Single-file Canvas2D application with additive blending (`globalCompositeOperation: 'lighter'`).

**1. Interactive Dot Globe**
- Dots sampled from `land_mask.png` (Natural Earth data) for accurate coastlines
- Coastal dots are larger, interior dots are smaller (coastDist function checks neighbor pixels)
- RESEX Jaci-Paraná region blinks green — click it to zoom into topo view
- Dark ocean with blue atmosphere glow, directional lighting, specular highlight
- Starts facing South America (rotY=154) with RESEX visible, pauses 4s before auto-rotating
- Pulsing "Click the green region to explore" hint tracks RESEX position on globe
- Mobile: "Explore Reserve" button at bottom as alternative to tapping green dots
- Globe is laterally inverted (x negated in projection)

**2. Topo Dot Map with Deforestation Data** (transitions from globe on click)
- Dots colored by land cover state at selected year:
  - **Green** (#1F8D49) = forest still standing
  - **Tan/gold** (#EDCD61) = cleared to pasture
  - **Blue** (#3C8CFF) = water bodies (sampled from OSM river proximity, threshold 0.006°)
  - **Dark grey** = never was forest (non-water, non-forest)
- Water detection: each dot checks distance to nearest OSM river line (`rivers.geojson`), tagged `isWater` if within 0.006° (~660m). Brighter alpha (+0.4) for water dots.
- Data from `forest_loss.png`: each dot samples loss year (0=never forest, 1-254=year of loss, 255=stable)
- Loss pixel value decoded to actual year: `1996 + (val - 1) / 253 * 28`
- Dots placed via ray-casting point-in-polygon on `resex_boundary.geojson` (873-point polygon)
- Coast-style sizing: edge dots larger (distance-to-boundary calculation), interior dots smaller
- Grid spacing: 0.009° (~1000m), dot radius: `baseR * 0.26`
- Fills 96% of viewport
- No boundary line (removed — dots define the shape)
- Additive blending: overlapping dots glow brighter naturally

**2b. Surrounding Territory**
- Dots outside reserve boundary with `isOutside: true`, white color, faded by distance from boundary
- Real SRTM elevation from 4 tiles (S10W064, S10W065, S11W064, S11W065)
- `heightmap_expanded.png` (932x1280) covers BBOX ± 0.18° surround, elevation 51m-371m
- `SURROUND = 0.18` expansion around reserve boundary
- Viewport fit uses only reserve dots (not surrounding) for bounding box

**3. 3D Terrain Heightmap** (scroll down from topo view)
- Scroll-driven tilt transition: `topoTilt` 0→0.75 (max 70° × 0.75 = 52.5°)
- Y-axis rotation: base from tilt + user drag offset (`topoRotYTarget`), lerped smoothly
- Mobile horizontal swipe adds to `topoRotYTarget` for free Y-axis rotation
- Each dot has `d.elev` sampled from `heightmap_expanded.png` (SRTM 30m, 51-371m range)
- Elevation scale: `topoTilt * gridH * 0.12` (gentle hills, not mountains — real terrain is 0.28% grade)
- Proper 3D camera model: perspective projection with `camDist = gridH * 1.2`
- Two-pass rendering: pass 1 projects all dots + finds bounding box, pass 2 scales to fill viewport
- Back-to-front depth sorting when tilted
- Smooth lerped transitions (tilt lerp 0.08, no abrupt jumps)
- "Scroll to explore terrain" hint (bottom-right) appears on entering topo view, dismisses on first interaction

**4. Year Slider + Stats**
- Slider at bottom of topo view: 1996–2024
- Large year display above slider
- Stats line below: `X ha forest · Y ha pasture` from `meta.json`
- Forest in green, pasture in gold — numbers use `en-US` locale formatting
- Panel appears on entering topo view, hides on zoom out

**5. Biodiversity Clusters**
- 8,300 GBIF records grouped into spatial grid clusters (0.04° cell size, ~4.4km)
- Each cluster rendered as a dark box with neon glow border (dominant category color)
- Neon border twinkles via sine wave with position-based phase offset
- Uniform category circles inside each box, color-coded by taxonomic class
- Clusters hidden when year slider passes all their species' last observation year
- Handles null years (always show), pre-1996 records (always show), and in-range years (filter)
- **Click popup (desktop):** positioned near cursor, shows species grouped by class with year info
- **Tap popup (mobile):** full-screen overlay with X close button
- Species listed with italic names, year in green (still observed 2020+) or red (not resurveyed)
- Footer legend explains green/red year coloring

**6. Layer Toggle Buttons**
- Pill-shaped toggle buttons in top-right: Forest, Pasture, Water, Species
- Each button has a colored dot swatch and toggles its layer on/off
- Active state: colored border + tinted background. Off state: dimmed to 35% opacity
- Appears on entering topo view, hides on zoom out

**State Machine:** `globe` → `zoomIn` → `topo` → `zoomOut` → `globe`
- "← GLOBE" back button appears in topo view
- Zoom transition: globe rotates to center RESEX, zooms 6x, crossfades to topo

**7. Mobile Support**
- Landscape prompt overlay for portrait mode ("Rotate your device")
- Single-finger vertical swipe: tilt terrain into 3D
- Single-finger horizontal swipe: rotate map on Y-axis
- Tap cluster boxes: full-screen species overlay with X close button
- "Explore Reserve" button on globe view (alternative to tapping green dots)
- "Swipe to explore terrain" hint (vs "Scroll" on desktop)
- Reduced `shadowBlur` on mobile for performance (3+3 vs 8+8, skip second stroke pass)
- `isMobile` detection via `ontouchstart` / `maxTouchPoints`

### Deployment
- **GitHub:** https://github.com/bipinbaby/jaci-parana-dataviz
- **Vercel:** jaci-parana-dataviz.vercel.app
- `vercel.json` rewrites `/` → `/web/index.html`
- `.gitignore` excludes: cobertura_tiff/, RESEX_Jaci_parana/, *.zip, *.xlsx, *.jpeg, *.hgt.gz, td_assets/

### Removed Features
- **Road overlay** — removed because elevation exaggeration made roads look unrealistically steep. Road data (`roads.geojson`) still in web_assets if needed later.
- **Separate river dot overlay** — replaced by water detection on base topo dots (OSM river proximity check)

### User Preferences for Web
- YES colored data dots (green=forest, tan=pasture) on black
- YES clean, readable, map-based data visualization
- YES scrollytelling with text panels (not yet built)
- YES additive blending for emissive look
- YES interactive toggle buttons for layers
- YES species popups with conservation status
- NO shadowBlur per dot (performance hit — causes jank)
- NO heavy satellite imagery (too taxing)
- NO abstract particle effects or heavy WebGL shaders
- NO road overlay (inaccurate with terrain exaggeration)
- NO turntable rotation slider (tried, reverted)
- NO title "DISSOLVE" — renamed to "DATAVIZ"
- Build piece by piece, not all at once

### What's NOT Built Yet
- **Deforestation projection** — BFS-based future loss prediction from existing data (discussed, deferred)
- **Landsat satellite imagery** — `pipeline/fetch_landsat.py` written but blocked by API issues
- Scrollytelling text panels with narrative
- Stats/charts section (area chart of forest vs pasture over time)
- Active clearing front highlight (dots cleared in selected year shown differently)
- Full MapBiomas category breakdown (use cat_YYYY.png for agriculture, urban, grassland)
- Audio/sonification
- **Fire hotspots** (NASA FIRMS) — high-priority data source identified but not yet fetched
- **Cattle census** (IBGE SIDRA PPM) — Porto Velho municipal herd data identified but not yet fetched

## Data Sources Identified (Not Yet Fetched)
- **INPE PRODES** — annual deforestation polygons 1988–2024 (terrabrasilis.dpi.inpe.br)
- **NASA FIRMS** — MODIS/VIIRS fire hotspots 2000–present (firms.modaps.eosdis.nasa.gov)
- **IBGE SIDRA PPM** — cattle herd per municipality 1974–2024 (sidra.ibge.gov.br)
- **Hansen GFC** — 30m annual loss pixels 2001–2023 (Google Earth Engine)
- **Trase** — cattle supply chain deforestation data (trase.earth)
- **Sentinel-2** — 10m satellite imagery 2017+ (Copernicus/GEE)
- **RAISG** — indigenous territories + protected area network (raisg.org)
- **ICMBio/CNUC** — official RESEX management plan documents

## Biodiversity Data Notes
- **Zero overlap** between pre-2000 and post-2020 observed species
- This is a survey gap, not confirmed extinction — different research teams surveyed different taxa:
  - 1984: botanical survey (91 plant records) — trees like *Minquartia guianensis*, *Dialium guianense*
  - 1994: ichthyological survey (53 fish records) — *Carnegiella marthae*, *Hoplias malabaricus*
  - 2022–2024: eBird citizen science (5,200+ bird records)
- No one has resurveyed the 1984 plants or 1994 fish — with 77% forest gone, many are likely lost
- The absence of resurvey data IS the story

## TouchDesigner — Not Started
Three layered audio-reactive concepts selected:
- **B. "Chainsaw Granular"** — live audio drives destruction (bass=dissolve speed, mids=ember, highs=sparks)
- **C. "Sonification of Loss"** — data generates audio (each lost pixel emits a grain)
- **D. "Fishbone Resonance"** — raster rows scanned as waveforms

## Key Stats (from meta.json)
- 1996: 196,736 ha forest, 73 ha pasture
- 2004: 191,453 ha forest, 5,466 ha pasture (roads push in)
- 2017: 108,552 ha forest, 88,157 ha pasture (near crossover)
- 2024: 44,775 ha forest, 151,852 ha pasture (77% destroyed)

## MapBiomas Color Palette
```
3:  #1F8D49  Forest Formation
6:  #206849  Floodable Forest
15: #EDCD61  Pasture
18: #E0A43B  Agriculture
33: #2358AB  Water (River/Lake)
24: #E9485E  Urban
12: #B7DB74  Grassland
```
