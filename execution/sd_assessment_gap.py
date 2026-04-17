"""
Assessment Gap Method for finding distressed SFH properties in San Diego County.

Queries the SANDAG GIS Parcels layer for SFH matching base buyer criteria,
then identifies properties assessed significantly below their community median —
indicating the home is in poor condition compared to neighbors.

Endpoint: https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query
"""

import csv
import time
import statistics
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TMP_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = TMP_DIR / "sd_filter_test_assessment_gap.csv"

GIS_URL = "https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query"
MAX_RECORDS = 2000

# Target communities to query (keep manageable)
TARGET_COMMUNITIES = [
    "SAN DIEGO",
    "EL CAJON",
    "SPRING VALLEY",
    "ESCONDIDO",
    "LEMON GROVE",
]

# Fields we need
OUT_FIELDS = [
    "apn", "situs_address", "situs_community", "situs_zip",
    "nucleus_use_cd", "asr_total", "asr_land", "asr_impr",
    "total_lvg_area", "bedrooms", "baths", "year_effective",
    "stories", "units",
]

# Base WHERE clause for SFH matching buyer criteria
# nucleus_use_cd = '111' (SFH)
# asr_total between 100000 and 600000
# total_lvg_area >= 1000
# bedrooms >= 3
# year_effective handling: 70-99 = 1970-1999, 00-26 = 2000-2026
BASE_WHERE = (
    "nucleus_use_cd = '111' "
    "AND asr_total >= 100000 AND asr_total <= 600000 "
    "AND total_lvg_area >= 1000 "
    "AND bedrooms >= '003'"
)


