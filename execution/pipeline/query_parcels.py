"""
query_parcels.py - Query a county's ArcGIS REST API for parcels matching a buybox.

DB-driven refactor of execution/query_gis_parcels.py. All GIS URLs, field names,
WKIDs, and filters are read from the BuyBox/County models rather than hardcoded.

Usage:
    python query_parcels.py --buybox-id <UUID>
    python query_parcels.py --buybox-id <UUID> --dry-run
"""

import argparse
import csv
import json
import sys
import time
from typing import Any, Dict, List

from pipeline_common import (
    build_where_clause,
    format_epoch,
    get_step_path,
    load_buybox,
    paginated_query,
    safe_float,
    safe_int,
    simplify_rings,
    spatial_query,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_mailing_address(row: Dict[str, Any], field_map: Dict[str, str]) -> str:
    """Combine mailing address component fields into a single string.

    Args:
        row: Parcel attribute dict (keyed by GIS field names).
        field_map: County field_map mapping canonical names to GIS field names.

    Returns:
        Formatted mailing address string.
    """
    parts = [
        str(row.get(field_map.get("mailing_number", ""), "") or ""),
        str(row.get(field_map.get("mailing_prefix", ""), "") or ""),
        str(row.get(field_map.get("mailing_street", ""), "") or ""),
        str(row.get(field_map.get("mailing_suffix", ""), "") or ""),
    ]
    street = " ".join(p for p in parts if p).strip()
    city = str(row.get(field_map.get("mailing_city", ""), "") or "")
    state = str(row.get(field_map.get("mailing_state", ""), "") or "")
    zipcode = str(row.get(field_map.get("mailing_zip", ""), "") or "")
    if city:
        return f"{street}, {city}, {state} {zipcode}".strip(", ")
    return street


def get_parcel_out_fields(field_map: Dict[str, str]) -> str:
    """Build the outFields parameter from the county's field map.

    Args:
        field_map: County field_map dict (canonical -> GIS field name).

    Returns:
        Comma-separated GIS field names for the parcel query.
    """
    return ",".join(field_map.values())


def format_parcel_row(attrs: Dict[str, Any], field_map: Dict[str, str]) -> Dict[str, str]:
    """Convert raw GIS attributes into a standardised output row.

    Args:
        attrs: Raw attribute dict from ArcGIS (keyed by GIS field names).
        field_map: County field_map mapping canonical -> GIS field names.

    Returns:
        Dict with canonical output column names.
    """
    def _get(canonical: str) -> Any:
        gis_field = field_map.get(canonical, "")
        return attrs.get(gis_field, "")

    return {
        "parcel_id": _get("parcel_id"),
        "address": _get("address"),
        "owner": _get("owner_1"),
        "owner_2": _get("owner_2"),
        "owner_mailing": format_mailing_address(attrs, field_map),
        "calc_acres": _get("calc_acres"),
        "land_use_code": _get("land_use"),
        "district": _get("district"),
        "land_value": _get("land_value"),
        "building_value": _get("building_value"),
        "appraised_value": _get("appraised_value"),
        "assessed_value": _get("assessed_value"),
        "last_sale_date": format_epoch(_get("sale_date_1")),
        "last_sale_price": _get("sale_price_1"),
        "assessor_link": _get("assessor_link"),
    }


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "parcel_id", "address", "owner", "owner_2", "owner_mailing",
    "calc_acres", "land_use_code", "district",
    "land_value", "building_value", "appraised_value", "assessed_value",
    "last_sale_date", "last_sale_price",
    "assessor_link",
]


def fetch_zone_polygons(buybox) -> List[Dict[str, Any]]:
    """Fetch all zoning polygons matching the buybox's target zones.

    Paginates through the zoning layer using the county's zoning URL and
    max_records_per_query setting.

    Args:
        buybox: BuyBox instance with county relation loaded.

    Returns:
        List of ArcGIS feature dicts (each with 'attributes' and 'geometry').
    """
    county = buybox.county
    zone_field = county.zoning_zone_field
    target_zones = buybox.target_zoning

    # Build zone filter: ZONE IN ('R-2', 'R-3', ...)
    zone_values = ", ".join(f"'{z}'" for z in target_zones)
    where = f"{zone_field} IN ({zone_values})"

    params = {
        "where": where,
        "returnGeometry": "true",
        "outFields": zone_field,
        "f": "json",
    }

    url = county.zoning_layer_url.rstrip("/") + "/query"
    max_records = county.max_records_per_query or 1000

    features = paginated_query(url, params, max_records)
    return features


