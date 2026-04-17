"""
San Diego County SFH Distressed Property Finder - Age + Low Improvement Ratio Strategy

Queries SANDAG ArcGIS REST API for single-family homes that show signs of deferred
maintenance based on:
  - Low improvement-to-total value ratio (building worth less than land)
  - Older construction (pre-1985)
  - Below-average price per sqft within their community
  - Outdated layouts (low bath:bedroom ratio, small living area vs lot)

Endpoint: https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query
"""

import csv
import json
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = TMP_DIR / "sd_filter_test_age_ratio.csv"

API_URL = "https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query"
MAX_RECORDS = 2000

# Fields we need from the API
OUT_FIELDS = [
    "apn",
    "situs_addr", "situs_zip",
    "situs_community",       # jurisdiction / community name
    "nucleus_use_cd",
    "asr_land", "asr_impr", "asr_total",
    "total_lvg_area", "total_usable_sq_ftg",
    "bedrooms", "baths",
    "year_effective",
    "lot_sqft",
    "owner_name",
]

# Target communities
COMMUNITIES = [
    "El Cajon",
    "Spring Valley",
    "Lemon Grove",
    "National City",
    "Escondido",
    "Lakeside",
    "San Diego",
    "La Mesa",
]


def build_where_clause(community: str) -> str:
    """
    Build WHERE clause for SFH in a community matching base criteria.

    year_effective is 2-digit: 70-85 means 1970-1985
    We want older homes (pre-1985) that are under $600K total assessed value.
    """
    parts = [
        "nucleus_use_cd = '111'",         # SFH
        "asr_total > 0",                   # has value
        "asr_total <= 600000",             # under $600K
        "asr_impr > 0",                    # has improvement value (not vacant)
        "asr_land > 0",                    # has land value
        "total_lvg_area >= 1000",          # 1000+ sqft
        "bedrooms >= '003'",               # 3+ bedrooms (string field)
        # Year built 1970-1985 (2-digit: 70-85)
        "year_effective >= '70'",
        "year_effective <= '85'",
        f"situs_community = '{community}'",
    ]
    return " AND ".join(parts)


def query_community(community: str) -> list[dict]:
    """Query all SFH in a community matching criteria, with pagination."""
    where = build_where_clause(community)
    all_features = []
    offset = 0

    while True:
        data = {
            "where": where,
            "outFields": ",".join(OUT_FIELDS),
            "returnGeometry": "false",
            "resultOffset": str(offset),
            "resultRecordCount": str(MAX_RECORDS),
            "f": "json",
        }
        try:
            r = requests.post(API_URL, data=data, timeout=60)
            r.raise_for_status()
            result = r.json()
        except Exception as e:
            print(f"    ERROR querying {community} (offset {offset}): {e}")
            break

        if result.get("error"):
            print(f"    API error for {community}: {result['error'].get('message', result['error'])}")
            break

        features = result.get("features", [])
        all_features.extend([f["attributes"] for f in features])

        # Check if we got a full page (need to paginate)
        if len(features) < MAX_RECORDS:
            break
        offset += MAX_RECORDS
        time.sleep(0.3)

    return all_features


def compute_metrics(parcels: list[dict]) -> list[dict]:
    """Add computed metrics to each parcel."""
    enriched = []
    for p in parcels:
        asr_total = p.get("asr_total") or 0
        asr_impr = p.get("asr_impr") or 0
        asr_land = p.get("asr_land") or 0
        sqft = p.get("total_lvg_area") or 0
        lot_sqft = p.get("lot_sqft") or 0
        beds = p.get("bedrooms") or 0
        baths = p.get("baths") or 0
        year_eff = p.get("year_effective") or 0

        # Skip if missing critical data
        if asr_total <= 0 or sqft <= 0:
            continue

        # Improvement ratio: what fraction of total value is the building?
        impr_ratio = asr_impr / asr_total if asr_total > 0 else 0

        # Price per square foot
        price_per_sqft = asr_total / sqft if sqft > 0 else 0

        # Bath to bedroom ratio (low = outdated layout)
        bath_bed_ratio = baths / beds if beds > 0 else 0

        # Living area to lot ratio (low = expansion potential)
        lvg_lot_ratio = sqft / lot_sqft if lot_sqft > 0 else 0

        # Convert 2-digit year to 4-digit
        if year_eff >= 70:
            year_built = 1900 + year_eff
        else:
            year_built = 2000 + year_eff

        p["impr_ratio"] = round(impr_ratio, 3)
        p["price_per_sqft"] = round(price_per_sqft, 2)
        p["bath_bed_ratio"] = round(bath_bed_ratio, 2)
        p["lvg_lot_ratio"] = round(lvg_lot_ratio, 3)
        p["year_built"] = year_built

        enriched.append(p)

    return enriched


