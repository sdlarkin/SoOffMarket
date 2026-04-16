"""
Set up DNS records for a new project via Porkbun API.
Configures: api.DOMAIN -> Droplet IP, DOMAIN -> Vercel, www.DOMAIN -> Vercel.

Usage:
    python execution/setup_dns.py --domain sooffmarket.com --ip 164.90.157.203

Requires PORKBUN_API_KEY and PORKBUN_SECRET_KEY in .env
"""

import argparse
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_KEY = os.environ.get("PORKBUN_API_KEY", "").strip()
SECRET_KEY = os.environ.get("PORKBUN_SECRET_KEY", "").strip()
BASE = "https://api.porkbun.com/api/json/v3"


def porkbun(endpoint, extra=None):
    body = {"apikey": API_KEY, "secretapikey": SECRET_KEY}
    if extra:
        body.update(extra)
    r = requests.post(f"{BASE}/{endpoint}", json=body, timeout=15)
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Set up DNS for a Vercel + DO project")
    parser.add_argument("--domain", required=True, help="Root domain e.g. sooffmarket.com")
    parser.add_argument("--ip", required=True, help="DigitalOcean droplet IP")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    if not API_KEY or not SECRET_KEY:
        print("ERROR: PORKBUN_API_KEY and PORKBUN_SECRET_KEY must be set in .env")
        sys.exit(1)

    domain = args.domain
    ip = args.ip

    # 1. List existing records
    print(f"Current records for {domain}:")
    result = porkbun(f"dns/retrieve/{domain}")
    if result.get("status") != "SUCCESS":
        print(f"  ERROR: {result.get('message')}")
        print("  Make sure API access is enabled for this domain at porkbun.com")
        sys.exit(1)

    existing = result.get("records", [])
    for rec in existing:
        print(f"  {rec['type']:<6} {rec.get('name', ''):<35} -> {rec.get('content', '')}")

    # 2. Remove Porkbun parking records
    parking = [r for r in existing if r["type"] in ("A", "CNAME", "ALIAS") and "porkbun" in r.get("content", "")]
    if parking:
        print(f"\nRemoving {len(parking)} Porkbun parking records...")
        for rec in parking:
            if args.dry_run:
                print(f"  [DRY RUN] Would delete {rec['type']} {rec.get('name', '')} -> {rec.get('content', '')}")
            else:
                porkbun(f"dns/delete/{domain}/{rec['id']}")
                print(f"  Deleted {rec['type']} {rec.get('name', '')} -> {rec.get('content', '')}")

    # 3. Create records
    records_to_create = [
        {"type": "A", "name": "api", "content": ip, "ttl": "300", "desc": f"api.{domain} -> {ip} (backend)"},
        {"type": "CNAME", "name": "", "content": "cname.vercel-dns.com", "ttl": "300", "desc": f"{domain} -> Vercel (frontend)"},
        {"type": "CNAME", "name": "www", "content": "cname.vercel-dns.com", "ttl": "300", "desc": f"www.{domain} -> Vercel (frontend)"},
    ]

    print(f"\nCreating records:")
    for rec in records_to_create:
        desc = rec.pop("desc")
        if args.dry_run:
            print(f"  [DRY RUN] Would create: {desc}")
        else:
            result = porkbun(f"dns/create/{domain}", rec)
            status = result.get("status", "ERROR")
            if status == "SUCCESS":
                print(f"  OK: {desc}")
            else:
                print(f"  FAILED: {desc} -> {result.get('message', '')}")

    # 4. Verify
    if not args.dry_run:
        print(f"\nFinal records:")
        result = porkbun(f"dns/retrieve/{domain}")
        for rec in result.get("records", []):
            print(f"  {rec['type']:<6} {rec.get('name', ''):<35} -> {rec.get('content', '')}")

    print(f"\nNext steps:")
    print(f"  1. Wait ~5 min for DNS propagation")
    print(f"  2. Run SSL: ssh root@{ip} 'certbot --nginx -d api.{domain} --non-interactive --agree-tos -m YOUR_EMAIL'")
    print(f"  3. Add {domain} and www.{domain} as custom domains in Vercel")


if __name__ == "__main__":
    main()
