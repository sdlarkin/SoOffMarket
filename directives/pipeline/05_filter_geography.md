# Step 05: Filter by Target Geography

**Script:** `execution/pipeline/filter_geography.py --buybox-id UUID`

## Purpose
Filter parcels down to the buyer's target areas using district codes and address keyword exclusions. Some districts are mixed — containing both desirable and undesirable sub-areas — so this step handles fine-grained geography filtering.

## Input
- `.tmp/{buyer}/{county}/step_04_entities_filtered.csv`

## Output
- `.tmp/{buyer}/{county}/step_05_geo_filtered.csv`

## Process

### 1. Read Geography Configuration
Load `BuyBox.target_geography`, which is a JSON structure:
```json
{
  "target_districts": ["1", "2", "5"],
  "exclude_districts": ["8", "9"],
  "mixed_districts": {
    "3": {
      "exclude_address_keywords": ["SODDY", "DAISY", "SALE CREEK"]
    }
  }
}
```

### 2. Check for Empty Geography
If `target_geography` is null, empty, or has no district lists — skip this step entirely. Copy step_04 CSV to step_05 CSV unchanged and log that geography filtering was skipped.

### 3. Filter by District
For each parcel:
1. If the parcel's district is in `target_districts` — keep it
2. If the parcel's district is in `exclude_districts` — remove it
3. If the parcel's district is in `mixed_districts` — apply address keyword exclusions (step 4)
4. If the parcel's district is not in any list — remove it (unlisted = not in target area)

### 4. Handle Mixed Districts
For parcels in mixed districts, check the parcel's address against the exclusion keywords for that district. If the address contains any excluded keyword (case-insensitive), remove the parcel.

Example: District 3 in Hamilton County contains both Hixson (target) and Soddy Daisy (not target). Parcels with "SODDY" or "DAISY" in the address get removed; the rest stay.

### 5. Write Output
Write surviving parcels to CSV. Log:
- Parcels kept by district
- Parcels removed by district exclusion
- Parcels removed by address keyword (per mixed district)

## Decision Points
- **Geography is empty in BuyBox**: Skip this step entirely — the buyer wants all areas.
- **Most parcels removed**: The target geography may be too narrow. Check if the buyer missed a district or if district codes have changed.
- **Parcels with no district field**: If the district column is null or missing for some parcels, keep them and flag for manual review.
- **Mixed district has too many exclusions**: If more than half the addresses in a mixed district get excluded, consider moving it to `exclude_districts` entirely.

## Edge Cases
- District codes may be numeric strings ("3") or alphanumeric ("3A") — compare as strings, not numbers
- Address may be empty — keep the parcel (can't determine sub-area, better to include than miss a deal)
- Buyer updates target areas mid-pipeline — just update `BuyBox.target_geography` and re-run from this step

## Self-Annealing
- When a new sub-area is discovered within a mixed district, add the address keywords to the mixed district's exclusion list in the BuyBox.
- When district codes change (county redistricting), update the BuyBox and document the old-to-new mapping in the County record.
- Update this directive with any county-specific quirks about district boundaries.