def query_community(community: str) -> list[dict]:
    """Query all SFH in a community, paginating through results."""
    all_records = []
    offset = 0
    where = f"{BASE_WHERE} AND situs_community = '{community}'"

    while True:
        data = {
            "where": where,
            "outFields": ",".join(OUT_FIELDS),
            "returnGeometry": "false",
            "resultOffset": str(offset),
            "resultRecordCount": str(MAX_RECORDS),
            "f": "json",
        }
        resp = requests.post(GIS_URL, data=data, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if "error" in result:
            print(f"  ERROR for {community}: {result['error']}")
            break

        features = result.get("features", [])
        if not features:
            break

        for f in features:
            all_records.append(f["attributes"])

        print(f"  {community}: fetched {len(features)} records (offset {offset})")

        # Check if there are more records
        if len(features) < MAX_RECORDS:
            break
        offset += len(features)
        time.sleep(0.5)  # polite delay

    return all_records


def analyze_assessment_gaps(records: list[dict]) -> list[dict]:
    """
    Group by community, compute medians, flag properties significantly
    below their community median.
    """
    # Group by community
    by_community = {}
    for r in records:
        comm = r.get("situs_community", "UNKNOWN")
        by_community.setdefault(comm, []).append(r)

    print(f"\n--- Community Summary ---")
    community_stats = {}
    for comm, props in sorted(by_community.items()):
        if len(props) < 10:
            print(f"  {comm}: {len(props)} properties (skipping, too few)")
            continue

        values = [p["asr_total"] for p in props if p.get("asr_total") and p["asr_total"] > 0]
        sqft_vals = []
        for p in props:
            if p.get("asr_total") and p.get("total_lvg_area") and p["total_lvg_area"] > 0:
                sqft_vals.append(p["asr_total"] / p["total_lvg_area"])

        if len(values) < 10:
            continue

        med_value = statistics.median(values)
        med_psf = statistics.median(sqft_vals) if sqft_vals else 0
        community_stats[comm] = {
            "median_value": med_value,
            "median_psf": med_psf,
            "count": len(props),
        }
        print(f"  {comm}: {len(props)} properties, median ${med_value:,.0f}, median $/sqft ${med_psf:,.0f}")

    # Flag distressed properties
    flagged = []
    for r in records:
        comm = r.get("situs_community")
        if comm not in community_stats:
            continue

        stats = community_stats[comm]
        asr = r.get("asr_total", 0)
        asr_impr = r.get("asr_impr", 0)
        sqft = r.get("total_lvg_area", 0)

        if not asr or asr <= 0:
            continue

        # Compute gap metrics
        gap_pct = asr / stats["median_value"]  # e.g. 0.5 = 50% of median
        impr_ratio = asr_impr / asr if asr > 0 else 0
        psf = asr / sqft if sqft > 0 else 0
        psf_gap = psf / stats["median_psf"] if stats["median_psf"] > 0 else 1

        # Flag criteria:
        # 1) Assessed value < 60% of community median
        # 2) Improvement ratio < 40% (land worth more than building)
        flag_below_median = gap_pct < 0.60
        flag_low_impr = impr_ratio < 0.40

        if flag_below_median or flag_low_impr:
            # Compute a distress score (lower = more distressed)
            # Combine gap_pct and impr_ratio — both low = very distressed
            distress_score = (gap_pct * 0.5) + (impr_ratio * 0.3) + (psf_gap * 0.2)

            # Format year
            yr = r.get("year_effective")
            if yr is not None:
                if yr >= 70:
                    year_built = 1900 + yr
                else:
                    year_built = 2000 + yr
            else:
                year_built = None

            reasons = []
            if flag_below_median:
                reasons.append(f"Value={gap_pct:.0%} of median")
            if flag_low_impr:
                reasons.append(f"Impr ratio={impr_ratio:.0%}")

            flagged.append({
                "address": r.get("situs_address", ""),
                "community": comm,
                "zip": r.get("situs_zip", ""),
                "asr_total": asr,
                "asr_land": r.get("asr_land", 0),
                "asr_impr": asr_impr,
                "community_median": stats["median_value"],
                "gap_pct": gap_pct,
                "impr_ratio": impr_ratio,
                "psf": psf,
                "community_median_psf": stats["median_psf"],
                "sqft": sqft,
                "bedrooms": r.get("bedrooms"),
                "baths": r.get("baths"),
                "year_built": year_built,
                "stories": r.get("stories"),
                "distress_score": distress_score,
                "flags": " | ".join(reasons),
                "apn": r.get("apn", ""),
            })

    # Sort by distress score (most distressed first)
    flagged.sort(key=lambda x: x["distress_score"])
    return flagged, community_stats


def main():
    print("=" * 70)
    print("ASSESSMENT GAP METHOD — Distressed SFH Finder")
    print("San Diego County GIS (SANDAG Parcels)")
    print("=" * 70)

    # Step 1: Query each target community
    all_records = []
    for comm in TARGET_COMMUNITIES:
        print(f"\nQuerying {comm}...")
        records = query_community(comm)
        all_records.extend(records)
        print(f"  Total from {comm}: {len(records)}")
        time.sleep(0.3)

    print(f"\n{'=' * 70}")
    print(f"TOTAL SFH matching base criteria: {len(all_records)}")
    print(f"{'=' * 70}")

    if not all_records:
        print("No records found. Check query parameters.")
        return

    # Step 2-4: Analyze gaps
    flagged, community_stats = analyze_assessment_gaps(all_records)

    print(f"\nCommunities with enough data: {len(community_stats)}")
    print(f"Properties flagged as distressed: {len(flagged)}")

    # Step 5: Report top 20
    top = flagged[:20]
    print(f"\n{'=' * 70}")
    print(f"TOP {len(top)} DISTRESSED CANDIDATES (Assessment Gap Method)")
    print(f"{'=' * 70}")

    for i, p in enumerate(top, 1):
        print(f"\n#{i} — {p['address']}, {p['community']} {p['zip']}")
        print(f"   APN: {p['apn']}")
        print(f"   Assessed: ${p['asr_total']:,.0f}  (Land: ${p['asr_land']:,.0f} / Impr: ${p['asr_impr']:,.0f})")
        print(f"   Community Median: ${p['community_median']:,.0f}  →  Gap: {p['gap_pct']:.0%} of median")
        print(f"   Impr/Total ratio: {p['impr_ratio']:.0%}  (< 40% = land worth more than building)")
        print(f"   $/sqft: ${p['psf']:.0f}  vs community median $/sqft: ${p['community_median_psf']:.0f}")
        print(f"   Size: {p['sqft']:,.0f} sqft | {p['bedrooms']} bed / {p['baths']} bath | Year: {p['year_built']} | Stories: {p['stories']}")
        print(f"   FLAGS: {p['flags']}")

    # Step 6: Save all flagged to CSV
    if flagged:
        fieldnames = [
            "address", "community", "zip", "apn", "asr_total", "asr_land",
            "asr_impr", "community_median", "gap_pct", "impr_ratio", "psf",
            "community_median_psf", "sqft", "bedrooms", "baths", "year_built",
            "stories", "distress_score", "flags",
        ]
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flagged)
        print(f"\nSaved {len(flagged)} flagged properties to: {OUTPUT_CSV}")
    else:
        print("\nNo properties flagged. Try adjusting thresholds.")


if __name__ == "__main__":
    main()
