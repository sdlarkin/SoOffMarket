"""
filter_lot_shape.py - Filter out unbuildable lot shapes and too-small parcels.

Pipeline step 08: Reads step_07 (with_acreage), computes Polsby-Popper
compactness from WGS84 geometry rings, filters out parcels that are too
narrow/irregular or too small by real computed acreage, and writes step_08
(buildable).

The geometry_rings stored in step_07 are in WGS84 [[lon,lat],...] format.
For compactness, we need approximate feet. We use the lat_scale/lon_scale
conversion from pipeline_common: at ~35N, lat_scale=364000, lon_scale=298000
ft/degree. compute_compactness with wkid=4326 handles this internally.
"""

import argparse
import csv
import json
import sys
from typing import List

from pipeline_common import (
    compute_compactness,
    load_buybox,
    get_step_path,
)


def main():
    parser = argparse.ArgumentParser(description="Filter parcels by lot shape and minimum acreage")
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)
    min_compactness = buybox.min_compactness or 0.25
    min_acres = buybox.min_acres or 0.0

    print(f"Min compactness: {min_compactness}")
    print(f"Min acres (real): {min_acres}")

    # Read input CSV (step_07 with_acreage)
    input_path = get_step_path(buybox, 7, "with_acreage")
    print(f"Reading: {input_path}")

    rows = []
    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} parcels")

    if args.dry_run:
        print("[DRY RUN] Would filter by shape and acreage. Exiting.")
        return

    # Process each parcel
    kept = []
    removed_shape = 0
    removed_small = 0
    no_geometry = 0

    new_cols = ["compactness"]
    out_fieldnames = fieldnames + [c for c in new_cols if c not in fieldnames]

    for row in rows:
        # Parse geometry rings from JSON
        rings_json = row.get("geometry_rings", "")
        if not rings_json:
            # No geometry available - keep the parcel but mark compactness as unknown
            row["compactness"] = ""
            kept.append(row)
            no_geometry += 1
            continue

        try:
            rings = json.loads(rings_json)
        except (json.JSONDecodeError, TypeError):
            row["compactness"] = ""
            kept.append(row)
            no_geometry += 1
            continue

        # Compute compactness using WGS84 coordinates
        # pipeline_common.compute_compactness with wkid=4326 handles the
        # degree-to-feet conversion internally
        compactness = compute_compactness(rings, wkid=4326)
        row["compactness"] = f"{compactness:.4f}"

        # Check compactness threshold
        if compactness < min_compactness:
            removed_shape += 1
            continue

        # Check minimum acreage by real computed measurement
        computed_acres_str = row.get("computed_acres", "")
        if computed_acres_str:
            try:
                computed_acres = float(computed_acres_str)
                if computed_acres < min_acres:
                    removed_small += 1
                    continue
            except (ValueError, TypeError):
                pass  # Keep if we can't parse - let downstream handle it

        kept.append(row)

    # Write output CSV (step_08 buildable)
    output_path = get_step_path(buybox, 8, "buildable")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    # Summary
    print(f"\n--- Lot Shape Filter Summary ---")
    print(f"Input parcels: {len(rows)}")
    print(f"Removed for bad shape (compactness < {min_compactness}): {removed_shape}")
    print(f"Removed for too small (acres < {min_acres}): {removed_small}")
    print(f"No geometry (kept): {no_geometry}")
    print(f"Kept: {len(kept)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
