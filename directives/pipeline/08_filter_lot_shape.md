# Step 08: Filter by Lot Shape and Minimum Acreage

**Script:** `execution/pipeline/filter_lot_shape.py --buybox-id UUID`

## Purpose
Remove parcels that are too small or have irregular shapes that make them unbuildable. Uses the Polsby-Popper compactness score to quantify lot shape quality and `computed_acres` from Step 07 for reliable acreage filtering.

## Input
- `.tmp/{buyer}/{county}/step_07_with_acreage.csv`

## Output
- `.tmp/{buyer}/{county}/step_08_buildable.csv`
- Adds column: `compactness`

## Process

### 1. Fetch Polygon Geometry
For each parcel, fetch its polygon geometry from the GIS (or reuse cached geometry from Step 07 if available).

### 2. Compute Polsby-Popper Compactness
For each parcel polygon:
1. Compute area (A) using the shoelace formula
2. Compute perimeter (P) by summing edge lengths
3. Calculate Polsby-Popper score: `4 * pi * A / P^2`
4. Score ranges from 0 to 1: a perfect circle = 1, a long narrow strip approaches 0

A square has a score of ~0.785. Most buildable residential lots score 0.4 or higher.

### 3. Filter by Compactness
Remove parcels below `BuyBox.min_compactness` threshold. Typical values:
- **0.25**: Very permissive — keeps odd shapes, only removes extreme slivers
- **0.30**: Moderate — removes most slivers and very irregular lots
- **0.40**: Strict — only keeps roughly rectangular or square lots

### 4. Filter by Minimum Acreage
Remove parcels where `computed_acres` < `BuyBox.min_acres`. Use `computed_acres` (from Step 07), not the original GIS `CALCACRES`, because CALCACRES is unreliable (often defaults to 1.0).

### 5. Log Removed Parcels
For each removed parcel, log:
- Parcel ID, address
- Reason (compactness below threshold, or acreage below minimum)
- The actual compactness score or acreage value

This allows visual review of borderline cases.

### 6. Write Output
Write surviving parcels to CSV with the `compactness` column added.

## Decision Points
- **Threshold selection (0.25-0.40)**: Start with the BuyBox value. If too many good-looking lots are removed, lower it. If slivers are getting through, raise it.
- **Borderline parcels**: Parcels scoring 0.01-0.02 above or below the threshold are worth a visual check on the map. The agent should spot-check a few removed parcels.
- **Corner lots and L-shaped lots**: These may score lower but still be buildable. A threshold of 0.25-0.30 accommodates most of these.

## Edge Cases
- Parcels with no geometry — cannot compute compactness, remove and log
- Multi-ring polygons — use the outer ring only for compactness (holes don't affect buildability assessment)
- Very large parcels (10+ acres) with low compactness may still be subdividable — the buyer can evaluate these manually if interested

## Self-Annealing
- If the buyer reviews removed parcels and identifies lots that should have passed, lower the compactness threshold in the BuyBox and re-run.
- If slivers are getting through, raise the threshold.
- If a new shape edge case is found (e.g., flag-shaped lots with a narrow access strip), document it here and consider adding a separate check for minimum lot width.
