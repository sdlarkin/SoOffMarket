"""
pipeline_common.py - Shared utility module for the parcel sourcing pipeline.

Used by all pipeline scripts. Provides Django bootstrapping, ArcGIS query
helpers, geometry math, data parsing, and entity filtering.
"""

import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Django bootstrap
# ---------------------------------------------------------------------------
# The backend lives one level above execution/pipeline/.
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_api.settings")

import django  # noqa: E402
django.setup()

from buyers.models import BuyBox  # noqa: E402

# Project root (contains .tmp/, execution/, etc.)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

import requests  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SQFT_PER_ACRE = 43_560

# WGS84 approximate scale factors at ~35N latitude (US feet per degree)
WGS84_LAT_SCALE = 364_000  # ft per degree latitude
WGS84_LON_SCALE = 298_000  # ft per degree longitude


# ═══════════════════════════════════════════════════════════════════════════
# Django helpers
# ═══════════════════════════════════════════════════════════════════════════

def load_buybox(buybox_id: str) -> BuyBox:
    """Load a BuyBox by primary key with related buyer and county.

    Args:
        buybox_id: UUID string for the BuyBox.

    Returns:
        BuyBox instance with buyer and county pre-loaded.

    Raises:
        SystemExit: If the BuyBox is not found.
    """
    try:
        return BuyBox.objects.select_related("buyer", "county").get(pk=buybox_id)
    except BuyBox.DoesNotExist:
        print(f"ERROR: BuyBox {buybox_id} not found.")
        raise SystemExit(1)


def get_output_dir(buybox: BuyBox) -> Path:
    """Return the working directory for a buybox run, creating it if needed.

    Path: PROJECT_ROOT / .tmp / {buyer.slug} / {county.slug}
    """
    out = PROJECT_ROOT / ".tmp" / buybox.buyer.slug / buybox.county.slug
    out.mkdir(parents=True, exist_ok=True)
    return out


def get_step_path(buybox: BuyBox, step_num: int, name: str) -> Path:
    """Return a CSV path for a numbered pipeline step.

    Example: .tmp/sara-holt/hamilton-tn/step_01_query.csv

    Args:
        buybox: BuyBox instance (used for directory).
        step_num: Step number (zero-padded to 2 digits).
        name: Descriptive step name (used in filename).

    Returns:
        Path object for the step CSV.
    """
    out_dir = get_output_dir(buybox)
    return out_dir / f"step_{step_num:02d}_{name}.csv"


# ═══════════════════════════════════════════════════════════════════════════
# ArcGIS query helpers
# ═══════════════════════════════════════════════════════════════════════════

