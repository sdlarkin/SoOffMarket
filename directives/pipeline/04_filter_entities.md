# Step 04: Filter Out Non-Seller Entities

**Script:** `execution/pipeline/filter_entities.py --buybox-id UUID`

## Purpose
Remove parcels owned by entities that will never sell to an investor — government agencies, HOAs, churches, schools, and other institutional owners. Optionally separate out LLCs and businesses for review (they could be motivated sellers in some cases).

## Input
- `.tmp/{buyer}/{county}/step_03_parcels_raw.csv`

## Output
- `.tmp/{buyer}/{county}/step_04_entities_filtered.csv`

## Process

### 1. Load Entity Keywords
Two sources of keywords are combined:
- **Universal keywords** from `pipeline_common.UNIVERSAL_ENTITY_KEYWORDS` — covers common patterns across all counties (e.g., "COUNTY", "CITY OF", "STATE OF", "CHURCH", "BAPTIST", "METHODIST", "HOA", "HOMEOWNERS", "SCHOOL", "UNIVERSITY", "HOUSING AUTHORITY", "UTILITY DISTRICT")
- **County-specific keywords** from `County.entity_keywords` — covers local entities unique to that county (e.g., "HAMILTON COUNTY", "EPB", "TVA" for Hamilton County TN)

### 2. Check Each Parcel's Owner
For each parcel, check if the owner name contains any keyword (case-insensitive substring match). If it matches, flag the parcel for removal.

### 3. Handle LLCs and Business Entities
LLCs and business entities are a gray area:
- Some are investors who may sell
- Some are holding companies for individuals
- Flag them separately: mark as `entity_type = "LLC"` but do not remove by default
- The agent or buyer can review LLC-owned parcels later

### 4. Remove Flagged Parcels
Write the surviving parcels to the output CSV. Log the count of removed parcels by category (government, religious, HOA, other institutional).

### 5. Write Removal Summary
Log to console:
- Total input parcels
- Removed by category (government: N, religious: N, HOA: N, institutional: N)
- LLCs kept but flagged: N
- Total output parcels

## Decision Points
- **>50% of parcels removed**: The keyword list may be too aggressive. Review the removed parcels — are legitimate individual owners being caught? Check for overly broad keywords (e.g., "TRUST" catches family trusts that might sell).
- **LLC handling**: If the buyer explicitly wants LLC-owned parcels excluded, pass `--exclude-llcs` flag. Otherwise keep them flagged but included.
- **Trust handling**: Family trusts (e.g., "SMITH FAMILY TRUST") are often individuals. Don't filter these by default — only filter institutional trusts ("BANK TRUST", "NATIONAL TRUST").

## Edge Cases
- Owner name is blank or null — keep the parcel (missing data, not an entity)
- Owner name is all numbers or codes — keep and flag for manual review
- Same entity owns dozens of parcels — this is expected for government entities, confirms correct filtering

## Self-Annealing
- When a new entity type is discovered that should be filtered (e.g., a local land bank), add the keyword to `County.entity_keywords` in the database.
- When a legitimate seller is accidentally filtered, narrow the keyword that caught them (e.g., change "TRUST" to "BANK TRUST") and update `pipeline_common.UNIVERSAL_ENTITY_KEYWORDS`.
- Update this directive with any new entity categories encountered.
