"""
score_duplex.py - Pipeline Step 10: Calculate duplex friendliness score.

Queries nearby residential properties within 0.25 miles and computes:
  - Count of SFR vs duplex/multi-family
  - Duplex ratio (% of nearby residential that are multi-family)
  - Duplex friendliness rating (A/B/C/D)

If buybox.duplex_scoring_enabled is False, copies input to output unchanged.

Usage:
    python score_duplex.py --buybox-id <UUID>
    python score_duplex.py --buybox-id <UUID> --dry-run
"""

import argparse
import csv
import json
import shutil
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Tuple

import requests

from pipeline_common import (
    get_step_path,
    load_buybox,
    spatial_query,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Search radius: 0.25 miles in feet
SEARCH_RADIUS_FT = 1320

# Standard ArcGIS land use codes
LU_SFR = 111
LU_DUPLEX = 112
LU_TRIPLEX = 113
LU_QUAD = 114
RESIDENTIAL_CODES = [LU_SFR, LU_DUPLEX, LU_TRIPLEX, LU_QUAD]

# Duplex friendliness grade thresholds
GRADE_A_THRESHOLD = 0.15   # >= 15% multi-family
GRADE_B_THRESHOLD = 0.05   # >= 5%
# C = > 0%, D = 0%

# Batch size for centroid fetches
CENTROID_BATCH_SIZE = 50

# Output columns added by this step
SCORE_FIELDS = [
    "nearby_sfr", "nearby_duplex", "nearby_triplex", "nearby_quad",
    "nearby_total", "duplex_ratio", "duplex_friendliness",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_state_plane_centroids(
    parcel_url: str, tax_map_nos: List[str],
    parcel_id_field: str, wkid: int,
) -> Dict[str, Tuple[float, float]]:
    """Batch fetch centroids in native WKID for spatial queries."""
    ids_str = ",".join(f"'{pid}'" for pid in tax_map_nos)
    r = requests.post(parcel_url.rstrip("/") + "/query", data={
        "where": f"{parcel_id_field} IN ({ids_str})",
        "outFields": parcel_id_field,
        "returnGeometry": "true",
        "outSR": str(wkid),
        "f": "json",
    }, timeout=30)
    data = r.json()
    centroids = {}
    for feat in data.get("features", []):
        pid = feat["attributes"][parcel_id_field]
        rings = feat.get("geometry", {}).get("rings", [[]])
        if rings and rings[0]:
            pts = rings[0]
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            centroids[pid] = (cx, cy)
    return centroids


def get_residential_mix(
    parcel_url: str, cx: float, cy: float,
    field_map: Dict[str, str], wkid: int,
) -> Dict[int, int]:
    """Query nearby residential properties using groupByFieldsForStatistics.
    Returns {land_use_code: count}."""
    bldg_field = field_map.get("building_value", "BUILDVALUE")
    lu_field = field_map.get("land_use", "LUCODE")
    codes_str = ",".join(str(c) for c in RESIDENTIAL_CODES)

    point = {"x": cx, "y": cy, "spatialReference": {"wkid": wkid}}
    r = requests.post(parcel_url.rstrip("/") + "/query", data={
        "where": f"{bldg_field} > 0 AND {lu_field} IN ({codes_str})",
        "geometry": json.dumps(point),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(SEARCH_RADIUS_FT),
        "units": "esriSRUnit_Foot",
        "inSR": str(wkid),
        "outFields": "",
        "groupByFieldsForStatistics": lu_field,
        "outStatistics": json.dumps([{
            "statisticType": "count",
            "onStatisticField": "OBJECTID",
            "outStatisticFieldName": "cnt",
        }]),
        "f": "json",
    }, timeout=30)
    data = r.json()
    counts = {}
    for feat in data.get("features", []):
        code = int(feat["attributes"][lu_field])
        cnt = int(feat["attributes"]["cnt"])
        counts[code] = cnt
    return counts


def score_duplex_friendliness(counts: Dict[int, int]) -> Dict[str, Any]:
    """Score how duplex-friendly the area is based on land use counts."""
    sfr = counts.get(LU_SFR, 0)
    duplex = counts.get(LU_DUPLEX, 0)
    triplex = counts.get(LU_TRIPLEX, 0)
    quad = counts.get(LU_QUAD, 0)
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

    if ratio >= GRADE_A_THRESHOLD:
        grade = "A - Duplex-friendly area"
    elif ratio >= GRADE_B_THRESHOLD:
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


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(buybox) -> None:
    """Score duplex friendliness for all parcels in step_09 CSV."""
    county = buybox.county
    parcel_url = county.parcel_layer_url
    field_map = county.field_map
    wkid = county.parcel_layer_wkid
    pid_field = field_map.get("parcel_id", "TAX_MAP_NO")

    input_path = get_step_path(buybox, 9, "comped")
    output_path = get_step_path(buybox, 10, "scored")

    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    # Check if duplex scoring is enabled
    if not buybox.duplex_scoring_enabled:
        print("Duplex scoring disabled for this buybox. Copying input to output unchanged.")
        shutil.copy2(input_path, output_path)
        print(f"  Copied: {input_path} -> {output_path}")
        return

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Scoring duplex friendliness for {len(rows)} parcels...\n")

    # Batch fetch state plane centroids
    all_pids = [r.get("parcel_id", "").strip() for r in rows]
    centroids = {}
    for i in range(0, len(all_pids), CENTROID_BATCH_SIZE):
        batch = all_pids[i:i + CENTROID_BATCH_SIZE]
        c = get_state_plane_centroids(parcel_url, batch, pid_field, wkid)
        centroids.update(c)
        print(f"  Centroids batch {i // CENTROID_BATCH_SIZE + 1}: {len(centroids)} total")
        time.sleep(0.2)

    # Score each parcel
    out_fields = fieldnames + SCORE_FIELDS

    for i, row in enumerate(rows, 1):
        pid = row.get("parcel_id", "").strip()
        if pid not in centroids:
            print(f"  [{i}/{len(rows)}] {pid} - NO CENTROID")
            row.update({k: "" for k in SCORE_FIELDS})
            continue

        cx, cy = centroids[pid]
        counts = get_residential_mix(parcel_url, cx, cy, field_map, wkid)
        scores = score_duplex_friendliness(counts)
        row.update(scores)

        grade = scores["duplex_friendliness"].split(" - ")[0]
        print(f"  [{i}/{len(rows)}] {pid} | {scores['nearby_total']} nearby | {scores['duplex_ratio']}% multi | {grade}")
        time.sleep(0.1)

    # Write output
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    grades = Counter(r.get("duplex_friendliness", "?").split(" - ")[0] for r in rows)
    print(f"\n{'=' * 60}")
    print(f"Step 10 - Duplex Friendliness ({len(rows)} parcels)")
    for g in ["A", "B", "C", "D"]:
        print(f"  {g}: {grades.get(g, 0)} parcels")
    print(f"  Output: {output_path}")


def dry_run(buybox) -> None:
    """Print configuration without making API calls."""
    county = buybox.county
    input_path = get_step_path(buybox, 9, "comped")
    output_path = get_step_path(buybox, 10, "scored")

    print("=" * 60)
    print("DRY RUN - score_duplex.py (Step 10)")
    print("=" * 60)
    print()
    print(f"BuyBox:               {buybox.pk}")
    print(f"Buyer:                {buybox.buyer}")
    print(f"County:               {county}")
    print(f"Duplex scoring:       {'ENABLED' if buybox.duplex_scoring_enabled else 'DISABLED'}")
    print(f"Search radius:        {SEARCH_RADIUS_FT} ft ({SEARCH_RADIUS_FT / 5280:.2f} mi)")
    print(f"Parcel layer URL:     {county.parcel_layer_url}")
    print(f"Parcel layer WKID:    {county.parcel_layer_wkid}")
    print()
    print(f"Input:                {input_path}")
    print(f"Output:               {output_path}")
    print(f"Input exists:         {input_path.exists()}")
    print()
    print("Grade thresholds:")
    print(f"  A: >= {GRADE_A_THRESHOLD * 100:.0f}% multi-family")
    print(f"  B: >= {GRADE_B_THRESHOLD * 100:.0f}% multi-family")
    print(f"  C: > 0% multi-family")
    print(f"  D: 0% multi-family")
    print()
    print("No API calls made.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Step 10: Score duplex friendliness for parcels."
    )
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print config without API calls.")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)

    if args.dry_run:
        dry_run(buybox)
    else:
        run_pipeline(buybox)


if __name__ == "__main__":
    main()
