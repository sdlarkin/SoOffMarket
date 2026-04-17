# Market Research: Profitability by Exit Strategy & State Rules

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
