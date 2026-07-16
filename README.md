# Beast Affiliates — portal + hub article pages

Companion website for the WhatsApp affiliate bot. Registered users get a
dashboard (portal) and per-user "hub" article pages whose **View on Amazon**
button routes through a click-counting redirect to the user's tagged affiliate
link.

- `backend/` — FastAPI (managed with **uv**), deployed on Vercel. Serves the
  article pages (`/p/<id>/<slug>`), click redirect (`/go/<id>`), view beacon
  (`/b/<id>`), and the server-to-server mint API (`POST /api/links`).
- `frontend/` — React + TypeScript (Vite) portal (login, analytics, links).

## Domain routing

| Marketplace | Article domain |
|---|---|
| US (amazon.com) | `beastaffiliates.com` (also hosts the portal) |
| all others | second domain (`ARTICLE_BASE_INTL`) |

Both domains attach to the SAME Vercel backend project; the minted article URL
picks the domain by marketplace (`app/config.py: article_base`).

## Product data

Per (marketplace, ASIN), cached forever in the `products` table:
**PA-API v5** (env credentials per marketplace) → **scrape fallback** →
**sender-message fallback** (phase 2). PA-API signing is implemented in
`app/paapi.py` (stdlib SigV4, no SDK).

## Local dev

```bash
cd backend
cp .env.example .env       # fill what you need; empty DATABASE_URL = SQLite
uv sync
uv run uvicorn main:app --port 4200
# open http://localhost:4200  (test form for creating links)
```

Frontend: `cd frontend && npm install && npm run dev`.

## Deploy (Vercel)

1. Push this repo to GitHub.
2. Vercel → New Project → import repo → **Root Directory: `backend`**
   (vercel.json + requirements.txt are there). Add env vars from
   `backend/.env.example` (DATABASE_URL from Neon, SERVICE_KEY = long random
   string, ARTICLE_BASE_US/INTL, all PAAPI_* keys).
3. Attach both domains to the project (Cloudflare DNS → CNAME to Vercel).
4. Frontend deploys later as a second Vercel project (Root: `frontend`).

`requirements.txt` is exported from uv — after adding deps run:
`uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`.

## Bot integration contract (phase 2)

`POST /api/links` with header `X-Service-Key: <SERVICE_KEY>` and JSON
`{url, tag, store_name, sender, fallback_title?, fallback_image?}` →
`{link_id, article_url, tagged_url, title, source}` or 422 with `{error}` —
on ANY non-200 the bot must reply with its normal direct tagged link.
