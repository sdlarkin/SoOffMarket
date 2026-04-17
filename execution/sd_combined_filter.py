"""
San Diego County — Distressed SFH Finder
Tests 3 filtering approaches simultaneously and compares results.

1. Assessment Gap: homes assessed below community median
2. Sale History/Distress: long ownership, non-owner-occupied, low improvement
3. Age + Improvement Ratio: older homes where building has depreciated vs land

GIS: SANDAG Parcels FeatureServer
"""

import csv
import time
import statistics
import requests
from pathlib import Path
from collections import defaultdict

URL = "https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query"
TMP = Path(__file__).resolve().parent.parent / ".tmp"
TMP.mkdir(exist_ok=True)

FIELDS = "apn,situs_address,situs_street,situs_community,situs_zip,asr_land,asr_impr,asr_total,total_lvg_area,bedrooms,baths,acreage,docdate,nucleus_use_cd,year_effective,ownerocc"

COMMUNITIES = ["SAN DIEGO", "EL CAJON", "SPRING VALLEY", "ESCONDIDO", "LEMON GROVE", "NATIONAL CITY", "LAKESIDE", "LA MESA"]


def query_community(community):
    where = (
        f"nucleus_use_cd = '111' "
        f"AND asr_total > 100000 AND asr_total <= 600000 "
        f"AND asr_impr > 0 "
        f"AND total_lvg_area >= 1000 "
        f"AND bedrooms >= '003' "
        f"AND situs_community = '{community}'"
    )
    all_feats = []
    offset = 0
    while True:
        r = requests.post(URL, data={
            "where": where,
            "outFields": FIELDS,
            "returnGeometry": "false",
            "resultOffset": str(offset),
            "resultRecordCount": "2000",
            "f": "json"
        }, timeout=30)
        data = r.json()
        if data.get("error"):
            print(f"  ERROR {community}: {data['error']['message']}")
            return []
        feats = [f["attributes"] for f in data.get("features", [])]
        all_feats.extend(feats)
        if len(feats) < 2000:
            break
        offset += 2000
    return all_feats


def parse_year(ye):
    if not ye:
        return None
    try:
        y = int(str(ye).strip())
        return 1900 + y if y > 26 else 2000 + y
    except (ValueError, TypeError):
        return None


def parse_docdate(dd):
    if not dd or len(str(dd)) < 6:
        return None
    try:
        s = str(dd).zfill(6)
        yy = int(s[4:6])
        return 1900 + yy if yy > 26 else 2000 + yy
    except (ValueError, TypeError):
        return None