def score_parcels(parcels: list[dict]) -> list[dict]:
    """
    Score parcels for flip potential. Higher score = better candidate.

    Scoring factors (0-100 total):
    1. Improvement ratio (0-30): Lower ratio = higher score
       - < 30% = 30pts, 30-40% = 20pts, 40-50% = 10pts
    2. Price per sqft vs community avg (0-25): Lower relative to avg = higher
    3. Age factor (0-15): Older = more likely needs rehab
    4. Bath/bed ratio (0-15): Lower = more outdated layout
    5. Living/lot ratio (0-15): Lower = more expansion potential
    """
    if not parcels:
        return []

    # Compute community-level averages for relative scoring
    community_stats = {}
    for p in parcels:
        comm = p.get("situs_community", "Unknown")
        if comm not in community_stats:
            community_stats[comm] = {"prices_sqft": [], "impr_ratios": []}
        community_stats[comm]["prices_sqft"].append(p["price_per_sqft"])
        community_stats[comm]["impr_ratios"].append(p["impr_ratio"])

    for comm, stats in community_stats.items():
        stats["avg_price_sqft"] = sum(stats["prices_sqft"]) / len(stats["prices_sqft"]) if stats["prices_sqft"] else 0
        stats["avg_impr_ratio"] = sum(stats["impr_ratios"]) / len(stats["impr_ratios"]) if stats["impr_ratios"] else 0

    scored = []
    for p in parcels:
        score = 0
        comm = p.get("situs_community", "Unknown")
        comm_avg_ppsf = community_stats.get(comm, {}).get("avg_price_sqft", 0)

        # 1. Improvement ratio score (0-30)
        ir = p["impr_ratio"]
        if ir < 0.25:
            score += 30
        elif ir < 0.30:
            score += 25
        elif ir < 0.35:
            score += 20
        elif ir < 0.40:
            score += 15
        elif ir < 0.45:
            score += 10
        elif ir < 0.50:
            score += 5

        # 2. Price/sqft vs community average (0-25)
        if comm_avg_ppsf > 0:
            ppsf_ratio = p["price_per_sqft"] / comm_avg_ppsf
            if ppsf_ratio < 0.60:
                score += 25
            elif ppsf_ratio < 0.70:
                score += 20
            elif ppsf_ratio < 0.80:
                score += 15
            elif ppsf_ratio < 0.90:
                score += 10
            elif ppsf_ratio < 1.00:
                score += 5

        # 3. Age factor (0-15) - older = more rehab likely
        year = p["year_built"]
        if year <= 1972:
            score += 15
        elif year <= 1975:
            score += 12
        elif year <= 1978:
            score += 9
        elif year <= 1981:
            score += 6
        elif year <= 1985:
            score += 3

        # 4. Bath/bed ratio (0-15) - lower = more outdated
        bbr = p["bath_bed_ratio"]
        if bbr < 0.50:
            score += 15
        elif bbr < 0.67:
            score += 10
        elif bbr < 0.75:
            score += 7
        elif bbr < 1.0:
            score += 3

        # 5. Living area / lot ratio (0-15) - lower = expansion potential
        llr = p["lvg_lot_ratio"]
        if llr < 0.10:
            score += 15
        elif llr < 0.15:
            score += 12
        elif llr < 0.20:
            score += 9
        elif llr < 0.25:
            score += 6
        elif llr < 0.30:
            score += 3

        p["score"] = score
        p["comm_avg_ppsf"] = round(comm_avg_ppsf, 2)
        scored.append(p)

    # Sort by score descending, then by improvement ratio ascending
    scored.sort(key=lambda x: (-x["score"], x["impr_ratio"]))
    return scored


