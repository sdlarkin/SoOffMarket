"""
check_utilities.py - Check which parcels have city water and sewer access.

Pipeline step 06: Reads step_05 (geo_filtered), queries utility district
polygons from the county's water/sewer ArcGIS layers, performs spatial
intersection to determine which parcels fall within service areas, and
writes step_06 (with_utilities).
"""

import argparse
import csv
import json
import sys
import time
from typing import Any, Dict, List, Optional

from pipeline_common import (
    load_buybox,
    get_step_path,
    paginated_query,
    simplify_rings,
    spatial_query,
)


def fetch_utility_districts(
    layer_url: str,
    provider_field: str,
) -> List[Dict[str, Any]]:
    """Fetch all utility district polygons from an ArcGIS layer.

    Args:
        layer_url: ArcGIS REST layer URL (without /query).
        provider_field: Field name containing the provider/district name.

    Returns:
        List of dicts with 'name' (provider) and 'rings' (polygon rings).
    """
    query_url = layer_url.rstrip("/") + "/query"
    features = paginated_query(
        query_url,
        params={
            "where": "1=1",
            "outFields": provider_field,
            "returnGeometry": "true",
            "f": "json",
        },
    )

    districts = []
    for feat in features:
        name = feat.get("attributes", {}).get(provider_field, "Unknown")
        geom = feat.get("geometry", {})
        rings = geom.get("rings", [])
        if rings:
            districts.append({"name": name or "Unknown", "rings": rings})

    return districts


def count_ring_points(rings: List[List[List[float]]]) -> int:
    """Count total points across all rings."""
    return sum(len(ring) for ring in rings)


def check_parcels_in_district(
    parcel_layer_url: str,
    district_rings: List[List[List[float]]],
    parcel_ids: List[str],
    parcel_id_field: str,
    in_sr: int,
) -> List[str]:
    """Check which parcels from a list fall within a utility district polygon.

    Batches parcel IDs in groups of 50 to avoid query size limits.

    Args:
        parcel_layer_url: ArcGIS REST query endpoint for parcels.
        district_rings: Polygon rings for the utility district.
        parcel_ids: List of parcel IDs to check.
        parcel_id_field: GIS field name for parcel ID.
        in_sr: Input spatial reference WKID (from parcel layer).

    Returns:
        List of parcel IDs that fall within the district.
    """
    # Simplify large polygons to avoid request size limits
    rings_for_query = district_rings
    if count_ring_points(district_rings) > 1500:
        rings_for_query = simplify_rings(district_rings, keep_every_n=5)

    geometry = {"rings": rings_for_query}
    matched_ids = []

    # Batch parcel IDs in groups of 50
    batch_size = 50
    for i in range(0, len(parcel_ids), batch_size):
        batch = parcel_ids[i : i + batch_size]
        # Build WHERE clause to filter to our parcels
        escaped = [pid.replace("'", "''") for pid in batch]
        id_list = ",".join(f"'{pid}'" for pid in escaped)
        where = f"{parcel_id_field} IN ({id_list})"

        results = spatial_query(
            parcel_layer_url,
            geometry=geometry,
            geometry_type="esriGeometryPolygon",
            spatial_rel="esriSpatialRelIntersects",
            where=where,
            out_fields=parcel_id_field,
            in_sr=in_sr,
            return_geometry=False,
        )

        for attr in results:
            pid = str(attr.get(parcel_id_field, ""))
            if pid:
                matched_ids.append(pid)

        time.sleep(0.1)  # Small delay between batches

    return matched_ids