def query_parcels_for_zone(buybox, zone_geometry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Spatial query: find parcels within a zone polygon matching buybox filters.

    If the initial query fails (geometry too complex), simplifies the polygon
    rings and retries once.

    Args:
        buybox: BuyBox instance.
        zone_geometry: ArcGIS geometry dict with 'rings'.

    Returns:
        List of attribute dicts for matching parcels.
    """
    county = buybox.county
    parcel_url = county.parcel_layer_url.rstrip("/") + "/query"
    zoning_wkid = county.zoning_layer_wkid
    where = build_where_clause(buybox)
    out_fields = get_parcel_out_fields(county.field_map)

    try:
        return spatial_query(
            parcel_url,
            geometry=zone_geometry,
            geometry_type="esriGeometryPolygon",
            spatial_rel="esriSpatialRelIntersects",
            where=where,
            out_fields=out_fields,
            in_sr=zoning_wkid,
        )
    except Exception as e:
        # Geometry may be too complex — simplify and retry
        rings = zone_geometry.get("rings", [])
        if not rings:
            print(f"    Query failed, no rings to simplify: {e}")
            return []

        print(f"    Simplifying geometry ({e})... ", end="", flush=True)
        simplified_geom = {"rings": simplify_rings(rings)}
        try:
            results = spatial_query(
                parcel_url,
                geometry=simplified_geom,
                geometry_type="esriGeometryPolygon",
                spatial_rel="esriSpatialRelIntersects",
                where=where,
                out_fields=out_fields,
                in_sr=zoning_wkid,
            )
            print("OK")
            return results
        except Exception as e2:
            print(f"FAILED: {e2}")
            return []


def run_pipeline(buybox) -> None:
    """Execute the full parcel query pipeline for a buybox.

    1. Fetch zone polygons matching target zoning.
    2. Spatial query parcels within each zone.
    3. Deduplicate by parcel_id.
    4. Write results to CSV.

    Args:
        buybox: BuyBox instance with county and buyer loaded.
    """
    county = buybox.county
    field_map = county.field_map
    parcel_id_field = field_map.get("parcel_id", "")

    # Step 1: Fetch zoning polygons
    print(f"Fetching zone polygons for {buybox.target_zoning}...")
    zones = fetch_zone_polygons(buybox)
    print(f"  Found {len(zones)} zone polygons\n")

    if not zones:
        print("No matching zone polygons found. Exiting.")
        sys.exit(1)

    # Step 2: Spatial query parcels per zone, deduplicate
    all_parcels: Dict[str, Dict[str, Any]] = {}

    for i, zone in enumerate(zones, 1):
        print(f"  [{i}/{len(zones)}] Querying parcels in zone... ", end="", flush=True)
        try:
            parcels = query_parcels_for_zone(buybox, zone["geometry"])
            new = 0
            for p in parcels:
                key = p.get(parcel_id_field, "")
                if key and key not in all_parcels:
                    all_parcels[key] = p
                    new += 1
            print(f"{len(parcels)} hits, {new} new (total: {len(all_parcels)})")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.2)

    print(f"\nTotal unique parcels: {len(all_parcels)}")

    if not all_parcels:
        print("No parcels found.")
        sys.exit(1)

    # Step 3: Format rows
    rows = [format_parcel_row(attrs, field_map) for attrs in all_parcels.values()]

    # Sort by appraised value descending
    rows.sort(key=lambda r: safe_float(r.get("appraised_value", 0), 0.0), reverse=True)

    # Step 4: Write CSV
    output_path = get_step_path(buybox, 3, "parcels_raw")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} parcels to {output_path}")


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

def dry_run(buybox) -> None:
    """Print configuration and query parameters without making API calls.

    Args:
        buybox: BuyBox instance with county and buyer loaded.
    """
    county = buybox.county
    field_map = county.field_map
    where = build_where_clause(buybox)
    out_fields = get_parcel_out_fields(field_map)
    output_path = get_step_path(buybox, 3, "parcels_raw")

    zone_field = county.zoning_zone_field
    zone_values = ", ".join(f"'{z}'" for z in buybox.target_zoning)
    zone_where = f"{zone_field} IN ({zone_values})"

    print("=" * 60)
    print("DRY RUN — query_parcels.py")
    print("=" * 60)
    print()
    print(f"BuyBox ID:            {buybox.pk}")
    print(f"Buyer:                {buybox.buyer}")
    print(f"County:               {county}")
    print()
    print("--- Zoning Layer ---")
    print(f"URL:                  {county.zoning_layer_url}")
    print(f"WKID:                 {county.zoning_layer_wkid}")
    print(f"Zone field:           {zone_field}")
    print(f"Zone WHERE:           {zone_where}")
    print()
    print("--- Parcel Layer ---")
    print(f"URL:                  {county.parcel_layer_url}")
    print(f"WKID:                 {county.parcel_layer_wkid}")
    print(f"Parcel WHERE:         {where}")
    print(f"Out fields:           {out_fields}")
    print(f"Max records/query:    {county.max_records_per_query}")
    print()
    print("--- Field Map ---")
    for canonical, gis_name in sorted(field_map.items()):
        print(f"  {canonical:20s} -> {gis_name}")
    print()
    print(f"Output path:          {output_path}")
    print()
    print("No API calls made.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Query ArcGIS parcels matching a BuyBox's criteria."
    )
    parser.add_argument(
        "--buybox-id",
        required=True,
        help="UUID of the BuyBox to query.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config and query parameters without making API calls.",
    )
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)

    if args.dry_run:
        dry_run(buybox)
    else:
        run_pipeline(buybox)


if __name__ == "__main__":
    main()
