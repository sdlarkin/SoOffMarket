"""
Vercel project setup, diagnostics, and fix tool.
Handles the common issues: wrong framework, missing env vars, 404s, domain setup.

Usage:
    python execution/setup_vercel.py --project-id prj_xxx --check
    python execution/setup_vercel.py --project-id prj_xxx --fix-framework
    python execution/setup_vercel.py --project-id prj_xxx --set-api-url https://api.example.com/api
    python execution/setup_vercel.py --project-id prj_xxx --add-domain example.com
    python execution/setup_vercel.py --project-id prj_xxx --full-setup --domain example.com --api-url https://api.example.com/api

Requires VERCEL_API_TOKEN in .env
"""

import argparse
import json
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TOKEN = os.environ.get("VERCEL_API_TOKEN", "").strip()
BASE = "https://api.vercel.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def api_get(path):
    r = requests.get(f"{BASE}{path}", headers=HEADERS, timeout=15)
    return r.json()


def api_post(path, data):
    r = requests.post(f"{BASE}{path}", headers=HEADERS, json=data, timeout=15)
    return r.json()


def api_patch(path, data):
    r = requests.patch(f"{BASE}{path}", headers=HEADERS, json=data, timeout=15)
    return r.json()


def check_project(project_id):
    """Diagnose common issues with a Vercel project."""
    print(f"Checking project {project_id}...\n")

    # Project info
    proj = api_get(f"/v9/projects/{project_id}")
    if "error" in proj:
        print(f"ERROR: {proj['error'].get('message', proj['error'])}")
        return

    name = proj.get("name", "?")
    framework = proj.get("framework")
    root_dir = proj.get("rootDirectory")

    print(f"  Name: {name}")
    print(f"  Framework: {framework}")
    print(f"  Root directory: {root_dir}")

    # Framework check
    if not framework or framework == "null":
        print(f"\n  WARNING: Framework is not set! This causes 404 on all routes.")
        print(f"  Fix with: python setup_vercel.py --project-id {project_id} --fix-framework")
    elif framework != "nextjs":
        print(f"\n  WARNING: Framework is '{framework}', expected 'nextjs'.")

    # Env vars
    envs = api_get(f"/v9/projects/{project_id}/env")
    env_list = envs.get("envs", [])
    print(f"\n  Environment variables ({len(env_list)}):")
    api_url_found = False
    for e in env_list:
        value = e.get("value", "[encrypted]")
        print(f"    {e.get('key')} = {value} (target: {e.get('target')})")
        if e.get("key") == "NEXT_PUBLIC_API_URL":
            api_url_found = True
            if not value.startswith("https://"):
                print(f"    WARNING: API URL is not HTTPS!")

    if not api_url_found:
        print(f"\n  WARNING: NEXT_PUBLIC_API_URL is not set!")
        print(f"  The frontend won't know where the API is.")

    # Domains
    domains = api_get(f"/v9/projects/{project_id}/domains")
    domain_list = domains.get("domains", [])
    print(f"\n  Custom domains ({len(domain_list)}):")
    for d in domain_list:
        verified = "verified" if d.get("verified") else "NOT VERIFIED"
        print(f"    {d.get('name')} ({verified})")

    if not domain_list:
        print(f"    None configured. .vercel.app URLs may return 401 due to SSO protection.")

    # Latest deployment
    deps = api_get(f"/v6/deployments?projectId={project_id}&limit=1")
    dep_list = deps.get("deployments", [])
    if dep_list:
        dep = dep_list[0]
        print(f"\n  Latest deployment:")
        print(f"    State: {dep.get('readyState')}")
        print(f"    URL: {dep.get('url')}")

    print(f"\nDiagnostics complete.")


def fix_framework(project_id):
    """Set framework to nextjs."""
    print(f"Setting framework to 'nextjs'...")
    result = api_patch(f"/v9/projects/{project_id}", {"framework": "nextjs"})
    if "error" in result:
        print(f"  ERROR: {result['error'].get('message')}")
    else:
        print(f"  Done. Framework is now: {result.get('framework')}")
        print(f"  Trigger a rebuild: git commit --allow-empty -m 'Trigger rebuild' && git push")


def set_env_var(project_id, key, value):
    """Create or update an env var."""
    # Check if it exists
    envs = api_get(f"/v9/projects/{project_id}/env")
    existing = next((e for e in envs.get("envs", []) if e.get("key") == key), None)

    if existing:
        print(f"Updating {key}...")
        result = api_patch(f"/v9/projects/{project_id}/env/{existing['id']}", {"value": value})
    else:
        print(f"Creating {key}...")
        result = api_post(f"/v10/projects/{project_id}/env", {
            "key": key, "value": value,
            "target": ["production", "preview", "development"],
            "type": "plain"
        })

    if "error" in result:
        print(f"  ERROR: {result['error'].get('message')}")
    else:
        print(f"  Done. {key} = {value}")
        print(f"  Trigger a rebuild for this to take effect.")


def add_domain(project_id, domain):
    """Add a custom domain to the project."""
    print(f"Adding domain: {domain}")
    result = api_post(f"/v10/projects/{project_id}/domains", {"name": domain})
    if "error" in result:
        print(f"  ERROR: {result['error'].get('message')}")
    else:
        verified = "verified" if result.get("verified") else "not verified (check DNS)"
        print(f"  Done. {domain} — {verified}")


def full_setup(project_id, domain, api_url):
    """Run the complete setup: fix framework, set env, add domains."""
    print(f"=== Full Vercel setup for {domain} ===\n")

    fix_framework(project_id)
    print()
    set_env_var(project_id, "NEXT_PUBLIC_API_URL", api_url)
    print()
    add_domain(project_id, domain)
    add_domain(project_id, f"www.{domain}")
    print()
    print(f"Setup complete. Trigger a rebuild:")
    print(f"  git commit --allow-empty -m 'Trigger rebuild' && git push")


def main():
    if not TOKEN:
        print("ERROR: VERCEL_API_TOKEN must be set in .env")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Vercel project setup and diagnostics")
    parser.add_argument("--project-id", required=True, help="Vercel project ID (prj_xxx)")
    parser.add_argument("--check", action="store_true", help="Run diagnostics")
    parser.add_argument("--fix-framework", action="store_true", help="Set framework to nextjs")
    parser.add_argument("--set-api-url", help="Set NEXT_PUBLIC_API_URL env var")
    parser.add_argument("--add-domain", help="Add a custom domain")
    parser.add_argument("--full-setup", action="store_true", help="Run complete setup")
    parser.add_argument("--domain", help="Domain for full setup")
    parser.add_argument("--api-url", help="API URL for full setup")
    args = parser.parse_args()

    if args.full_setup:
        if not args.domain or not args.api_url:
            print("ERROR: --full-setup requires --domain and --api-url")
            sys.exit(1)
        full_setup(args.project_id, args.domain, args.api_url)
    elif args.check:
        check_project(args.project_id)
    elif args.fix_framework:
        fix_framework(args.project_id)
    elif args.set_api_url:
        set_env_var(args.project_id, "NEXT_PUBLIC_API_URL", args.set_api_url)
    elif args.add_domain:
        add_domain(args.project_id, args.add_domain)
    else:
        check_project(args.project_id)


if __name__ == "__main__":
    main()
