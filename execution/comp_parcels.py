"""
Generate comparable sales for vacant R-2 parcels using Hamilton County GIS data.

For each parcel, queries nearby properties to produce:
  1. Land comps - recent vacant lot sales within radius
  2. ARV comps  - recent duplex/improved sales within radius (what a built duplex sells for)

Data source: Hamilton County Live_Parcels MapServer
Land use codes: 111=SFR, 112=Duplex, 113=Triplex, 114=Quad, 116=Condo, 117=Townhome
"""

import csv
import json
import sys
import time
import statistics
import requests
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp" / "sara_holt_segments"

INPUT_CSV = TMP_DIR / "top_deals.csv"
OUTPUT_CSV = TMP_DIR / "top_deals_comped.csv"

PARCEL_URL = "https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_Parcels/MapServer/0/query"

# $/acre bounds for land comps, derived from the county's own sales distribution.
# Floor: bottom percentile (filters distress sales, tax liens, family transfers)
# Cap: multiplier of median (filters subdivision/new-construction lots)
PPA_FLOOR_PERCENTILE = 25   # 25th percentile of county $/acre
PPA_CAP_MULTIPLIER = 3.0    # 300% of county median $/acre

# Search parameters - start tight, widen if needed
LAND_COMP_CONFIGS = [
    {"radius_ft": 2640, "date_cutoff": "2024-10-14", "label": "0.5mi/18mo"},
    {"radius_ft": 5280, "date_cutoff": "2024-04-14", "label": "1mi/2yr"},
    {"radius_ft": 10560, "date_cutoff": "2023-04-14", "label": "2mi/3yr"},
]

ARV_COMP_CONFIGS = [
    {"radius_ft": 2640, "date_cutoff": "2024-10-14", "label": "0.5mi/18mo"},
    {"radius_ft": 5280, "date_cutoff": "2024-04-14", "label": "1mi/2yr"},
    {"radius_ft": 10560, "date_cutoff": "2023-04-14", "label": "2mi/3yr"},
]

MIN_LAND_COMPS = 2
MIN_ARV_COMPS = 2


def get_parcel_centroid(tax_map_no: str) -> tuple[float, float] | None:
    """Get the centroid of a parcel polygon."""
    r = requests.get(PARCEL_URL, params={
        "where": f"TAX_MAP_NO = '{tax_map_no}'",
        "outFields": "TAX_MAP_NO",
        "returnGeometry": "true",
        "outSR": "6576",
        "f": "json",
    }, timeout=15)
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    rings = feats[0]["geometry"].get("rings", [[]])
    if not rings or not rings[0]:
        return None
    pts = rings[0]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return (cx, cy)


SQFT_PER_ACRE = 43560

# Will be set at startup by compute_county_ppa_bounds()
COUNTY_PPA_CAP = None
COUNTY_PPA_FLOOR = None


def compute_county_ppa_bounds() -> tuple[float, float]:
    """Query countywide vacant land sales to compute dynamic $/acre bounds.
    Returns (floor, cap) based on the county's own sales distribution."""
    print("Computing county $/acre bounds for land comp filtering...")
    r = requests.get(PARCEL_URL, params={
        "where": (
            "BUILDVALUE = 0 AND CALCACRES > 0.1 AND CALCACRES <> 1 "
            "AND SALE1CONSD >= 5000 AND SALE1DATE >= date '2024-04-15'"
        ),
        "outFields": "CALCACRES,SALE1CONSD",
        "returnGeometry": "false",
        "resultRecordCount": "1000",
        "f": "json",
    }, timeout=30)
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        print("  WARNING: No county sales data found, using fallbacks")
        return (5000, 150000)

    ppas = sorted(f["attributes"]["SALE1CONSD"] / f["attributes"]["CALCACRES"] for f in feats)
    median_ppa = statistics.median(ppas)
    floor = ppas[int(len(ppas) * PPA_FLOOR_PERCENTILE / 100)]
    cap = median_ppa * PPA_CAP_MULTIPLIER
    print(f"  County sample: {len(feats)} sales | median $/acre: ${median_ppa:,.0f}")
    print(f"  Floor ({PPA_FLOOR_PERCENTILE}th pct): ${floor:,.0f}/acre | Cap ({PPA_CAP_MULTIPLIER}x median): ${cap:,.0f}/acre")
    return (floor, cap)


def compute_acres_from_geometry(geometry: dict) -> float:
    """Compute real acreage from a parcel polygon in state plane feet (WKID 6576)."""
    rings = geometry.get("rings", [[]])
    if not rings or not rings[0] or len(rings[0]) < 3:
        return 0
    pts = rings[0]
    n = len(pts)
    area = abs(sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
        for i in range(n)
    )) / 2
    return area / SQFT_PER_ACRE


