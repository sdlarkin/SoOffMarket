# Step 01: Parse Buyer's Buy Box

**Type:** Orchestration only (no script — the agent does this)

## Purpose
Extract structured criteria from a buyer's email, conversation, or intake form and create the corresponding `Buyer`, `BuyBox`, and `County` records in the Django database.

## Input
A buyer's communication describing what they want to buy. Example:

> I'm Buying Land Here: Chattanooga, Ooltewah, Collegedale
> - 0.3+ acres, Up to $80,000, Must have city water
> - Zoned R2 OR strong R2 potential
> - Vacant or unused land, Off-market, Flat / easy to build

## Output
Three Django records:
1. `Buyer` — name, slug, email, location
2. `County` — GIS configuration (may already exist from prior searches)
3. `BuyBox` — linked to Buyer + County, with all pipeline parameters populated

## Process

### 1. Identify the Buyer
- Extract: name, email, phone, company (if any)
- Create `Buyer` record (or find existing by email)
- Slug auto-generates from name

### 2. Identify the County
- Extract target location(s) from the email
- Determine which county (Google "Chattanooga TN county" → Hamilton County)
- Check if a `County` record already exists (by slug or name+state)
- If not, create one and proceed to Step 02 (Discover GIS) to populate it

### 3. Build the BuyBox
Map the buyer's natural language criteria to structured fields:

| Buyer Says | BuyBox Field | Value |
|------------|-------------|-------|
| "0.3+ acres" | `min_acres` | 0.3 |
| "Up to $80,000" | `max_price` | 80000 |
| "Zoned R2" | `target_zoning` | ["R-2"] |
| "Chattanooga, Ooltewah, Collegedale" | `target_geography` | {target_districts: [...]} |
| "Must have city water" | `strategy_notes` + pipeline will check utilities |
| "Flat / easy to build" | `min_compactness` | 0.25-0.40 |
| "Vacant or unused land" | Implied: building_value = 0 |
| "Cash buyer" | `is_cash_buyer` | "Yes" |

### 4. Geography Mapping
The geography section requires county-specific knowledge (district codes). If the County record is new:
- Run Step 02 (Discover GIS) first to populate GIS URLs
- Query the parcel layer for distinct `DISTRICT` values
- Cross-reference districts with the buyer's target cities
- Populate `target_geography` with district codes

### 5. Set Defaults for Pipeline Parameters
If the buyer doesn't specify:
- `min_compactness`: default 0.25
- `comp_search_tiers`: default [0.5mi/18mo, 1mi/2yr, 2mi/3yr]
- `duplex_scoring_enabled`: default True (unless buyer isn't doing multi-family)

## Decision Points
- **Ambiguous location**: "Chattanooga area" — ask buyer to specify which areas/cities
- **No zoning preference**: Search all residential zones, not just R-2
- **No price limit**: Set max_price very high ($500K) rather than null
- **Multiple counties**: Create one BuyBox per county, each linked to its own County record

## Edge Cases
- Buyer wants multiple property types (land + existing homes) — create separate BuyBoxes
- Buyer's target area spans multiple counties — one BuyBox per county
- Buyer updates criteria later — update the BuyBox, re-run pipeline from Step 03
