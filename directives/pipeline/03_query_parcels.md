# Step 03: Query Parcels from County GIS

**Script:** `execution/pipeline/query_parcels.py --buybox-id UUID`

## Purpose
Query the county's ArcGIS parcel and zoning layers to find all parcels matching the buybox criteria. This is the most API-intensive step — it spatial-joins the zoning layer with the parcel layer.

## Input
- BuyBox ID (reads County GIS config + filter criteria from DB)

## Output
- `.tmp/{buyer}/{county}/step_03_parcels_raw.csv`
- Fields: parcel_id, address, owner, mailing address, acreage, values, zoning, district, sale history, assessor link

## Process

### 1. Fetch Zoning Polygons
Query the zoning layer for all zones matching `buybox.target_zoning`:
```
POST {county.zoning_layer_url}/query
WHERE: {county.zoning_zone_field} = 'R-2'
returnGeometry: true
```
Paginate if needed (may return 100+ zones).

### 2. Spatial Query Parcels
For each zoning polygon, query the parcel layer for parcels that intersect it:
```
POST {county.parcel_layer_url}/query
WHERE: {building_value} = 0 AND {calc_acres} >= {buybox.min_acres} AND {appraised_value} <= {buybox.max_price} AND {appraised_value} > 0
geometry: {zoning polygon}
geometryType: esriGeometryPolygon
spatialRel: esriSpatialRelIntersects
inSR: {county.zoning_layer_wkid}
```
**Important**: Pass `inSR` matching the zoning layer's WKID since the polygon comes from that layer. The server reprojects automatically.

### 3. Deduplicate
Parcels near zone boundaries may appear in multiple zones. Deduplicate by parcel_id.

### 4. Format Mailing Addresses
Combine mailing address fields (number, prefix, street, suffix, city, state, zip) into a single string using the county's field_map.

### 5. Write CSV

## Decision Points
- **0 parcels returned**: Filters too narrow. Try: wider acreage range, higher price cap, additional zoning codes.
- **>5000 parcels**: Filters too broad. The comp and scoring steps will be slow. Consider narrowing geography first.
- **Zoning layer missing**: Skip the spatial join. Query all parcels matching the non-spatial filters instead.
- **API timeout on large zones**: Simplify the zone polygon geometry before using it as a spatial filter.

## API Cost
Free — county GIS APIs are public.

## Polite Scraping
- Add 0.2-0.5 second delays between requests
- Use a reasonable User-Agent header
- Don't parallelize aggressively (1 request at a time per layer)

## Self-Annealing
- If a spatial query returns an error, the zone polygon may be too complex. Use `simplify_rings()` from pipeline_common.
- If field names don't match, check `county.field_map` and update if needed.
- If `CALCACRES` defaults to 1.0 for most parcels, this is a known GIS data quality issue — Step 07 will fix it by computing real acreage from geometry.
