"""
Filter scraped assessor parcels to remove non-actionable rows.
Removes parcels owned by government, HOAs, churches, or other entities
that are unlikely to sell to an individual buyer.
Outputs a filtered CSV ready for enrichment.
"""

import csv
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"

INPUT_CSV = TMP_DIR / "sara_holt_parcels_scraped.csv"
OUTPUT_CSV = TMP_DIR / "sara_holt_parcels_filtered.csv"

# Keywords in owner names that indicate non-actionable parcels
EXCLUDE_KEYWORDS = [
    "CITY OF", "COUNTY", "STATE OF", "UNITED STATES",
    "CHURCH", "BAPTIST", "METHODIST", "MINISTRY", "MINISTRIES",
    "HOMEOWNERS ASSOC", "COMMUNITY ASSOC", "HOA",
    "SCHOOL", "BOARD OF EDUCATION",
    "UTILITY", "ELECTRIC", "WATER DIST",
]


def is_excluded(owner: str) -> bool:
    owner_upper = owner.upper()
    return any(kw in owner_upper for kw in EXCLUDE_KEYWORDS)


def main():
    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    kept = []
    removed = []
    for row in rows:
        owner = row.get("owner", "")
        if is_excluded(owner):
            removed.append(row)
        else:
            kept.append(row)

    print(f"Total parcels: {len(rows)}")
    print(f"Kept: {len(kept)}")
    print(f"Removed: {len(removed)}")
    for r in removed:
        print(f"  X  {r['parcel_id']} - {r['owner']}")
    print()
    for k in kept:
        print(f"  OK {k['parcel_id']} - {k['owner']} - {k['location']}")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\nWrote {len(kept)} filtered records to {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
