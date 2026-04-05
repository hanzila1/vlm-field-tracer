# Test Imagery

This folder is for sample GeoTIFF files used to test and demonstrate the pipeline.

> **Note:** GeoTIFF files are listed in `.gitignore` and are not tracked by git.  
> Add your own test images locally. See below for how to download free Sentinel-2 tiles.

---

## Recommended Test Image Specs

| Property | Recommended |
|---|---|
| **Source** | Copernicus Sentinel-2 Level-2A |
| **Bands** | RGB (B4, B3, B2) — 3-band GeoTIFF |
| **Resolution** | 10m/pixel |
| **Size** | 512×512 to 2048×2048 px (larger = use --grid) |
| **Scene** | Agricultural area, cloud cover < 20% |
| **Seasons** | Planting or harvest season preferred |

---

## How to Download Test Imagery

### Option A — Google Earth Engine (recommended)

Open [Google Earth Engine Code Editor](https://code.earthengine.google.com/) and run:

```javascript
// Export a Sentinel-2 test tile as GeoTIFF
var geometry = ee.Geometry.Rectangle([72.8, 31.4, 73.2, 31.7]); // Example: Punjab, Pakistan

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterDate('2023-04-01', '2023-06-30')
  .filterBounds(geometry)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .median()
  .select(['B4', 'B3', 'B2']);  // RGB bands

// Clip and visualize
var visParams = {min: 0, max: 3000, bands: ['B4', 'B3', 'B2']};
Map.centerObject(geometry, 12);
Map.addLayer(s2.clip(geometry), visParams, 'Sentinel-2 RGB');

// Export to Google Drive
Export.image.toDrive({
  image: s2.clip(geometry),
  description: 'sentinel2_test_tile',
  folder: 'vlm_field_tracer',
  fileNamePrefix: 'test_sentinel2_rgb',
  region: geometry,
  scale: 10,
  crs: 'EPSG:32643',   // UTM Zone 43N for Pakistan — change as needed
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});
```

### Option B — Copernicus Data Space Ecosystem

1. Go to [dataspace.copernicus.eu](https://dataspace.copernicus.eu/)
2. Register for a free account
3. Search for Sentinel-2 Level-2A tiles over your area of interest
4. Download and open in QGIS → export as 3-band RGB GeoTIFF

### Option C — EO Browser

1. Go to [apps.sentinel-hub.com/eo-browser](https://apps.sentinel-hub.com/eo-browser/)
2. Select Sentinel-2 L2A, choose date and area
3. Download as GeoTIFF (analytical)

---

## Suggested Test Regions

These are regions with clear agricultural field patterns — good for demonstrating boundary extraction:

| Region | Coordinates (approx.) | Notes |
|---|---|---|
| Punjab, Pakistan | 73.0°E, 31.5°N | Mixed field sizes, irrigation patterns |
| Nile Delta, Egypt | 31.0°E, 30.5°N | Very regular grid fields |
| Po Valley, Italy | 11.0°E, 45.0°N | Large European fields, FTW covered |
| Mekong Delta, Vietnam | 105.5°E, 10.0°N | FTW Phase 2 target region |
| Central Valley, USA | -120.5°E, 36.5°N | Large commercial farms |

---

## Naming Convention

Name your test files descriptively:

```
test_imagery/
├── punjab_10m_rgb_2023.tif
├── nile_delta_10m_rgb_2023.tif
└── ...
```

---

## Running the Pipeline on a Test Image

```bash
# Basic run
python -m vft test_imagery/punjab_10m_rgb_2023.tif -k YOUR_GEMINI_KEY

# With tiling for large images
python -m vft test_imagery/punjab_10m_rgb_2023.tif -k YOUR_KEY --grid 2x2

# Force UTM Zone 43N (Pakistan)
python -m vft test_imagery/punjab_10m_rgb_2023.tif -k YOUR_KEY --epsg 32643
```

Outputs will be saved to the current directory (or use `-o outputs/` to specify).
