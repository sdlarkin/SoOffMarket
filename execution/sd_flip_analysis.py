"""
San Diego County — Fix-and-Flip Pattern Analysis

Uses Prop 13 assessment mechanics to identify completed flips:
- In CA, assessment resets to sale price when property transfers
- A recently-sold home with HIGH assessment = bought at market (or post-flip)
- A long-ago-sold home with LOW assessment = Prop 13 frozen value

Strategy:
1. Find homes sold 2022-2026 with assessment ABOVE community median (post-flip indicator)
2. Find homes sold 2022-2026 with assessment BELOW community median (pre-flip / distressed buy)
3. Analyze differences between the two groups to find flip markers
4. Also: find homes with unusually high improvement-to-total ratio + recent sale = renovated
"""

import csv
import time
import statistics
import requests
from pathlib import Path
from collections import defaultdict, Counter

URL = "https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query"
TMP = Path(__file__).resolve().parent.parent / ".tmp"
TMP.mkdir(exist_ok=True)

FIELDS = "apn,situs_address,situs_street,situs_community,situs_zip,asr_land,asr_impr,asr_total,total_lvg_area,bedrooms,baths,acreage,docdate,nucleus_use_cd,year_effective,ownerocc,qual_class_shape"

COMMUNITIES = ["SAN DIEGO", "EL CAJON", "SPRING VALLEY", "ESCONDIDO", "LA MESA", "NATIONAL CITY"]


def query(where, max_results=2000):
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
            print(f"  ERROR: {data['error']['message']}")
            return []
        feats = [f["attributes"] for f in data.get("features", [])]
        all_feats.extend(feats)
        if len(feats) < 2000 or len(all_feats) >= max_results:
            break
        offset += 2000
        time.sleep(0.2)
    return all_feats


def parse_docdate_year(dd):
    if not dd or len(str(dd)) < 6:
        return None
    try:
        s = str(dd).zfill(6)
        yy = int(s[4:6])
        return 1900 + yy if yy > 26 else 2000 + yy
    except (ValueError, TypeError):
        return None


def parse_year_effective(ye):
    if not ye:
        return None
    try:
        y = int(str(ye).strip())
        return 1900 + y if y > 26 else 2000 + y
    except (ValueError, TypeError):
        return None


