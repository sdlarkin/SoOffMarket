# Vercel Deployment & Automation SOP

> **CRITICAL VERCEL ROUTING RULE:** When creating a completely new deployment on Vercel via the dashboard, Vercel frequently hallucinates and forces `Framework Preset: None` (or `Other`) even if you specifically clicked Next.js! 
> This causes Vercel to successfully compile Next.js but then Vercel's Edge Network serves a global `404: NOT_FOUND` because it searches for a static HTML output folder instead of booting the Next.js Node server.

## 1. Automated Vercel Diagnostics
To prevent manually hunting for configuration settings in the confusing Vercel UI, future agents must rely strictly on Vercel's REST API.

We maintain a primary Vercel API token in our `.env` files (`VERCEL_API_TOKEN`). This token allows us to manage and deploy any new project attached to this Vercel account.

### The 404 Fixer Protocol
When a new Vercel deployment completes successfully but still throws a `404 Not Found`:
1. Use the `VERCEL_API_TOKEN` to fetch `GET https://api.vercel.com/v9/projects/<project_id>`.
2. Inspect the `framework` property. If it is `null` or `None`, this is the smoking gun.
3. Fire a `PATCH` request to the exact same endpoint with the payload `{"framework": "nextjs"}`.
4. Push an empty git commit (`git commit --allow-empty -m "Trigger rebuild" ; git push`) to force Vercel to rebuild using the corrected Node.js Engine.

## 2. Decoupled DNS Architecture
Next.js frontends permanently reside on Vercel. 
Django backends reside on the DigitalOcean droplet.
- **Frontend State:** The Vercel Frontend environment variable (`NEXT_PUBLIC_API_URL`) must always point to the secure subdomain `https://api.[domain].com`.
- **Backend State:** The Django Backend `.env` must strictly include the Vercel `.vercel.app` production domain inside `CORS_ALLOWED_ORIGINS`.
