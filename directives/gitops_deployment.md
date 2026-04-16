# Git-Ops Deployment SOP (Vercel + DigitalOcean)

This directive defines the automated "Push-to-Deploy" strategy used across all projects.

## Architecture

```
GitHub Repo (main branch)
  ├── push triggers → Vercel (auto-builds Next.js frontend)
  └── push triggers → GitHub Actions → SSH into DO Droplet (pulls + restarts Django)
```

| Layer | Host | Domain Pattern | SSL |
|-------|------|----------------|-----|
| Frontend (Next.js) | Vercel | `[domain].com` | Vercel auto-managed |
| Backend (Django) | DigitalOcean Droplet | `api.[domain].com` | Certbot (Let's Encrypt) |
| DNS | Porkbun | See `porkbun_dns.md` | N/A |

## Frontend Deployment (Vercel)

**Trigger:** Push to `main` branch.

### Initial Setup
1. Import GitHub repo into Vercel at [vercel.com/new](https://vercel.com/new)
2. Set **Root Directory** to `frontend`
3. Verify framework is set to `nextjs` (see Vercel 404 Fixer below)
4. Add env var: `NEXT_PUBLIC_API_URL` = `https://api.[domain].com/api`
5. Add custom domain via Vercel API or dashboard (see `porkbun_dns.md` for DNS setup)

### Vercel 404 Fixer Protocol
Vercel frequently ignores the Next.js framework selection and defaults to `None`, causing 404s on all routes even though the build succeeds.

**Diagnosis and fix via API** (preferred over the dashboard):
```bash
# Check framework setting
curl -s -H "Authorization: Bearer $VERCEL_API_TOKEN" \
  "https://api.vercel.com/v9/projects/$PROJECT_ID" | python -c \
  "import sys,json; print(json.load(sys.stdin).get('framework'))"

# Fix if null/None
curl -s -X PATCH -H "Authorization: Bearer $VERCEL_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.vercel.com/v9/projects/$PROJECT_ID" \
  -d '{"framework": "nextjs"}'

# Trigger rebuild
git commit --allow-empty -m "Trigger rebuild" && git push
```

### Vercel SSO/Auth Note
On the hobby plan, Vercel applies SSO protection to `.vercel.app` subdomains but NOT to custom domains. If you get 401s on the `.vercel.app` URL, add the custom domain — it will work immediately.

### Vercel API Quick Reference
```bash
TOKEN=$VERCEL_API_TOKEN  # stored in .env

# Get project info
GET https://api.vercel.com/v9/projects/$PROJECT_ID

# List deployments
GET https://api.vercel.com/v6/deployments?projectId=$PROJECT_ID&limit=5

# Add env var
POST https://api.vercel.com/v10/projects/$PROJECT_ID/env
Body: {"key":"KEY","value":"VALUE","target":["production","preview","development"],"type":"plain"}

# Update env var
PATCH https://api.vercel.com/v9/projects/$PROJECT_ID/env/$ENV_ID
Body: {"value":"NEW_VALUE"}

# Add custom domain
POST https://api.vercel.com/v10/projects/$PROJECT_ID/domains
Body: {"name":"sooffmarket.com"}
```

## Backend Deployment (DigitalOcean)

**Trigger:** GitHub Actions on push to `main`.

### Droplet Setup (one-time)
```bash
# Install system packages
apt-get update && apt-get install -y nginx python3-venv python3-pip git certbot python3-certbot-nginx

# Clone repo
mkdir -p /opt/$PROJECT_NAME
cd /opt/$PROJECT_NAME
git clone https://github.com/$GITHUB_USER/$REPO_NAME.git .

# Python environment
cd backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

# Create production .env (NEVER commit this)
cat > .env << 'EOF'
DEBUG=False
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///db.sqlite3
EOF

# Run Django setup
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Gunicorn systemd service
cat > /etc/systemd/system/gunicorn_$PROJECT_NAME.service << 'EOF'
[Unit]
Description=Gunicorn daemon for $PROJECT_NAME
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/opt/$PROJECT_NAME/backend
ExecStart=/opt/$PROJECT_NAME/backend/env/bin/gunicorn backend_api.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now gunicorn_$PROJECT_NAME

# Nginx config
cat > /etc/nginx/sites-available/$PROJECT_NAME << 'EOF'
server {
    listen 80;
    server_name api.$DOMAIN $DROPLET_IP;

    location /static/ {
        alias /opt/$PROJECT_NAME/backend/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/$PROJECT_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# SSL (after DNS A record is pointing)
certbot --nginx -d api.$DOMAIN --non-interactive --agree-tos -m $EMAIL
```

### GitHub Actions Workflow Template
Every repo MUST include `.github/workflows/deploy.yml`:

```yaml
name: Deploy Backend to DigitalOcean

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout Code
      uses: actions/checkout@v3

    - name: Deploy to DigitalOcean
      uses: appleboy/ssh-action@v1.0.3
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        GITHUB_REPO: ${{ github.repository }}
      with:
        host: ${{ secrets.SERVER_IP }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        envs: GITHUB_TOKEN,GITHUB_REPO
        script: |
          cd /opt/$PROJECT_NAME
          git config --global --add safe.directory /opt/$PROJECT_NAME
          git remote set-url origin https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git
          git fetch --all
          git reset --hard origin/main
          git clean -fd
          
          cd /opt/$PROJECT_NAME/backend
          source env/bin/activate
          pip install -r requirements.txt
          python manage.py migrate --noinput
          python manage.py collectstatic --noinput
          sudo systemctl restart gunicorn_$PROJECT_NAME
          sudo systemctl reload nginx
```

### Required GitHub Secrets
| Secret | Value |
|--------|-------|
| `SERVER_IP` | Droplet IP address |
| `SERVER_USER` | `root` |
| `SSH_PRIVATE_KEY` | SSH private key for the droplet |

## Security Rules
- **NEVER** commit `.env` files to Git
- Production secrets go in **GitHub Actions Secrets** (backend) and **Vercel Environment Variables** (frontend)
- Use **DigitalOcean Reserved IPs** so the server IP survives reboots
- Django `ALLOWED_HOSTS` must include: `api.[domain].com`, the droplet IP, `localhost`
- Django `CORS_ALLOW_ALL_ORIGINS = True` for dev; lock down to specific origins for production

## Verification Checklist
After every push to `main`:
1. GitHub Actions tab → green checkmark (backend deployed)
2. Vercel Dashboard → "Ready" (frontend deployed)
3. `curl https://api.[domain].com/api/` → 200
4. `curl https://[domain].com/` → 200
5. Test the actual feature you changed in a browser