def main():
    print("=" * 70)
    print("SAN DIEGO COUNTY — Fix-and-Flip Pattern Analysis")
    print("Using Prop 13 assessment mechanics to identify completed flips")
    print("=" * 70)

    # Step 1: Collect ALL recent SFH sales (2020-2026) in target communities
    # These represent the post-Prop-13-reset universe
    print("\n--- Phase 1: Collecting recent SFH sales ---")
    recent_sales = []
    old_sales = []

    for comm in COMMUNITIES:
        print(f"\n  {comm}...", end=" ", flush=True)

        # Recent sales (2020+): docdate MMDDYY where YY >= 20
        # The date field is a string, so we need creative filtering
        # YY 20-26 means docdate ends in 20,21,22,23,24,25,26
        recent = query(
            f"nucleus_use_cd = '111' AND asr_total > 100000 AND asr_total <= 800000 "
            f"AND total_lvg_area >= 800 AND asr_impr > 0 "
            f"AND situs_community = '{comm}' "
            f"AND (docdate LIKE '%20' OR docdate LIKE '%21' OR docdate LIKE '%22' "
            f"OR docdate LIKE '%23' OR docdate LIKE '%24' OR docdate LIKE '%25' OR docdate LIKE '%26')",
            max_results=4000
        )
        print(f"{len(recent)} recent", end="", flush=True)
        recent_sales.extend(recent)

        # Old sales (pre-2010): owned a long time, Prop 13 frozen
        old = query(
            f"nucleus_use_cd = '111' AND asr_total > 50000 AND asr_total <= 800000 "
            f"AND total_lvg_area >= 800 AND asr_impr > 0 "
            f"AND situs_community = '{comm}' "
            f"AND (docdate LIKE '%00' OR docdate LIKE '%01' OR docdate LIKE '%02' "
            f"OR docdate LIKE '%03' OR docdate LIKE '%04' OR docdate LIKE '%05' "
            f"OR docdate LIKE '%06' OR docdate LIKE '%07' OR docdate LIKE '%08' OR docdate LIKE '%09')",
            max_results=4000
        )
        print(f" | {len(old)} old", flush=True)
        old_sales.extend(old)
        time.sleep(0.3)

    print(f"\nTotal: {len(recent_sales)} recent sales, {len(old_sales)} old sales")

    # Step 2: Compute community statistics
    print("\n--- Phase 2: Computing community benchmarks ---")
    all_recent = defaultdict(list)
    for p in recent_sales:
        if p["asr_total"] and p["total_lvg_area"]:
            all_recent[p["situs_community"]].append(p)

    comm_stats = {}
    for comm, props in all_recent.items():
        totals = [p["asr_total"] for p in props]
        ppsfs = [p["asr_total"] / p["total_lvg_area"] for p in props]
        impr_ratios = [p["asr_impr"] / p["asr_total"] for p in props if p["asr_total"]]
        comm_stats[comm] = {
            "median_total": statistics.median(totals),
            "median_ppsf": statistics.median(ppsfs),
            "median_impr_ratio": statistics.median(impr_ratios),
            "p75_total": sorted(totals)[int(len(totals) * 0.75)],
            "p25_total": sorted(totals)[int(len(totals) * 0.25)],
            "count": len(props),
        }
        print(f"  {comm}: median ${comm_stats[comm]['median_total']:,.0f} | "
              f"$/sqft ${comm_stats[comm]['median_ppsf']:.0f} | "
              f"impr ratio {comm_stats[comm]['median_impr_ratio']:.0%}")

    # Step 3: Identify likely COMPLETED FLIPS
    # A completed flip looks like: recently sold, HIGH assessment (reset to market),
    # HIGH improvement ratio (renovated), assessment ABOVE community median
    print("\n--- Phase 3: Identifying completed flips ---")
    likely_flips = []
    normal_recent = []

    for p in recent_sales:
        comm = p["situs_community"]
        if comm not in comm_stats:
            continue
        total = p["asr_total"] or 0
        impr = p["asr_impr"] or 0
        sqft = p["total_lvg_area"] or 1
        if total == 0:
            continue

        stats = comm_stats[comm]
        impr_ratio = impr / total
        ppsf = total / sqft
        year_built = parse_year_effective(p.get("year_effective"))
        sale_year = parse_docdate_year(p.get("docdate"))

        # Flip indicators:
        # 1. Assessment above 75th percentile (bought at premium = post-reno)
        # 2. High improvement ratio (> 65% = recently improved building)
        # 3. Older home (built before 1990) with high value = was renovated
        is_above_p75 = total > stats["p75_total"]
        is_high_impr = impr_ratio > 0.65
        is_old_renovated = bool(year_built and year_built < 1990 and ppsf > stats["median_ppsf"])

        flip_signals = sum([is_above_p75, is_high_impr, is_old_renovated])

        entry = {
            "apn": p["apn"],
            "address": f"{p.get('situs_address', '')} {p.get('situs_street', '')}".strip(),
            "community": comm,
            "zip": p.get("situs_zip", ""),
            "total": total,
            "land": p.get("asr_land", 0),
            "impr": impr,
            "impr_ratio": round(impr_ratio, 3),
            "sqft": sqft,
            "ppsf": round(ppsf),
            "beds": p.get("bedrooms", ""),
            "baths": p.get("baths", ""),
            "year_built": year_built,
            "sale_year": sale_year,
            "owner_occ": p.get("ownerocc", ""),
            "qual_class": p.get("qual_class_shape", ""),
            "flip_signals": flip_signals,
            "above_p75": is_above_p75,
            "high_impr": is_high_impr,
            "old_renovated": is_old_renovated,
            "comm_median": stats["median_total"],
            "comm_ppsf": stats["median_ppsf"],
        }

        if flip_signals >= 2:
            likely_flips.append(entry)
        else:
            normal_recent.append(entry)

    print(f"  Likely completed flips (2+ signals): {len(likely_flips)}")
    print(f"  Normal recent sales: {len(normal_recent)}")

    # Step 4: Identify likely PRE-FLIP (distressed) properties
    print("\n--- Phase 4: Profiling old-sale (pre-flip candidate) properties ---")
    pre_flip = []
    for p in old_sales:
        comm = p["situs_community"]
        if comm not in comm_stats:
            continue
        total = p["asr_total"] or 0
        impr = p["asr_impr"] or 0
        sqft = p["total_lvg_area"] or 1
        if total == 0:
            continue

        stats = comm_stats[comm]
        impr_ratio = impr / total
        ppsf = total / sqft
        year_built = parse_year_effective(p.get("year_effective"))

        pre_flip.append({
            "apn": p["apn"],
            "total": total,
            "impr_ratio": impr_ratio,
            "ppsf": ppsf,
            "year_built": year_built,
            "owner_occ": p.get("ownerocc", ""),
        })

    # Step 5: Compare profiles
    print("\n" + "=" * 70)
    print("FLIP vs NON-FLIP vs PRE-FLIP PROFILE COMPARISON")
    print("=" * 70)

    def profile(label, group, key_fn):
        vals = [key_fn(g) for g in group if key_fn(g) is not None]
        if not vals:
            return
        print(f"\n  {label} (n={len(vals)}):")
        print(f"    Median: {statistics.median(vals):.2f}")
        print(f"    Mean:   {statistics.mean(vals):.2f}")
        if len(vals) >= 4:
            s = sorted(vals)
            print(f"    25th:   {s[len(s)//4]:.2f}")
            print(f"    75th:   {s[3*len(s)//4]:.2f}")

    print("\n--- Improvement Ratio (impr / total) ---")
    profile("Completed Flips", likely_flips, lambda g: g["impr_ratio"])
    profile("Normal Recent Sales", normal_recent, lambda g: g["impr_ratio"])
    profile("Old Sales (pre-flip pool)", pre_flip, lambda g: g["impr_ratio"])

    print("\n--- Price per Sqft ---")
    profile("Completed Flips", likely_flips, lambda g: g["ppsf"])
    profile("Normal Recent Sales", normal_recent, lambda g: g["ppsf"])
    profile("Old Sales (pre-flip pool)", pre_flip, lambda g: g["ppsf"])

    print("\n--- Total Assessment ---")
    profile("Completed Flips", likely_flips, lambda g: g["total"])
    profile("Normal Recent Sales", normal_recent, lambda g: g["total"])
    profile("Old Sales (pre-flip pool)", pre_flip, lambda g: g["total"])

    print("\n--- Year Built ---")
    profile("Completed Flips", likely_flips, lambda g: g["year_built"])
    profile("Normal Recent Sales", normal_recent, lambda g: g["year_built"])
    profile("Old Sales (pre-flip pool)", pre_flip, lambda g: g["year_built"])

    print("\n--- Owner Occupied Rate ---")
    for label, group in [("Flips", likely_flips), ("Normal", normal_recent), ("Pre-flip", pre_flip)]:
        occ = [g["owner_occ"] for g in group]
        y = sum(1 for o in occ if o == "Y")
        n = len(occ) - y
        print(f"  {label}: {y}/{len(occ)} owner-occ ({100*y/max(len(occ),1):.0f}%), {n} non-owner-occ ({100*n/max(len(occ),1):.0f}%)")

    # Step 6: What quality/class do flipped homes have?
    print("\n--- Quality Class (qual_class_shape) Distribution ---")
    flip_quals = Counter(f.get("qual_class", "?")[:1] for f in likely_flips)
    normal_quals = Counter(f.get("qual_class", "?")[:1] for f in normal_recent)
    print(f"  Flips: {dict(flip_quals.most_common(5))}")
    print(f"  Normal: {dict(normal_quals.most_common(5))}")

    # Step 7: Save top flips and top pre-flip candidates
    likely_flips.sort(key=lambda x: -x["flip_signals"])
    csv_path = TMP / "sd_flip_analysis_completed_flips.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(likely_flips[0].keys()) if likely_flips else [])
        writer.writeheader()
        writer.writerows(likely_flips)

    print(f"\n\nSaved {len(likely_flips)} likely completed flips to {csv_path.name}")

    # Top 15 most obvious flips
    print(f"\n{'='*70}")
    print("TOP 15 MOST OBVIOUS COMPLETED FLIPS")
    print(f"{'='*70}")
    for i, f in enumerate(likely_flips[:15], 1):
        markers = []
        if f["above_p75"]:
            markers.append("above P75")
        if f["high_impr"]:
            markers.append("high impr")
        if f["old_renovated"]:
            markers.append("old+renovated")
        print(f"\n  #{i} | {f['address']}, {f['community']} {f['zip']}")
        print(f"     ${f['total']:,} | {f['sqft']}sqft ${f['ppsf']}/sqft | {f['beds']}bd/{f['baths']}ba | Built {f['year_built']} | Sold {f['sale_year']}")
        print(f"     Impr: {f['impr_ratio']:.0%} (${f['impr']:,}) | Land: ${f['land']:,} | Markers: {', '.join(markers)}")

    # Key findings
    print(f"\n{'='*70}")
    print("KEY FINDINGS — What markers identify a flip candidate?")
    print(f"{'='*70}")

    # Compare flips vs pre-flip pool
    flip_impr = statistics.median([f["impr_ratio"] for f in likely_flips])
    preflip_impr = statistics.median([f["impr_ratio"] for f in pre_flip])
    flip_ppsf = statistics.median([f["ppsf"] for f in likely_flips])
    preflip_ppsf = statistics.median([f["ppsf"] for f in pre_flip])

    print(f"\n  Flipped homes have:")
    print(f"    - Improvement ratio: {flip_impr:.0%} (vs {preflip_impr:.0%} in pre-flip pool)")
    print(f"    - $/sqft: ${flip_ppsf} (vs ${preflip_ppsf} in pre-flip pool)")
    print(f"\n  Pre-flip candidates (the BEFORE picture) tend to have:")
    print(f"    - LOW improvement ratio (building depreciated vs land)")
    print(f"    - LOW $/sqft relative to community median")
    print(f"    - LONG ownership (Prop 13 frozen, deferred maintenance)")
    print(f"    - Higher non-owner-occupancy rate")


if __name__ == "__main__":
    main()
