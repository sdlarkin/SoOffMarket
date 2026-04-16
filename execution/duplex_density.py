"""
Calculate duplex friendliness score for each parcel.
Queries nearby residential properties within 0.25 miles and computes:
  - Count of SFR vs duplex/multi-family
  - Duplex ratio (% of nearby residential that are multi-family)
  - Duplex friendliness rating (A/B/C/D)

Land use codes:
  111 = Single Family Residential
  112 = Duplex
  113 = Triplex
  114 = Fourplex/Quadplex
"""

import csv
import json
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp" / "sara_holt_segments"

INPUT_CSV = TMP_DIR / "individuals_buildable.csv"
OUTPUT_CSV = TMP_DIR / "individuals_scored.csv"

PARCEL_URL = "https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_Parcels/MapServer/0/query"

SEARCH_RADIUS_FT = 1320  # 0.25 miles


def get_state_plane_centroids(tax_map_nos: list[str]) -> dict[str, tuple[float, float]]:
    """Get centroids in state plane coords (WKID 6576) for spatial queries."""
    ids_str = ",".join(f"'{pid}'" for pid in tax_map_nos)
    r = requests.post(PARCEL_URL, data={
        "where": f"TAX_MAP_NO IN ({ids_str})",
        "outFields": "TAX_MAP_NO",
        "returnGeometry": "true",
        "outSR": "6576",
        "f": "json",
    }, timeout=30)
    data = r.json()
    centroids = {}
    for feat in data.get("features", []):
        pid = feat["attributes"]["TAX_MAP_NO"]
        rings = feat["geometry"].get("rings", [[]])
        if rings and rings[0]:
            pts = rings[0]
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            centroids[pid] = (cx, cy)
    return centroids


def get_residential_mix(cx: float, cy: float) -> dict:
    """Query nearby residential properties and return type counts."""
    point = {"x": cx, "y": cy, "spatialReference": {"wkid": 6576}}
    r = requests.post(PARCEL_URL, data={
        "where": "BUILDVALUE > 0 AND LUCODE IN (111, 112, 113, 114)",
        "geometry": json.dumps(point),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(SEARCH_RADIUS_FT),
        "units": "esriSRUnit_Foot",
        "inSR": "6576",
        "outFields": "",
        "groupByFieldsForStatistics": "LUCODE",
        "outStatistics": json.dumps([{
            "statisticType": "count",
            "onStatisticField": "OBJECTID",
            "outStatisticFieldName": "cnt"
        }]),
        "f": "json",
    }, timeout=30)
    data = r.json()
    counts = {}
    for feat in data.get("features", []):
        code = int(feat["attributes"]["LUCODE"])
        cnt = int(feat["attributes"]["cnt"])
        counts[code] = cnt
    return counts


def score_duplex_friendliness(counts: dict) -> dict:
    """Score how duplex-friendly the area is."""
    sfr = counts.get(111, 0)
    duplex = counts.get(112, 0)
    triplex = counts.get(113, 0)
    quad = counts.get(114, 0)
    multi = duplex + triplex + quad
    total = sfr + multi

    if total == 0:
        return {
            "nearby_sfr": 0,
            "nearby_duplex": 0,
            "nearby_triplex": 0,
            "nearby_quad": 0,
            "nearby_total": 0,
            "duplex_ratio": 0,
            "duplex_friendliness": "D - No residential nearby",
        }

    ratio = multi / total

    # Rating:
    # A = 15%+ multi-family — very duplex-friendly, established multi-family area
    # B = 5-15% — some duplexes exist, area is warming to it
    # C = 1-5% — mostly SFR but a few duplexes, possible pushback
    # D = 0% — pure SFR, you'd be the first duplex
    if ratio >= 0.15:
        grade = "A - Duplex-friendly area"
    elif ratio >= 0.05:
        grade = "B - Some duplexes nearby"
    elif multi > 0:
        grade = "C - Few duplexes, mostly SFR"
    else:
        grade = "D - All single-family"

    return {
        "nearby_sfr": sfr,
        "nearby_duplex": duplex,
        "nearby_triplex": triplex,
        "nearby_quad": quad,
        "nearby_total": total,
        "duplex_ratio": round(ratio * 100, 1),
        "duplex_friendliness": grade,
    }


def main():
    if not INPUT_CSV.exists():
        print(f"ERROR: {INPUT_CSV} not found")
        sys.exit(1)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Scoring duplex friendliness for {len(rows)} parcels...\n")

    # Batch fetch state plane centroids
    all_pids = [r["parcel_id"] for r in rows]
    centroids = {}
    batch_size = 50
    for i in range(0, len(all_pids), batch_size):
        batch = all_pids[i:i + batch_size]
        c = get_state_plane_centroids(batch)
        centroids.update(c)
        print(f"  Centroids batch {i // batch_size + 1}: {len(centroids)} total")
        time.sleep(0.2)

    # Score each parcel
    score_fields = [
        "nearby_sfr", "nearby_duplex", "nearby_triplex", "nearby_quad",
        "nearby_total", "duplex_ratio", "duplex_friendliness",
    ]
    out_fields = fieldnames + score_fields

    for i, row in enumerate(rows, 1):
        pid = row["parcel_id"]
        if pid not in centroids:
            print(f"  [{i}/{len(rows)}] {pid} - NO CENTROID")
            row.update({k: "" for k in score_fields})
            continue

        cx, cy = centroids[pid]
        counts = get_residential_mix(cx, cy)
        scores = score_duplex_friendliness(counts)
        row.update(scores)

        grade = scores["duplex_friendliness"].split(" - ")[0]
        print(f"  [{i}/{len(rows)}] {pid} | {scores['nearby_total']} nearby | {scores['duplex_ratio']}% multi | {grade}")
        time.sleep(0.1)

    # Write output
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    from collections import Counter
    grades = Counter(r.get("duplex_friendliness", "?").split(" - ")[0] for r in rows)
    print(f"\n{'='*50}")
    print(f"Duplex Friendliness Summary ({len(rows)} parcels):")
    for g in ["A", "B", "C", "D"]:
        print(f"  {g}: {grades.get(g, 0)} parcels")
    print(f"\nWrote {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
