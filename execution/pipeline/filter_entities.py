"""
filter_entities.py - Pipeline Step 04: Remove entity-owned parcels.

Reads the step_03 CSV (raw parcels), filters out rows where the owner name
matches known entity keywords (government, religious, business, etc.),
and writes the surviving parcels to step_04.

Usage:
    python filter_entities.py --buybox-id <UUID> [--dry-run]
"""

import argparse
import csv
import sys

from pipeline_common import (
    UNIVERSAL_ENTITY_KEYWORDS,
    get_step_path,
    is_excluded_entity,
    load_buybox,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 04: Filter out entity-owned parcels."
    )
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview results without writing the output file.",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load BuyBox and resolve paths / field names
    # ------------------------------------------------------------------
    buybox = load_buybox(args.buybox_id)
    county = buybox.county

    county_keywords = county.entity_keywords or []
    owner_field = county.field_map.get("owner_name", "OWNER_NAME")

    input_path = get_step_path(buybox, 3, "parcels_raw")
    output_path = get_step_path(buybox, 4, "entities_filtered")

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Read and filter
    # ------------------------------------------------------------------
    kept_rows = []
    removed_samples = []
    total = 0

    with open(input_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames

        for row in reader:
            total += 1
            owner = row.get(owner_field, "")

            if is_excluded_entity(owner, county_keywords=county_keywords):
                if len(removed_samples) < 10:
                    removed_samples.append(owner)
            else:
                kept_rows.append(row)

    kept = len(kept_rows)
    removed = total - kept

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"Step 04 — Entity Filter")
    print(f"  Input:   {input_path}")
    print(f"  Total:   {total:,}")
    print(f"  Kept:    {kept:,}")
    print(f"  Removed: {removed:,}")
    if removed_samples:
        print(f"  Sample removals:")
        for name in removed_samples:
            print(f"    - {name}")

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    if args.dry_run:
        print("\n  [DRY RUN] No output file written.")
        return

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept_rows)

    print(f"  Output:  {output_path}")


if __name__ == "__main__":
    main()
