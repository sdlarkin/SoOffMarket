# Step 09: Generate Comparable Sales

**Script:** `execution/pipeline/generate_comps.py --buybox-id UUID`

## Purpose
For each target parcel, find nearby recent sales to estimate land value and after-repair value (ARV). This is the most API-intensive step in the pipeline — it queries the county GIS for comparable sales around every parcel. The output drives the deal analysis: what the land is worth, and what the finished product would sell for.

## Input
- `.tmp/{buyer}/{county}/step_08_buildable.csv`

## Output
- `.tmp/{buyer}/{county}/step_09_comped.csv`
- Adds 14+ columns including: `land_comp_count`, `land_comp_median_ppa`, `land_est_value`, `land_comps_json`, `arv_comp_count`, `arv_comp_median`, `arv_comps_json`, and more

## Process

### 1. Land Comps — Find Nearby Vacant Land Sales
For each target parcel, search for comparable vacant land sales:

**Query criteria:**
- `building_value = 0` (vacant land)
- Sold within a recent time window
- Within a search radius of the target parcel
- Sale price > 0

**Search tier strategy** (from `BuyBox.comp_search_tiers`):
Search expands outward in tiers until enough comps are found:
```json
[
  {"radius_miles": 0.5, "months": 18, "min_comps": 3},
  {"radius_miles": 1.0, "months": 24, "min_comps": 3},
  {"radius_miles": 2.0, "months": 36, "min_comps": 3}
]
```
Start with the tightest radius/timeframe. If fewer than `min_comps` found, widen to the next tier. Stop as soon as the minimum is met.

### 2. Land Comps — Filter Outliers
Apply dynamic price-per-acre (PPA) bounds:
- **Floor**: 25th percentile of all land sales PPA in the county
- **Cap**: 3x the county median PPA
- Remove comps outside these bounds — they are likely data errors (e.g., $1 family transfers, or inflated assemblage deals)

### 3. Land Comps — Fix Fake Acreage on Comps
Comp parcels also suffer from the CALCACRES = 1.0 problem. For each comp:
- If `CALCACRES` = 1.0 exactly, fetch the polygon geometry and compute real acreage (same shoelace method as Step 07)
- Recalculate PPA using the corrected acreage
- This prevents wildly incorrect PPA values from contaminating the estimate

### 4. Land Comps — Compute Estimate
From the filtered comps:
- `land_comp_count`: number of valid comps
- `land_comp_median_ppa`: median price per acre
- `land_est_value`: median PPA * target parcel's computed_acres
- `land_comps_json`: full details of each comp (for review)

### 5. ARV Comps — Find Nearby Improved Sales
For each target parcel, search for recent sales of improved properties with target land use codes:
- **Primary**: 112 (duplex), 113 (triplex), 114 (quad) — multi-family, which is what the buyer plans to build
- **Fallback**: 111 (SFR) — if fewer than 3 multi-family comps found nearby, fall back to single-family residential

**Query criteria:**
- `building_value > 0` (improved property)
- Land use code in target list
- Sold recently (within 24 months)
- Within 1 mile of target parcel
- Sale price > 0

### 6. ARV Comps — Compute Estimate
- `arv_comp_count`: number of valid ARV comps
- `arv_comp_median`: median sale price of ARV comps
- `arv_comps_json`: full details
- `arv_comp_type`: "multi-family" or "SFR fallback"

### 7. Write Output
Add all comp columns to each parcel row. Parcels with 0 comps found still get written — they just have null comp values. The agent or buyer can decide whether to keep them.

## Decision Points
- **0 land comps found at widest tier**: The area may have very few vacant land sales. Consider widening the search further, or accept that the land value is unestimable for this parcel.
- **Land estimates seem too high or too low**: Check the outlier bounds. If the county median PPA is skewed, adjust the floor/cap logic.
- **ARV fallback to SFR**: If the buyer is building duplexes but there are no duplex sales nearby, SFR comps provide a conservative floor. Note this in the output.
- **API rate limiting**: This step makes many queries. If the GIS server starts returning errors or slowdowns, increase the delay between requests.

## Edge Cases
- Comp parcels may have been subdivided or merged since sale — the acreage at time of sale may differ from current GIS acreage
- Some sales are recorded at $0 or $1 (tax transfers, family transfers) — filter these out
- Parcels at the edge of the county may find comps in an adjacent county's jurisdiction — these are still valid comps but won't appear in the same GIS layer

## Self-Annealing
- If outlier bounds are removing too many comps, adjust the percentile thresholds and document the county-specific PPA distribution.
- If the fake-acreage fix is slow (geometry fetch for every comp), consider caching geometry data from earlier steps.
- If a new land use code appears that should be included in ARV comps, add it to the target list and update this directive.
- Track API call counts per run. If a run exceeds reasonable limits (>5000 queries), optimize the batching strategy.
