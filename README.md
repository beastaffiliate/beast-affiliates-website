# Beast Affiliates — marketing site, portal, and hub article pages

Companion website for the WhatsApp affiliate bot. Registered users get a
dashboard (portal) and per-user "hub" article pages whose **View on Amazon**
button routes through a click-counting redirect to the user's tagged affiliate
link. Last updated 2026-07-22 — live on both domains.

- `backend/` — FastAPI (managed with **uv**), deployed on Vercel. Serves:
  - the **public marketing site** (`app/site.py`, server-rendered): Home,
    Articles & Guides, About, Contact, Privacy Policy, Terms. One
    implementation shared by both domains, branded per host.
  - article pages (`/p/<id>/<slug>`), click redirect (`/go/<id>`), view beacon
    (`/b/<id>`), public store pages (`/u/<slug>`), and the server-to-server
    mint API (`POST /api/links`).
  - `GET /api/links/{id}/resolve` (X-Service-Key) — the untagged Amazon URL and
    owner for one of our own links, recording **no** view or click, so the bot
    can re-tag a forwarded article to the new sender without inflating the
    original creator's stats.
  - the **portal API** (`app/portal.py`, `/portal/*`) and the **admin API**
    (`/api/admin/*`, X-Service-Key) that the bot dashboard proxies.
- `frontend/` — React + TypeScript (Vite) portal, served at **`/dashboard`**
  (the site root is the marketing homepage). Tabs: Overview, Earnings,
  WhatsApp Linking, Profile.

## Data model (Neon Postgres in prod, SQLite locally)

`products` (per marketplace+ASIN article cache), `links`, `link_events` (raw
view/click rows), `portal_accounts` (login, avatar, store slug, payout bank
details, commission_rate, orders, disabled), `wa_link_codes` (3-minute
single-use WhatsApp linking codes), `portal_settings` (default_rate,
min_payout), `earnings_entries`, `payout_records`, `referrals`.

`create_all()` never ALTERs existing tables, so new columns are added by the
hand-rolled idempotent startup migrations in `PORTAL_MIGRATIONS` (Postgres
`IF NOT EXISTS`; retried without it for SQLite, duplicate-column errors
swallowed).

## Domain routing

| Marketplace | Article domain |
|---|---|
| US (amazon.com) | `beastaffiliates.com` (also hosts the marketing site + portal) |
| all others | `beastassociate.com` (`ARTICLE_BASE_INTL`) |

Both domains attach to the SAME Vercel backend project; the minted article URL
picks the domain by marketplace (`app/config.py: article_base`), and an article
opened on the wrong domain 308s to its own.

**Two routing gotchas that cost real debugging time:**

- Vercel *rewrites* run only after the filesystem check, so `dist/index.html`
  won `/` before the marketing rewrite could fire. Fixed by using explicit
  `routes` with the filesystem handle placed AFTER the marketing proxies.
- Proxying replaces the Host header, so the app cannot tell the domains apart.
  The `?xfh=us` / `?xfh=aff` markers exist for exactly this — removing them
  reintroduces an infinite redirect loop.

## Product data

Per (marketplace, ASIN), cached in the `products` table: **scrape first**
(`USE_PAAPI=false` — the owner's choice), with PA-API v5 kept in the tree
behind that flag, then a **sender-message fallback**. PA-API signing is in
`app/paapi.py` (stdlib SigV4, no SDK).

The scraper tries 3 browser identities in random order, **desktop first** —
mobile pages lack the image fields, which is why non-US articles once had no
images. Cached products missing an image self-heal on the next link creation.

Articles are published for **every** send: the per-user link dedup was removed,
so each rewritten link creates a fresh `Link` row (per-send views/clicks) while
the product cache is kept, so this adds no extra scraping.

## Local dev

```bash
cd backend
cp .env.example .env       # fill what you need; empty DATABASE_URL = SQLite
uv sync
uv run uvicorn main:app --port 4200
# open http://localhost:4200
```

Frontend: `cd frontend && npm install && npm run dev`.

To exercise the admin API end-to-end you need the bot API running too, with
each side pointed at the other (`SERVICE_KEY` / `BOT_API_URL` here,
`HUB_API_URL` / `HUB_SERVICE_KEY` on the bot).

## Deploy (Vercel)

1. Push this repo to GitHub.
2. Vercel → New Project → import repo → **Root Directory: `backend`**
   (vercel.json + requirements.txt are there). Add env vars from
   `backend/.env.example` (DATABASE_URL from Neon, SERVICE_KEY = long random
   string, ARTICLE_BASE_US/INTL, BOT_API_URL, BOT_SERVICE_KEY, BOT_WA_NUMBER,
   PORTAL_SECRET, all PAAPI_* keys).
3. Attach both domains to the project (Cloudflare DNS → CNAME to Vercel).

`requirements.txt` is exported from uv — after adding deps run:
`uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`.
Missing `psycopg2-binary` here once caused FUNCTION_INVOCATION_FAILED on the
first production deploy.

## Bot integration contract

`POST /api/links` with header `X-Service-Key: <SERVICE_KEY>` and JSON
`{url, tag, store_name, sender, fallback_title?, fallback_image?,
source_link_id?}` → `{link_id, article_url, tagged_url, title, source}` or 422
with `{error}` — on ANY non-200 the bot must reply with its normal direct
tagged link. `source_link_id` makes a user forwarding their OWN article get
that same article back instead of a duplicate.

## Admin API (consumed by the bot dashboard's "Portal administration" tab)

All under `/api/admin/*`, all requiring `X-Service-Key`. Accounts (list,
create, reset password, disable, delete, set orders, links), linked numbers,
performance, and earnings — settings, per-user rate, entries (add / **edit** /
delete), payouts, referrals (add / **edit** / delete).

Editing rules worth knowing: an earnings entry's **share** defaults to
gross × rate but is stored as sent, so the admin can record what Amazon
actually paid when the two disagree; switching an entry's kind to
bonus/adjustment zeroes gross and rate. A referral's referred party can be
switched between a portal account and a free-text name in either direction,
and self-referral is rejected.
