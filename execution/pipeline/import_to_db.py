"""
import_to_db.py - Pipeline Step 11+: Import final parcel data into Django database.

Reads the step_11 CSV (final pipeline output) and creates/updates Parcel records.
Geometry rings are sourced from step_07 CSV or from a geometry_rings column in step_11.
Preserves existing ParcelRatings (only updates parcel data fields).

Usage:
    python import_to_db.py --buybox-id <UUID>
    python import_to_db.py --buybox-id <UUID> --dry-run
"""

import argparse
import csv
import json
import sys
from typing import Any, Dict

from pipeline_common import (
    get_step_path,
    load_buybox,
    safe_float,
    safe_int,
)

from parcels.models import Parcel, ParcelRating  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_geometry_from_step07(buybox) -> Dict[str, Any]:
    """Load geometry_rings from step_07 CSV if available.

    Step 07 typically contains geometry data from the GIS query phase.
    Returns a dict mapping parcel_id -> rings (list of coordinate rings).
    """
    geom_path = get_step_path(buybox, 7, "geometry")
    if not geom_path.exists():
        # Try alternate naming conventions
        from pathlib import Path
        out_dir = geom_path.parent
        candidates = list(out_dir.glob("step_07_*.csv"))
        if candidates:
            geom_path = candidates[0]
        else:
            print(f"  No step_07 geometry file found at {geom_path.parent}")
            return {}

    print(f"  Loading geometry from {geom_path.name}...")
    geom_map = {}
    with open(geom_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get("parcel_id", "").strip()
            rings_raw = row.get("geometry_rings", "")
            if pid and rings_raw:
                try:
                    rings = json.loads(rings_raw)
                    if rings:
                        geom_map[pid] = rings
                except (json.JSONDecodeError, TypeError):
                    pass

    print(f"  Loaded geometry for {len(geom_map)} parcels")
    return geom_map


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(buybox) -> None:
    """Import step_11 CSV into Parcel model."""
    county = buybox.county
    county_name = county.name
    state = county.state
    zoning = buybox.target_zoning[0] if buybox.target_zoning else ""

    input_path = get_step_path(buybox, 11, "final")
    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    print(f"Loading data from {input_path.name}...")

    # Load geometry rings from step_07 or fallback
    geom_map = load_geometry_from_step07(buybox)

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"  Found {len(rows)} parcels in CSV\n")

    created = 0
    updated = 0

    for row in rows:
        pid = row.get("parcel_id", "").strip()
        if not pid:
            continue

        # Extract duplex_friendliness as single char (A/B/C/D)
        df_raw = row.get("duplex_friendliness", "")
        df_grade = df_raw.strip()[:1] if df_raw else ""

        # Geometry: prefer step_11 column, fallback to step_07 data
        geometry_rings = []
        rings_raw = row.get("geometry_rings", "")
        if rings_raw:
            try:
                geometry_rings = json.loads(rings_raw)
            except (json.JSONDecodeError, TypeError):
                pass
        if not geometry_rings:
            geometry_rings = geom_map.get(pid, [])

        defaults = {
            "address": row.get("address", ""),
            "county": county_name,
            "state": state,
            "owner_name": row.get("owner", ""),
            "owner_name_2": row.get("owner_2", ""),
            "owner_mailing": row.get("owner_mailing", ""),
            "calc_acres": safe_float(row.get("calc_acres")),
            "computed_acres": safe_float(row.get("computed_acres")),
            "compactness": safe_float(row.get("compactness")),
            "land_value": safe_int(row.get("land_value")),
            "building_value": safe_int(row.get("building_value")),
            "appraised_value": safe_int(row.get("appraised_value")),
            "assessed_value": safe_int(row.get("assessed_value")),
            "zoning": zoning,
            "land_use_code": row.get("land_use_code", ""),
            "district": row.get("district", ""),
            "water_provider": row.get("water_provider", ""),
            "sewer_provider": row.get("sewer_provider", ""),
            "utilities_score": row.get("utilities_score", ""),
            "lat": safe_float(row.get("lat")),
            "lon": safe_float(row.get("lon")),
            "geometry_rings": geometry_rings,
            "last_sale_date": row.get("last_sale_date", ""),
            "last_sale_price": safe_int(row.get("last_sale_price")),
            "assessor_link": row.get("assessor_link", ""),
            # Comp analysis
            "land_comp_count": safe_int(row.get("land_comp_count")),
            "land_comp_radius": row.get("land_comp_radius", ""),
            "land_comp_min": safe_int(row.get("land_comp_min")) or None,
            "land_comp_max": safe_int(row.get("land_comp_max")) or None,
            "land_comp_median": safe_float(row.get("land_comp_median")),
            "land_comp_avg_ppa": safe_float(row.get("land_comp_avg_ppa")),
            "land_est_value": safe_float(row.get("land_est_value")),
            "land_comp_details": row.get("land_comp_details", ""),
            "arv_comp_count": safe_int(row.get("arv_comp_count")),
            "arv_comp_radius": row.get("arv_comp_radius", ""),
            "arv_comp_min": safe_int(row.get("arv_comp_min")) or None,
            "arv_comp_max": safe_int(row.get("arv_comp_max")) or None,
            "arv_comp_median": safe_float(row.get("arv_comp_median")),
            "arv_comp_details": row.get("arv_comp_details", ""),
            # Duplex friendliness
            "nearby_sfr": safe_int(row.get("nearby_sfr")),
            "nearby_duplex": safe_int(row.get("nearby_duplex")),
            "nearby_triplex": safe_int(row.get("nearby_triplex")),
            "nearby_quad": safe_int(row.get("nearby_quad")),
            "nearby_total": safe_int(row.get("nearby_total")),
            "duplex_ratio": safe_float(row.get("duplex_ratio")),
            "duplex_friendliness": df_grade,
            # Deal classification
            "deal_tier": row.get("deal_tier", ""),
            "geo_priority": row.get("geo_priority", ""),
            # BuyBox FK and target flag
            "buybox": buybox,
            "is_target": True,
        }

        parcel, was_created = Parcel.objects.update_or_create(
            parcel_id=pid, defaults=defaults
        )

        if was_created:
            created += 1
        else:
            updated += 1

        status = "NEW" if was_created else "UPD"
        print(f"  {status} {pid} | {defaults['address'][:30]} | {df_grade} | {defaults.get('geo_priority', '')[:20]}")

    print(f"\nDone: {created} created, {updated} updated, {created + updated} total")
    print(f"Parcels in DB for this buybox: {Parcel.objects.filter(buybox=buybox, is_target=True).count()}")


def dry_run(buybox) -> None:
    """Print configuration without modifying the database."""
    county = buybox.county
    input_path = get_step_path(buybox, 11, "final")
    zoning = buybox.target_zoning[0] if buybox.target_zoning else ""

    print("=" * 60)
    print("DRY RUN - import_to_db.py")
    print("=" * 60)
    print()
    print(f"BuyBox:               {buybox.pk}")
    print(f"Buyer:                {buybox.buyer}")
    print(f"County:               {county.name}, {county.state}")
    print(f"Zoning:               {zoning}")
    print()
    print(f"Input:                {input_path}")
    print(f"Input exists:         {input_path.exists()}")
    if input_path.exists():
        with open(input_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"Rows in CSV:          {len(rows)}")
    print()
    print(f"Existing parcels (buybox): {Parcel.objects.filter(buybox=buybox).count()}")
    print(f"Existing parcels (target): {Parcel.objects.filter(buybox=buybox, is_target=True).count()}")
    print()
    print("No database changes made.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import final pipeline CSV into Django Parcel model."
    )
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without DB changes.")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)

    if args.dry_run:
        dry_run(buybox)
    else:
        run_pipeline(buybox)


if __name__ == "__main__":
    main()
