"""
filter_geography.py - Pipeline Step 05: Filter parcels by target geography.

Reads the step_04 CSV (entity-filtered parcels), applies district-level
geography rules from the BuyBox's target_geography config, and writes
surviving parcels to step_05.

Usage:
    python filter_geography.py --buybox-id <UUID> [--dry-run]
"""

import argparse
import csv
import shutil
import sys

from pipeline_common import get_step_path, load_buybox


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 05: Filter parcels by target geography / districts."
    )
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview results without writing the output file.",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load BuyBox and resolve paths / config
    # ------------------------------------------------------------------
    buybox = load_buybox(args.buybox_id)
    county = buybox.county

    input_path = get_step_path(buybox, 4, "entities_filtered")
    output_path = get_step_path(buybox, 5, "geo_filtered")

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    geo = buybox.target_geography or {}

    # If no geography config, skip filtering entirely.
    if not geo:
        print("Step 05 — Geography Filter")
        print("  No target_geography configured — copying input to output.")
        if not args.dry_run:
            shutil.copy2(input_path, output_path)
            print(f"  Output: {output_path}")
        else:
            print("  [DRY RUN] No output file written.")
        return

    # Parse geography config
    target_districts = set(str(d) for d in geo.get("target_districts", []))
    exclude_districts = set(str(d) for d in geo.get("exclude_districts", []))
    mixed_districts = geo.get("mixed_districts", {})
    # Normalise mixed district keys to strings
    mixed_districts = {str(k): v for k, v in mixed_districts.items()}

    # Resolve the district and address field names from the county field_map
    district_field = county.field_map.get("district", "DISTRICT")
    address_field = county.field_map.get("address", "ADDRESS")

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
            district = str(row.get(district_field, "")).strip()
            keep = True

            if district in exclude_districts:
                keep = False

            elif district in target_districts:
                keep = True

            elif district in mixed_districts:
                # Mixed district: keep unless address contains an
                # excluded keyword.
                mixed_cfg = mixed_districts[district]
                exclude_kws = mixed_cfg.get("exclude_address_keywords", [])
                address = (row.get(address_field, "") or "").upper()

                for kw in exclude_kws:
                    if kw.upper() in address:
                        keep = False
                        break

            else:
                # Unknown district — keep for human review
                keep = True

            if keep:
                kept_rows.append(row)
            else:
                if len(removed_samples) < 10:
                    removed_samples.append(
                        f"district={district}  addr={row.get(address_field, '')}"
                    )

    kept = len(kept_rows)
    removed = total - kept

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"Step 05 — Geography Filter")
    print(f"  Input:   {input_path}")
    print(f"  Total:   {total:,}")
    print(f"  Kept:    {kept:,}")
    print(f"  Removed: {removed:,}")
    if removed_samples:
        print(f"  Sample removals:")
        for sample in removed_samples:
            print(f"    - {sample}")

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
