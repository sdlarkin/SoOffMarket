"""
skip_trace.py - Skip trace property owners linked to a specific buybox.

Uses the Apify Skip Trace actor to look up phone numbers and emails for
owners of Yes/Maybe rated parcels. Creates/updates Owner records in Django
and links them to their Parcel via FK. Deduplicates owners across parcels.

Usage:
    python skip_trace.py --buybox-id <UUID>
    python skip_trace.py --buybox-id <UUID> --dry-run
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from dotenv import load_dotenv

from pipeline_common import (
    get_step_path,
    load_buybox,
    parse_address,
    parse_owner_name,
    PROJECT_ROOT,
)

from parcels.models import Owner, Parcel, ParcelRating  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Load .env for API tokens
load_dotenv(PROJECT_ROOT / ".env")

APIFY_TOKEN = os.environ.get("APIFY_SDANELARKIN_TOKEN", "").strip()
ACTOR_ID = "one-api~skip-trace"

# Default ratings to trace
DEFAULT_RATINGS_TO_TRACE = ["yes", "maybe"]


# ---------------------------------------------------------------------------
# Apify API
# ---------------------------------------------------------------------------

def run_skip_trace_batch(people: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Run the Apify skip trace actor for a batch of people.

    Input format per the actor: name as 'FIRST LAST; CITY, STATE ZIP'
    and address as 'STREET; CITY, STATE ZIP'.

    Args:
        people: List of dicts with 'owner_name' and 'owner_mailing' keys.

    Returns:
        List of result dicts from the actor.
    """
    name_list = []
    address_list = []

    for p in people:
        first, last = parse_owner_name(p["owner_name"])
        addr = parse_address(p["owner_mailing"])

        name_str = f"{first} {last}; {addr['city']}, {addr['state']} {addr['zip']}".strip()
        name_list.append(name_str)

        addr_str = f"{addr['street']}; {addr['city']}, {addr['state']} {addr['zip']}".strip()
        address_list.append(addr_str)

    run_input = {
        "name": name_list,
        "street_citystatezip": address_list,
    }

    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    params = {"token": APIFY_TOKEN, "timeout": 300}

    r = requests.post(url, json=run_input, params=params, timeout=360)
    if r.status_code not in (200, 201):
        print(f"    API error: {r.status_code} {r.text[:300]}")
        return []

    results = r.json()
    if isinstance(results, list):
        return results
    return []