def main():
    parser = argparse.ArgumentParser(description="Check utility access for parcels")
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)
    county = buybox.county
    fm = county.field_map
    parcel_id_field = fm.get("parcel_id", "PARCEL_ID")
    parcel_layer_url = county.parcel_layer_url.rstrip("/") + "/query"
    in_sr = county.parcel_layer_wkid

    # Determine utility layer availability
    water_url = getattr(county, "water_layer_url", "") or ""
    sewer_url = getattr(county, "sewer_layer_url", "") or ""
    water_provider_field = getattr(county, "water_layer_provider_field", "DISTRICT") or "DISTRICT"
    sewer_provider_field = getattr(county, "sewer_layer_provider_field", "ServiceProvider") or "ServiceProvider"

    has_water_layer = bool(water_url.strip())
    has_sewer_layer = bool(sewer_url.strip())

    print(f"Water layer: {'available' if has_water_layer else 'NOT configured (marking Unknown)'}")
    print(f"Sewer layer: {'available' if has_sewer_layer else 'NOT configured (marking Unknown)'}")

    # Read input CSV (step_05 geo_filtered)
    input_path = get_step_path(buybox, 5, "geo_filtered")
    print(f"Reading: {input_path}")

    rows = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} parcels")

    if args.dry_run:
        print("[DRY RUN] Would process utilities for these parcels. Exiting.")
        return

    # Collect all parcel IDs
    parcel_ids = [row.get("parcel_id", "") for row in rows]
    parcel_ids = [pid for pid in parcel_ids if pid]

    # Initialize utility columns
    water_map: Dict[str, str] = {}  # parcel_id -> provider name
    sewer_map: Dict[str, str] = {}

    # --- Water layer ---
    if has_water_layer:
        print(f"\nFetching water district polygons from: {water_url}")
        water_districts = fetch_utility_districts(water_url, water_provider_field)
        print(f"  Found {len(water_districts)} water district polygons")

        for idx, district in enumerate(water_districts):
            name = district["name"]
            print(f"  Checking water district [{idx+1}/{len(water_districts)}]: {name} "
                  f"({count_ring_points(district['rings'])} pts)")

            matched = check_parcels_in_district(
                parcel_layer_url,
                district["rings"],
                parcel_ids,
                parcel_id_field,
                in_sr,
            )
            for pid in matched:
                water_map[pid] = str(name)

            print(f"    -> {len(matched)} parcels in this district")
    else:
        for pid in parcel_ids:
            water_map[pid] = "Unknown"

    # --- Sewer layer ---
    if has_sewer_layer:
        print(f"\nFetching sewer district polygons from: {sewer_url}")
        sewer_districts = fetch_utility_districts(sewer_url, sewer_provider_field)
        print(f"  Found {len(sewer_districts)} sewer district polygons")

        for idx, district in enumerate(sewer_districts):
            name = district["name"]
            print(f"  Checking sewer district [{idx+1}/{len(sewer_districts)}]: {name} "
                  f"({count_ring_points(district['rings'])} pts)")

            matched = check_parcels_in_district(
                parcel_layer_url,
                district["rings"],
                parcel_ids,
                parcel_id_field,
                in_sr,
            )
            for pid in matched:
                sewer_map[pid] = str(name)

            print(f"    -> {len(matched)} parcels in this district")
    else:
        for pid in parcel_ids:
            sewer_map[pid] = "Unknown"

    # --- Build output rows ---
    output_path = get_step_path(buybox, 6, "with_utilities")
    new_cols = ["water_provider", "sewer_provider", "utilities_score"]
    out_fieldnames = fieldnames + [c for c in new_cols if c not in fieldnames]

    for row in rows:
        pid = row.get("parcel_id", "")
        water = water_map.get(pid, "None")
        sewer = sewer_map.get(pid, "None")

        row["water_provider"] = water
        row["sewer_provider"] = sewer

        # Score: count available utilities (water, sewer, electric assumed present)
        score = 1  # Electric assumed for all parcels
        if water not in ("None", ""):
            score += 1
        if sewer not in ("None", ""):
            score += 1
        row["utilities_score"] = f"{score}/3"

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    water_count = sum(1 for r in rows if r["water_provider"] not in ("None", ""))
    sewer_count = sum(1 for r in rows if r["sewer_provider"] not in ("None", ""))
    print(f"\n--- Utilities Summary ---")
    print(f"Total parcels: {len(rows)}")
    print(f"With water: {water_count}")
    print(f"With sewer: {sewer_count}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