def main():
    print("=" * 60)
    print("SAN DIEGO COUNTY - Distressed SFH Finder")
    print("3 approaches tested simultaneously")
    print("=" * 60)

    all_props = []
    for comm in COMMUNITIES:
        print(f"\n  Querying {comm}...", end=" ", flush=True)
        props = query_community(comm)
        print(f"{len(props)} SFH")
        all_props.extend(props)
        time.sleep(0.3)

    print(f"\nTotal SFH collected: {len(all_props)}")
    if not all_props:
        print("No data. Exiting.")
        return

    # Community medians
    by_comm = defaultdict(list)
    for p in all_props:
        by_comm[p["situs_community"]].append(p)

    comm_medians = {}
    comm_ppsf = {}
    for comm, props in by_comm.items():
        values = [p["asr_total"] for p in props if p["asr_total"]]
        ppsfs = [p["asr_total"] / p["total_lvg_area"] for p in props if p.get("total_lvg_area") and p["asr_total"]]
        if len(values) >= 10:
            comm_medians[comm] = statistics.median(values)
        if len(ppsfs) >= 10:
            comm_ppsf[comm] = statistics.median(ppsfs)

    print(f"\nCommunity medians:")
    for c in sorted(comm_medians.keys()):
        print(f"  {c}: median ${comm_medians[c]:,.0f} | $/sqft ${comm_ppsf.get(c, 0):.0f}")

    # Score every property
    scored = []
    for p in all_props:
        comm = p["situs_community"]
        total = p["asr_total"] or 0
        impr = p["asr_impr"] or 0
        land = p["asr_land"] or 0
        sqft = p["total_lvg_area"] or 1
        year_built = parse_year(p.get("year_effective"))
        sale_year = parse_docdate(p.get("docdate"))
        owner_occ = p.get("ownerocc", "")

        if total == 0:
            continue

        impr_ratio = impr / total
        ppsf = total / sqft

        # Approach 1: Assessment Gap
        gap_score = 0
        median = comm_medians.get(comm)
        median_ppsf = comm_ppsf.get(comm)
        if median:
            pct_of_median = total / median
            if pct_of_median < 0.60:
                gap_score += 3
            elif pct_of_median < 0.75:
                gap_score += 2
            elif pct_of_median < 0.90:
                gap_score += 1
        if impr_ratio < 0.40:
            gap_score += 2
        elif impr_ratio < 0.50:
            gap_score += 1

        # Approach 2: Distress Signals
        distress_score = 0
        if sale_year and sale_year < 2010:
            distress_score += 2
        elif sale_year and sale_year < 2015:
            distress_score += 1
        if owner_occ and owner_occ.upper() != "Y":
            distress_score += 2
        if impr_ratio < 0.50:
            distress_score += 1

        # Approach 3: Age + Ratio
        age_score = 0
        if year_built and year_built < 1985:
            age_score += 2
            if year_built < 1975:
                age_score += 1
        if impr_ratio < 0.50:
            age_score += 2
        elif impr_ratio < 0.60:
            age_score += 1
        if median_ppsf and ppsf < median_ppsf * 0.75:
            age_score += 1

        combined = gap_score + distress_score + age_score
        addr = f"{p.get('situs_address', '')} {p.get('situs_street', '')}".strip()

        scored.append({
            "apn": p["apn"],
            "address": addr,
            "community": comm,
            "zip": p.get("situs_zip", ""),
            "total": total,
            "land": land,
            "impr": impr,
            "impr_ratio": round(impr_ratio, 2),
            "sqft": sqft,
            "ppsf": round(ppsf),
            "beds": p.get("bedrooms", ""),
            "baths": p.get("baths", ""),
            "year_built": year_built,
            "sale_year": sale_year,
            "owner_occ": owner_occ,
            "gap_score": gap_score,
            "distress_score": distress_score,
            "age_score": age_score,
            "combined_score": combined,
            "comm_median": median,
            "comm_ppsf": median_ppsf,
        })

    scored.sort(key=lambda x: -x["combined_score"])

    # Results
    print(f"\n{'='*60}")
    print("APPROACH COMPARISON")
    print(f"{'='*60}")
    for approach, key in [("Assessment Gap", "gap_score"), ("Distress Signals", "distress_score"), ("Age + Ratio", "age_score")]:
        high = [s for s in scored if s[key] >= 3]
        print(f"  {approach}: {len(high)} high-scoring (>= 3)")

    top_combined = [s for s in scored if s["combined_score"] >= 8]
    print(f"\n  COMBINED (>= 8): {len(top_combined)} properties")

    # Overlap
    top_gap = {s["apn"] for s in scored if s["gap_score"] >= 3}
    top_dist = {s["apn"] for s in scored if s["distress_score"] >= 3}
    top_age = {s["apn"] for s in scored if s["age_score"] >= 3}
    all_three = top_gap & top_dist & top_age
    print(f"\n  Overlap (all 3 approaches flag it): {len(all_three)} properties")
    print(f"  Gap + Distress: {len(top_gap & top_dist)}")
    print(f"  Gap + Age: {len(top_gap & top_age)}")
    print(f"  Distress + Age: {len(top_dist & top_age)}")

    print(f"\n{'='*60}")
    print("TOP 20 COMBINED CANDIDATES")
    print(f"{'='*60}")
    for i, s in enumerate(scored[:20], 1):
        print(f"\n  #{i} | {s['address']}, {s['community']} {s['zip']}")
        print(f"     APN: {s['apn']} | ${s['total']:,} (${s['land']:,} land + ${s['impr']:,} impr)")
        print(f"     {s['sqft']}sqft | {s['beds']}bd/{s['baths']}ba | Built {s['year_built'] or '?'} | Sold {s['sale_year'] or '?'} | OwnerOcc: {s['owner_occ']}")
        print(f"     Impr ratio: {s['impr_ratio']:.0%} | $/sqft: ${s['ppsf']} (community: ${s['comm_ppsf'] or 0:.0f})")
        print(f"     Scores: Gap={s['gap_score']} Distress={s['distress_score']} Age={s['age_score']} COMBINED={s['combined_score']}")

    # Save CSV
    csv_path = TMP / "sd_combined_distressed_sfh.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(scored[0].keys()))
        writer.writeheader()
        writer.writerows(scored)
    print(f"\n\nSaved {len(scored)} scored properties to {csv_path.name}")


if __name__ == "__main__":
    main()
