# Step 07: Compute Real Acreage and Centroids

**Script:** `execution/pipeline/compute_acreage.py --buybox-id UUID`

## Purpose
Fetch the actual polygon geometry for each parcel from the county GIS and compute real acreage using the shoelace formula. Many counties have a known data quality issue where `CALCACRES` defaults to exactly 1.0 for parcels that haven't been properly surveyed. This step overrides those bad values with computed acreage. Also computes each parcel's centroid in lat/lon (WGS84) for mapping.

## Input
- `.tmp/{buyer}/{county}/step_06_with_utilities.csv`

## Output
- `.tmp/{buyer}/{county}/step_07_with_acreage.csv`
- Adds columns: `computed_acres`, `lat`, `lon`

## Process

### 1. Batch Parcels for Geometry Fetch
Group parcels into batches of ~50 (ArcGIS query limits). For each batch, query the parcel layer to fetch polygon geometry:
```
POST {county.parcel_layer_url}/query
WHERE: {parcel_id_field} IN ('id1', 'id2', ...)
returnGeometry: true
outSR: {county.parcel_layer_wkid}  (native coordinate system)
outFields: {parcel_id_field}
```

### 2. Compute Acreage via Shoelace Formula
For each parcel polygon (in the layer's native WKID, which uses linear units like feet or meters):
1. Extract the outer ring coordinates
2. Apply the shoelace formula to compute area in square feet (or square meters)
3. Convert to acres (1 acre = 43,560 sq ft)
4. For multi-ring polygons, subtract inner rings (holes) from the outer ring area

### 3. Override Bad CALCACRES
If the GIS-reported `CALCACRES` equals exactly 1.0 and the computed acreage differs significantly, use the computed value. This is a known GIS default for unsurveyed parcels. If `CALCACRES` is not 1.0, still store the computed value but also keep the original for reference.

### 4. Fetch Centroids in WGS84
Make a second geometry request with `outSR: 4326` (WGS84) to get lat/lon coordinates:
```
POST {county.parcel_layer_url}/query
WHERE: {parcel_id_field} IN ('id1', 'id2', ...)
returnGeometry: true
outSR: 4326
returnCentroid: true
```
If `returnCentroid` is not supported, compute the centroid manually from the polygon vertices (average of all x coordinates, average of all y coordinates).

### 5. Write Output
Add `computed_acres`, `lat`, `lon` columns. The `computed_acres` value is what downstream steps should use for acreage filtering (not the original `CALCACRES`).

## Decision Points
- **Geometry fetch fails for some parcels**: Some parcels may have been deleted or merged since the initial query. Log them and proceed with the rest.
- **Computed acreage is wildly different from CALCACRES**: If the difference is >2x for a parcel where CALCACRES is not 1.0, log a warning — the parcel boundaries may have changed.
- **Native WKID uses meters vs feet**: The shoelace formula produces area in the square of the native unit. Convert correctly: 1 acre = 43,560 sq ft = 4,046.86 sq m.

## Edge Cases
- Parcels with no geometry (point-only records) — cannot compute acreage, keep the original CALCACRES and flag
- Multi-part polygons (one parcel, multiple separate pieces) — compute total area across all parts
- Very small parcels (<0.01 acres computed) may be slivers or data errors — keep them, the shape filter in Step 08 will catch bad geometry

## Self-Annealing
- If the geometry endpoint returns errors for certain parcels, they may have invalid geometry in the GIS. Skip them and note the parcel IDs in the log.
- If the WKID is unrecognized, check the EPSG registry for the unit of measure and update the unit conversion in the script.
- If batches of 50 timeout, reduce to batches of 25 and update the batch size constant in the script.
