# Step 06: Check Utility Availability

**Script:** `execution/pipeline/check_utilities.py --buybox-id UUID`

## Purpose
Determine whether each parcel has access to municipal water and sewer service by performing spatial queries against utility district polygon layers. This is critical for buildability — parcels without utilities may require wells and septic, which limits development potential and buyer interest.

## Input
- `.tmp/{buyer}/{county}/step_05_geo_filtered.csv`

## Output
- `.tmp/{buyer}/{county}/step_06_with_utilities.csv`
- Adds columns: `water_provider`, `sewer_provider`

## Process

### 1. Load Utility Layer URLs
Read `County.water_layer_url` and `County.sewer_layer_url` from the database. These are ArcGIS FeatureServer/MapServer layer URLs.

### 2. Compute Parcel Centroids
For each parcel, use its lat/lon (if available from prior steps) or compute a rough centroid from the parcel address via geocoding. The centroid is used as the query point.

### 3. Spatial Query — Water
For each parcel centroid, query the water utility layer:
```
POST {county.water_layer_url}/query
geometry: {centroid point}
geometryType: esriGeometryPoint
spatialRel: esriSpatialRelIntersects
outFields: [provider name field]
returnGeometry: false
```
If the point falls within a water district polygon, record the provider name. Otherwise, mark as "None".

### 4. Spatial Query — Sewer
Same approach against the sewer utility layer.

### 5. Handle Large Polygons
Some utility district polygons are very large and complex. If queries fail or timeout:
- Use `simplify_rings` on the query geometry
- Or batch parcels by proximity and query once per cluster

### 6. Batch for Efficiency
Rather than querying one parcel at a time, batch centroids into groups and use a single spatial query per batch where possible. The ArcGIS `query` endpoint supports point-in-polygon checks efficiently.

### 7. Write Output
Add `water_provider` and `sewer_provider` columns to each parcel row. Values are the provider name string (e.g., "WWTA", "Hixson Utility District") or "None" if outside all service areas.

## Decision Points
- **No utility layers configured for the county**: If `County.water_layer_url` or `County.sewer_layer_url` is null, mark all parcels as "Unknown" for that utility type. Log a warning and proceed — utility info can be added later.
- **Buyer requires utilities**: If the buyer's notes specify "must have city water", the agent should flag parcels with water_provider = "None" for potential exclusion. This is an agent-level decision, not automated in the script.
- **Mixed results**: Some parcels at the edge of service areas may get inconsistent results. These are fine to keep — the buyer can verify on a case-by-case basis.

## Edge Cases
- Utility layers may use a different spatial reference than the parcel layer — always pass `inSR` with the centroid's coordinate system
- Some counties have multiple water/sewer providers with separate layers — the County record should list the primary layer; additional providers may need manual lookup
- Utility service boundaries change over time — if results seem wrong, re-check the layer URL for updates

## Self-Annealing
- If a utility layer URL returns 404 or errors, the county may have updated their GIS. Re-run Step 02 (Discover GIS) to find the new URL and update the County record.
- If spatial queries timeout on complex polygons, add polygon simplification logic to the script and note the tolerance that worked.
- When a new county is onboarded that has no utility layers, document this in the County record's notes field so future runs know to skip.
