"""
check_adjacency.py - Check if parcel owners also own adjacent properties.

Pipeline step 11: Reads step_10 (scored), queries GIS for neighboring
parcels within a 50ft buffer, checks if any neighbor shares the same
owner last name, and whether that neighbor has a building (suggesting
the owner lives next door). Writes step_11 (final).
"""

import argparse
import csv
import json
import sys
import time
from typing import Any, Dict, List, Tuple

from pipeline_common import (
    load_buybox,
    get_step_path,
    parse_owner_name,
    spatial_query,
)


def get_parcel_geometry(
    parcel_layer_url: str,
    parcel_id_field: str,
    parcel_id: str,
    wkid: int,
) -> Dict[str, Any]:
    """Fetch a single parcel's geometry from GIS.

    Args:
        parcel_layer_url: ArcGIS REST layer URL (without /query).
        parcel_id_field: GIS field name for parcel ID.
        parcel_id: The parcel ID to fetch.
        wkid: Spatial reference WKID for output geometry.

    Returns:
        Geometry dict with 'rings', or empty dict if not found.
    """
    import requests

    query_url = parcel_layer_url.rstrip("/") + "/query"
    escaped = parcel_id.replace("'", "''")
    params = {
        "where": f"{parcel_id_field} = '{escaped}'",
        "outFields": parcel_id_field,
        "outSR": wkid,
        "returnGeometry": "true",
        "f": "json",
    }

    resp = requests.post(query_url, data=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    features = data.get("features", [])
    if features:
        return features[0].get("geometry", {})
    return {}


def query_neighbors(
    parcel_layer_url: str,
    geometry: Dict[str, Any],
    parcel_id_field: str,
    owner_field: str,
    building_value_field: str,
    exclude_parcel_id: str,
    wkid: int,
) -> List[Dict[str, Any]]:
    """Query neighboring parcels within 50ft of the given geometry.

    Args:
        parcel_layer_url: ArcGIS REST query endpoint.
        geometry: Parcel geometry dict (with 'rings').
        parcel_id_field: GIS field name for parcel ID.
        owner_field: GIS field name for owner name.
        building_value_field: GIS field name for building value.
        exclude_parcel_id: Parcel ID to exclude (the target parcel itself).
        wkid: Spatial reference WKID.

    Returns:
        List of neighbor attribute dicts.
    """
    query_url = parcel_layer_url.rstrip("/") + "/query"

    escaped = exclude_parcel_id.replace("'", "''")
    where = f"{parcel_id_field} <> '{escaped}'"

    out_fields = f"{parcel_id_field},{owner_field},{building_value_field}"

    # Use geometry with distance buffer
    geom_str = json.dumps(geometry)

    params = {
        "geometry": geom_str,
        "geometryType": "esriGeometryPolygon",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": 50,
        "units": "esriSRUnit_Foot",
        "where": where,
        "outFields": out_fields,
        "inSR": wkid,
        "returnGeometry": "false",
        "f": "json",
    }

    import requests

    resp = requests.post(query_url, data=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    return [f["attributes"] for f in data.get("features", [])]


def extract_last_name_keywords(owner_name: str) -> List[str]:
    """Extract last name keywords from an owner name for matching.

    Uses parse_owner_name to get the last name, then splits on spaces
    to handle multi-word last names. Filters out short tokens (<=2 chars)
    that are likely initials or suffixes.

    Args:
        owner_name: Raw owner name string.

    Returns:
        List of uppercase last name keywords (length > 2).
    """
    _, last = parse_owner_name(owner_name)
    if not last:
        return []

    # Split on spaces for multi-word last names
    keywords = [w.upper().strip() for w in last.split() if len(w.strip()) > 2]
    return keywords


def main():
    parser = argparse.ArgumentParser(description="Check adjacency for parcel owners")
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)
    county = buybox.county
    fm = county.field_map
    parcel_id_field = fm.get("parcel_id", "PARCEL_ID")
    owner_field = fm.get("owner_name", "OWNER_NAME")
    building_value_field = fm.get("building_value", "BUILDING_VALUE")
    native_wkid = county.parcel_layer_wkid
    parcel_layer_url = county.parcel_layer_url

    # Read input CSV (step_10 scored)
    input_path = get_step_path(buybox, 10, "scored")
    print(f"Reading: {input_path}")

    rows = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} parcels")

    if args.dry_run:
        print("[DRY RUN] Would check adjacency for each parcel. Exiting.")
        return

    # Process each parcel
    new_cols = ["owner_adjacent", "owner_lives_adjacent", "adjacent_details"]
    out_fieldnames = fieldnames + [c for c in new_cols if c not in fieldnames]

    adjacent_count = 0
    lives_adjacent_count = 0

    for idx, row in enumerate(rows):
        pid = row.get("parcel_id", "")
        owner_name = row.get("owner_name", "")

        row["owner_adjacent"] = "False"
        row["owner_lives_adjacent"] = "False"
        row["adjacent_details"] = ""

        if not pid or not owner_name:
            continue

        # Progress
        if (idx + 1) % 10 == 0 or idx == 0:
            print(f"  Processing {idx + 1}/{len(rows)}: {pid}")

        # Get parcel geometry from GIS
        geom = get_parcel_geometry(
            parcel_layer_url, parcel_id_field, pid, native_wkid
        )

        if not geom or not geom.get("rings"):
            row["adjacent_details"] = "No geometry found"
            time.sleep(0.2)
            continue

        # Query neighbors within 50ft
        neighbors = query_neighbors(
            parcel_layer_url,
            geom,
            parcel_id_field,
            owner_field,
            building_value_field,
            exclude_parcel_id=pid,
            wkid=native_wkid,
        )

        time.sleep(0.2)  # Rate limiting between API calls

        if not neighbors:
            row["adjacent_details"] = "No neighbors found"
            continue

        # Extract last name keywords from the target parcel owner
        last_keywords = extract_last_name_keywords(owner_name)
        if not last_keywords:
            row["adjacent_details"] = f"{len(neighbors)} neighbors, no parseable owner name"
            continue

        # Check each neighbor for matching owner last name
        matching_neighbors = []
        for nbr in neighbors:
            nbr_owner = str(nbr.get(owner_field, ""))
            nbr_pid = str(nbr.get(parcel_id_field, ""))
            nbr_bldg = nbr.get(building_value_field, 0)

            # Check if any last name keyword matches the neighbor's owner
            nbr_upper = nbr_owner.upper()
            matched = any(kw in nbr_upper for kw in last_keywords)

            if matched:
                try:
                    bldg_val = float(str(nbr_bldg).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    bldg_val = 0

                matching_neighbors.append({
                    "parcel_id": nbr_pid,
                    "owner": nbr_owner,
                    "building_value": bldg_val,
                    "lives_there": bldg_val > 0,
                })

        if matching_neighbors:
            row["owner_adjacent"] = "True"
            adjacent_count += 1

            # Check if any matching neighbor has a building (owner lives there)
            lives_there = any(n["lives_there"] for n in matching_neighbors)
            if lives_there:
                row["owner_lives_adjacent"] = "True"
                lives_adjacent_count += 1

            # Build details string
            details = []
            for n in matching_neighbors:
                flag = " (LIVES HERE)" if n["lives_there"] else ""
                details.append(f"{n['parcel_id']}: {n['owner']}{flag}")
            row["adjacent_details"] = "; ".join(details)
        else:
            row["adjacent_details"] = f"{len(neighbors)} neighbors, no owner match"

    # Write output CSV (step_11 final)
    output_path = get_step_path(buybox, 11, "final")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    print(f"\n--- Adjacency Summary ---")
    print(f"Total parcels: {len(rows)}")
    print(f"Owner has adjacent property: {adjacent_count}")
    print(f"Owner lives adjacent: {lives_adjacent_count}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
