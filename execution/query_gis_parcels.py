"""
Query Hamilton County GIS for vacant R-2 parcels matching a buyer's criteria.
Uses ArcGIS REST API spatial queries to join parcel data with zoning layers.

Data sources:
  - Parcels: https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_Parcels/MapServer/0
  - Zoning:  https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_PropertyZoning/MapServer/17

Zoning layer uses WKID 2274, Parcels use WKID 6576. We pass inSR=2274
so the server reprojects automatically.
"""

import csv
import json
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
OUTPUT_CSV = TMP_DIR / "gis_r2_vacant_parcels.csv"

PARCEL_URL = "https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_Parcels/MapServer/0/query"
ZONING_URL = "https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_PropertyZoning/MapServer/17/query"

# Parcel fields to extract
PARCEL_FIELDS = [
    "TAX_MAP_NO", "ADDRESS", "OWNERNAME1", "OWNERNAME2",
    "CALCACRES", "LUCODE", "LANDVALUE", "BUILDVALUE", "APPVALUE", "ASSVALUE",
    "DISTRICT", "SALE1DATE", "SALE1CONSD",
    "MASTNUM", "MADIRPFX", "MASTNAME", "MATYPESFX", "MACITY", "MASTATE", "MAZIP",
    "RecordsOnl",
]

# Buybox filters applied on the parcel query
PARCEL_WHERE = "BUILDVALUE = 0 AND CALCACRES >= 0.3 AND APPVALUE <= 80000 AND APPVALUE > 0"

# Zoning filter
ZONE_VALUE = "R-2"

# Max records per ArcGIS query
MAX_RECORDS = 1000


def get_all_r2_zones() -> list[dict]:
    """Fetch all R-2 zone polygons from the zoning layer, paginating if needed."""
    all_features = []
    offset = 0
    while True:
        params = {
            "where": f"ZONE = '{ZONE_VALUE}'",
            "returnGeometry": "true",
            "outFields": "ZONE",
            "resultOffset": str(offset),
            "resultRecordCount": str(MAX_RECORDS),
            "f": "json",
        }
        r = requests.get(ZONING_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        all_features.extend(features)
        if len(features) < MAX_RECORDS:
            break
        offset += MAX_RECORDS
    return all_features


def query_parcels_in_zone(zone_geometry: dict) -> list[dict]:
    """Spatial query: find parcels matching buybox within a zoning polygon."""
    post_data = {
        "where": PARCEL_WHERE,
        "geometry": json.dumps(zone_geometry),
        "geometryType": "esriGeometryPolygon",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "2274",
        "outFields": ",".join(PARCEL_FIELDS),
        "returnGeometry": "false",
        "f": "json",
    }
    r = requests.post(PARCEL_URL, data=post_data, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        print(f"    API error: {data['error']['message']}")
        return []
    return [f["attributes"] for f in data.get("features", [])]


def format_mailing_address(row: dict) -> str:
    """Combine mailing address fields into a single string."""
    parts = [
        row.get("MASTNUM", ""),
        row.get("MADIRPFX", ""),
        row.get("MASTNAME", ""),
        row.get("MATYPESFX", ""),
    ]
    street = " ".join(p for p in parts if p).strip()
    city = row.get("MACITY", "")
    state = row.get("MASTATE", "")
    zipcode = row.get("MAZIP", "")
    if city:
        return f"{street}, {city}, {state} {zipcode}".strip(", ")
    return street


def format_sale_date(epoch_ms) -> str:
    """Convert epoch milliseconds to readable date."""
    if not epoch_ms:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        return dt.strftime("%m/%d/%Y")
    except (OSError, ValueError, OverflowError):
        return str(epoch_ms)


def main():
    print("Fetching R-2 zone polygons...")
    zones = get_all_r2_zones()
    print(f"  Found {len(zones)} R-2 zones\n")

    all_parcels = {}  # deduplicate by TAX_MAP_NO
    for i, zone in enumerate(zones, 1):
        print(f"  [{i}/{len(zones)}] Querying parcels in R-2 zone... ", end="", flush=True)
        try:
            parcels = query_parcels_in_zone(zone["geometry"])
            new = 0
            for p in parcels:
                key = p.get("TAX_MAP_NO", "")
                if key and key not in all_parcels:
                    all_parcels[key] = p
                    new += 1
            print(f"{len(parcels)} hits, {new} new (total: {len(all_parcels)})")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.2)  # polite delay

    print(f"\nTotal unique parcels: {len(all_parcels)}")

    if not all_parcels:
        print("No parcels found.")
        sys.exit(1)

    # Format and write CSV
    output_fields = [
        "parcel_id", "address", "owner", "owner_2", "owner_mailing",
        "calc_acres", "land_use_code", "district",
        "land_value", "building_value", "appraised_value", "assessed_value",
        "last_sale_date", "last_sale_price",
        "assessor_link",
    ]

    rows = []
    for p in all_parcels.values():
        rows.append({
            "parcel_id": p.get("TAX_MAP_NO", ""),
            "address": p.get("ADDRESS", ""),
            "owner": p.get("OWNERNAME1", ""),
            "owner_2": p.get("OWNERNAME2", ""),
            "owner_mailing": format_mailing_address(p),
            "calc_acres": p.get("CALCACRES", ""),
            "land_use_code": p.get("LUCODE", ""),
            "district": p.get("DISTRICT", ""),
            "land_value": p.get("LANDVALUE", ""),
            "building_value": p.get("BUILDVALUE", ""),
            "appraised_value": p.get("APPVALUE", ""),
            "assessed_value": p.get("ASSVALUE", ""),
            "last_sale_date": format_sale_date(p.get("SALE1DATE")),
            "last_sale_price": p.get("SALE1CONSD", ""),
            "assessor_link": p.get("RecordsOnl", ""),
        })

    # Sort by appraised value descending (best deals near top)
    rows.sort(key=lambda r: r.get("appraised_value", 0) or 0, reverse=True)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} parcels to {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
