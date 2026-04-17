# Caching: GISParcelCache and MarketSnapshot

## Purpose

Avoid re-querying 300K+ parcels from the county GIS every time we run the pipeline for the same county. GIS queries are free but slow — a full Hamilton County query takes 15-20 minutes and thousands of API calls. Caching makes subsequent pipeline runs start in seconds instead of minutes.

Two models handle this:
- **`GISParcelCache`**: raw parcel data per county, one record per parcel
- **`MarketSnapshot`**: county-wide computed statistics (medians, benchmarks, flip rates)

## GISParcelCache Model

Stores raw parcel data from GIS queries, keyed by `county` + `parcel_id` (unique together).

**Parsed fields** (indexed for fast querying):
| Field | Type | Index | Use |
|-------|------|-------|-----|
| `address` | CharField | yes | Display, deduplication |
| `community` | CharField | yes | Community-level comp analysis |
| `total_value` | IntegerField | yes | Price filtering, comp PPA bounds |
| `land_value` | IntegerField | — | Land/improvement ratio |
| `impr_value` | IntegerField | — | Improvement ratio, distress signals |
| `sqft` | IntegerField | — | $/sqft calculations |
| `bedrooms` | IntegerField | — | Comp matching |
| `year_built` | IntegerField | — | Age-based filtering |
| `acreage` | FloatField | — | Acreage filtering |
| `owner_occupied` | BooleanField | yes | Distress indicator |
| `sale_year` | IntegerField | yes | Comp recency filtering |
| `land_use_code` | CharField | yes | Property type filtering (111=SFR, 112=duplex, etc.) |

**Geometry fields**: `lat`, `lon`, `geometry_rings` (polygon rings for spatial calculations).

**Raw data**: `raw_data` JSONField stores all original GIS fields, so nothing is lost if we need to re-parse.

**Compound indexes** (for common pipeline queries):
- `(county, land_use_code, total_value)` — filter by property type and price
- `(county, community, total_value)` — community-level analysis
- `(county, sale_year)` — recent sales for comp analysis

**Computed properties** (not stored, calculated on access):
- `impr_ratio`: improvement value / total value
- `ppsf`: total value / sqft

## MarketSnapshot Model

Stores county-wide computed statistics. One snapshot per computation, linked to a County via FK. Ordered by `computed_at` descending — latest snapshot is always first.

**County-wide stats:**
| Field | Description |
|-------|-------------|
| `parcel_count` | Total parcels in the cache |
| `median_total_value` | County-wide median total value |
| `median_ppsf` | Median price per sqft |
| `median_land_value` | Median land value |
| `median_impr_ratio` | Median improvement ratio |
| `ppa_floor` | 25th percentile $/acre (for land comp outlier filtering) |
| `ppa_cap` | 3x median $/acre (for land comp outlier filtering) |

**Community-level stats** (`community_stats` JSON):
```json
{
    "OOLTEWAH": {"median_total": 285000, "median_ppsf": 145, "p75_total": 350000, "count": 1240},
    "COLLEGEDALE": {"median_total": 310000, "median_ppsf": 160, "p75_total": 380000, "count": 890}
}
```

**Flip analysis data:**
| Field | Description |
|-------|-------------|
| `flip_rate` | % of recent sales that are likely flips |
| `flip_non_owner_occ_rate` | % of flips by non-owner-occupants |
| `flip_median_ppsf` | Median $/sqft for flipped properties |

**Yearly trends** (`yearly_trends` JSON):
```json
{
    "2023": {"flip_pct": 8.2, "median_total": 275000, "median_ppsf": 140},
    "2024": {"flip_pct": 9.1, "median_total": 290000, "median_ppsf": 148}
}
```

**Staleness**: The `is_stale` property returns `True` if the snapshot is older than 30 days.

## Cache Lifecycle

### 1. First Pipeline Run (Cold Cache)

