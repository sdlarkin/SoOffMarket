# Parcel Sourcing Pipeline — Master SOP

This is the master directive for sourcing off-market vacant land deals for a buyer. Follow these steps in order. Each step has its own directive with detailed instructions.

## Architecture

The pipeline follows the 3-layer architecture defined in `CLAUDE.md`:
- **Directives** (this folder): What to do, in what order, with what decision points
- **Orchestration** (you, the agent): Read directives, make decisions, call execution scripts
- **Execution** (`execution/pipeline/`): Deterministic Python scripts that do the work

## Workflow Variants

The pipeline adapts based on the buyer's exit strategy. The `County.market_rules.comp_strategy` field determines which variant runs:

| Strategy | comp_strategy | Description | Steps Skipped |
|----------|---------------|-------------|---------------|
| Vacant Land | `land_arv` | Find cheap land, estimate build-out ARV | None |
| Fix-and-Flip | `acquisition_arv` | Find distressed homes, estimate renovation ARV | 06, 07, 08, 11 |
| Wholesale | `single` | Find motivated sellers, estimate assignment fee | 05, 06, 07, 08, 11 |

Each variant uses the same infrastructure but different filters, comp approaches, and scoring. See `workflow_variants.md` for full details on each variant's pipeline configuration, BuyBox fields, and best markets.

Market rules (`County.market_rules`) also control how scripts interpret assessed values, handle Prop 13 states, and identify distress signals. See `market_rules.md` for the full key reference and examples.

## Caching

The pipeline caches GIS data to avoid re-querying 300K+ parcels on every run for the same county.

- **`GISParcelCache`**: Raw parcel data per county, indexed for fast querying. First run queries the GIS API; subsequent runs read from cache.
- **`MarketSnapshot`**: County-wide computed statistics (medians, $/sqft, flip rates). Has a 30-day TTL — automatically recomputed when stale.

Cache is county-level, not BuyBox-level. Multiple buyers in the same county share cached data. Pass `--refresh-cache` to force a full re-query from GIS.

See `caching.md` for the full model reference, cache lifecycle, and invalidation rules.

## Configuration

All pipeline parameters are stored in the Django database — no config files needed.

- **`County` model** (`parcels.County`): GIS layer URLs, field mappings, spatial references, entity keywords. One record per county.
- **`BuyBox` model** (`buyers.BuyBox`): Buyer's criteria — zoning, acreage, price, geography, comp search tiers, scoring flags. Links to a County via FK.

Every pipeline script takes `--buybox-id UUID` and reads all parameters from these models.

## Pipeline Steps

| Step | Directive | Script | Input | Output |
|------|-----------|--------|-------|--------|
| 01 | `01_parse_buybox.md` | Orchestration only | Buyer email/conversation | County + BuyBox records in DB |
| 02 | `02_discover_gis.md` | `discover_gis_services.py` | County name + state | County record populated with GIS URLs |
| 03 | `03_query_parcels.md` | `query_parcels.py` | BuyBox ID | `step_03_parcels_raw.csv` |
| 04 | `04_filter_entities.md` | `filter_entities.py` | Step 03 CSV | `step_04_entities_filtered.csv` |
| 05 | `05_filter_geography.md` | `filter_geography.py` | Step 04 CSV | `step_05_geo_filtered.csv` |
| 06 | `06_check_utilities.md` | `check_utilities.py` | Step 05 CSV | `step_06_with_utilities.csv` |
| 07 | `07_compute_acreage.md` | `compute_acreage.py` | Step 06 CSV | `step_07_with_acreage.csv` |
| 08 | `08_filter_lot_shape.md` | `filter_lot_shape.py` | Step 07 CSV | `step_08_buildable.csv` |
| 09 | `09_generate_comps.md` | `generate_comps.py` | Step 08 CSV | `step_09_comped.csv` |
| 10 | `10_score_duplex.md` | `score_duplex.py` | Step 09 CSV | `step_10_scored.csv` |
| 11 | `11_check_adjacency.md` | `check_adjacency.py` | Step 10 CSV | `step_11_final.csv` |
| 12 | `12_import_database.md` | `import_to_db.py` | Step 11 CSV | Parcel records in Django DB |
| 13 | `13_skip_trace.md` | `skip_trace.py` | Rated parcels from DB | Owner records with phone/email |

## File Naming Convention

All intermediate files go to: `.tmp/{buyer_slug}/{county_slug}/`

Example for Sara Holt, Hamilton County TN:
```
.tmp/sara-holt/hamilton-tn/step_03_parcels_raw.csv
.tmp/sara-holt/hamilton-tn/step_04_entities_filtered.csv
...
.tmp/sara-holt/hamilton-tn/step_11_final.csv
```

## Running the Pipeline

```bash
# Prerequisite: County and BuyBox must exist in Django DB
# Get the BuyBox UUID from Django admin or the deals API

BUYBOX_ID="your-buybox-uuid"
PYTHON="C:/Users/sdane/anaconda3/python.exe"

# Run each step
$PYTHON execution/pipeline/query_parcels.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/filter_entities.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/filter_geography.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/check_utilities.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/compute_acreage.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/filter_lot_shape.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/generate_comps.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/score_duplex.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/check_adjacency.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/import_to_db.py --buybox-id $BUYBOX_ID
$PYTHON execution/pipeline/skip_trace.py --buybox-id $BUYBOX_ID
```

Each script is idempotent — safe to re-run. Steps 9 and 13 make external API calls that cost money (GIS queries are free; Apify skip trace is ~$0.007/lookup).

## Decision Points for the Orchestrating Agent

After each step, check the output:

- **Step 03 (Query)**: If 0 parcels, filters are too narrow — widen zoning, acreage, or price. If >5000, too broad — tighten.
- **Step 04 (Entities)**: If >50% removed, review the entity keyword list — may be too aggressive.
- **Step 05 (Geography)**: If geography section is empty in BuyBox, skip this step.
- **Step 06 (Utilities)**: If no utility layers found for the county, mark all as "Unknown" and proceed.
- **Step 08 (Shape)**: Review a few removed parcels in the map viewer to verify the compactness threshold is appropriate.
- **Step 09 (Comps)**: Check a few land estimates for sanity. If they seem off, adjust the comp_search_tiers in the BuyBox.
- **Step 13 (Skip Trace)**: Only run after the buyer/agent has rated parcels yes/maybe. Estimate cost before running.

## Self-Annealing

When something breaks:
1. Read the error and stack trace
2. Fix the script or adjust the BuyBox/County config
3. Re-run the failing step (idempotent, safe to retry)
4. Update this directive or the step's directive with what you learned
5. The system is now stronger

## Testing

```bash
pytest tests/pipeline/ -v
```

Unit tests validate pure logic (compactness math, outlier removal, entity filtering, address parsing). They run without API calls or Django.
