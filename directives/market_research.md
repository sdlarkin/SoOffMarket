# Market Research: Profitability by Exit Strategy & State Rules

This is a living document. Update it as we enter new markets and discover new patterns.

## How to Evaluate a New Market

Follow these steps when considering a new county for the pipeline.

### Step 1: Check GIS Data Availability

Search for the county's ArcGIS REST services:
- Google: `"{county name}" arcgis rest services site:*.gov OR site:*.com`
- Check for parcel layer with owner, value, and sale fields
- Check for zoning layer (needed for vacant land variant only)
- Check for utility layers (water, sewer — needed for vacant land variant only)

**GIS quality tiers** (see reference data below): Tier 1 states (TN, FL, TX, NC, VA, CO) have excellent REST APIs. Tier 3 states (NY, NJ, CT, LA, AL) are fragmented and may not be worth the effort.

If no ArcGIS REST service exists, the county cannot be added to the pipeline without significant custom work. Move on.

### Step 2: Identify State Property Tax Rules

Research the state's property tax framework:
- Does assessment reflect market value? (TX, WA, IN = yes. CA, FL homesteaded, PA = no)
- Is there a Prop 13-style freeze? (CA, OR Measure 50)
- Homestead exemption? (FL = $50K, TX = $100K)
- Assessment frequency? (annual, biennial, quadrennial, on-sale, irregular)
- Assessment ratio? (TN = 25%, OH = 35%, TX = 100%)

These determine `County.market_rules` settings. See `pipeline/market_rules.md` for the full key reference.

### Step 3: Compute Land/Improvement Ratio from Sample Data

Pull a sample of 100-200 parcels from the GIS and calculate:
- **Average land % of total value**: `land_value / total_value`
- High land % (>40%) = bad for flips (renovation adds less % ROI), good for wholesale
- Low land % (<25%) = great for flips (renovation adds proportionally more value)

This single metric quickly tells you which exit strategies work in this market.

### Step 4: Check Flip Rate and ROI from Recent Sales Data

From the sample data, identify likely flips:
- Sold twice within 18 months
- Significant price increase between sales (>30%)
- Non-owner-occupied at time of first sale

Calculate:
- **Flip rate**: % of sales that are likely flips
- **Median flip ROI**: (second sale - first sale) / first sale
- **Flip volume**: total flips per year in the county

High flip rate + high ROI = validated flip market. Low flip rate may still work for wholesale or new construction.

### Step 5: Match to Buyer BuyBoxes

Based on the market characteristics, determine which exit strategies fit:

| Market Signal | Best Strategy |
|---------------|---------------|
| Cheap R-2 land, growing suburbs | Vacant Land (land_arv) |
| Low land %, $50-200K homes, high flip rate | Fix-and-Flip (acquisition_arv) |
| High volume, low friction (no transfer tax) | Wholesale (single) |
| Strong rent-to-price ratio | BRRRR (use acquisition_arv) |

See `pipeline/workflow_variants.md` for detailed variant specifications.

### Step 6: Create County Record with Market Rules

Create a `County` record in Django with:
1. GIS layer URLs from Step 1
2. Field mappings (run `discover_gis_services.py` to auto-detect)
3. `market_rules` JSON populated from Steps 2-5
4. Entity keywords for the county (local government names, school districts)

See `pipeline/market_rules.md` for example configurations by state.

### Step 7: Run a Test Pipeline

Create a test `BuyBox` with conservative parameters and run the pipeline:
1. Verify GIS queries return data
2. Check that filters produce reasonable parcel counts (500-3000 for a county)
3. Validate comp results make sense for the market
4. Review a handful of parcels manually

If results look wrong, check `market_rules` configuration first — `assessment_reflects_market` and `comp_strategy` are the most common sources of bad output.

---

## Reference Data

The sections below contain research findings from market analysis. This data informs the evaluation process above and should be updated as we enter new markets.

## Key Finding: Best Markets by Exit Strategy

### Fix-and-Flip (Highest ROI)
**Target markets where land is cheap relative to improvements (land < 25% of total value):**
1. **Pittsburgh PA** (Allegheny Co) — 10-20% land, $80-150K acquisitions, ~80-90% ROI
2. **Baltimore MD** (Baltimore City/Co) — 15-25% land, $80-200K acquisitions
3. **Cleveland OH** (Cuyahoga Co) — 10-20% land, $50-120K acquisitions
4. **Indianapolis IN** (Marion Co) — 15-25% land, no transfer tax, annual assessment
5. **Memphis TN** (Shelby Co) — 15-25% land, strong rental demand
6. **Nashville TN** (Davidson Co) — higher price points but strong appreciation

**Avoid for flip ROI:** California (40-60% land), Seattle, NYC, DC — land dominates value, reno adds less %

### BRRRR (Best rent-to-price ratio)
Memphis TN, Birmingham AL, Indianapolis IN, Cleveland OH, Kansas City MO, Jacksonville FL

### Wholesale (Highest volume, best spreads)
Houston TX, Dallas TX, San Antonio TX, Atlanta GA, Phoenix AZ — TX has no transfer tax

### New Construction
Chattanooga TN (our existing pipeline), Nashville suburbs, Charlotte NC, Raleigh NC, Austin TX suburbs

## State-Specific Rules (stored in County.market_rules)

### Assessment Reliability

| Reliable (use for pricing) | Unreliable (comps only) |
|---|---|
| TX — annual at 100% market | CA — Prop 13 frozen at purchase |
| WA — annual at 100% | FL — Save Our Homes cap (homesteaded) |
| VA — annual at ~100% | PA — outdated, irregular reassessment |
| IN — annual at market | OR — Measure 50 frozen |
| OH — appraised = market (assessed = 35%) | MI — Prop A capped |
| TN — reliable in reappraisal years | |

### Transfer Tax Impact

| $0 (no transfer tax) | Low (<0.5%) | High (>1%) |
|---|---|---|
| TX, IN, CO | TN (0.37%), OH (0.1%), CA (0.11%) | PA (2%), NJ (0.4-1.2%), FL (0.7%) |

### GIS Data Quality (for our pipeline)

**Tier 1 (excellent ArcGIS REST):** TN, FL, TX, NC, VA, CO
**Tier 2 (good, may need work):** CA, MI, PA, MD, IN, AZ
**Tier 3 (fragmented/difficult):** NY, NJ, CT, LA, AL

## Recommended Expansion Order

1. **Phase 1:** More TN counties + Florida (same rules, best GIS)
2. **Phase 2:** Texas + Ohio (no transfer tax, annual assessment)
3. **Phase 3:** NC + GA (growth markets, good GIS)
4. **Phase 4:** Midwest value markets (IN, MI, PA)

## Pipeline Implications

- `County.market_rules.assessment_reflects_market` determines whether Step 09 (comps) is primary or supplementary pricing
- `County.market_rules.comp_strategy` branches between "land_arv" (vacant land), "acquisition_arv" (fix-flip), "single" (wholesale)
- `County.market_rules.prop_13` triggers community-median-based pricing instead of assessment-based
- `GISParcelCache` stores raw data so we don't re-query the same county
- `MarketSnapshot` stores community medians, flip rates, $/sqft benchmarks

## Self-Annealing

- When entering a new market, follow the 7-step evaluation process above and update the reference data sections with findings.
- If a market underperforms expectations, revisit the land/improvement ratio and flip rate analysis — the initial sample may have been unrepresentative.
- Update the GIS Data Quality tiers as we discover new county GIS services (some Tier 2/3 states have individual counties with excellent data).
- When state property tax laws change, update both the reference tables here and the affected `County.market_rules` records.
