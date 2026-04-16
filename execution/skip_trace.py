"""
Skip trace property owners using Apify's Skip Trace actor (one-api/skip-trace).
Feeds owner name + mailing address, gets back phone numbers, emails, etc.
Only traces unique owners from Yes/Maybe rated parcels.

Apify actor: https://apify.com/one-api/skip-trace
Cost: ~$0.007 per lookup
"""

import json
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APIFY_TOKEN = os.environ.get("APIFY_SDANELARKIN_TOKEN", "").strip()
ACTOR_ID = "one-api~skip-trace"

# Setup Django
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_api.settings")
import django
django.setup()
from parcels.models import Parcel


def parse_address(mailing: str) -> dict:
    """Parse 'STREET, CITY, STATE ZIP' into components."""
    parts = [p.strip() for p in mailing.split(",")]
    if len(parts) >= 3:
        street = parts[0]
        city = parts[1]
        state_zip = parts[2].split()
        state = state_zip[0] if state_zip else ""
        zipcode = state_zip[1] if len(state_zip) > 1 else ""
    elif len(parts) == 2:
        street = parts[0]
        city_state_zip = parts[1].split()
        city = " ".join(city_state_zip[:-2]) if len(city_state_zip) > 2 else ""
        state = city_state_zip[-2] if len(city_state_zip) >= 2 else ""
        zipcode = city_state_zip[-1] if len(city_state_zip) >= 1 else ""
    else:
        street = mailing
        city = state = zipcode = ""
    return {"street": street, "city": city, "state": state, "zip": zipcode}


def parse_owner_name(name: str) -> tuple[str, str]:
    """Parse 'LASTNAME FIRSTNAME MIDDLE...' into (first, last).
    County records are LAST FIRST format."""
    parts = name.strip().split()
    if len(parts) >= 2:
        # Handle "& SPOUSE" by taking just the primary person
        amp_idx = None
        for i, p in enumerate(parts):
            if p == "&":
                amp_idx = i
                break
        if amp_idx and amp_idx >= 2:
            parts = parts[:amp_idx]
        last = parts[0]
        first = parts[1] if len(parts) > 1 else ""
        return (first, last)
    return (name, "")


def run_skip_trace_batch(people: list[dict]) -> list[dict]:
    """Run the Apify skip trace actor for a batch of people.
    Input format: name as 'FIRST LAST; CITY, STATE' and address as 'STREET; CITY, STATE ZIP'"""
    name_list = []
    address_list = []

    for p in people:
        first, last = parse_owner_name(p["owner_name"])
        addr = parse_address(p["owner_mailing"])

        # Format: "First Last; City, State ZIP"
        name_str = f"{first} {last}; {addr['city']}, {addr['state']} {addr['zip']}".strip()
        name_list.append(name_str)

        # Format: "Street; City, State ZIP"
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


def extract_contacts(result: dict) -> tuple[list[str], list[str]]:
    """Extract phone and email lists from a skip trace result.
    Actor returns fields like Phone-1, Phone-2, Email-1, Email-2, etc."""
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


def main():
    if not APIFY_TOKEN:
        print("ERROR: APIFY_SDANELARKIN_TOKEN not found in .env")
        sys.exit(1)

    # Get unique owners from Yes/Maybe parcels
    rated = Parcel.objects.filter(
        is_target=True,
        rating__rating__in=['yes', 'maybe']
    ).select_related('rating')

    seen_owners = set()
    to_trace = []
    for p in rated:
        owner_key = p.owner_name.strip().upper()
        if owner_key and owner_key not in seen_owners:
            seen_owners.add(owner_key)
            to_trace.append({
                "parcel_id": p.parcel_id,
                "owner_name": p.owner_name,
                "owner_mailing": p.owner_mailing,
                "rating": p.rating.rating,
            })

    print(f"Skip tracing {len(to_trace)} unique owners in one batch...\n")
    for t in to_trace:
        first, last = parse_owner_name(t["owner_name"])
        addr = parse_address(t["owner_mailing"])
        print(f"  [{t['rating']}] {first} {last} -> {addr['street']}, {addr['city']} {addr['state']}")

    print(f"\nCalling Apify actor...")
    raw_results = run_skip_trace_batch(to_trace)
    print(f"Got {len(raw_results)} results back\n")

    # Debug: print raw result structure if we got anything
    if raw_results:
        print(f"Sample result keys: {list(raw_results[0].keys())[:15]}")
        print(f"Sample result preview: {json.dumps(raw_results[0], indent=2)[:500]}\n")

    # Match results back to owners
    # Results may come back in order or may need matching by name
    final = []
    for i, t in enumerate(to_trace):
        first, last = parse_owner_name(t["owner_name"])

        # Try to find matching result
        matched = None
        if i < len(raw_results):
            matched = raw_results[i]
        else:
            # Try name matching
            for r in raw_results:
                r_name = (r.get("name", "") or r.get("fullName", "")).upper()
                if last.upper() in r_name:
                    matched = r
                    break

        if matched:
            phone_list, email_list = extract_contacts(matched)
            print(f"  {t['owner_name'][:35]:<36} -> {len(phone_list)} phones, {len(email_list)} emails")
            final.append({
                "parcel_id": t["parcel_id"],
                "owner": t["owner_name"],
                "phones": phone_list,
                "emails": email_list,
                "raw": matched,
            })
        else:
            print(f"  {t['owner_name'][:35]:<36} -> NO MATCH")
            final.append({
                "parcel_id": t["parcel_id"],
                "owner": t["owner_name"],
                "phones": [],
                "emails": [],
                "raw": {},
            })

    # Save full results
    output_path = BASE_DIR / ".tmp" / "skip_trace_results.json"
    with open(output_path, "w") as f:
        json.dump(final, f, indent=2)
    print(f"\nSaved full results to {output_path.name}")

    # Summary
    with_phone = sum(1 for r in final if r["phones"])
    with_email = sum(1 for r in final if r["emails"])
    print(f"\nSummary: {with_phone}/{len(final)} have phones, {with_email}/{len(final)} have emails")
    print(f"\nContact info:")
    for r in final:
        phones = ", ".join(r["phones"][:3]) if r["phones"] else "none"
        emails = ", ".join(r["emails"][:2]) if r["emails"] else "none"
        print(f"  {r['owner'][:35]:<36} ph: {phones}  |  em: {emails}")


if __name__ == "__main__":
    main()