def paginated_query(
    url: str,
    params: Dict[str, Any],
    max_records: int = 1000,
) -> List[Dict[str, Any]]:
    """Execute a paginated ArcGIS REST feature query.

    Automatically handles resultOffset/resultRecordCount to retrieve all
    matching features beyond the server's per-request limit.

    Args:
        url: ArcGIS REST query endpoint (ending in /query).
        params: Base query parameters (where, outFields, f, etc.).
        max_records: Page size per request.

    Returns:
        List of feature dicts (each has 'attributes' and optionally 'geometry').
    """
    all_features: List[Dict[str, Any]] = []
    offset = 0

    while True:
        page_params = {**params, "resultOffset": offset, "resultRecordCount": max_records}
        resp = requests.post(url, data=page_params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        offset += len(features)

        # If we got fewer than requested, we've reached the end.
        if len(features) < max_records:
            break

    return all_features


def spatial_query(
    parcel_url: str,
    geometry: Any,
    geometry_type: str,
    spatial_rel: str,
    where: str,
    out_fields: str,
    in_sr: int,
    return_geometry: bool = False,
) -> List[Dict[str, Any]]:
    """Execute a spatial query against an ArcGIS REST feature layer.

    Args:
        parcel_url: ArcGIS REST query endpoint.
        geometry: Geometry object (JSON-serialisable dict or string).
        geometry_type: e.g. 'esriGeometryPolygon', 'esriGeometryEnvelope'.
        spatial_rel: e.g. 'esriSpatialRelIntersects'.
        where: SQL WHERE clause.
        out_fields: Comma-separated field names or '*'.
        in_sr: Input spatial reference WKID.
        return_geometry: Whether to include geometry in results.

    Returns:
        List of attribute dicts (geometry stripped unless return_geometry=True).
    """
    import json as _json

    geom_str = geometry if isinstance(geometry, str) else _json.dumps(geometry)

    params = {
        "geometry": geom_str,
        "geometryType": geometry_type,
        "spatialRel": spatial_rel,
        "where": where,
        "outFields": out_fields,
        "inSR": in_sr,
        "returnGeometry": str(return_geometry).lower(),
        "f": "json",
    }

    resp = requests.post(parcel_url, data=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    features = data.get("features", [])
    if return_geometry:
        return features
    return [f["attributes"] for f in features]


def simplify_rings(rings: List[List[List[float]]], keep_every_n: int = 5) -> List[List[List[float]]]:
    """Reduce polygon point count by keeping every Nth point.

    Useful when passing large geometries as spatial filters to avoid
    URL/body size limits.

    Args:
        rings: List of polygon rings, each a list of [x, y] coordinate pairs.
        keep_every_n: Keep every Nth point (plus always the first and last).

    Returns:
        Simplified rings with reduced point counts.
    """
    simplified = []
    for ring in rings:
        if len(ring) <= keep_every_n * 2:
            simplified.append(ring)
            continue
        kept = [ring[i] for i in range(0, len(ring), keep_every_n)]
        # Ensure the ring is closed (first == last).
        if kept[-1] != ring[-1]:
            kept.append(ring[-1])
        simplified.append(kept)
    return simplified


def build_where_clause(buybox: BuyBox) -> str:
    """Construct an ArcGIS WHERE clause from BuyBox filters.

    Filters applied:
      - building_value = 0 (vacant land)
      - calc_acres >= min_acres
      - appraised_value <= max_price
      - appraised_value > 0

    Uses county.field_map to resolve canonical field names to the actual
    GIS field names for the target county.

    Args:
        buybox: BuyBox with county.field_map populated.

    Returns:
        SQL WHERE string for ArcGIS REST queries.
    """
    fm = buybox.county.field_map
    clauses = []

    # Vacant land: building value must be 0
    bldg_field = fm.get("building_value", "BUILDING_VALUE")
    clauses.append(f"{bldg_field} = 0")

    # Minimum acreage
    if buybox.min_acres is not None:
        acres_field = fm.get("calc_acres", "CALCACRES")
        clauses.append(f"{acres_field} >= {buybox.min_acres}")

    # Maximum appraised value
    if buybox.max_price is not None:
        appr_field = fm.get("appraised_value", "APPRAISED_VALUE")
        clauses.append(f"{appr_field} <= {buybox.max_price}")

    # Appraised value must be positive (excludes tax-exempt/zero-value)
    appr_field = fm.get("appraised_value", "APPRAISED_VALUE")
    clauses.append(f"{appr_field} > 0")

    return " AND ".join(clauses)


# ═══════════════════════════════════════════════════════════════════════════
# Geometry math (pure functions, no API calls)
# ═══════════════════════════════════════════════════════════════════════════

def _ring_area_sqft(ring: List[List[float]], wkid: int = 6576) -> float:
    """Compute signed area of a single ring using the shoelace formula.

    Args:
        ring: List of [x, y] coordinate pairs.
        wkid: Spatial reference. State plane (6576) coords are in feet.
              WGS84 (4326) uses approximate degree-to-feet conversion.

    Returns:
        Absolute area in square feet.
    """
    n = len(ring)
    if n < 3:
        return 0.0

    area = 0.0
    if wkid == 4326:
        # Approximate conversion for WGS84 at ~35N
        for i in range(n):
            j = (i + 1) % n
            x_i = ring[i][0] * WGS84_LON_SCALE
            y_i = ring[i][1] * WGS84_LAT_SCALE
            x_j = ring[j][0] * WGS84_LON_SCALE
            y_j = ring[j][1] * WGS84_LAT_SCALE
            area += x_i * y_j - x_j * y_i
    else:
        # State plane feet — coordinates are already in feet.
        for i in range(n):
            j = (i + 1) % n
            area += ring[i][0] * ring[j][1] - ring[j][0] * ring[i][1]

    return abs(area) / 2.0


def _ring_perimeter(ring: List[List[float]], wkid: int = 6576) -> float:
    """Compute perimeter of a ring in feet.

    Args:
        ring: List of [x, y] coordinate pairs.
        wkid: Spatial reference WKID.

    Returns:
        Perimeter in feet.
    """
    n = len(ring)
    if n < 2:
        return 0.0

    perimeter = 0.0
    for i in range(n):
        j = (i + 1) % n
        if wkid == 4326:
            dx = (ring[j][0] - ring[i][0]) * WGS84_LON_SCALE
            dy = (ring[j][1] - ring[i][1]) * WGS84_LAT_SCALE
        else:
            dx = ring[j][0] - ring[i][0]
            dy = ring[j][1] - ring[i][1]
        perimeter += math.sqrt(dx * dx + dy * dy)

    return perimeter


def compute_acres_from_rings(rings: List[List[List[float]]], wkid: int = 6576) -> float:
    """Compute area in acres from polygon rings.

    The first ring is the outer boundary; subsequent rings are holes
    (subtracted). State plane coordinates (WKID 6576) are in US feet,
    so the shoelace formula gives area directly in square feet.

    Args:
        rings: List of polygon rings, each a list of [x, y] pairs.
        wkid: Spatial reference WKID (default 6576 = state plane feet).

    Returns:
        Area in acres.
    """
    if not rings:
        return 0.0

    # First ring is outer boundary (positive area).
    total_sqft = _ring_area_sqft(rings[0], wkid)

    # Subsequent rings are holes (subtract).
    for hole in rings[1:]:
        total_sqft -= _ring_area_sqft(hole, wkid)

    return max(total_sqft, 0.0) / SQFT_PER_ACRE


def compute_compactness(rings: List[List[List[float]]], wkid: int = 6576) -> float:
    """Compute the Polsby-Popper compactness ratio.

    Formula: 4 * pi * area / perimeter^2
    Result is 0-1 where 1 = perfect circle, approaching 0 = elongated strip.

    Uses only the outer ring (first ring) for the calculation.

    Args:
        rings: Polygon rings.
        wkid: Spatial reference WKID.

    Returns:
        Compactness ratio (float 0-1).
    """
    if not rings or len(rings[0]) < 3:
        return 0.0

    area = _ring_area_sqft(rings[0], wkid)
    perimeter = _ring_perimeter(rings[0], wkid)

    if perimeter == 0:
        return 0.0

    return (4.0 * math.pi * area) / (perimeter * perimeter)


def compute_centroid(rings: List[List[List[float]]]) -> Tuple[float, float]:
    """Compute the centroid (average of all points) of the outer ring.

    Args:
        rings: Polygon rings. Uses only the first (outer) ring.

    Returns:
        Tuple (cx, cy) — centroid coordinates.
    """
    if not rings or not rings[0]:
        return (0.0, 0.0)

    ring = rings[0]
    n = len(ring)
    cx = sum(pt[0] for pt in ring) / n
    cy = sum(pt[1] for pt in ring) / n
    return (cx, cy)


# ═══════════════════════════════════════════════════════════════════════════
# Outlier removal
# ═══════════════════════════════════════════════════════════════════════════

def remove_outliers(
    comps: List[Dict[str, Any]],
    price_key: str = "SALE1CONSD",
    acres_key: str = "CALCACRES",
    is_land: bool = False,
    ppa_floor: Optional[float] = None,
    ppa_cap: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Remove outlier comps using IQR-based filtering.

    Steps:
      1. Enforce a $5,000 minimum sale price.
      2. Compute price-per-acre values.
      3. Remove PPA outliers outside 1.5 * IQR.
      4. If is_land and floor/cap provided, also clip by $/acre bounds.

    Args:
        comps: List of comp dicts with price and acreage fields.
        price_key: Key for sale price in each comp dict.
        acres_key: Key for acreage in each comp dict.
        is_land: If True, also apply ppa_floor/ppa_cap filtering.
        ppa_floor: Minimum $/acre (only used if is_land=True).
        ppa_cap: Maximum $/acre (only used if is_land=True).

    Returns:
        Filtered list of comp dicts.
    """
    MIN_SALE_PRICE = 5_000

    # Step 1: enforce minimum sale price
    filtered = []
    for c in comps:
        price = safe_float(c.get(price_key, 0))
        if price is not None and price >= MIN_SALE_PRICE:
            filtered.append(c)

    if not filtered:
        return filtered

    # Step 2: compute PPA values
    ppas = []
    for c in filtered:
        price = safe_float(c.get(price_key, 0)) or 0.0
        acres = safe_float(c.get(acres_key, 0)) or 0.0
        if acres > 0:
            ppas.append(price / acres)

    if not ppas:
        return filtered

    # Step 3: IQR-based outlier removal on PPA
    ppas_sorted = sorted(ppas)
    n = len(ppas_sorted)
    q1 = ppas_sorted[n // 4] if n >= 4 else ppas_sorted[0]
    q3 = ppas_sorted[(3 * n) // 4] if n >= 4 else ppas_sorted[-1]
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    result = []
    for c in filtered:
        price = safe_float(c.get(price_key, 0)) or 0.0
        acres = safe_float(c.get(acres_key, 0)) or 0.0
        if acres <= 0:
            result.append(c)  # Keep comps without acreage data
            continue
        ppa = price / acres
        if lower_bound <= ppa <= upper_bound:
            result.append(c)

    # Step 4: apply explicit PPA floor/cap for land comps
    if is_land and (ppa_floor is not None or ppa_cap is not None):
        bounded = []
        for c in result:
            price = safe_float(c.get(price_key, 0)) or 0.0
            acres = safe_float(c.get(acres_key, 0)) or 0.0
            if acres <= 0:
                bounded.append(c)
                continue
            ppa = price / acres
            if ppa_floor is not None and ppa < ppa_floor:
                continue
            if ppa_cap is not None and ppa > ppa_cap:
                continue
            bounded.append(c)
        return bounded

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Data helpers
# ═══════════════════════════════════════════════════════════════════════════

def safe_int(val: Any, default: int = 0) -> int:
    """Robustly convert a value to int.

    Handles dollar signs, commas, whitespace, empty strings, and None.

    Args:
        val: Input value (str, int, float, or None).
        default: Fallback if conversion fails.

    Returns:
        Integer value.
    """
    if val is None:
        return default
    try:
        cleaned = str(val).replace("$", "").replace(",", "").strip()
        if not cleaned:
            return default
        return int(float(cleaned))
    except (ValueError, TypeError):
        return default


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Robustly convert a value to float.

    Handles dollar signs, commas, whitespace, empty strings, and None.

    Args:
        val: Input value.
        default: Fallback if conversion fails.

    Returns:
        Float value or default.
    """
    if val is None:
        return default
    try:
        cleaned = str(val).replace("$", "").replace(",", "").strip()
        if not cleaned:
            return default
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def format_epoch(epoch_ms: Any) -> str:
    """Convert epoch milliseconds to MM/YYYY string.

    Args:
        epoch_ms: Epoch timestamp in milliseconds (int, float, or string).

    Returns:
        Formatted date string, or empty string on error.
    """
    try:
        ts = float(epoch_ms) / 1000.0
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%m/%Y")
    except (ValueError, TypeError, OSError, OverflowError):
        return ""


def parse_owner_name(name: str) -> Tuple[str, str]:
    """Parse a county-style owner name into (first, last).

    County records use LASTNAME FIRSTNAME MIDDLE format. If '&' is present
    (indicating multiple owners), only the first person is parsed.

    Args:
        name: Raw owner name string, e.g. "SMITH JOHN DAVID & JANE".

    Returns:
        Tuple (first_name, last_name). Empty strings if unparseable.
    """
    if not name or not name.strip():
        return ("", "")

    # Take only the first person if & present
    name = name.strip()
    if "&" in name:
        name = name.split("&")[0].strip()

    parts = name.split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])

    last = parts[0]
    first = parts[1]
    return (first, last)


def parse_address(mailing: str) -> Dict[str, str]:
    """Parse a mailing address string into components.

    Expected format: "STREET, CITY, STATE ZIP"

    Args:
        mailing: Raw address string.

    Returns:
        Dict with keys: street, city, state, zip. Missing parts are empty strings.
    """
    result = {"street": "", "city": "", "state": "", "zip": ""}

    if not mailing or not mailing.strip():
        return result

    parts = [p.strip() for p in mailing.split(",")]

    if len(parts) >= 1:
        result["street"] = parts[0]

    if len(parts) >= 2:
        result["city"] = parts[1]

    if len(parts) >= 3:
        # Last part should be "STATE ZIP" or just "STATE"
        state_zip = parts[2].strip()
        sz_parts = state_zip.split()
        if len(sz_parts) >= 1:
            result["state"] = sz_parts[0]
        if len(sz_parts) >= 2:
            result["zip"] = sz_parts[1]

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Entity filtering
# ═══════════════════════════════════════════════════════════════════════════

UNIVERSAL_ENTITY_KEYWORDS: List[str] = [
    # Government
    "CITY OF", "COUNTY OF", "STATE OF", "UNITED STATES",
    # Religious
    "CHURCH", "BAPTIST", "METHODIST", "MINISTRY", "MINISTRIES",
    "CONGREGATION", "DIOCESE", "TEMPLE", "MOSQUE", "SYNAGOGUE",
    # Associations / HOA
    "HOMEOWNERS ASSOC", "COMMUNITY ASSOC", "HOA",
    "PROPERTY OWNERS", "TOWNHOME OWNERS", "CONDO ASSOC",
    # Institutional
    "SCHOOL", "BOARD OF EDUCATION", "UNIVERSITY", "COLLEGE",
    "HOSPITAL", "CEMETERY", "MEMORIAL",
    # Utility
    "UTILITY DIST", "ELECTRIC POWER", "WATER DIST",
    # Business entities
    "LLC", "INC", "CORP", "LTD", "COMPANY",
    "CONSTRUCTION", "DEVELOPMENT", "PROPERTIES", "REALTY",
    "REAL ESTATE", "INVESTMENT", "HOLDINGS",
    "PARTNERS", "PARTNERSHIP", "GROUP", "ENTERPRISE",
    "MANAGEMENT", "CAPITAL", "VENTURES", "FUND",
]


def is_excluded_entity(
    owner_name: str,
    county_keywords: Optional[List[str]] = None,
) -> bool:
    """Check if an owner name matches any exclusion keywords.

    Tests against UNIVERSAL_ENTITY_KEYWORDS plus any county-specific
    keywords (stored in County.entity_keywords).

    Args:
        owner_name: Owner name to check.
        county_keywords: Additional county-specific keywords to check.

    Returns:
        True if the owner should be excluded.
    """
    if not owner_name:
        return False

    upper = owner_name.upper()
    for kw in UNIVERSAL_ENTITY_KEYWORDS:
        if kw in upper:
            return True

    if county_keywords:
        for kw in county_keywords:
            if kw.upper() in upper:
                return True

    return False
