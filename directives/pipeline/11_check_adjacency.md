# Step 11: Check Adjacent Parcel Ownership

**Script:** `execution/pipeline/check_adjacency.py --buybox-id UUID`

## Purpose
For each target parcel, find adjacent parcels and check if any share the same owner. This reveals an important motivation signal: if the owner lives on an adjacent parcel (has a building on it), the vacant lot is likely being used as a yard or garden, and the owner is less likely to sell cheaply. Conversely, an absentee owner with an adjacent vacant lot may be more motivated.

## Input
- `.tmp/{buyer}/{county}/step_10_scored.csv`

## Output
- `.tmp/{buyer}/{county}/step_11_final.csv`
- Adds columns: `owner_adjacent`, `owner_lives_adjacent`, `adjacent_details`

## Process

### 1. Find Adjacent Parcels
For each target parcel, query the parcel layer for parcels within a 50-foot buffer:
```
POST {county.parcel_layer_url}/query
geometry: {parcel polygon or centroid}
geometryType: esriGeometryPolygon
spatialRel: esriSpatialRelIntersects
distance: 50
units: esriSRUnit_Foot
outFields: {parcel_id}, {owner_1}, {building_value}, {address}
returnGeometry: false
```
The 50-foot buffer catches parcels that share a boundary (touching or very close) without pulling in parcels across the street.

### 2. Match Owner Names
Compare the target parcel's owner to each adjacent parcel's owner using last name matching:
1. Extract last name from owner string (typically the first word, e.g., "SMITH JOHN" -> "SMITH")
2. Case-insensitive comparison
3. If last names match, flag as `owner_adjacent = True`

### 3. Check if Owner Lives Adjacent
For each adjacent parcel that matches the owner:
- If `building_value > 0`, the adjacent parcel has a structure — the owner likely lives there
- Set `owner_lives_adjacent = True`
- This is a key insight: the vacant lot is probably their side yard

### 4. Build Adjacent Details
Create a text summary for the `adjacent_details` column:
- "Owner SMITH also owns adjacent parcel 123-456 (improved, building value $150,000)"
- "Owner SMITH also owns adjacent parcel 123-457 (vacant)"
- Or "No adjacent parcels with same owner"

### 5. Write Output
Add the three adjacency columns. This is the final CSV before database import.

## Decision Points
- **High percentage of owner-lives-adjacent**: These parcels are lower priority for cold outreach — the owner uses the land. The buyer may still want to include them but should expect lower response rates.
- **Owner has multiple adjacent vacant parcels**: This could indicate a land holder or developer — potentially more motivated to sell individual lots.
- **Last name matching is imperfect**: Common last names (SMITH, JOHNSON) may produce false positives. The agent should spot-check a few matches.

## Edge Cases
- Owner name format varies by county ("SMITH, JOHN" vs "JOHN SMITH" vs "SMITH JOHN M") — the last-name extraction logic must handle all common formats
- Corporate owners (LLCs) — last name matching doesn't apply, compare the full entity name instead
- Adjacent parcels may belong to a different person with the same last name (neighbors who happen to share a surname) — this is an accepted false positive rate
- Parcel has no adjacent parcels (isolated, surrounded by roads) — mark all adjacency fields as False/empty

## Self-Annealing
- If last name extraction fails for a county's name format, update the parsing logic in the script and document the format.
- If the 50-foot buffer is too wide (catching parcels across the street) or too narrow (missing parcels that share a boundary), adjust the buffer distance and document the county-specific value.
- If owner matching produces too many false positives on common names, consider adding first-name matching as a secondary check.
