"""
compute_acreage.py - Compute real acreage and centroid from parcel polygon geometry.

Pipeline step 07: Reads step_06 (with_utilities), batch-fetches parcel
geometries from the county GIS in both native WKID (for accurate acreage)
and WGS84/4326 (for lat/lon centroid and Leaflet map display), then writes
step_07 (with_acreage).
"""

import argparse
import csv
import json
import sys
import time
from typing import Any, Dict, List, Tuple

from pipeline_common import (
    compute_acres_from_rings,
    compute_centroid,
    load_buybox,
    get_step_path,
    paginated_query,
)


def fetch_parcel_geometries(
    parcel_layer_url: str,
    parcel_id_field: str,
    parcel_ids: List[str],
    out_sr: int,
) -> Dict[str, Any]:
    """Batch-fetch parcel geometries from GIS in a given spatial reference.

    Args:
        parcel_layer_url: ArcGIS REST layer URL (without /query).
        parcel_id_field: GIS field name for parcel ID.
        parcel_ids: List of parcel IDs to fetch.
        out_sr: Output spatial reference WKID.

    Returns:
        Dict mapping parcel_id -> geometry dict (with 'rings').
    """
    query_url = parcel_layer_url.rstrip("/") + "/query"
    result: Dict[str, Any] = {}

    batch_size = 50
    for i in range(0, len(parcel_ids), batch_size):
        batch = parcel_ids[i : i + batch_size]
        escaped = [pid.replace("'", "''") for pid in batch]
        id_list = ",".join(f"'{pid}'" for pid in escaped)
        where = f"{parcel_id_field} IN ({id_list})"

        features = paginated_query(
            query_url,
            params={
                "where": where,
                "outFields": parcel_id_field,
                "outSR": out_sr,
                "returnGeometry": "true",
                "f": "json",
            },
        )

        for feat in features:
            pid = str(feat.get("attributes", {}).get(parcel_id_field, ""))
            geom = feat.get("geometry", {})
            if pid and geom.get("rings"):
                result[pid] = geom

        if i + batch_size < len(parcel_ids):
            time.sleep(0.1)

        done = min(i + batch_size, len(parcel_ids))
        print(f"  Fetched geometries: {done}/{len(parcel_ids)}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Compute real acreage and centroid from GIS geometry")
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)
    county = buybox.county
    fm = county.field_map
    parcel_id_field = fm.get("parcel_id", "PARCEL_ID")
    native_wkid = county.parcel_layer_wkid
    parcel_layer_url = county.parcel_layer_url

    # Read input CSV (step_06 with_utilities)
    input_path = get_step_path(buybox, 6, "with_utilities")
    print(f"Reading: {input_path}")

    rows = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} parcels")
    print(f"Native WKID: {native_wkid}")

    if args.dry_run:
        print("[DRY RUN] Would fetch geometries and compute acreage. Exiting.")
        return

    # Collect parcel IDs
    parcel_ids = [row.get("parcel_id", "") for row in rows]
    parcel_ids = [pid for pid in parcel_ids if pid]

    # Fetch geometries in native WKID (for accurate acreage in state plane feet)
    print(f"\nFetching geometries in native WKID {native_wkid} (for acreage)...")
    native_geoms = fetch_parcel_geometries(
        parcel_layer_url, parcel_id_field, parcel_ids, native_wkid
    )
    print(f"  Got {len(native_geoms)} geometries in native WKID")

    # Fetch geometries in WGS84/4326 (for lat/lon centroid and Leaflet rings)
    print(f"\nFetching geometries in WGS84/4326 (for centroid & map display)...")
    wgs84_geoms = fetch_parcel_geometries(
        parcel_layer_url, parcel_id_field, parcel_ids, 4326
    )
    print(f"  Got {len(wgs84_geoms)} geometries in WGS84")

    # Compute acreage and centroid for each parcel
    new_cols = ["computed_acres", "lat", "lon", "geometry_rings"]
    out_fieldnames = fieldnames + [c for c in new_cols if c not in fieldnames]

    no_native = 0
    no_wgs84 = 0

    for row in rows:
        pid = row.get("parcel_id", "")

        # Acreage from native WKID geometry
        native_geom = native_geoms.get(pid)
        if native_geom and native_geom.get("rings"):
            acres = compute_acres_from_rings(native_geom["rings"], wkid=native_wkid)
            row["computed_acres"] = f"{acres:.4f}"
        else:
            row["computed_acres"] = ""
            no_native += 1

        # Centroid and rings from WGS84 geometry
        wgs84_geom = wgs84_geoms.get(pid)
        if wgs84_geom and wgs84_geom.get("rings"):
            rings_4326 = wgs84_geom["rings"]
            cx, cy = compute_centroid(rings_4326)
            # ArcGIS returns [lon, lat] for WGS84; centroid gives (cx=lon, cy=lat)
            row["lat"] = f"{cy:.6f}"
            row["lon"] = f"{cx:.6f}"
            # Store rings as JSON for later map display
            row["geometry_rings"] = json.dumps(rings_4326)
        else:
            row["lat"] = ""
            row["lon"] = ""
            row["geometry_rings"] = ""
            no_wgs84 += 1

    # Write output CSV (step_07 with_acreage)
    output_path = get_step_path(buybox, 7, "with_acreage")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    has_acres = sum(1 for r in rows if r.get("computed_acres"))
    print(f"\n--- Acreage Summary ---")
    print(f"Total parcels: {len(rows)}")
    print(f"With computed acres: {has_acres}")
    print(f"Missing native geometry: {no_native}")
    print(f"Missing WGS84 geometry: {no_wgs84}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
