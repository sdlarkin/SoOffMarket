# Step 12: Import Parcels to Django Database

**Script:** `execution/pipeline/import_to_db.py --buybox-id UUID`

## Purpose
Read the final pipeline CSV and create or update Parcel records in the Django database. This makes parcels available in the web-based map viewer for the buyer or agent to review and rate. Also fetches full polygon geometry in WGS84 for Leaflet map display.

## Input
- `.tmp/{buyer}/{county}/step_11_final.csv`

## Output
- `Parcel` records in the Django database (parcels app)
- Each parcel linked to the BuyBox via foreign key

## Process

### 1. Read Final CSV
Load `step_11_final.csv`. Each row becomes one Parcel record.

### 2. Fetch WGS84 Geometry for Map Display
For each parcel (batched), fetch polygon geometry projected to WGS84 (WKID 4326):
```
POST {county.parcel_layer_url}/query
WHERE: {parcel_id_field} IN ('id1', 'id2', ...)
returnGeometry: true
outSR: 4326
```
This provides lat/lon polygon rings for the Leaflet map viewer.

### 3. Create or Update Parcel Records
Use Django's `update_or_create` keyed on `parcel_id`:
```python
Parcel.objects.update_or_create(
    parcel_id=row['parcel_id'],
    defaults={
        'buybox': buybox,
        'address': row['address'],
        'owner': row['owner'],
        'computed_acres': row['computed_acres'],
        'lat': row['lat'],
        'lon': row['lon'],
        'geometry_rings': polygon_rings_json,
        'is_target': True,
        'water_provider': row['water_provider'],
        'sewer_provider': row['sewer_provider'],
        'compactness': row['compactness'],
        'land_est_value': row['land_est_value'],
        'arv_comp_median': row['arv_comp_median'],
        'duplex_grade': row['duplex_grade'],
        'owner_adjacent': row['owner_adjacent'],
        'owner_lives_adjacent': row['owner_lives_adjacent'],
        # ... all other pipeline columns
    }
)
```

### 4. Idempotency
The `update_or_create` keyed on `parcel_id` ensures:
- First run: creates all records
- Re-run: updates existing records with latest data
- No duplicates, no data loss

### 5. Log Import Summary
Report:
- Total records processed
- New records created
- Existing records updated
- Errors (if any — e.g., validation failures)

## Decision Points
- **Geometry fetch fails for some parcels**: Import the parcel without geometry — it won't appear on the map but will still be in the database. Log which parcels are missing geometry.
- **Re-running after pipeline changes**: Safe to re-run. Updated CSV values overwrite old database values. Parcels removed from the CSV in a re-run will NOT be deleted from the database (they just won't be updated).
- **Large import (>1000 parcels)**: Consider using Django's `bulk_create` with `update_conflicts=True` for performance, instead of individual `update_or_create` calls.

## Edge Cases
- Parcel ID format may contain special characters (hyphens, dots, spaces) — ensure the database field can handle them
- Some CSV fields may be null/empty — the Parcel model should allow null for optional fields (comp data, duplex score, adjacency info)
- If the BuyBox is re-run with different criteria, old parcels that no longer match stay in the DB with `is_target=True` — the agent should consider marking them `is_target=False` if a clean re-import is desired

## Self-Annealing
- If the Parcel model schema changes (new fields added), update the import script's field mapping and re-run.
- If WGS84 geometry fetch is slow, cache the geometry from Step 07 and reproject locally instead of making additional API calls.
- If `update_or_create` is too slow for large datasets, switch to `bulk_create` with `update_conflicts` and document the performance improvement.
