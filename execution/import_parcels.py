"""
Import parcel data from CSV + HTML viewer into Django database.
Reads the top_deals.csv for target parcels and extracts geometry
rings from the parcel_viewer.html for map display.

Usage:
    cd backend
    python manage.py shell -c "exec(open('../execution/import_parcels.py').read())"

Or run directly with Django settings configured:
    DJANGO_SETTINGS_MODULE=backend_api.settings python ../execution/import_parcels.py
"""

import csv
import json
import os
import sys
from pathlib import Path

# Setup Django
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_api.settings")

import django
django.setup()

from parcels.models import Parcel, ParcelRating

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp" / "sara_holt_segments"
CSV_PATH = TMP_DIR / "top_deals_comped.csv"
HTML_PATH = TMP_DIR / "parcel_viewer.html"


def load_geometry_from_html() -> dict:
    """Extract parcel geometry rings from the viewer HTML."""
    if not HTML_PATH.exists():
        print("  WARNING: parcel_viewer.html not found, skipping geometry")
        return {}

    html = HTML_PATH.read_text(encoding="utf-8")
    start = html.index("const parcels = ") + len("const parcels = ")
    end = html.index(";\n", start)
    parcels = json.loads(html[start:end])

    geom_map = {}
    for p in parcels:
        pid = p.get("parcel_id", "")
        rings = p.get("rings", [])
        if pid and rings:
            geom_map[pid] = rings
    print(f"  Loaded geometry for {len(geom_map)} parcels from HTML")
    return geom_map


def safe_int(val, default=0):
    if not val or val == "":
        return default
    try:
        return int(float(str(val).replace(",", "").replace("$", "")))
    except (ValueError, TypeError):
        return default


def safe_float(val, default=None):
    if not val or val == "":
        return default
    try:
        return float(str(val).replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return default


def main():
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found")
        sys.exit(1)

    print(f"Loading data from {CSV_PATH.name}...")
    geom_map = load_geometry_from_html()

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
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

        defaults = {
            "address": row.get("address", ""),
            "county": "Hamilton",
            "state": "TN",
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
            "zoning": "R-2",
            "land_use_code": row.get("land_use_code", ""),
            "district": row.get("district", ""),
            "water_provider": row.get("water_provider", ""),
            "sewer_provider": row.get("sewer_provider", ""),
            "utilities_score": row.get("utilities_score", ""),
            "lat": safe_float(row.get("lat")),
            "lon": safe_float(row.get("lon")),
            "geometry_rings": geom_map.get(pid, []),
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
            # Classification
            "deal_tier": row.get("deal_tier", ""),
            "geo_priority": row.get("geo_priority", ""),
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
    print(f"Parcels in DB: {Parcel.objects.filter(is_target=True).count()}")


if __name__ == "__main__":
    main()
