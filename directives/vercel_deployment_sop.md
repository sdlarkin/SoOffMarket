# Vercel Deployment & Automation SOP

> **CRITICAL:** Always verify and manage Vercel via the REST API, not the dashboard. The dashboard frequently misapplies framework settings.

## API Token
Stored in `.env` as `VERCEL_API_TOKEN`. This token manages all Vercel projects under the account.

## New Project Checklist

1. **Import repo** at [vercel.com/new](https://vercel.com/new) or via API
2. **Verify framework** is `nextjs` via API (see 404 Fixer in `gitops_deployment.md`)
3. **Set root directory** to `frontend` (if monorepo)
4. **Add env vars** via API:
   ```bash
   curl -X POST -H "Authorization: Bearer $VERCEL_API_TOKEN" \
     -H "Content-Type: application/json" \
     "https://api.vercel.com/v10/projects/$PROJECT_ID/env" \
     -d '{"key":"NEXT_PUBLIC_API_URL","value":"https://api.DOMAIN.com/api","target":["production","preview","development"],"type":"plain"}'
   ```
5. **Add custom domain** via API:
   ```bash
   curl -X POST -H "Authorization: Bearer $VERCEL_API_TOKEN" \
     -H "Content-Type: application/json" \
     "https://api.vercel.com/v10/projects/$PROJECT_ID/domains" \
     -d '{"name":"DOMAIN.com"}'
   ```
6. **Set up DNS** on Porkbun (see `porkbun_dns.md`):
   - Root domain: CNAME → `cname.vercel-dns.com`
   - www: CNAME → `cname.vercel-dns.com`
7. **Trigger rebuild** after env var changes:
   ```bash
   git commit --allow-empty -m "Trigger rebuild" && git push
   ```

## Decoupled Architecture
- Next.js frontends reside on Vercel: `https://[domain].com`
- Django backends reside on DigitalOcean: `https://api.[domain].com`
- Frontend env var `NEXT_PUBLIC_API_URL` points to `https://api.[domain].com/api`
- Backend `CORS_ALLOWED_ORIGINS` includes the Vercel domain

## Common Issues

### 404 on all routes after successful build
**Cause:** Framework set to `None` instead of `nextjs`.
**Fix:** PATCH the project via API to set `{"framework": "nextjs"}`, then trigger rebuild.

### 401 on .vercel.app URLs
**Cause:** SSO Deployment Protection on hobby plan blocks `.vercel.app` subdomains.
**Fix:** Add a custom domain — custom domains bypass SSO protection.

### Env vars not taking effect
**Cause:** Vercel caches builds. Env vars added after a build require a new deployment.
**Fix:** `git commit --allow-empty -m "Trigger rebuild" && git push`

### Build succeeds but API calls fail
**Cause:** `NEXT_PUBLIC_API_URL` not set or pointing to HTTP instead of HTTPS.
**Fix:** Update env var via API, trigger rebuild. Ensure the API domain has SSL (certbot on DO).

## Useful API Endpoints
```
GET    /v9/projects/{id}                    # Project info (check framework)
PATCH  /v9/projects/{id}                    # Update project settings
GET    /v6/deployments?projectId={id}       # List deployments
POST   /v10/projects/{id}/env               # Create env var
PATCH  /v9/projects/{id}/env/{envId}        # Update env var
GET    /v9/projects/{id}/env                # List env vars
POST   /v10/projects/{id}/domains           # Add custom domain
GET    /v9/projects/{id}/domains            # List domains
DELETE /v9/projects/{id}/domains/{domain}   # Remove domain
```

All requests require header: `Authorization: Bearer $VERCEL_API_TOKEN`
