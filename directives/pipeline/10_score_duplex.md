# Step 10: Score Duplex Viability

**Script:** `execution/pipeline/score_duplex.py --buybox-id UUID`

## Purpose
Assess how receptive each parcel's neighborhood is to multi-family development by counting the ratio of duplexes/triplexes/quads to single-family homes nearby. A neighborhood with existing multi-family is more likely to support new duplex construction (zoning precedent, neighbor acceptance, market demand).

## Input
- `.tmp/{buyer}/{county}/step_09_comped.csv`

## Output
- `.tmp/{buyer}/{county}/step_10_scored.csv`
- Adds columns: `duplex_score`, `duplex_grade`, `nearby_sfr_count`, `nearby_multi_count`

## Process

### 1. Check if Scoring is Enabled
Read `BuyBox.duplex_scoring_enabled`. If False, skip this step — copy step_09 CSV to step_10 CSV unchanged and log that duplex scoring was skipped.

### 2. Query Nearby Residential Properties
For each target parcel, query the parcel layer for all residential properties within 0.25 miles (1,320 feet):
```
POST {county.parcel_layer_url}/query
geometry: {parcel centroid as point}
geometryType: esriGeometryPoint
spatialRel: esriSpatialRelIntersects
distance: 1320
units: esriSRUnit_Foot
where: {building_value} > 0
```

### 3. Use Efficient Counting
Instead of fetching all records and counting locally, use ArcGIS `groupByFieldsForStatistics`:
```
groupByFieldsForStatistics: {land_use_field}
outStatistics: [{"statisticType": "count", "onStatisticField": "{parcel_id_field}", "outStatisticFieldName": "cnt"}]
```
This returns a single row per land use code with counts — one API call per parcel instead of potentially hundreds of records.

### 4. Compute Score and Grade
From the grouped counts:
- SFR count: records with land use code 111
- Multi-family count: records with land use codes 112, 113, 114
- `duplex_score`: multi_count / (sfr_count + multi_count) as a percentage
- `duplex_grade`:
  - **A**: >= 15% multi-family
  - **B**: 5% to 15%
  - **C**: 1% to 5%
  - **D**: 0% (no multi-family at all)

### 5. Write Output
Add scoring columns to each parcel row. Parcels where the nearby query returned 0 residential properties get grade "D" by default.

## Decision Points
- **All parcels score D**: The area may not have multi-family zoning precedent. This doesn't mean duplexes can't be built — it means the buyer should verify zoning allows it.
- **BuyBox.duplex_scoring_enabled is False**: Skip entirely. The buyer may be building SFR or has no interest in this metric.
- **Search radius of 0.25 miles**: This is a reasonable default for suburban areas. In rural areas, consider widening to 0.5 miles. In dense urban areas, 0.15 miles may be more appropriate.

## Edge Cases
- Parcels near the county border may have fewer nearby properties — the score is based on what's available, which is still valid
- Some counties don't have land use codes (LUCODE) — if the field is missing, skip this step and note it
- Mixed-use properties (e.g., retail with apartments above) may have different land use codes — these don't count toward the multi-family tally unless their code is in the target list

## Self-Annealing
- If the `groupByFieldsForStatistics` endpoint is not supported on a county's GIS, fall back to fetching records and counting locally. Update the script to detect this and switch automatically.
- If new land use codes are discovered for multi-family (e.g., 115 for 5+ units), add them to the multi-family code list and update this directive.
- If the scoring thresholds (A/B/C/D) don't feel right for a market, adjust them in the BuyBox or script config and document the reasoning.