When a pipeline runs for a county with no cached data:
1. `query_parcels.py` queries the GIS API for all matching parcels
2. Each parcel is stored in `GISParcelCache` with parsed fields extracted from `raw_data`
3. After all parcels are cached, county-wide stats are computed and stored as a `MarketSnapshot`
4. Subsequent pipeline steps read from `GISParcelCache` instead of the GIS API

### 2. Subsequent Runs (Warm Cache)

When a pipeline runs for a county that already has cached data:
1. `query_parcels.py` checks for existing cache entries
2. If cache exists, reads from `GISParcelCache` — no GIS API calls
3. Checks if the latest `MarketSnapshot` is stale (>30 days)
4. If stale, recomputes the snapshot from cached parcels
5. Pipeline continues with cached data

### 3. Cache Refresh

To force a full re-query from GIS:
- Pass `--refresh-cache` flag to `query_parcels.py`
- Or run a dedicated refresh script
- This deletes existing cache entries for the county and re-queries everything

## How Pipeline Scripts Should Check Cache

```python
from parcels.models import GISParcelCache, MarketSnapshot

# Check for cached parcels
cached = GISParcelCache.objects.filter(county=county, land_use_code='111')
if cached.exists():
    # Use cached data — no GIS API call needed
    parcels = cached.values('parcel_id', 'address', 'total_value', 'lat', 'lon')
else:
    # Query GIS and populate cache
    raw_parcels = query_gis_layer(county.parcel_layer_url, where_clause)
    for raw in raw_parcels:
        GISParcelCache.objects.update_or_create(
            county=county,
            parcel_id=raw['parcel_id'],
            defaults={'raw_data': raw, 'total_value': raw.get('TOTALVALUE'), ...}
        )
```

### MarketSnapshot Usage

```python
# Get latest snapshot for comp analysis
try:
    snapshot = MarketSnapshot.objects.filter(county=county).latest()
    if snapshot.is_stale:
        snapshot = recompute_market_snapshot(county)
except MarketSnapshot.DoesNotExist:
    snapshot = recompute_market_snapshot(county)

# Use snapshot data
ppa_floor = snapshot.ppa_floor          # 25th percentile $/acre — outlier floor
ppa_cap = snapshot.ppa_cap              # 3x median $/acre — outlier cap
community_median = snapshot.community_stats.get(parcel.community, {}).get('median_total')
flip_rate = snapshot.flip_rate          # Market-wide flip rate benchmark
```

## When to Invalidate Cache

| Trigger | Action | Why |
|---------|--------|-----|
| County reassessment year | Full refresh (`--refresh-cache`) | All assessed values change |
| Major market shift | Recompute `MarketSnapshot` only | Medians and benchmarks shift |
| New GIS fields discovered | Full refresh | Need to re-parse raw data into new fields |
| Manual admin action | Delete via Django admin | Troubleshooting, data corruption |
| 30+ days since last snapshot | Automatic (scripts check `is_stale`) | Keep benchmarks current |

## Decision Points

- **Cache size**: A county with 300K parcels = ~300K rows in `GISParcelCache`. This is fine for PostgreSQL. If using SQLite for dev, consider filtering by land_use_code to reduce volume.
- **Partial cache**: If a previous run was interrupted, the cache may be incomplete. The `--refresh-cache` flag handles this by wiping and re-querying.
- **Multiple BuyBoxes, same county**: Cache is county-level, not BuyBox-level. Different BuyBoxes for the same county share the same cache. This is intentional — the raw data is the same, only the filters differ.

## Self-Annealing

- If a pipeline step finds 0 parcels but the cache has data, check the filter criteria — the cache may have the data under different field values.
- If `MarketSnapshot` medians look wrong, inspect the underlying `GISParcelCache` data for outliers or data quality issues (e.g., $0 values, null fields).
- If cache refresh is slow, check the GIS API rate limits and batch size (`max_records_per_query` on the County model).
- Update this directive if new parsed fields are added to `GISParcelCache` — any new indexed field should be documented here.
