"""
generate_comps.py - Pipeline Step 09: Generate comparable sales for parcels.

For each parcel, queries nearby properties to produce:
  1. Land comps - recent vacant lot sales within radius
  2. ARV comps  - recent duplex/improved sales within radius

GIS URLs, field names, and search tiers are read from the BuyBox/County models.
PPA floor/cap are dynamically computed from countywide sales data.

Usage:
    python generate_comps.py --buybox-id <UUID>
    python generate_comps.py --buybox-id <UUID> --dry-run
"""

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pipeline_common import (
    build_where_clause,
    compute_acres_from_rings,
    format_epoch,
    get_step_path,
    load_buybox,
    remove_outliers,
    safe_float,
    safe_int,
    spatial_query,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Standard ArcGIS land use codes
LU_SFR = 111
LU_DUPLEX = 112
LU_TRIPLEX = 113
LU_QUAD = 114
DUPLEX_CODES = [LU_DUPLEX, LU_TRIPLEX, LU_QUAD]
SFR_FALLBACK_CODE = LU_SFR

# PPA bounds: derived from county sales distribution
PPA_FLOOR_PERCENTILE = 25   # 25th percentile of county $/acre
PPA_CAP_MULTIPLIER = 3.0    # 300% of county median $/acre

# Minimum comps needed before widening search
MIN_LAND_COMPS = 2
MIN_ARV_COMPS = 2

# Default search tiers when buybox.comp_search_tiers is empty
DEFAULT_SEARCH_TIERS = [
    {"radius_ft": 2640, "lookback_months": 18, "label": "0.5mi/18mo"},
    {"radius_ft": 5280, "lookback_months": 24, "label": "1mi/2yr"},
    {"radius_ft": 10560, "lookback_months": 36, "label": "2mi/3yr"},
]

SQFT_PER_ACRE = 43_560

# Output columns added by this step
COMP_FIELDS = [
    "land_comp_count", "land_comp_radius", "land_comp_min", "land_comp_max",
    "land_comp_median", "land_comp_avg_ppa", "land_est_value", "land_comp_details",
    "arv_comp_count", "arv_comp_radius", "arv_comp_min", "arv_comp_max",
    "arv_comp_median", "arv_comp_details",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_search_tiers(buybox) -> List[Dict[str, Any]]:
    """Return comp search tiers from buybox or defaults."""
    tiers = buybox.comp_search_tiers
    if tiers:
        return tiers
    return DEFAULT_SEARCH_TIERS


def date_cutoff_from_months(months: int) -> str:
    """Compute a date cutoff string (YYYY-MM-DD) from lookback months."""
    cutoff = datetime.now() - timedelta(days=months * 30)
    return cutoff.strftime("%Y-%m-%d")


def get_parcel_centroid(
    parcel_url: str, parcel_id: str, parcel_id_field: str, wkid: int
) -> Optional[Tuple[float, float]]:
    """Get the centroid of a parcel polygon in native WKID."""
    import requests
    r = requests.get(parcel_url.rstrip("/") + "/query", params={
        "where": f"{parcel_id_field} = '{parcel_id}'",
        "outFields": parcel_id_field,
        "returnGeometry": "true",
        "outSR": str(wkid),
        "f": "json",
    }, timeout=15)
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    rings = feats[0].get("geometry", {}).get("rings", [[]])
    if not rings or not rings[0]:
        return None
    pts = rings[0]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return (cx, cy)


def query_comps(
    parcel_url: str, cx: float, cy: float, where: str,
    radius_ft: int, fields: str, wkid: int
) -> List[Dict[str, Any]]:
    """Spatial radius query for comparable sales. Computes real acreage from geometry."""
    import requests
    point = {"x": cx, "y": cy, "spatialReference": {"wkid": wkid}}
    r = requests.post(parcel_url.rstrip("/") + "/query", data={
        "where": where,
        "geometry": json.dumps(point),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(radius_ft),
        "units": "esriSRUnit_Foot",
        "inSR": str(wkid),
        "outFields": fields,
        "returnGeometry": "true",
        "outSR": str(wkid),
        "f": "json",
    }, timeout=30)
    data = r.json()
    if data.get("error"):
        return []
    results = []
    for f in data.get("features", []):
        attrs = f["attributes"]
        # Compute real acreage if GIS reports exactly 1.0 (known bad default)
        acres_field = _find_acres_field(attrs)
        if acres_field and attrs.get(acres_field) == 1.0 and f.get("geometry"):
            rings = f["geometry"].get("rings", [])
            real = compute_acres_from_rings(rings, wkid)
            if real > 0.01:
                attrs[acres_field] = round(real, 3)
        results.append(attrs)
    return results


def _find_acres_field(attrs: Dict[str, Any]) -> Optional[str]:
    """Find the acreage field name in attributes (varies by county)."""
    for key in ("CALCACRES", "CALC_ACRES", "ACRES", "GIS_ACRES"):
        if key in attrs:
            return key
    return None


def compute_county_ppa_bounds(
    parcel_url: str, field_map: Dict[str, str], wkid: int
) -> Tuple[float, float]:
    """Query countywide vacant land sales to compute dynamic $/acre bounds.
    Returns (floor, cap) based on the county's own sales distribution."""
    import requests

    acres_field = field_map.get("calc_acres", "CALCACRES")
    sale_price_field = field_map.get("sale_price_1", "SALE1CONSD")
    bldg_field = field_map.get("building_value", "BUILDVALUE")
    sale_date_field = field_map.get("sale_date_1", "SALE1DATE")

    # Look back 2 years for county-wide data
    cutoff = date_cutoff_from_months(24)

    where = (
        f"{bldg_field} = 0 AND {acres_field} > 0.1 AND {acres_field} <> 1 "
        f"AND {sale_price_field} >= 5000 AND {sale_date_field} >= date '{cutoff}'"
    )

    print("Computing county $/acre bounds for land comp filtering...")
    r = requests.get(parcel_url.rstrip("/") + "/query", params={
        "where": where,
        "outFields": f"{acres_field},{sale_price_field}",
        "returnGeometry": "false",
        "resultRecordCount": "1000",
        "f": "json",
    }, timeout=30)
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        print("  WARNING: No county sales data found, using fallbacks")
        return (5000.0, 150000.0)

    ppas = sorted(
        f["attributes"][sale_price_field] / f["attributes"][acres_field]
        for f in feats
        if f["attributes"].get(acres_field, 0) > 0.01
    )
    if not ppas:
        return (5000.0, 150000.0)

    median_ppa = statistics.median(ppas)
    floor = ppas[int(len(ppas) * PPA_FLOOR_PERCENTILE / 100)]
    cap = median_ppa * PPA_CAP_MULTIPLIER
    print(f"  County sample: {len(feats)} sales | median $/acre: ${median_ppa:,.0f}")
    print(f"  Floor ({PPA_FLOOR_PERCENTILE}th pct): ${floor:,.0f}/acre | Cap ({PPA_CAP_MULTIPLIER}x median): ${cap:,.0f}/acre")
    return (floor, cap)


# ---------------------------------------------------------------------------
# Comp finders
# ---------------------------------------------------------------------------

def find_land_comps(
    parcel_url: str, cx: float, cy: float, subject_acres: float,
    tiers: List[Dict], field_map: Dict[str, str], wkid: int,
    ppa_floor: float, ppa_cap: float,
) -> Dict[str, Any]:
    """Find vacant land comps, widening search until we get enough."""
    acres_field = field_map.get("calc_acres", "CALCACRES")
    sale_price_field = field_map.get("sale_price_1", "SALE1CONSD")
    sale_date_field = field_map.get("sale_date_1", "SALE1DATE")
    bldg_field = field_map.get("building_value", "BUILDVALUE")
    address_field = field_map.get("address", "ADDRESS")
    pid_field = field_map.get("parcel_id", "TAX_MAP_NO")
    appr_field = field_map.get("appraised_value", "APPVALUE")
    land_field = field_map.get("land_value", "LANDVALUE")

    fields = f"{pid_field},{address_field},{acres_field},{sale_date_field},{sale_price_field},{appr_field},{land_field}"

    for tier in tiers:
        date_cutoff = date_cutoff_from_months(tier["lookback_months"])
        where = (
            f"{bldg_field} = 0 AND {acres_field} >= 0.15 AND {sale_price_field} > 0 "
            f"AND {sale_date_field} >= date '{date_cutoff}'"
        )
        comps = query_comps(parcel_url, cx, cy, where, tier["radius_ft"], fields, wkid)
        comps = remove_outliers(
            comps, price_key=sale_price_field, acres_key=acres_field,
            is_land=True, ppa_floor=ppa_floor, ppa_cap=ppa_cap,
        )

        if len(comps) >= MIN_LAND_COMPS:
            prices = [c[sale_price_field] for c in comps]
            ppa = [c[sale_price_field] / max(c.get(acres_field, 0.1), 0.1) for c in comps]
            return {
                "land_comp_count": len(comps),
                "land_comp_radius": tier["label"],
                "land_comp_min": min(prices),
                "land_comp_max": max(prices),
                "land_comp_median": statistics.median(prices),
                "land_comp_avg_ppa": round(statistics.mean(ppa)),
                "land_est_value": round(statistics.median(ppa) * subject_acres),
                "land_comp_details": "; ".join(
                    f"{c.get(address_field) or '?'} {c.get(acres_field, '?')}ac "
                    f"${c[sale_price_field]:,.0f} ({format_epoch(c.get(sale_date_field))})"
                    for c in sorted(comps, key=lambda x: x.get(sale_date_field) or 0, reverse=True)[:5]
                ),
            }

    return {
        "land_comp_count": 0,
        "land_comp_radius": "none",
        "land_comp_min": "",
        "land_comp_max": "",
        "land_comp_median": "",
        "land_comp_avg_ppa": "",
        "land_est_value": "",
        "land_comp_details": "No comps found within widest tier",
    }


def find_arv_comps(
    parcel_url: str, cx: float, cy: float,
    tiers: List[Dict], field_map: Dict[str, str], wkid: int,
) -> Dict[str, Any]:
    """Find duplex/improved ARV comps, widening search until we get enough."""
    sale_price_field = field_map.get("sale_price_1", "SALE1CONSD")
    sale_date_field = field_map.get("sale_date_1", "SALE1DATE")
    bldg_field = field_map.get("building_value", "BUILDVALUE")
    address_field = field_map.get("address", "ADDRESS")
    pid_field = field_map.get("parcel_id", "TAX_MAP_NO")
    acres_field = field_map.get("calc_acres", "CALCACRES")
    appr_field = field_map.get("appraised_value", "APPVALUE")
    lu_field = field_map.get("land_use", "LUCODE")

    fields = f"{pid_field},{address_field},{acres_field},{sale_date_field},{sale_price_field},{appr_field},{bldg_field},{lu_field}"

    duplex_codes_str = ",".join(str(c) for c in DUPLEX_CODES)

    for tier in tiers:
        date_cutoff = date_cutoff_from_months(tier["lookback_months"])

        # Primary: duplexes (112, 113, 114)
        where = (
            f"{lu_field} IN ({duplex_codes_str}) AND {bldg_field} > 50000 "
            f"AND {sale_price_field} > 50000 "
            f"AND {sale_date_field} >= date '{date_cutoff}'"
        )
        comps = query_comps(parcel_url, cx, cy, where, tier["radius_ft"], fields, wkid)
        comps = remove_outliers(comps, price_key=sale_price_field, acres_key=acres_field)

        if len(comps) >= MIN_ARV_COMPS:
            prices = [c[sale_price_field] for c in comps]
            return {
                "arv_comp_count": len(comps),
                "arv_comp_radius": tier["label"],
                "arv_comp_min": min(prices),
                "arv_comp_max": max(prices),
                "arv_comp_median": statistics.median(prices),
                "arv_comp_details": "; ".join(
                    f"{c.get(address_field) or '?'} ${c[sale_price_field]:,.0f} "
                    f"({format_epoch(c.get(sale_date_field))}) lu={safe_int(c.get(lu_field, 0))}"
                    for c in sorted(comps, key=lambda x: x.get(sale_date_field) or 0, reverse=True)[:5]
                ),
            }

        # Fallback: include SFR comps as rough ARV floor
        where_sfr = (
            f"{lu_field} = {SFR_FALLBACK_CODE} AND {bldg_field} > 50000 "
            f"AND {sale_price_field} > 50000 "
            f"AND {sale_date_field} >= date '{date_cutoff}'"
        )
        sfr_comps = query_comps(parcel_url, cx, cy, where_sfr, tier["radius_ft"], fields, wkid)
        sfr_comps = remove_outliers(sfr_comps, price_key=sale_price_field, acres_key=acres_field)

        all_comps = comps + sfr_comps
        if len(all_comps) >= MIN_ARV_COMPS:
            prices = [c[sale_price_field] for c in all_comps]
            return {
                "arv_comp_count": len(all_comps),
                "arv_comp_radius": tier["label"] + " (incl SFR)",
                "arv_comp_min": min(prices),
                "arv_comp_max": max(prices),
                "arv_comp_median": statistics.median(prices),
                "arv_comp_details": "; ".join(
                    f"{c.get(address_field) or '?'} ${c[sale_price_field]:,.0f} "
                    f"({format_epoch(c.get(sale_date_field))}) lu={safe_int(c.get(lu_field, 0))}"
                    for c in sorted(all_comps, key=lambda x: x.get(sale_date_field) or 0, reverse=True)[:5]
                ),
            }

    return {
        "arv_comp_count": 0,
        "arv_comp_radius": "none",
        "arv_comp_min": "",
        "arv_comp_max": "",
        "arv_comp_median": "",
        "arv_comp_details": "No duplex/SFR comps found within widest tier",
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(buybox) -> None:
    """Generate comps for all parcels in step_08 CSV."""
    county = buybox.county
    parcel_url = county.parcel_layer_url
    field_map = county.field_map
    wkid = county.parcel_layer_wkid
    pid_field = field_map.get("parcel_id", "TAX_MAP_NO")
    tiers = get_search_tiers(buybox)

    input_path = get_step_path(buybox, 8, "buildable")
    output_path = get_step_path(buybox, 9, "comped")

    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    # Compute dynamic PPA bounds from county data
    ppa_floor, ppa_cap = compute_county_ppa_bounds(parcel_url, field_map, wkid)

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        orig_fields = reader.fieldnames

    print(f"Comping {len(rows)} parcels using {len(tiers)} search tiers...\n")

    out_fields = orig_fields + COMP_FIELDS
    results = []

    for i, row in enumerate(rows, 1):
        pid = row.get("parcel_id", "").strip()
        acres = safe_float(row.get("calc_acres", 1), 1.0)
        print(f"  [{i}/{len(rows)}] {pid} ({row.get('address', '')})... ", end="", flush=True)

        centroid = get_parcel_centroid(parcel_url, pid, pid_field, wkid)
        if not centroid:
            print("NO GEOMETRY")
            row.update({k: "" for k in COMP_FIELDS})
            results.append(row)
            continue

        cx, cy = centroid
        land = find_land_comps(parcel_url, cx, cy, acres, tiers, field_map, wkid, ppa_floor, ppa_cap)
        arv = find_arv_comps(parcel_url, cx, cy, tiers, field_map, wkid)
        row.update(land)
        row.update(arv)
        results.append(row)

        lc = land["land_comp_count"]
        ac = arv["arv_comp_count"]
        lv = f"${land['land_est_value']:,.0f}" if land.get("land_est_value") else "?"
        av = f"${arv['arv_comp_median']:,.0f}" if arv.get("arv_comp_median") else "?"
        print(f"land={lc} est {lv} ({land['land_comp_radius']}) | ARV={ac} median {av} ({arv['arv_comp_radius']})")

        time.sleep(0.15)

    # Write output
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    # Summary
    with_land = [r for r in results if r.get("land_comp_count") and r["land_comp_count"] > 0]
    with_arv = [r for r in results if r.get("arv_comp_count") and r["arv_comp_count"] > 0]
    print(f"\n{'=' * 60}")
    print(f"Step 09 - Generate Comps")
    print(f"  Parcels:        {len(results)}")
    print(f"  Land comps:     {len(with_land)}/{len(results)}")
    print(f"  ARV comps:      {len(with_arv)}/{len(results)}")
    print(f"  Output:         {output_path}")


def dry_run(buybox) -> None:
    """Print configuration without making API calls."""
    county = buybox.county
    tiers = get_search_tiers(buybox)
    input_path = get_step_path(buybox, 8, "buildable")
    output_path = get_step_path(buybox, 9, "comped")

    print("=" * 60)
    print("DRY RUN - generate_comps.py (Step 09)")
    print("=" * 60)
    print()
    print(f"BuyBox:               {buybox.pk}")
    print(f"Buyer:                {buybox.buyer}")
    print(f"County:               {county}")
    print(f"Parcel layer URL:     {county.parcel_layer_url}")
    print(f"Parcel layer WKID:    {county.parcel_layer_wkid}")
    print()
    print("--- Search Tiers ---")
    for t in tiers:
        print(f"  {t['label']:20s} radius={t['radius_ft']}ft  lookback={t['lookback_months']}mo")
    print()
    print(f"Input:                {input_path}")
    print(f"Output:               {output_path}")
    print(f"Input exists:         {input_path.exists()}")
    print()
    print("--- Field Map ---")
    for canonical, gis_name in sorted(county.field_map.items()):
        print(f"  {canonical:20s} -> {gis_name}")
    print()
    print("No API calls made.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Step 09: Generate comparable sales for parcels."
    )
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print config without API calls.")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)

    if args.dry_run:
        dry_run(buybox)
    else:
        run_pipeline(buybox)


if __name__ == "__main__":
    main()