def extract_contacts(result: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Extract phone and email lists from a skip trace result.

    Actor returns fields like Phone-1, Phone-2, Email-1, Email-2, etc.

    Returns:
        Tuple of (phone_list, email_list).
    """
    phone_list = []
    email_list = []
    for key, val in result.items():
        if not val or not str(val).strip():
            continue
        if key.startswith("Phone-"):
            phone_list.append(str(val).strip())
        elif key.startswith("Email-"):
            email_list.append(str(val).strip())
    return phone_list, email_list


def extract_phone_type(result: Dict[str, Any], index: int) -> str:
    """Extract phone type (Landline/Wireless/VoIP) for a given phone index."""
    key = f"Phone-{index}-Type"
    return str(result.get(key, "")).strip()


# ---------------------------------------------------------------------------
# Owner management
# ---------------------------------------------------------------------------

def create_or_update_owner(
    owner_name: str, mailing: str,
    phones: List[str], emails: List[str],
    raw_result: Dict[str, Any],
) -> Owner:
    """Create or update an Owner record with skip trace data.

    Deduplicates by owner name (case-insensitive match).

    Args:
        owner_name: Raw owner name from county records.
        mailing: Mailing address string.
        phones: List of phone numbers.
        emails: List of email addresses.
        raw_result: Full raw result from Apify for extracting phone types.

    Returns:
        Owner instance.
    """
    first, last = parse_owner_name(owner_name)

    defaults = {
        "first_name": first,
        "last_name": last,
        "mailing_address": mailing,
        "skip_traced": True,
        "skip_trace_date": datetime.now(),
    }

    # Assign phones (up to 3)
    if len(phones) >= 1:
        defaults["phone_1"] = phones[0]
        defaults["phone_1_type"] = extract_phone_type(raw_result, 1)
    if len(phones) >= 2:
        defaults["phone_2"] = phones[1]
        defaults["phone_2_type"] = extract_phone_type(raw_result, 2)
    if len(phones) >= 3:
        defaults["phone_3"] = phones[2]
        defaults["phone_3_type"] = extract_phone_type(raw_result, 3)

    # Assign emails (up to 3)
    if len(emails) >= 1:
        defaults["email_1"] = emails[0]
    if len(emails) >= 2:
        defaults["email_2"] = emails[1]
    if len(emails) >= 3:
        defaults["email_3"] = emails[2]

    # Age if available
    age = raw_result.get("Age", "") or raw_result.get("age", "")
    if age:
        defaults["age"] = str(age).strip()

    owner, _ = Owner.objects.update_or_create(
        name=owner_name.strip(),
        defaults=defaults,
    )
    return owner


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(buybox) -> None:
    """Skip trace owners of rated parcels linked to this buybox."""
    if not APIFY_TOKEN:
        print("ERROR: APIFY_SDANELARKIN_TOKEN not found in .env")
        sys.exit(1)

    # Get parcels for this specific buybox with yes/maybe ratings
    ratings_to_trace = DEFAULT_RATINGS_TO_TRACE
    rated_parcels = Parcel.objects.filter(
        buybox=buybox,
        is_target=True,
        rating__rating__in=ratings_to_trace,
    ).select_related("rating")

    # Deduplicate owners across parcels
    seen_owners = set()
    to_trace = []
    parcel_map = {}  # owner_key -> list of parcels

    for p in rated_parcels:
        owner_key = p.owner_name.strip().upper()
        if not owner_key:
            continue
        if owner_key not in seen_owners:
            seen_owners.add(owner_key)
            to_trace.append({
                "parcel_id": p.parcel_id,
                "owner_name": p.owner_name,
                "owner_mailing": p.owner_mailing,
                "rating": p.rating.rating,
            })
            parcel_map[owner_key] = [p]
        else:
            parcel_map[owner_key].append(p)

    if not to_trace:
        print("No rated parcels found to trace for this buybox.")
        return

    print(f"Skip tracing {len(to_trace)} unique owners from {rated_parcels.count()} parcels...\n")
    for t in to_trace:
        first, last = parse_owner_name(t["owner_name"])
        addr = parse_address(t["owner_mailing"])
        print(f"  [{t['rating']}] {first} {last} -> {addr['street']}, {addr['city']} {addr['state']}")

    print(f"\nCalling Apify actor ({ACTOR_ID})...")
    raw_results = run_skip_trace_batch(to_trace)
    print(f"Got {len(raw_results)} results back\n")

    # Debug: print raw result structure
    if raw_results:
        print(f"Sample result keys: {list(raw_results[0].keys())[:15]}")

    # Match results back to owners and create/update Owner records
    owners_created = 0
    owners_with_phone = 0
    owners_with_email = 0

    for i, t in enumerate(to_trace):
        owner_key = t["owner_name"].strip().upper()

        # Match result by index, fallback to name matching
        matched = None
        if i < len(raw_results):
            matched = raw_results[i]
        else:
            first, last = parse_owner_name(t["owner_name"])
            for r in raw_results:
                r_name = (r.get("name", "") or r.get("fullName", "")).upper()
                if last.upper() in r_name:
                    matched = r
                    break

        if matched:
            phones, emails = extract_contacts(matched)
        else:
            phones, emails = [], []

        # Create/update Owner record
        owner = create_or_update_owner(
            t["owner_name"], t["owner_mailing"],
            phones, emails, matched or {},
        )
        owners_created += 1
        if phones:
            owners_with_phone += 1
        if emails:
            owners_with_email += 1

        # Link Owner to all their parcels
        parcels = parcel_map.get(owner_key, [])
        for parcel in parcels:
            parcel.owner = owner
            parcel.save(update_fields=["owner"])

        phone_str = ", ".join(phones[:3]) if phones else "none"
        email_str = ", ".join(emails[:2]) if emails else "none"
        print(f"  {t['owner_name'][:35]:<36} ph: {phone_str}  |  em: {email_str}  |  {len(parcels)} parcels")

    # Save full results to tmp
    output_path = get_step_path(buybox, 12, "skip_trace_results").with_suffix(".json")
    full_results = []
    for i, t in enumerate(to_trace):
        result = raw_results[i] if i < len(raw_results) else {}
        phones, emails = extract_contacts(result) if result else ([], [])
        full_results.append({
            "parcel_id": t["parcel_id"],
            "owner": t["owner_name"],
            "phones": phones,
            "emails": emails,
            "raw": result,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2, default=str)
    print(f"\nFull results saved to {output_path.name}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Skip Trace Summary")
    print(f"  Owners traced:    {owners_created}")
    print(f"  With phone:       {owners_with_phone}/{owners_created}")
    print(f"  With email:       {owners_with_email}/{owners_created}")
    print(f"  Parcels linked:   {sum(len(v) for v in parcel_map.values())}")


def dry_run(buybox) -> None:
    """Preview which owners would be traced without calling the API."""
    ratings_to_trace = DEFAULT_RATINGS_TO_TRACE

    rated_parcels = Parcel.objects.filter(
        buybox=buybox,
        is_target=True,
        rating__rating__in=ratings_to_trace,
    ).select_related("rating")

    # Deduplicate
    seen = set()
    unique_owners = []
    for p in rated_parcels:
        key = p.owner_name.strip().upper()
        if key and key not in seen:
            seen.add(key)
            unique_owners.append(p)

    print("=" * 60)
    print("DRY RUN - skip_trace.py")
    print("=" * 60)
    print()
    print(f"BuyBox:               {buybox.pk}")
    print(f"Buyer:                {buybox.buyer}")
    print(f"Ratings to trace:     {ratings_to_trace}")
    print(f"APIFY token set:      {'Yes' if APIFY_TOKEN else 'NO'}")
    print(f"Actor ID:             {ACTOR_ID}")
    print()
    print(f"Rated parcels:        {rated_parcels.count()}")
    print(f"Unique owners:        {len(unique_owners)}")
    est_cost = len(unique_owners) * 0.007
    print(f"Estimated cost:       ${est_cost:.2f} (~$0.007/lookup)")
    print()

    if unique_owners:
        print("Owners to trace:")
        for p in unique_owners[:20]:
            first, last = parse_owner_name(p.owner_name)
            print(f"  [{p.rating.rating}] {first} {last} | {p.owner_mailing[:40]}")
        if len(unique_owners) > 20:
            print(f"  ... and {len(unique_owners) - 20} more")

    print()
    print("No API calls made. No database changes.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Skip trace owners of rated parcels for a buybox."
    )
    parser.add_argument("--buybox-id", required=True, help="BuyBox UUID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls or DB changes.")
    args = parser.parse_args()

    buybox = load_buybox(args.buybox_id)

    if args.dry_run:
        dry_run(buybox)
    else:
        run_pipeline(buybox)


if __name__ == "__main__":
    main()
