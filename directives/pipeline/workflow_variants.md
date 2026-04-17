# Workflow Variants: Pipeline Configuration by Exit Strategy

## Overview

The pipeline steps are the same infrastructure, but parameters change based on the buyer's exit strategy. The `County.market_rules.comp_strategy` field determines which variant runs, and the `BuyBox` fields configure the specifics.

Three variants exist today. Each uses a different subset of pipeline steps with different parameters.

## Variant A: Vacant Land (Sara Holt Style)

**comp_strategy:** `"land_arv"`

Build new construction (duplexes, townhomes) on vacant land. Find cheap land in good locations, estimate what the built product would sell for.

### Pipeline Steps

| Step | Run? | Notes |
|------|------|-------|
| 01 Parse BuyBox | Yes | |
| 02 Discover GIS | Yes | |
| 03 Query Parcels | Yes | Filter: `BUILDVALUE=0` (vacant land) |
| 04 Filter Entities | Yes | Remove government, church, utility owners |
| 05 Filter Geography | Yes | Target specific districts/communities |
| 06 Check Utilities | Yes | Critical — land must have water/sewer access |
| 07 Compute Acreage | Yes | Verify lot meets minimum size |
| 08 Filter Lot Shape | Yes | Compactness check — lot must be buildable |
| 09 Generate Comps | Yes | Land comps (vacant sales) + ARV comps (built product sales) |
| 10 Score Duplex | Yes | Duplex friendliness grade, nearby multi-family density |
| 11 Check Adjacency | Yes | Same-owner adjacent parcels (assemblage opportunity) |
| 12 Import Database | Yes | |
| 13 Skip Trace | Yes | After buyer rates parcels |

### Key BuyBox Fields

| Field | Typical Value | Purpose |
|-------|---------------|---------|
| `min_acres` | 0.3 | Minimum lot size for duplex |
| `max_price` | 80000 | Max land acquisition price |
| `target_zoning` | ["R-2", "R-3"] | Zones allowing multi-family |
| `min_compactness` | 0.25 | Lot shape threshold |
| `comp_search_tiers` | [{0.5mi, 18mo}, {1mi, 24mo}, {2mi, 36mo}] | Expanding comp search |
| `duplex_scoring_enabled` | true | Run Step 10 |

### Comp Strategy Details

- **Land comps**: Nearby vacant land sales (`building_value=0`, recent, within radius tiers). Estimates what the raw land is worth.
- **ARV comps**: Nearby improved property sales (duplexes preferred, SFR fallback). Estimates what the finished product will sell for.
- **Deal math**: `profit = ARV - land_cost - construction_cost - closing_costs`

### Best Markets

TN, NC, FL suburbs — anywhere with cheap R-2 zoned land, growing population, and strong rental demand. Look for communities where land is 30-50% of total property value.

---

## Variant B: Fix-and-Flip (Jose Style)

**comp_strategy:** `"acquisition_arv"`

Buy distressed existing homes below market, renovate, sell at ARV. Find undervalued properties with distress signals.

### Pipeline Steps

| Step | Run? | Notes |
|------|------|-------|
| 01 Parse BuyBox | Yes | |
| 02 Discover GIS | Yes | |
| 03 Query Parcels | Yes | Filter: SFH with improvements (`BUILDVALUE>0`, land_use_code=111) |
| 04 Filter Entities | Yes | Remove government, institutional owners |
| 05 Filter Geography | Yes | Target neighborhoods with flip activity |
| 06 Check Utilities | **Skip** | Existing homes already have utilities |
| 07 Compute Acreage | **Skip** | Lot size irrelevant for existing homes |
| 08 Filter Lot Shape | **Skip** | Already built, shape doesn't matter |
| 09 Generate Comps | Yes | Acquisition comps (distressed sales) + ARV comps (renovated sales) |
| 10 Score Duplex | **Modified** | Distress scoring instead of duplex scoring |
| 11 Check Adjacency | **Skip** | Not relevant for flip strategy |
| 12 Import Database | Yes | |
| 13 Skip Trace | Yes | After buyer rates parcels |

### Key BuyBox Fields

| Field | Typical Value | Purpose |
|-------|---------------|---------|
| `max_price` | 150000 | Max acquisition price |
| `target_land_use` | ["111"] | SFH only |
| `min_sqft` | 800 | Minimum living space |
| `max_year_built` | 2000 | Older homes have more upside |
| `flip_indicators` | (from market_rules) | Distress signals to weight |
| `duplex_scoring_enabled` | false | Use distress scoring instead |

### Comp Strategy Details

