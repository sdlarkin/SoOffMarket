# Step 02: Discover County GIS Services

**Script:** `execution/pipeline/discover_gis_services.py --county "Hamilton" --state "TN"`

## Purpose
Probe a county's ArcGIS REST services to find parcel, zoning, and utility layers. Populate the `County` model with URLs, field mappings, and spatial references.

## Input
- County name + state (from Step 01)
- Optional: known GIS base URL (if the agent already found it)

## Output
`County` record populated with:
- `parcel_layer_url`, `parcel_layer_wkid`
- `zoning_layer_url`, `zoning_layer_wkid`, `zoning_zone_field`
- `water_layer_url`, `sewer_layer_url`
- `field_map` (canonical → county-specific field name mapping)
- `entity_keywords` (county-specific additions)

## Process

### 1. Find the GIS Endpoint
Search strategies (in order):
1. Google: `"{county name} county {state} GIS parcel viewer"` or `"{county name} county ArcGIS REST services"`
2. Cal Poly GIS data guide: `https://guides.lib.calpoly.edu/gis/GISData` — search by county name
3. Check common patterns:
   - `https://gis.{county}county.gov/arcgis/rest/services`
   - `https://maps.{county}county.gov/arcgis/rest/services`
   - `https://services.arcgis.com/{org_id}/ArcGIS/rest/services`

### 2. Enumerate Available Services
Hit the services endpoint with `?f=json`:
```
GET {base_url}?f=json
```
This returns a JSON catalog of all available MapServer and FeatureServer services.

### 3. Identify Key Layers
Search the catalog for layers by name pattern:

| Layer Type | Name Patterns to Search |
|-----------|------------------------|
| Parcels | "Parcel", "Tax", "Cadastral", "Property" |
| Zoning | "Zoning", "Zone", "Land Use" |
| Water | "Water", "Utility", "WWTA" |
| Sewer | "Sewer", "Wastewater", "WWTA" |

For each candidate, fetch `{service_url}/{layer_id}?f=json` to inspect fields.

### 4. Map Field Names
Query the parcel layer for its field schema. Map to canonical names:

| Canonical | Common Field Names |
|-----------|-------------------|
| `parcel_id` | TAX_MAP_NO, PARCEL_ID, PIN, APN, PARCEL_NUMBER |
| `address` | ADDRESS, SITUS_ADDR, PROP_ADDR, SITE_ADDRESS |
| `owner_1` | OWNERNAME1, OWNER, OWNER_NAME, OWN_NAME |
| `calc_acres` | CALCACRES, ACREAGE, ACRES, LOT_AREA, LAND_AREA |
| `building_value` | BUILDVALUE, IMPR_VALUE, BUILDING_VAL, BLD_VAL |
| `appraised_value` | APPVALUE, TOTAL_VALUE, MARKET_VALUE, APPR_VALUE |
| `land_use` | LUCODE, LAND_USE, USE_CODE, PROP_TYPE |

If a field isn't found by exact match, check for partial matches (case-insensitive).

### 5. Detect Spatial Reference
Read the `spatialReference` from the layer's JSON metadata. Record the WKID.
- Parcels and zoning may have different WKIDs — record both.
- When querying across layers, use `inSR` parameter to let the server reproject.

### 6. Update the County Record
Store everything in the `County` model via Django ORM.

## Decision Points
- **Multiple parcel layers found**: Pick the one with the most fields (usually the detailed one, not the simplified overview layer).
- **No ArcGIS REST services**: The county may use a different GIS platform (MapServer, GeoServer, CKAN). Flag for manual research. The pipeline can accept a pre-formatted CSV at Step 03 as a bypass.
- **Behind authentication**: Some counties require login. Flag this — may need to request data via FOIA or purchase from the county.
- **Field names don't match any known pattern**: Query a sample record and inspect field names manually. Update the canonical mapping.

## Edge Cases
- Counties with separate city/county GIS systems (e.g., City of Chattanooga vs Hamilton County) — check both, use the one with more complete data.
- Zoning on a different server than parcels — store different base URLs.
- No zoning layer available — the pipeline can still run without zoning (skip the spatial join in Step 03, query all parcels matching other filters).

## Self-Annealing
When the discovery script encounters a county with unusual field names or layer structure:
1. Log the unknown fields
2. Add the mapping to the County record manually
3. Update the field name pattern lists in this directive for future runs
