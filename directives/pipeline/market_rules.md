# Market Rules: County-Specific Pipeline Configuration

## Purpose

The `County.market_rules` JSONField stores state/county-specific rules that change how the pipeline interprets data. Property tax law, assessment practices, and disclosure requirements vary dramatically between states. These rules let the pipeline adapt automatically rather than hard-coding assumptions.

Every pipeline script that touches pricing, comps, or scoring should read `county.market_rules` and branch accordingly.

## Full Key Reference

| Key | Type | Description |
|-----|------|-------------|
| `prop_13` | bool | CA Prop 13 — assessment frozen at purchase price, max 2%/yr increase. Assessment does NOT reflect market value. When true, scripts must ignore appraised_value for pricing and rely on comps or community medians instead. |
| `assessment_reflects_market` | bool | Whether assessed value tracks market value. True for TX, WA, VA, IN, TN (in reappraisal years). False for CA, FL (homesteaded), PA, OR. When false, appraised_value cannot be used as a pricing filter. |
| `reassessment_frequency` | str | How often the county reassesses property values. Values: `"annual"`, `"biennial"`, `"quadrennial"`, `"on_sale"`, `"irregular"`. Affects how stale the assessed values might be. |
| `homestead_exempt` | bool | Whether the state has a homestead exemption that affects tax burden. FL ($50K), TX ($100K). Affects investment analysis — homesteaded properties have artificially low assessments and tax bills. |
| `homestead_exemption_amount` | int | Dollar amount exempt from property tax under homestead. E.g., 50000 for FL, 100000 for TX. Used in tax burden calculations for investment analysis. |
| `transfer_tax_rate` | float | Transfer/documentary stamp tax as a decimal. 0.007 = 0.7%. TX and IN = 0.0. Affects closing cost estimates and wholesale assignment fee calculations. |
| `disclosure_state` | bool | Whether sellers must disclose known defects. FL and GA are caveat emptor (more off-market opportunity — sellers less afraid of disclosure liability). Affects marketing strategy, not pipeline logic directly. |
| `comp_strategy` | str | Which comp approach the pipeline uses. Values: `"land_arv"` (vacant land pipeline — land comps + ARV comps), `"acquisition_arv"` (fix-flip — acquisition comps + ARV comps), `"single"` (wholesale — just market value comps). This is the primary branching key for `generate_comps.py`. |
| `flip_indicators` | list | Which data signals indicate distress in this market. Used by filter and scoring scripts to identify motivated sellers. Examples: `["non_owner_occupied", "long_ownership", "low_ppsf_vs_community", "low_impr_ratio", "building_value_zero"]` |
| `assessment_ratio` | float | Multiplier to convert assessed value to estimated market value. E.g., 0.25 for TN (assessed = 25% of appraised), 0.35 for OH (assessed = 35% of appraised). When present, scripts can compute `market_estimate = assessed_value / assessment_ratio`. |
| `notes` | str | Free-form context about this market. Useful for edge cases, quirks, or reminders. Not read by scripts — purely for agent/human reference. |

## How Scripts Use Market Rules

### generate_comps.py

The `comp_strategy` key is the primary branch point:

```python
strategy = county.market_rules.get('comp_strategy', 'land_arv')

if strategy == 'land_arv':
    # Vacant land pipeline: find land comps (building_value=0) + ARV comps (what built product sells for)
    run_land_comps(parcel)
    run_arv_comps(parcel)
elif strategy == 'acquisition_arv':
    # Fix-flip: find acquisition comps (distressed sales) + ARV comps (renovated sales)
    run_acquisition_comps(parcel)
    run_arv_comps(parcel)
elif strategy == 'single':
    # Wholesale: just find market value comps
    run_market_comps(parcel)
```

### Filter scripts (Steps 04-08)

The `assessment_reflects_market` key determines whether appraised_value can be used for filtering:

```python
if county.market_rules.get('assessment_reflects_market', True):
    # Safe to use appraised_value as a price filter
    parcels = parcels.filter(total_value__lte=buybox.max_price)
else:
    # Cannot trust assessment — skip value-based filtering, rely on comps later
    pass
```

When `prop_13` is true, the pipeline uses community medians from `MarketSnapshot` instead of individual parcel assessments.

### Scoring scripts (Step 10)

The `flip_indicators` list tells the scoring script which signals to weight:

```python
indicators = county.market_rules.get('flip_indicators', [])
score = 0
if 'non_owner_occupied' in indicators and not parcel.owner_occupied:
    score += 2
if 'long_ownership' in indicators and parcel.ownership_years > 10:
    score += 2
if 'low_ppsf_vs_community' in indicators:
    # Compare parcel $/sqft to community median
    ...
```