- **Acquisition comps**: Nearby recent sales of similar distressed properties (non-owner-occupied, long ownership, low condition indicators). Estimates realistic purchase price.
- **ARV comps**: Nearby recent sales of renovated/move-in-ready properties (high $/sqft, recent renovation, owner-occupied). Estimates post-renovation value.
- **Deal math**: `profit = ARV - acquisition_price - renovation_cost - closing_costs - holding_costs`

### Distress Scoring

Replace duplex friendliness scoring with distress indicators:

| Signal | Points | Source |
|--------|--------|--------|
| Non-owner-occupied | +2 | `owner_occupied = false` |
| Long ownership (>10 yrs) | +2 | `sale_year` vs current year |
| Low $/sqft vs community | +2 | Parcel PPSF < 70% of community median |
| Low improvement ratio | +1 | `impr_value / total_value < 0.5` |
| High land % | +1 | `land_value / total_value > 0.4` |

### Best Markets

Pittsburgh, Baltimore, Cleveland, Indianapolis, Memphis — markets where land is <25% of total value, acquisition prices are $50-200K, and renovation adds significant percentage ROI.

---

## Variant C: Wholesale

**comp_strategy:** `"single"`

Find motivated sellers, get properties under contract, assign the contract to an investor buyer. No renovation, no construction — just arbitrage.

### Pipeline Steps

| Step | Run? | Notes |
|------|------|-------|
| 01 Parse BuyBox | Yes | |
| 02 Discover GIS | Yes | |
| 03 Query Parcels | Yes | Broad filter — any property type with motivated seller signals |
| 04 Filter Entities | Yes | Remove government, keep distressed individuals |
| 05 Filter Geography | **Optional** | Wholesaling works anywhere with volume |
| 06 Check Utilities | **Skip** | Irrelevant |
| 07 Compute Acreage | **Skip** | Irrelevant |
| 08 Filter Lot Shape | **Skip** | Irrelevant |
| 09 Generate Comps | Yes | Market value comps only (what it sells for to an investor) |
| 10 Score Duplex | **Modified** | Assignment fee scoring |
| 11 Check Adjacency | **Skip** | Irrelevant |
| 12 Import Database | Yes | |
| 13 Skip Trace | Yes | Critical — need to reach owners fast |

### Key BuyBox Fields

| Field | Typical Value | Purpose |
|-------|---------------|---------|
| `max_price` | 300000 | Wide net |
| `target_land_use` | ["111", "112", "000"] | Any residential + vacant |
| `motivated_seller_signals` | (from market_rules.flip_indicators) | What to look for |

### Comp Strategy Details

- **Market comps**: Nearby recent sales of similar properties in similar condition. Single comp set — no acquisition/ARV split needed.
- **Deal math**: `assignment_fee = estimated_market_value * 0.70 - estimated_acquisition_price`
- The 0.70 multiplier assumes the end buyer (investor) wants to buy at 70% of market value.

### Best Markets

TX (no transfer tax), GA (limited disclosure), FL (high volume) — markets with high transaction volume, low friction costs, and large pools of motivated sellers.

---

## Summary: Exit Strategy to Pipeline Configuration

| | Vacant Land | Fix-and-Flip | Wholesale |
|---|---|---|---|
| **comp_strategy** | `land_arv` | `acquisition_arv` | `single` |
| **Query filter** | BUILDVALUE=0 | BUILDVALUE>0, SFH | Broad |
| **Steps skipped** | None | 06, 07, 08, 11 | 05, 06, 07, 08, 11 |
| **Comp types** | Land + ARV | Acquisition + ARV | Market only |
| **Scoring** | Duplex friendliness | Distress score | Assignment fee potential |
| **Skip trace timing** | After rating | After rating | Immediately (speed matters) |
| **Key metric** | ARV - land - build | ARV - acquisition - reno | Market value * 0.70 - acquisition |

## Adding a New Variant

If a buyer has a different exit strategy (BRRRR, subject-to, lease option):
1. Define which pipeline steps apply
2. Decide on comp strategy (can reuse existing or add a new one)
3. Define scoring criteria
4. Add a new `comp_strategy` value to `market_rules`
5. Update `generate_comps.py` to handle the new strategy
6. Update this directive with the new variant

## Self-Annealing

- If a variant's comp results don't make sense, verify the `comp_strategy` in `County.market_rules` matches the buyer's actual exit strategy.
- If Steps are being skipped that shouldn't be (or vice versa), check the BuyBox configuration against the variant table above.
- When a buyer's strategy doesn't cleanly fit one variant, default to `acquisition_arv` (most flexible) and customize the BuyBox fields.
- Document any new variant patterns that emerge from real buyer interactions.
