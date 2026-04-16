"""
Provision a DigitalOcean droplet for a Django backend.
Installs system packages, clones repo, sets up venv, gunicorn, nginx, and SSL.

Usage:
    python execution/setup_droplet.py --ip 164.90.x.x --domain sooffmarket.com --repo sdlarkin/SoOffMarket --email dane@larkinautomation.com
    python execution/setup_droplet.py --ip 164.90.x.x --domain sooffmarket.com --repo sdlarkin/SoOffMarket --email dane@larkinautomation.com --dry-run

Requires SSH key access to the droplet as root.
"""

import argparse
import subprocess
import sys


def ssh_run(ip, commands, dry_run=False):
    """Run commands on the droplet via SSH."""
    script = "\n".join(commands)
    if dry_run:
        print(f"[DRY RUN] Would execute on {ip}:")
        for cmd in commands:
            print(f"  {cmd}")
        return True

    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{ip}", script],
        capture_output=True, text=True, timeout=300
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Provision DO droplet for Django backend")
    parser.add_argument("--ip", required=True, help="Droplet IP address")
    parser.add_argument("--domain", required=True, help="Root domain (e.g. sooffmarket.com)")
    parser.add_argument("--repo", required=True, help="GitHub repo (user/repo)")
    parser.add_argument("--email", required=True, help="Email for SSL cert")
    parser.add_argument("--project-dir", default=None, help="Project directory name (default: derived from domain)")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without executing")
    parser.add_argument("--ssl-only", action="store_true", help="Only set up SSL (skip everything else)")
    args = parser.parse_args()

    project = args.project_dir or args.domain.replace(".", "")
    project_path = f"/opt/{project}"
    service_name = f"gunicorn_{project}"

    if args.ssl_only:
        print(f"Setting up SSL for api.{args.domain}...")
        ssh_run(args.ip, [
            f"certbot --nginx -d api.{args.domain} --non-interactive --agree-tos -m {args.email}"
        ], args.dry_run)
        return

    print(f"Provisioning droplet at {args.ip} for {args.domain}...")
    print(f"  Project: {project}")
    print(f"  Path: {project_path}")
    print(f"  Repo: {args.repo}")
    print()

    # Step 1: System packages
    print("=== Step 1: Installing system packages ===")
    ssh_run(args.ip, [
        "apt-get update -qq",
        "apt-get install -y -qq nginx python3-venv python3-pip git certbot python3-certbot-nginx",
    ], args.dry_run)

    # Step 2: Clone repo
    print("\n=== Step 2: Cloning repository ===")
    ssh_run(args.ip, [
        f"mkdir -p {project_path}",
        f"cd {project_path}",
        f"if [ ! -d .git ]; then git init && git remote add origin https://github.com/{args.repo}.git; fi",
        f"cd {project_path} && git fetch --all && git checkout main || git checkout -b main origin/main",
    ], args.dry_run)

    # Step 3: Python setup
    print("\n=== Step 3: Python environment ===")
    ssh_run(args.ip, [
        f"cd {project_path}/backend",
        f"python3 -m venv env",
        f"source env/bin/activate && pip install -r requirements.txt -q",
    ], args.dry_run)

    # Step 4: Django setup
    print("\n=== Step 4: Django configuration ===")
    ssh_run(args.ip, [
        f"cd {project_path}/backend",
        f"if [ ! -f .env ]; then echo 'DEBUG=False' > .env && echo \"SECRET_KEY=$(openssl rand -hex 32)\" >> .env; fi",
        f"source env/bin/activate",
        f"python manage.py migrate --noinput",
        f"python manage.py collectstatic --noinput",
    ], args.dry_run)

    # Step 5: Gunicorn service
    print("\n=== Step 5: Gunicorn systemd service ===")
    service_content = f"""[Unit]
Description=Gunicorn daemon for {project}
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory={project_path}/backend
ExecStart={project_path}/backend/env/bin/gunicorn backend_api.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"""

    ssh_run(args.ip, [
        f"cat > /etc/systemd/system/{service_name}.service << 'SERVICEEOF'\n{service_content}\nSERVICEEOF",
        f"systemctl daemon-reload",
        f"systemctl enable --now {service_name}",
    ], args.dry_run)

    # Step 6: Nginx
    print("\n=== Step 6: Nginx configuration ===")
    nginx_content = f"""server {{
    listen 80;
    server_name api.{args.domain} {args.ip};

    location /static/ {{
        alias {project_path}/backend/staticfiles/;
    }}

    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}"""

    ssh_run(args.ip, [
        f"cat > /etc/nginx/sites-available/{project} << 'NGINXEOF'\n{nginx_content}\nNGINXEOF",
        f"ln -sf /etc/nginx/sites-available/{project} /etc/nginx/sites-enabled/",
        f"rm -f /etc/nginx/sites-enabled/default",
        f"nginx -t && systemctl restart nginx",
    ], args.dry_run)

    # Step 7: SSL
    print("\n=== Step 7: SSL (requires DNS to be pointing) ===")
    ssh_run(args.ip, [
        f"certbot --nginx -d api.{args.domain} --non-interactive --agree-tos -m {args.email} || echo 'SSL failed - DNS may not be pointing yet. Run with --ssl-only later.'",
    ], args.dry_run)

    # Verify
    print("\n=== Verification ===")
    ssh_run(args.ip, [
        f"curl -s -o /dev/null -w 'API status: %{{http_code}}\\n' http://127.0.0.1:8000/api/",
        f"systemctl is-active {service_name}",
    ], args.dry_run)

    print(f"\nDone. Backend should be live at https://api.{args.domain}/api/")
    print(f"\nRemember to:")
    print(f"  1. Copy your local db.sqlite3 if needed: scp backend/db.sqlite3 root@{args.ip}:{project_path}/backend/")
    print(f"  2. Set up GitHub Actions secrets: SERVER_IP, SERVER_USER, SSH_PRIVATE_KEY")
    print(f"  3. Set up DNS: python execution/setup_dns.py --domain {args.domain} --ip {args.ip}")


if __name__ == "__main__":
    main()