## Example Configurations

### Tennessee (Hamilton County) — Vacant Land

```json
{
    "prop_13": false,
    "assessment_reflects_market": true,
    "reassessment_frequency": "quadrennial",
    "homestead_exempt": false,
    "homestead_exemption_amount": 0,
    "transfer_tax_rate": 0.0037,
    "disclosure_state": true,
    "comp_strategy": "land_arv",
    "flip_indicators": ["building_value_zero"],
    "assessment_ratio": 0.25,
    "notes": "TN reassesses every 4 years. Assessed = 25% of appraised. Hamilton last reappraisal 2021, next 2025. Appraised value is reliable in reappraisal years."
}
```

### California (Los Angeles County) — Fix-and-Flip with Prop 13

```json
{
    "prop_13": true,
    "assessment_reflects_market": false,
    "reassessment_frequency": "on_sale",
    "homestead_exempt": false,
    "homestead_exemption_amount": 0,
    "transfer_tax_rate": 0.0011,
    "disclosure_state": true,
    "comp_strategy": "acquisition_arv",
    "flip_indicators": ["non_owner_occupied", "long_ownership", "low_ppsf_vs_community"],
    "assessment_ratio": null,
    "notes": "Prop 13 means assessed value is frozen at purchase price + max 2%/yr. A house bought in 1990 for $200K may be assessed at ~$280K but worth $800K. NEVER use assessment for pricing. Always use comps."
}
```

### Texas (Harris County) — Fix-and-Flip with Reliable Assessment

```json
{
    "prop_13": false,
    "assessment_reflects_market": true,
    "reassessment_frequency": "annual",
    "homestead_exempt": true,
    "homestead_exemption_amount": 100000,
    "transfer_tax_rate": 0.0,
    "disclosure_state": true,
    "comp_strategy": "acquisition_arv",
    "flip_indicators": ["non_owner_occupied", "long_ownership", "low_ppsf_vs_community", "low_impr_ratio"],
    "assessment_ratio": 1.0,
    "notes": "TX assesses annually at 100% market value. No transfer tax. $100K homestead exemption means homesteaded properties have lower effective tax. Great flip market."
}
```

### Florida (Duval County) — Fix-and-Flip with Save Our Homes

```json
{
    "prop_13": false,
    "assessment_reflects_market": false,
    "reassessment_frequency": "annual",
    "homestead_exempt": true,
    "homestead_exemption_amount": 50000,
    "transfer_tax_rate": 0.007,
    "disclosure_state": false,
    "comp_strategy": "acquisition_arv",
    "flip_indicators": ["non_owner_occupied", "long_ownership", "low_ppsf_vs_community"],
    "assessment_ratio": null,
    "notes": "FL Save Our Homes caps assessment increases at 3%/yr for homesteaded properties. Non-homesteaded assessed at market. Caveat emptor state — no seller disclosure required. High transfer tax (0.7%)."
}
```

## Setting Up Market Rules for a New County

1. **Research state property tax rules**: Search for "{state} property tax assessment rules". Determine if the state has Prop 13-style caps, homestead exemptions, or other quirks.
2. **Check assessment frequency**: Search for "{county} reassessment schedule". Annual, biennial, quadrennial, on-sale, or irregular?
3. **Determine assessment reliability**: If the state reassesses annually at 100% market, `assessment_reflects_market` = true. If there are caps or freezes, set to false.
4. **Look up transfer tax**: Search for "{state} transfer tax rate real estate". Record as decimal.
5. **Check disclosure laws**: Search for "{state} seller disclosure requirements real estate". Caveat emptor states (FL, GA) = false.
6. **Decide comp strategy**: Based on the buyer's exit strategy and market characteristics. See `workflow_variants.md`.
7. **Identify flip indicators**: Which signals are meaningful in this market? Non-owner-occupied is almost always relevant. Long ownership matters more in appreciation markets.
8. **Calculate assessment ratio**: If the state assesses at a fraction of market value (TN = 25%, OH = 35%), record the ratio so scripts can reverse-engineer market estimates.
9. **Write notes**: Document anything unusual — last reappraisal year, upcoming changes, local quirks.
10. **Populate the County record**: Set `market_rules` JSON via Django admin or a script.

## Self-Annealing

- If a pipeline run produces bad pricing in a new market, check whether `assessment_reflects_market` is set correctly. This is the most common misconfiguration.
- If comps seem irrelevant, verify `comp_strategy` matches the buyer's exit strategy.
- If a state changes its property tax rules (new homestead exemption, reassessment schedule change), update the affected County records and note the change date.
- When entering a new state for the first time, document findings in `market_research.md` for future reference.
