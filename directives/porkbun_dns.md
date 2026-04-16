# Porkbun DNS Management SOP

Manage DNS records programmatically via the Porkbun API. No more clicking through dashboards.

## API Credentials
Stored in `.env`:
- `PORKBUN_API_KEY` — API key from [porkbun.com/account/api](https://porkbun.com/account/api)
- `PORKBUN_SECRET_KEY` — Secret key paired with the API key

**Important:** Each domain must have "API Access" enabled individually in the Porkbun dashboard before the API will work for that domain.

## API Base URL
```
https://api.porkbun.com/api/json/v3
```
All requests are POST with JSON body. Every request requires `apikey` and `secretapikey` in the body.

## Standard DNS Setup for New Projects

For a project with domain `example.com`, backend on DO at `$DROPLET_IP`, frontend on Vercel:

```python
import requests

API_KEY = "pk1_..."
SECRET_KEY = "sk1_..."
DOMAIN = "example.com"
DROPLET_IP = "164.90.x.x"
BASE = "https://api.porkbun.com/api/json/v3"
auth = {"apikey": API_KEY, "secretapikey": SECRET_KEY}

# 1. Clear Porkbun parking records
existing = requests.post(f"{BASE}/dns/retrieve/{DOMAIN}", json=auth).json().get("records", [])
for rec in existing:
    if rec["type"] in ("A", "CNAME", "ALIAS") and "porkbun" in rec.get("content", ""):
        requests.post(f"{BASE}/dns/delete/{DOMAIN}/{rec['id']}", json=auth)

# 2. Backend: A record for api subdomain
requests.post(f"{BASE}/dns/create/{DOMAIN}", json={
    **auth, "type": "A", "name": "api", "content": DROPLET_IP, "ttl": "300"
})

# 3. Frontend: CNAME root -> Vercel
requests.post(f"{BASE}/dns/create/{DOMAIN}", json={
    **auth, "type": "CNAME", "name": "", "content": "cname.vercel-dns.com", "ttl": "300"
})

# 4. Frontend: CNAME www -> Vercel
requests.post(f"{BASE}/dns/create/{DOMAIN}", json={
    **auth, "type": "CNAME", "name": "www", "content": "cname.vercel-dns.com", "ttl": "300"
})
```

## API Reference

### Authentication
Every request body must include:
```json
{"apikey": "pk1_...", "secretapikey": "sk1_..."}
```

### List All Records
```
POST /dns/retrieve/{domain}
```
Returns `{"status": "SUCCESS", "records": [{"id": "123", "name": "api.example.com", "type": "A", "content": "1.2.3.4", "ttl": "300"}, ...]}`

### Create Record
```
POST /dns/create/{domain}
Body: {...auth, "type": "A|CNAME|MX|TXT", "name": "subdomain", "content": "value", "ttl": "300"}
```
- `name`: subdomain only (e.g. `api`, `www`, or `""` for root)
- Returns `{"status": "SUCCESS", "id": 123456}`

### Update Record
```
POST /dns/edit/{domain}/{record_id}
Body: {...auth, "type": "A", "name": "api", "content": "new_ip", "ttl": "300"}
```

### Delete Record
```
POST /dns/delete/{domain}/{record_id}
```

### Delete All Records of a Type
```
POST /dns/deleteByNameType/{domain}/{type}/{subdomain}
```
Example: Delete all A records for `api.example.com`:
```
POST /dns/deleteByNameType/example.com/A/api
```

## Common DNS Patterns

### Standard project (Vercel + DO)
| Record | Type | Name | Content |
|--------|------|------|---------|
| Backend | A | `api` | Droplet IP |
| Frontend | CNAME | `` (root) | `cname.vercel-dns.com` |
| Frontend | CNAME | `www` | `cname.vercel-dns.com` |

### Verify DNS propagation
```bash
# From local machine
dig +short api.example.com    # Should return droplet IP
dig +short example.com        # Should return Vercel IP
dig +short www.example.com    # Should return Vercel CNAME
```

### After DNS is pointing, add SSL to backend
```bash
ssh root@$DROPLET_IP "certbot --nginx -d api.$DOMAIN --non-interactive --agree-tos -m $EMAIL"
```

## Error Handling

### "Domain is not opted in to API access"
Go to porkbun.com → domain settings → toggle "API Access" on.

### Record already exists
Retrieve records first, delete the conflicting one, then create the new one.

### DNS not propagating
Porkbun default TTL is 300s (5 min). If using a CDN or proxy, check for cached stale records. Use `dig +trace` to debug.

## Execution Script
For a reusable script, see `execution/setup_dns.py` (create as needed per project). Input: domain name, droplet IP. Output: all DNS records configured.
