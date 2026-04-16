"""
Scrape Hamilton County TN Assessor property cards.
Reads a CSV of assessor URLs from .tmp/ and extracts:
  - Parcel ID, Address, Owner, Acreage, Zoning/Land Use,
    Building Value, Land Value, Total Value, Assessed Value,
    Sale Date, Sale Price, Grantor
Outputs enriched CSV to .tmp/
"""

import csv
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"

INPUT_CSV = TMP_DIR / "Properties in Chatanooga for Sara Holt - Sheet1.csv"
OUTPUT_CSV = TMP_DIR / "sara_holt_parcels_scraped.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def load_urls(csv_path: Path) -> list[str]:
    """Read assessor URLs from the input CSV (single column, header row)."""
    urls = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if row and row[0].strip().startswith("http"):
                urls.append(row[0].strip())
    return urls


def parse_card(html: str, url: str) -> dict:
    """Extract property data from an assessor card page."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    def after(label: str) -> str:
        """Return the line immediately after a label line."""
        for i, l in enumerate(lines):
            if l == label and i + 1 < len(lines):
                return lines[i + 1]
        return ""

    def after_pair(label: str) -> str:
        """For 'Label  Value' on same line, split on double-space."""
        for l in lines:
            if l.startswith(label):
                rest = l[len(label):].strip()
                if rest:
                    return rest
        return after(label)

    # Acreage from narrative
    acreage = ""
    for l in lines:
        m = re.search(r"\(([0-9.,]+ ACRES?)\)", l, re.IGNORECASE)
        if m:
            acreage = m.group(1)
            break

    # Owner address - combine address fields
    owner = after("Owner")
    owner_address = after("Address")
    owner_city = after("City")
    owner_state = after("State")
    owner_zip = after("Zip")
    mailing = f"{owner_address}, {owner_city}, {owner_state} {owner_zip}".strip(", ")

    return {
        "url": url,
        "parcel_id": after_pair("Parcel ID"),
        "location": after_pair("Location"),
        "account_number": after_pair("Property Account Number"),
        "property_type": after_pair("Property Type"),
        "land_use": after_pair("Land Use"),
        "district": after_pair("District"),
        "owner": owner,
        "owner_mailing_address": mailing,
        "sale_date": after("Sale Date"),
        "sale_price": after("Sale Price"),
        "grantor": after("Grantor(Seller)"),
        "building_value": after("Building Value"),
        "xtra_features_value": after("Xtra Features Value"),
        "land_value": after("Land Value"),
        "total_value": after("Total Value"),
        "assessed_value": after("Assessed Value"),
        "acreage": acreage,
    }


def main():
    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    urls = load_urls(INPUT_CSV)
    print(f"Loaded {len(urls)} URLs from {INPUT_CSV.name}")

    results = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] Scraping {url} ... ", end="", flush=True)
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = parse_card(r.text, url)
            results.append(data)
            print(f"OK - {data['parcel_id']} / {data['owner']}")
        except Exception as e:
            print(f"FAILED - {e}")
            results.append({"url": url, "error": str(e)})
        time.sleep(0.5)  # polite delay

    # Write output
    if not results:
        print("No results to write.")
        sys.exit(1)

    fieldnames = [
        "parcel_id", "location", "owner", "owner_mailing_address",
        "acreage", "land_use", "district",
        "building_value", "land_value", "total_value", "assessed_value",
        "sale_date", "sale_price", "grantor",
        "account_number", "property_type", "url",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} records to {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