def main():
    print("=" * 70)
    print("SD COUNTY SFH DISTRESSED FINDER - Age + Low Improvement Ratio")
    print("=" * 70)

    all_parcels = []

    for community in COMMUNITIES:
        print(f"\n[{community}] Querying SFH (1970-1985, under $600K, 3+BR, 1000+sqft)...", flush=True)
        parcels = query_community(community)
        print(f"  -> {len(parcels)} raw matches")
        all_parcels.extend(parcels)
        time.sleep(0.3)

    print(f"\n{'='*70}")
    print(f"TOTAL RAW MATCHES: {len(all_parcels)}")
    print(f"{'='*70}")

    # Compute metrics
    enriched = compute_metrics(all_parcels)
    print(f"After enrichment (valid data): {len(enriched)}")

    # Filter to improvement ratio < 50%
    filtered = [p for p in enriched if p["impr_ratio"] < 0.50]
    print(f"After impr_ratio < 50% filter: {len(filtered)}")

    # Score and rank
    scored = score_parcels(filtered)

    # Community stats summary
    print(f"\n{'='*70}")
    print("COMMUNITY STATS (filtered pool)")
    print(f"{'='*70}")
    comm_counts = {}
    for p in scored:
        c = p.get("situs_community", "?")
        if c not in comm_counts:
            comm_counts[c] = {"count": 0, "avg_score": 0, "scores": []}
        comm_counts[c]["count"] += 1
        comm_counts[c]["scores"].append(p["score"])
    for c, info in sorted(comm_counts.items(), key=lambda x: -x[1]["count"]):
        avg_s = sum(info["scores"]) / len(info["scores"])
        print(f"  {c:20s}: {info['count']:4d} properties, avg score {avg_s:.1f}")

    # Top 20
    top = scored[:20]
    print(f"\n{'='*70}")
    print(f"TOP 20 REHAB CANDIDATES (of {len(scored)} filtered)")
    print(f"{'='*70}")

    for i, p in enumerate(top, 1):
        addr = p.get("situs_addr", "N/A")
        comm = p.get("situs_community", "?")
        total = p.get("asr_total", 0)
        impr = p.get("asr_impr", 0)
        land = p.get("asr_land", 0)
        sqft = p.get("total_lvg_area", 0)
        beds = p.get("bedrooms", 0)
        baths = p.get("baths", 0)
        lot = p.get("lot_sqft", 0)
        yr = p.get("year_built", 0)
        ir = p.get("impr_ratio", 0)
        ppsf = p.get("price_per_sqft", 0)
        avg_ppsf = p.get("comm_avg_ppsf", 0)
        score = p.get("score", 0)
        apn = p.get("apn", "")

        print(f"\n  #{i:2d} | SCORE: {score}/100")
        print(f"      APN: {apn}")
        print(f"      Address: {addr}, {comm}")
        print(f"      Assessed: ${total:,.0f} (Land: ${land:,.0f} | Impr: ${impr:,.0f})")
        print(f"      Impr Ratio: {ir:.1%}  |  $/sqft: ${ppsf:.0f} (comm avg: ${avg_ppsf:.0f})")
        print(f"      {beds}BR / {baths}BA  |  {sqft:,.0f} sqft  |  Lot: {lot:,.0f} sqft  |  Built: {yr}")

    # Save all scored results to CSV
    csv_fields = [
        "score", "apn", "situs_addr", "situs_community", "situs_zip",
        "asr_total", "asr_land", "asr_impr", "impr_ratio",
        "price_per_sqft", "comm_avg_ppsf",
        "total_lvg_area", "lot_sqft", "bedrooms", "baths",
        "bath_bed_ratio", "lvg_lot_ratio",
        "year_built", "year_effective",
        "owner_name",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(scored)

    print(f"\n{'='*70}")
    print(f"Saved {len(scored)} scored properties to {OUTPUT_CSV}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