def query_comps(cx: float, cy: float, where: str, radius_ft: int, fields: str) -> list[dict]:
    """Spatial radius query for comparable sales. Computes real acreage from geometry."""
    point = {"x": cx, "y": cy, "spatialReference": {"wkid": 6576}}
    r = requests.post(PARCEL_URL, data={
        "where": where,
        "geometry": json.dumps(point),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(radius_ft),
        "units": "esriSRUnit_Foot",
        "inSR": "6576",
        "outFields": fields,
        "returnGeometry": "true",
        "outSR": "6576",
        "f": "json",
    }, timeout=30)
    data = r.json()
    if data.get("error"):
        return []
    results = []
    for f in data.get("features", []):
        attrs = f["attributes"]
        # Compute real acreage if GIS reports exactly 1.0 (known bad default)
        if attrs.get("CALCACRES") == 1.0 and f.get("geometry"):
            real = compute_acres_from_geometry(f["geometry"])
            if real > 0.01:
                attrs["CALCACRES"] = round(real, 3)
        results.append(attrs)
    return results


def format_epoch(epoch_ms) -> str:
    if not epoch_ms:
        return ""
    try:
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%m/%Y")
    except (OSError, ValueError):
        return ""


def remove_outliers(comps: list[dict], key: str = "SALE1CONSD", is_land: bool = False) -> list[dict]:
    """Remove statistical outliers using IQR method on sale price.
    For land comps, also caps $/acre to filter out premium subdivision lots."""
    # Floor: remove non-arm's-length sales
    comps = [c for c in comps if c[key] >= 5000]

    # For land comps: remove lots with $/acre outside county bounds
    # Floor filters distress/non-arm's-length sales, cap filters subdivision lots
    if is_land and COUNTY_PPA_FLOOR and COUNTY_PPA_CAP:
        comps = [c for c in comps
                 if c.get("CALCACRES", 1) > 0.01
                 and COUNTY_PPA_FLOOR <= c[key] / max(c["CALCACRES"], 0.01) <= COUNTY_PPA_CAP]

    if len(comps) < 4:
        return comps

    prices = sorted(c[key] for c in comps)
    q1 = prices[len(prices) // 4]
    q3 = prices[3 * len(prices) // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    lower = max(lower, 5000)
    return [c for c in comps if lower <= c[key] <= upper]


def find_land_comps(cx: float, cy: float, subject_acres: float) -> dict:
    """Find vacant land comps, widening search until we get enough."""
    fields = "TAX_MAP_NO,ADDRESS,CALCACRES,SALE1DATE,SALE1CONSD,APPVALUE,LANDVALUE"

    for config in LAND_COMP_CONFIGS:
        where = (
            f"BUILDVALUE = 0 AND CALCACRES >= 0.15 AND SALE1CONSD > 0 "
            f"AND SALE1DATE >= date '{config['date_cutoff']}'"
        )
        comps = query_comps(cx, cy, where, config["radius_ft"], fields)
        # Remove outliers: non-arm's-length sales (<$5K) and IQR extremes
        comps = remove_outliers(comps, is_land=True)

        if len(comps) >= MIN_LAND_COMPS:
            prices = [c["SALE1CONSD"] for c in comps]
            # Price per acre for normalization
            ppa = [c["SALE1CONSD"] / max(c["CALCACRES"], 0.1) for c in comps]
            return {
                "land_comp_count": len(comps),
                "land_comp_radius": config["label"],
                "land_comp_min": min(prices),
                "land_comp_max": max(prices),
                "land_comp_median": statistics.median(prices),
                "land_comp_avg_ppa": round(statistics.mean(ppa)),
                "land_est_value": round(statistics.median(ppa) * subject_acres),
                "land_comp_details": "; ".join(
                    f"{c['ADDRESS'] or '?'} {c['CALCACRES']}ac ${c['SALE1CONSD']:,.0f} ({format_epoch(c['SALE1DATE'])})"
                    for c in sorted(comps, key=lambda x: x["SALE1DATE"] or 0, reverse=True)[:5]
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
        "land_comp_details": "No comps found within 2mi/3yr",
    }


def find_arv_comps(cx: float, cy: float) -> dict:
    """Find duplex/improved ARV comps, widening search until we get enough."""
    fields = "TAX_MAP_NO,ADDRESS,CALCACRES,SALE1DATE,SALE1CONSD,APPVALUE,BUILDVALUE,LUCODE"

    for config in ARV_COMP_CONFIGS:
        # Duplexes (112) and small multi-family
        where = (
            f"LUCODE IN (112,113,114) AND BUILDVALUE > 50000 AND SALE1CONSD > 50000 "
            f"AND SALE1DATE >= date '{config['date_cutoff']}'"
        )
        comps = query_comps(cx, cy, where, config["radius_ft"], fields)
        comps = remove_outliers(comps)

        if len(comps) >= MIN_ARV_COMPS:
            prices = [c["SALE1CONSD"] for c in comps]
            return {
                "arv_comp_count": len(comps),
                "arv_comp_radius": config["label"],
                "arv_comp_min": min(prices),
                "arv_comp_max": max(prices),
                "arv_comp_median": statistics.median(prices),
                "arv_comp_details": "; ".join(
                    f"{c['ADDRESS'] or '?'} ${c['SALE1CONSD']:,.0f} ({format_epoch(c['SALE1DATE'])}) lu={int(c['LUCODE'])}"
                    for c in sorted(comps, key=lambda x: x["SALE1DATE"] or 0, reverse=True)[:5]
                ),
            }

        # If no duplexes, fall back to SFR comps as rough ARV floor
        if len(comps) < MIN_ARV_COMPS:
            where_sfr = (
                f"LUCODE = 111 AND BUILDVALUE > 50000 AND SALE1CONSD > 50000 "
                f"AND SALE1DATE >= date '{config['date_cutoff']}'"
            )
            sfr_comps = query_comps(cx, cy, where_sfr, config["radius_ft"], fields)
            sfr_comps = remove_outliers(sfr_comps)

            all_comps = comps + sfr_comps
            if len(all_comps) >= MIN_ARV_COMPS:
                prices = [c["SALE1CONSD"] for c in all_comps]
                return {
                    "arv_comp_count": len(all_comps),
                    "arv_comp_radius": config["label"] + " (incl SFR)",
                    "arv_comp_min": min(prices),
                    "arv_comp_max": max(prices),
                    "arv_comp_median": statistics.median(prices),
                    "arv_comp_details": "; ".join(
                        f"{c['ADDRESS'] or '?'} ${c['SALE1CONSD']:,.0f} ({format_epoch(c['SALE1DATE'])}) lu={int(c['LUCODE'])}"
                        for c in sorted(all_comps, key=lambda x: x["SALE1DATE"] or 0, reverse=True)[:5]
                    ),
                }

    return {
        "arv_comp_count": 0,
        "arv_comp_radius": "none",
        "arv_comp_min": "",
        "arv_comp_max": "",
        "arv_comp_median": "",
        "arv_comp_details": "No duplex/SFR comps found within 2mi/3yr",
    }


def main():
    global COUNTY_PPA_FLOOR, COUNTY_PPA_CAP
    COUNTY_PPA_FLOOR, COUNTY_PPA_CAP = compute_county_ppa_bounds()

    if not INPUT_CSV.exists():
        print(f"ERROR: {INPUT_CSV} not found")
        sys.exit(1)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        orig_fields = reader.fieldnames

    print(f"Comping {len(rows)} parcels...\n")

    comp_fields = [
        "land_comp_count", "land_comp_radius", "land_comp_min", "land_comp_max",
        "land_comp_median", "land_comp_avg_ppa", "land_est_value", "land_comp_details",
        "arv_comp_count", "arv_comp_radius", "arv_comp_min", "arv_comp_max",
        "arv_comp_median", "arv_comp_details",
    ]
    out_fields = orig_fields + comp_fields

    results = []
    for i, row in enumerate(rows, 1):
        pid = row["parcel_id"]
        acres = float(row.get("calc_acres", 1) or 1)
        print(f"  [{i}/{len(rows)}] {pid} ({row.get('address','')})... ", end="", flush=True)

        centroid = get_parcel_centroid(pid)
        if not centroid:
            print("NO GEOMETRY")
            row.update({k: "" for k in comp_fields})
            results.append(row)
            continue

        cx, cy = centroid
        land = find_land_comps(cx, cy, acres)
        arv = find_arv_comps(cx, cy)
        row.update(land)
        row.update(arv)
        results.append(row)

        lc = land["land_comp_count"]
        ac = arv["arv_comp_count"]
        lv = f"${land['land_est_value']:,.0f}" if land.get("land_est_value") else "?"
        av = f"${arv['arv_comp_median']:,.0f}" if arv.get("arv_comp_median") else "?"
        print(f"land={lc} comps est {lv} ({land['land_comp_radius']}) | ARV={ac} comps median {av} ({arv['arv_comp_radius']})")

        time.sleep(0.15)

    # Write output
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    # Summary stats
    with_land = [r for r in results if r.get("land_comp_count") and r["land_comp_count"] > 0]
    with_arv = [r for r in results if r.get("arv_comp_count") and r["arv_comp_count"] > 0]
    print(f"\n{'='*60}")
    print(f"Results: {len(results)} parcels")
    print(f"  Land comps found: {len(with_land)}/{len(results)}")
    print(f"  ARV comps found:  {len(with_arv)}/{len(results)}")
    print(f"Output: {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
