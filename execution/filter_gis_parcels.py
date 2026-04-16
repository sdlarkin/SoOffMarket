"""
Filter GIS-queried R-2 vacant parcels for a specific buyer's criteria.

Filters applied:
  1. Entity filter - remove government, HOA, church, institutional owners
  2. Geography filter - keep only parcels in buyer's target areas
  3. Segment by acreage into separate output files

Buyer: Sara Holt
Target areas: Chattanooga, Ooltewah, Collegedale
"""

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"

INPUT_CSV = TMP_DIR / "gis_r2_vacant_parcels.csv"
OUTPUT_DIR = TMP_DIR / "sara_holt_segments"

# ── Entity exclusion keywords ──
EXCLUDE_OWNER_KEYWORDS = [
    # Government
    "CITY OF", "COUNTY OF", "STATE OF", "UNITED STATES", "HAMILTON COUNTY",
    "CHATT CITY", "TOWN OF",
    # Religious
    "CHURCH", "BAPTIST", "METHODIST", "MINISTRY", "MINISTRIES",
    "CONGREGATION", "DIOCESE", "TEMPLE", "MOSQUE", "SYNAGOGUE",
    # Associations / HOA
    "HOMEOWNERS ASSOC", "COMMUNITY ASSOC", "HOA ", "PROPERTY OWNERS",
    # Institutional
    "SCHOOL", "BOARD OF EDUCATION", "UNIVERSITY", "COLLEGE",
    "HOSPITAL", "CEMETERY", "MEMORIAL",
    # Utility
    "UTILITY DIST", "ELECTRIC POWER", "WATER DIST",
]

# ── Geography: target areas ──
# Sara wants Chattanooga, Ooltewah, Collegedale.
# District mapping (from analysis):
#   1    = Chattanooga city
#   2    = Chattanooga/Ooltewah/Harrison
#   2C   = Collegedale area
#   2E   = East Brainerd / Park City (near Ooltewah/Collegedale)
#   2R   = Chattanooga (Red Bank area)
#   3    = Hixson/N. Chattanooga/Soddy Daisy (mixed)
#   3LS  = Lakesite (outside target)
#   3SD  = Soddy Daisy (outside target)

# Districts that are clearly in target area
TARGET_DISTRICTS = {"1", "2", "2C", "2E", "2R"}

# District 3 is mixed - Hixson is greater Chattanooga but Soddy Daisy isn't.
# We include district 3 parcels but exclude ones with Soddy Daisy / Sale Creek indicators.
MIXED_DISTRICTS = {"3"}

# Streets/areas in district 3 that indicate Soddy Daisy / Sale Creek (outside target)
EXCLUDE_STREET_KEYWORDS = [
    "SODDY", "SALE CREEK", "DAYTON PIKE", "BACK VALLEY",
]

# Districts to fully exclude
EXCLUDE_DISTRICTS = {"3LS", "3SD"}


def is_excluded_entity(owner: str) -> bool:
    upper = owner.upper()
    return any(kw in upper for kw in EXCLUDE_OWNER_KEYWORDS)


def is_in_target_geography(row: dict) -> bool:
    district = row.get("district", "").strip()

    if district in EXCLUDE_DISTRICTS:
        return False

    if district in TARGET_DISTRICTS:
        return True

    if district in MIXED_DISTRICTS:
        address = row.get("address", "").upper()
        return not any(kw in address for kw in EXCLUDE_STREET_KEYWORDS)

    # Unknown district - include it, let human review
    return True


def segment_label(acres: float) -> str:
    if acres < 1:
        return "under_1_acre"
    elif acres <= 3:
        return "1_to_3_acres"
    else:
        return "over_3_acres"


def main():
    if not INPUT_CSV.exists():
        print(f"ERROR: Input not found: {INPUT_CSV}")
        sys.exit(1)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Input: {len(rows)} parcels\n")

    # Step 1: Entity filter
    entity_removed = []
    after_entity = []
    for r in rows:
        owner = r.get("owner", "") + " " + r.get("owner_2", "")
        if is_excluded_entity(owner):
            entity_removed.append(r)
        else:
            after_entity.append(r)

    print(f"Entity filter: removed {len(entity_removed)}, kept {len(after_entity)}")
    if entity_removed:
        print("  Sample removals:")
        for r in entity_removed[:8]:
            print(f"    X {r['parcel_id']} - {r['owner']}")

    # Step 2: Geography filter
    geo_removed = []
    after_geo = []
    for r in after_entity:
        if is_in_target_geography(r):
            after_geo.append(r)
        else:
            geo_removed.append(r)

    print(f"\nGeography filter: removed {len(geo_removed)}, kept {len(after_geo)}")
    if geo_removed:
        print("  Sample removals:")
        for r in geo_removed[:8]:
            print(f"    X {r['parcel_id']} - {r['address']} (district {r['district']})")

    # Step 3: Segment by acreage
    segments = {"under_1_acre": [], "1_to_3_acres": [], "over_3_acres": []}
    for r in after_geo:
        try:
            acres = float(r.get("calc_acres", 0))
        except (ValueError, TypeError):
            acres = 0
        segments[segment_label(acres)].append(r)

    # Write outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write combined filtered file
    combined_path = OUTPUT_DIR / "all_filtered.csv"
    with open(combined_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(after_geo)

    print(f"\n{'='*50}")
    print(f"RESULTS: {len(after_geo)} actionable parcels")
    print(f"{'='*50}")

    for label, parcels in segments.items():
        seg_path = OUTPUT_DIR / f"{label}.csv"
        with open(seg_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parcels)

        acres_range = {
            "under_1_acre": "0.3 - 0.99 acres",
            "1_to_3_acres": "1.0 - 3.0 acres",
            "over_3_acres": "3.0+ acres",
        }[label]
        print(f"\n  {label}.csv: {len(parcels)} parcels ({acres_range})")
        if parcels:
            # Show value range
            values = [float(p.get("appraised_value", 0) or 0) for p in parcels]
            print(f"    Value range: ${min(values):,.0f} - ${max(values):,.0f}")
            # Show top 5 by value
            sorted_p = sorted(parcels, key=lambda p: float(p.get("appraised_value", 0) or 0), reverse=True)
            for p in sorted_p[:5]:
                print(f"    {p['parcel_id']} | {p['address']} | {p['owner'][:30]} | {p['calc_acres']} ac | ${float(p.get('appraised_value',0)):,.0f}")

    print(f"\nFiles written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
