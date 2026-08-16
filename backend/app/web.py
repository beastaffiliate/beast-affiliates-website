"""FastAPI app: SSR article pages, click redirect, view beacon, mint API.

View counting is beacon-based (`/b/<id>` 1x1 gif requested by the page) so the
article HTML itself stays CDN-cacheable without losing counts. The `/go/<id>`
redirect must never be cached — it increments clicks.
"""

import base64
import html as htmllib
import json
import math
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote, urlsplit

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from . import amazon_url, service
from .favicon_asset import FAVICON_PNG_B64
from .config import (
    ARTICLE_BASE_INTL,
    ARTICLE_BASE_US,
    DEFAULT_STORE_NAME,
    SERVICE_KEY,
    article_base,
    all_article_hosts,
    link_base,
    whatsapp_url,
)
from .database import engine, get_session, init_db
from .models import Link, LinkEvent
from . import demo as demo_mod
from . import site
from .portal import PortalAccount, WaLinkCode, run_portal_migrations
from .portal import admin_router as portal_admin_router
from .portal import router as portal_router

app = FastAPI(title="Beast Affiliates", docs_url=None, redoc_url=None)
app.include_router(portal_router)
app.include_router(portal_admin_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    run_portal_migrations(engine)
    if not SERVICE_KEY:
        print("WARNING: SERVICE_KEY unset - /api/links is open (dev mode only)")


PIXEL_GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
FAVICON_PNG = base64.b64decode(FAVICON_PNG_B64)


@app.get("/favicon.ico")
@app.get("/favicon.png")
def favicon():
    return Response(FAVICON_PNG, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


def esc(v) -> str:
    return htmllib.escape(str(v or ""))


# ------------------------------------------------------------------ template

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font:16px/1.6 system-ui,-apple-system,'Segoe UI',sans-serif;color:#1a1a2e;background:#fff}
a{color:#1151ff;text-decoration:none}
header{background:#101828;color:#fff;padding:14px 32px;display:flex;justify-content:space-between;align-items:center}
header .brand{display:flex;gap:10px;align-items:center;font-weight:700;font-size:18px}
header .logo{width:30px;height:30px;border-radius:8px;background:#3b82f6;display:grid;place-items:center;font-size:15px}
header a{color:#cbd5e1;font-size:14px}
/* WhatsApp green regardless of the site's palette: the colour is what tells
   someone what the strip does before they read it. */
.wabar{display:flex;align-items:center;justify-content:center;gap:8px;
 background:#25d366;color:#fff;font-weight:700;font-size:14.5px;padding:11px 16px;
 text-decoration:none}
.wabar:hover{background:#1da851;color:#fff;text-decoration:none}
.wabar svg{flex-shrink:0}
.wrap{max-width:1200px;margin:0 auto;padding:28px 32px}
h1{font-size:30px;margin:6px 0 22px;font-weight:650}
.grid{display:grid;grid-template-columns:1fr 330px;gap:28px;align-items:start}
.imgcard{border:1px solid #e5e7eb;border-radius:12px;padding:36px;display:grid;place-items:center;min-height:420px}
.imgcard img{max-width:100%;max-height:480px}
.side{display:flex;flex-direction:column;gap:16px}
.cta{display:block;text-align:center;background:#f59e0b;color:#fff;font-weight:700;font-size:17px;
     padding:15px 10px;border-radius:10px;box-shadow:0 2px 8px rgba(245,158,11,.35)}
.cta:hover{background:#d97706}
.note{border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;font-size:13.5px;color:#475569;background:#f8fafc}
.also{border:1px solid #e5e7eb;border-radius:12px;padding:18px}
.also h3{font-size:16px;margin-bottom:12px}
.also .item{display:flex;gap:10px;align-items:center;padding:9px;border-radius:8px;background:#f8fafc;margin-bottom:8px}
.also .item img{width:44px;height:44px;object-fit:contain;background:#fff;border-radius:6px}
.also .item div{font-size:13.5px;line-height:1.35}
.also .item a{display:block;font-size:12.5px;margin-top:2px}
section{margin:30px 0}
h2{font-size:21px;margin-bottom:10px}
section p{margin-bottom:12px;color:#334155}
.box{border:1px solid #e5e7eb;border-radius:12px;padding:20px 22px;margin:18px 0}
.box h3{font-size:16px;margin-bottom:12px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.cols h4{font-size:13px;letter-spacing:.4px;margin-bottom:8px}
.pros h4{color:#059669}.cons h4{color:#dc2626}
.box li{margin:6px 0 6px 18px;color:#334155;font-size:14.5px}
.crossbar{border:1px dashed #cbd5e1;border-radius:10px;padding:12px 16px;margin:16px 0;font-size:14px;
          display:flex;justify-content:space-between;align-items:center;background:#fafafa}
.crossbar span{color:#94a3b8;font-size:12px;display:block}
footer{border-top:1px solid #e5e7eb;margin-top:40px;padding:18px 32px;color:#94a3b8;font-size:13px;text-align:center}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{border:1px solid #e5e7eb;border-radius:12px;padding:22px;margin-bottom:22px}
form.create{display:grid;gap:10px}
form.create input{padding:11px 13px;border:1px solid #cbd5e1;border-radius:8px;font-size:15px;width:100%}
form.create button{padding:12px;border:0;border-radius:8px;background:#101828;color:#fff;font-weight:600;font-size:15px;cursor:pointer}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
th{color:#64748b;font-size:12px;letter-spacing:.4px}
td img{width:38px;height:38px;object-fit:contain}
.err{background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:14px}
.okmsg{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:14px}
.pill{background:#eef2ff;color:#3730a3;border-radius:999px;padding:2px 10px;font-size:12px}
/* public store page */
.store-head{margin:8px 0 20px;text-align:center}
.store-head .slug{color:#94a3b8;font-size:12px;letter-spacing:.6px;text-transform:uppercase}
.store-head h1{margin:4px 0 4px}
.filters{border:1px solid #e5e7eb;border-radius:12px;padding:12px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;margin-bottom:22px}
.fbtn{display:inline-block;padding:8px 18px;border-radius:999px;font-size:14px;font-weight:600;color:#334155;background:#f1f5f9}
.fbtn.on{background:#4a154b;color:#fff}
.fbtn:hover{text-decoration:none}
/* flex + justify-content:center (not grid) so a partial row of cards is
   centered under the filter bar instead of stuck flush-left. */
.cards{display:flex;flex-wrap:wrap;gap:18px;justify-content:center}
.pcard{border:1px solid #e5e7eb;border-radius:12px;display:flex;flex-direction:column;overflow:hidden;
  flex:0 1 240px;width:240px}
.pcard .pimg{background:#fff;display:grid;place-items:center;height:210px;padding:14px}
.pcard .pimg img{max-width:100%;max-height:100%;object-fit:contain}
.pcard .pbody{padding:12px 14px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
.pcard .ptitle{font-size:14.5px;font-weight:600;line-height:1.35;color:#1a1a2e;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pcard .pmeta{font-size:12.5px;color:#64748b}
.pcard .pbtn{margin-top:auto;display:block;text-align:center;background:#4a154b;color:#fff;
  font-weight:700;font-size:14px;padding:11px;border-radius:8px}
.pcard .pbtn:hover{background:#611f69;text-decoration:none}
.empty{border:1px dashed #cbd5e1;border-radius:12px;padding:44px;text-align:center;color:#94a3b8}
/* responsive (portal traffic is mostly mobile) */
.cta-mobile{display:none}
@media(max-width:760px){.pcard{flex-basis:150px;width:150px}.pcard .pimg{height:150px}}
@media(max-width:420px){.pcard{flex-basis:130px;width:130px}}
@media(max-width:640px){
  .wrap{padding:18px 14px}
  h1{font-size:22px;margin-bottom:14px}
  h2{font-size:18px}
  header{padding:12px 16px}
  header .brand{font-size:16px}
  .imgcard{min-height:auto;padding:14px}
  .box{padding:14px 16px}
  .cols{grid-template-columns:1fr}
  .grid{gap:18px}
  .cta-mobile{display:block;margin:0 0 16px}
  .side .cta{display:none}
  .filters{padding:10px 12px}
  .fbtn{padding:7px 14px;font-size:13px}
}
"""


# WhatsApp's mark, drawn inline: an article page must not depend on an image
# host, and this stays crisp at any size.
WA_GLYPH = (
    "<svg viewBox='0 0 32 32' width='16' height='16' aria-hidden='true'>"
    "<path fill='currentColor' d='M16 3C8.8 3 3 8.8 3 16c0 2.3.6 4.5 1.7 6.4L3 29l6.8-1.8"
    "A13 13 0 1 0 16 3zm0 23.6c-2 0-4-.5-5.7-1.6l-.4-.2-4 1 1.1-3.9-.3-.4A10.6 10.6 0 1 1 "
    "16 26.6zm6-7.9c-.3-.2-1.9-1-2.2-1.1-.3-.1-.5-.2-.7.2s-.8 1-1 1.2-.4.2-.7 0a8.7 8.7 0 "
    "0 1-4.3-3.7c-.3-.6.3-.5.9-1.7.1-.2 0-.4 0-.6l-1-2.3c-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1"
    "-.9.4-.3.4-1.2 1.2-1.2 2.8s1.2 3.3 1.4 3.5c.2.2 2.4 3.7 5.9 5.1 2.2.9 3 1 4.1.8.7-.1 "
    "1.9-.8 2.2-1.6.3-.8.3-1.4.2-1.6-.1-.2-.3-.2-.6-.4z'/></svg>"
)


def wa_bar(product_title: str = "") -> str:
    """The support strip that sits under the header on every article page.

    The greeting names the product when we know it, so whoever answers can see
    which page the message came from without having to ask.
    """
    text = (f"Hi, I have a question about: {product_title[:70]}"
            if product_title else "")
    return (
        f"<a class='wabar' href='{esc(whatsapp_url(text))}' target='_blank' "
        f"rel='noopener'>{WA_GLYPH}<span>Support on WhatsApp</span></a>"
    )


def page(title: str, body: str, head_extra: str = "") -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='icon' type='image/png' href='/favicon.png'>"
        f"<title>{esc(title)}</title>{head_extra}<style>{CSS}</style></head>"
        f"<body>{body}<footer>© 2026 Beast Affiliates. All rights reserved."
        "</footer></body></html>"
    )


# -------------------------------------------------------------------- routes


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/links")
async def api_create_link(
    request: Request,
    session: Session = Depends(get_session),
    x_service_key: str = Header(default=""),
):
    """Server-to-server link minting (bot backend calls this in phase 2)."""
    if SERVICE_KEY and x_service_key != SERVICE_KEY:
        return Response(json.dumps({"error": "unauthorized"}), 401,
                        media_type="application/json")
    body = json.loads(await request.body() or b"{}")
    try:
        link, article_url = service.create_link(
            session,
            url=str(body.get("url", "")).strip(),
            tag=str(body.get("tag", "")).strip(),
            store_name=str(body.get("store_name", "")).strip() or DEFAULT_STORE_NAME,
            sender=str(body.get("sender", "")).strip(),
            fallback_title=str(body.get("fallback_title", "")).strip(),
            fallback_image=str(body.get("fallback_image", "")).strip(),
            source_link_id=str(body.get("source_link_id", "")).strip(),
            us_site=str(body.get("us_site", "")).strip(),
        )
    except service.LinkCreationError as e:
        return Response(json.dumps({"error": str(e)}), 422,
                        media_type="application/json")
    return {
        "link_id": link.id,
        "article_url": article_url,
        "tagged_url": link.tagged_url,
        "title": link.product.title,
        "source": link.product.source,
    }


@app.post("/api/wa-codes/claim")
async def claim_wa_code(
    request: Request,
    session: Session = Depends(get_session),
    x_service_key: str = Header(default=""),
):
    """Bot backend calls this when an unregistered number sends a 6-char code.
    Single-use: a successful claim consumes the code."""
    if SERVICE_KEY and x_service_key != SERVICE_KEY:
        return Response(json.dumps({"error": "unauthorized"}), 401,
                        media_type="application/json")
    body = json.loads(await request.body() or b"{}")
    code = str(body.get("code", "")).strip().upper()
    row = session.execute(
        select(WaLinkCode).where(WaLinkCode.code == code, WaLinkCode.used == 0)
    ).scalar_one_or_none()
    if row is None or row.expires_at < datetime.utcnow():
        return Response(json.dumps({"error": "invalid or expired"}), 404,
                        media_type="application/json")
    account = session.get(PortalAccount, row.account_id)
    if account is None:
        return Response(json.dumps({"error": "account gone"}), 404,
                        media_type="application/json")
    row.used = 1
    session.commit()
    return {"primary_number": account.whatsapp_number}


# ------------------------------------------------- public marketing website
# Server-rendered so BOTH domains share one implementation: beastassociate.com
# serves these directly, beastaffiliates.com proxies them (see frontend
# vercel.json). `?brand=` is a local preview override for the alternate skin.


def _site_ctx(request: Request, brand: str = ""):
    # Requests proxied from beastaffiliates.com carry ?xfh=aff because the
    # proxy rewrites the Host header to ours.
    if request.query_params.get("xfh") == "aff":
        return site.brand_for("", "affiliates"), "www.beastaffiliates.com"
    host = (
        request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    ).split(",")[0].strip()
    return site.brand_for(host, brand), host


ARTICLES_PER_PAGE = 24


def _article_cards(session: Session, brand: dict, limit: int, offset: int):
    """Real published articles for THIS domain, one card per product (the most
    recent article for it), newest first, excluding revoked links.

    Filtered by the site each article was published to, not just by
    marketplace: with several US domains, filtering on marketplace alone would
    show every user's US articles on every US site. Returns (cards, total)."""
    if not brand.get("us", True):
        mkt = Link.marketplace != "US"
    else:
        base = article_base("US", brand.get("site_key", ""))
        own = Link.site == base
        # Links created before per-user sites existed carry no site and belong
        # to the original US domain.
        if base == ARTICLE_BASE_US:
            own = or_(own, Link.site == "", Link.site.is_(None))
        mkt = and_(Link.marketplace == "US", own)
    # Latest article timestamp per product, so a product shows once even when
    # many users have shared it — the newest share represents it and floats up.
    latest = (
        select(Link.product_id, func.max(Link.created_at).label("mx"))
        .where(Link.revoked == 0, mkt)
        .group_by(Link.product_id)
        .subquery()
    )
    total = session.execute(select(func.count()).select_from(latest)).scalar_one()
    rows = session.execute(
        select(Link)
        .join(
            latest,
            (Link.product_id == latest.c.product_id)
            & (Link.created_at == latest.c.mx),
        )
        .where(Link.revoked == 0)
        .order_by(latest.c.mx.desc(), Link.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    cards, seen = [], set()
    for link in rows:
        if link.product_id in seen:  # guard against identical timestamps
            continue
        seen.add(link.product_id)
        p = link.product
        cards.append({
            "id": link.id, "slug": link.slug, "title": p.title,
            "image_url": p.image_url, "rating": p.rating,
            "bullets": json.loads(p.bullets_json or "[]"),
        })
    return cards, total


@app.get("/", response_class=HTMLResponse)
def site_home(request: Request, brand: str = "",
              session: Session = Depends(get_session)):
    b, host = _site_ctx(request, brand)
    cards, _ = _article_cards(session, b, limit=6, offset=0)
    return HTMLResponse(site.home(b, host, cards))


@app.get("/articles", response_class=HTMLResponse)
def site_articles(request: Request, brand: str = "", page: int = 1,
                  session: Session = Depends(get_session)):
    b, host = _site_ctx(request, brand)
    page = max(1, page)
    cards, total = _article_cards(
        session, b, limit=ARTICLES_PER_PAGE,
        offset=(page - 1) * ARTICLES_PER_PAGE,
    )
    total_pages = max(1, math.ceil(total / ARTICLES_PER_PAGE))
    return HTMLResponse(site.articles(b, host, cards, page, total_pages))


@app.get("/about", response_class=HTMLResponse)
def site_about(request: Request, brand: str = ""):
    b, host = _site_ctx(request, brand)
    return HTMLResponse(site.about(b, host))


@app.get("/contact", response_class=HTMLResponse)
def site_contact(request: Request, brand: str = ""):
    b, host = _site_ctx(request, brand)
    return HTMLResponse(site.contact(b, host))


@app.get("/privacy", response_class=HTMLResponse)
def site_privacy(request: Request, brand: str = ""):
    b, host = _site_ctx(request, brand)
    return HTMLResponse(site.privacy(b, host))


@app.get("/terms", response_class=HTMLResponse)
def site_terms(request: Request, brand: str = ""):
    b, host = _site_ctx(request, brand)
    return HTMLResponse(site.terms(b, host))


@app.get("/api/demo")
def demo_data():
    """Public (no-auth) full portal dataset for demo mode — dummy data for
    every tab (profile, overview, links, earnings, WhatsApp). Nothing here
    is in the database, so it never appears in admin/analytics."""
    return demo_mod.DEMO_PORTAL


def _render_demo_article(art: dict) -> HTMLResponse:
    from .articlegen import generate_copy

    copy = generate_copy(art["title"], art["bullets"], art.get("rating", ""),
                         art.get("price", ""))
    others = [a for a in demo_mod.DEMO_ARTICLES if a["id"] != art["id"]][:4]
    store = "Beast Affiliates"
    also_items = "".join(
        f"<div class='item'><img src='{esc(o['image_url'])}' alt=''>"
        f"<div>{esc(o['title'][:48])}"
        f"<a href='/p/{o['id']}/{o['slug']}'>View product →</a></div></div>"
        for o in others
    )
    readers_also = (
        f"<div class='crossbar'><div><span>Readers also viewed</span>"
        f"<a href='/p/{others[0]['id']}/{others[0]['slug']}'>"
        f"{esc(others[0]['title'][:70])}</a></div><div>→</div></div>"
        if others else ""
    )
    pros = "".join(f"<li>{esc(p)}</li>" for p in copy["pros"])
    cons = "".join(f"<li>{esc(c)}</li>" for c in copy["cons"])
    ideal = "".join(f"<li>{esc(i)}</li>" for i in copy["ideal"])
    tips = "".join(f"<li>{esc(t)}</li>" for t in copy["tips"])
    body = f"""
<header><div class='brand'><div class='logo'>{esc(store[:1].upper())}</div>{esc(store)}</div>
<a href='#disclosure'>Affiliate Disclosure</a></header>
{wa_bar(art['title'])}
<div class='wrap'>
  <h1>{esc(art['title'][:90])}</h1>
  <a class='cta cta-mobile' href='/go/{art['id']}' rel='nofollow sponsored'>View on Amazon</a>
  <div class='grid'>
    <div>
      <div class='imgcard'><img src='{esc(art['image_url'])}' alt='{esc(art['title'][:60])}'></div>
      <section>
        <h2>A closer look at {esc(art['title'][:60])}</h2>
        <p>{esc(copy['para1'])}</p>
        {f"<p>{esc(copy['para2'])}</p>" if copy['para2'] else ""}
      </section>
      {readers_also}
      <div class='box'>
        <h3>What We Like &amp; What to Consider</h3>
        <div class='cols'>
          <div class='pros'><h4>✓ PROS</h4><ul>{pros}</ul></div>
          <div class='cons'><h4>✗ CONS</h4><ul>{cons}</ul></div>
        </div>
      </div>
      <div class='box'><h3>Ideal For</h3><ul>{ideal}</ul></div>
      <div class='box'><h3>Worth Knowing</h3><ul>{tips}</ul></div>
    </div>
    <div class='side'>
      <a class='cta' href='/go/{art['id']}' rel='nofollow sponsored'>View on Amazon</a>
      <div class='note' id='disclosure'><b>Affiliate Link:</b> We earn a small
        commission when you buy through this link — at no extra cost to you.</div>
      <div class='note'><b>Note:</b> Product prices and availability are subject
        to change. Final prices are determined by the retailer at checkout.</div>
      <div class='also'><h3>You May Also Like</h3>{also_items}</div>
    </div>
  </div>
</div>"""
    return HTMLResponse(page(art["title"][:70], body))


@app.get("/api/links/{link_id}/resolve")
def resolve_link(
    link_id: str,
    session: Session = Depends(get_session),
    x_service_key: str = Header(default=""),
):
    """Pure lookup used by the BOT when a user forwards one of our article
    links: returns the underlying product's plain (untagged) Amazon URL plus
    the article's owner. Deliberately records NO view/click, so forwarding a
    link never inflates the original creator's stats."""
    if SERVICE_KEY and x_service_key != SERVICE_KEY:
        return Response(json.dumps({"error": "unauthorized"}), 401,
                        media_type="application/json")

    demo_art = demo_mod.DEMO_BY_ID.get(link_id)
    if demo_art is not None:
        return {
            "link_id": link_id, "marketplace": demo_art["marketplace"],
            "asin": demo_art["asin"], "sender": "",
            "amazon_url": amazon_url.canonical_tagged_url(
                demo_art["amazon_url"], demo_art["marketplace"], demo_art["asin"], ""
            ),
        }

    link = session.get(Link, link_id)
    if link is None:
        return Response(json.dumps({"error": "not found"}), 404,
                        media_type="application/json")
    return {
        "link_id": link.id,
        "marketplace": link.marketplace,
        "asin": link.asin,
        "sender": link.sender,
        "amazon_url": amazon_url.canonical_tagged_url(
            link.tagged_url, link.marketplace, link.asin, ""
        ),
    }


@app.get("/p/{link_id}/{slug}", response_class=HTMLResponse)
def article(link_id: str, slug: str, request: Request,
            session: Session = Depends(get_session)):
    demo_art = demo_mod.DEMO_BY_ID.get(link_id)
    if demo_art is not None:
        return _render_demo_article(demo_art)
    link = session.get(Link, link_id)
    if link is not None and not link.revoked:
        # Canonical-domain enforcement: US articles live on the US domain,
        # everything else on the INTL domain. Only redirect between the two
        # configured hosts so localhost/preview deployments are unaffected.
        canonical = link_base(link)
        canonical_host = urlsplit(canonical).netloc
        # Requests proxied by the portal-frontend project (beastaffiliates.com
        # rewrites /p/* here) carry ?xfh=us because Vercel's proxy replaces the
        # Host header with OUR domain — without the marker a US article would
        # look like it's on the wrong domain and 308 back, looping forever.
        if request.query_params.get("xfh") == "us":
            request_host = urlsplit(ARTICLE_BASE_US).netloc
        else:
            request_host = (
                request.headers.get("x-forwarded-host")
                or request.headers.get("host", "")
            ).split(",")[0].strip()
        # Every domain we publish on, so an article opened on any of them is
        # sent to the one it actually belongs to.
        known_hosts = all_article_hosts()
        if request_host in known_hosts and request_host != canonical_host:
            return RedirectResponse(f"{canonical}/p/{link.id}/{link.slug}",
                                    status_code=308)
    if link is None or link.revoked:
        return HTMLResponse(
            page("Not found", "<div class='wrap'><h1>This product page is no "
                 "longer available.</h1></div>"), 404)
    product = link.product
    copy = _copy_for(product)
    others = session.execute(
        select(Link)
        .where(Link.id != link.id, Link.revoked == 0,
               (Link.marketplace == "US") == (link.marketplace == "US"))
        .order_by(Link.created_at.desc())
        .limit(4)
    ).scalars().all()

    store = link.store_name or DEFAULT_STORE_NAME
    also_items = "".join(
        f"<div class='item'><img src='{esc(o.product.image_url)}' alt=''>"
        f"<div>{esc(o.product.title[:48])}"
        f"<a href='/p/{o.id}/{o.slug}'>View product →</a></div></div>"
        for o in others
    ) or ("<div style='color:#94a3b8;font-size:13.5px'>More products coming "
          "soon.</div>")
    readers_also = (
        f"<div class='crossbar'><div><span>Readers also viewed</span>"
        f"<a href='/p/{others[0].id}/{others[0].slug}'>"
        f"{esc(others[0].product.title[:70])}</a></div><div>→</div></div>"
        if others else ""
    )
    pros = "".join(f"<li>{esc(p)}</li>" for p in copy["pros"])
    cons = "".join(f"<li>{esc(c)}</li>" for c in copy["cons"])
    ideal = "".join(f"<li>{esc(i)}</li>" for i in copy["ideal"])
    tips = "".join(f"<li>{esc(t)}</li>" for t in copy["tips"])

    og = (
        f"<meta property='og:title' content='{esc(product.title[:90])}'>"
        f"<meta property='og:image' content='{esc(product.image_url)}'>"
        f"<meta property='og:description' content='{esc(copy['para1'][:150])}'>"
        "<meta property='og:type' content='product'>"
    )
    body = f"""
<header><div class='brand'><div class='logo'>{esc(store[:1].upper())}</div>{esc(store)}</div>
<a href='#disclosure'>Affiliate Disclosure</a></header>
{wa_bar(product.title)}
<div class='wrap'>
  <h1>{esc(product.title[:90])}</h1>
  <a class='cta cta-mobile' href='/go/{link.id}' rel='nofollow sponsored'>View on Amazon</a>
  <div class='grid'>
    <div>
      <div class='imgcard'><img src='{esc(product.image_url)}' alt='{esc(product.title[:60])}'></div>
      <section>
        <h2>A closer look at {esc(product.title[:60])}</h2>
        <p>{esc(copy['para1'])}</p>
        {f"<p>{esc(copy['para2'])}</p>" if copy['para2'] else ""}
      </section>
      {readers_also}
      <div class='box'>
        <h3>What We Like &amp; What to Consider</h3>
        <div class='cols'>
          <div class='pros'><h4>✓ PROS</h4><ul>{pros}</ul></div>
          <div class='cons'><h4>✗ CONS</h4><ul>{cons}</ul></div>
        </div>
      </div>
      <div class='box'><h3>Ideal For</h3><ul>{ideal}</ul></div>
      <div class='box'><h3>Worth Knowing</h3><ul>{tips}</ul></div>
    </div>
    <div class='side'>
      <a class='cta' href='/go/{link.id}' rel='nofollow sponsored'>View on Amazon</a>
      <div class='note' id='disclosure'><b>Affiliate Link:</b> We earn a small
        commission when you buy through this link — at no extra cost to you.</div>
      <div class='note'><b>Note:</b> Product prices and availability are subject
        to change. Final prices are determined by the retailer at checkout.</div>
      <div class='also'><h3>You May Also Like</h3>{also_items}</div>
    </div>
  </div>
</div>
<img src='/b/{link.id}' width='1' height='1' alt='' style='position:absolute;left:-9999px'>"""
    return HTMLResponse(page(product.title[:70], body, head_extra=og))


def _copy_for(product) -> dict:
    from .articlegen import generate_copy

    return generate_copy(product.title, json.loads(product.bullets_json),
                         product.rating, product.price)


@app.get("/u/{slug}", response_class=HTMLResponse)
def store_page(slug: str, request: Request, session: Session = Depends(get_session)):
    """Public store page: a user's recent products, filterable by day/country."""
    account = session.execute(
        select(PortalAccount).where(PortalAccount.store_slug == slug.strip().lower())
    ).scalar_one_or_none()
    if account is None or not account.store_enabled:
        return HTMLResponse(
            page("Not found", "<div class='wrap'><h1>This store page is not "
                 "available.</h1></div>"), 404)

    rng = request.query_params.get("range", "week")
    if rng not in ("today", "yesterday", "week"):
        rng = "week"
    country = request.query_params.get("country", "").upper()

    links = session.execute(
        select(Link)
        .where(Link.sender == account.whatsapp_number, Link.revoked == 0)
        .order_by(Link.created_at.desc())
        .limit(200)
    ).scalars().all()

    today = datetime.utcnow().date()
    if rng == "today":
        links = [l for l in links if l.created_at.date() == today]
    elif rng == "yesterday":
        links = [l for l in links if l.created_at.date() == today - timedelta(days=1)]
    else:
        links = [l for l in links if l.created_at >= datetime.utcnow() - timedelta(days=7)]
    if country:
        links = [l for l in links if l.marketplace == country]

    # Deduplicate products (same ASIN shared twice shows once, newest link wins).
    seen: set = set()
    unique_links = []
    for l in links:
        key = (l.marketplace, l.asin)
        if key not in seen:
            seen.add(key)
            unique_links.append(l)

    store_title = next((l.store_name for l in unique_links if l.store_name), "") or (
        account.username.capitalize()
    )
    countries = sorted({l.marketplace for l in links} | ({country} if country else set()))

    def fbtn(label: str, value: str) -> str:
        q = f"?range={value}" + (f"&country={country}" if country else "")
        return (f"<a class='fbtn {'on' if rng == value else ''}' "
                f"href='/u/{esc(account.store_slug)}{q}'>{label}</a>")

    options = "".join(
        f"<option value='{c}' {'selected' if c == country else ''}>{c}</option>"
        for c in countries
    )
    cards = "".join(
        f"""<div class='pcard'>
  <div class='pimg'><img src='{esc(l.product.image_url)}' alt='' loading='lazy'></div>
  <div class='pbody'>
    <div class='ptitle'>{esc(l.product.title[:110])}</div>
    <div class='pmeta'>{esc(l.marketplace)}{f" · ★ {esc(l.product.rating)}" if l.product.rating else ""}</div>
    <a class='pbtn' href='{esc(link_base(l))}/p/{l.id}/{l.slug}'>View product</a>
  </div>
</div>"""
        for l in unique_links
    )
    body = f"""
<header><div class='brand'><div class='logo'>{esc(store_title[:1].upper())}</div>{esc(store_title)}</div>
<a href='#'>Affiliate Disclosure</a></header>
{wa_bar()}
<div class='wrap'>
  <div class='store-head'>
    <span class='slug'>/u/{esc(account.store_slug)}</span>
    <h1>Shop by {esc(store_title)}</h1>
    <p style='color:#64748b'>Hand-picked Amazon products, refreshed as they come in.</p>
  </div>
  <div class='filters'>
    {fbtn("Today", "today")}{fbtn("Yesterday", "yesterday")}{fbtn("This Week", "week")}
    <select onchange="location='/u/{esc(account.store_slug)}?range={rng}'+(this.value?'&country='+this.value:'')"
      style='padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px'>
      <option value=''>All countries</option>{options}
    </select>
  </div>
  {f"<div class='cards'>{cards}</div>" if unique_links else
   "<div class='empty'>No products in this period yet — check back soon.</div>"}
</div>"""
    og = (f"<meta property='og:title' content='Shop by {esc(store_title)}'>"
          "<meta property='og:description' content='Hand-picked Amazon products'>")
    return HTMLResponse(page(f"Shop by {store_title}", body, head_extra=og))


# A repeat view/click from the SAME browser within this window doesn't
# recount — matches Amazon's own ~24h attribution cookie window, and stops
# reloading a page or double-clicking the button from inflating the stats.
DEDUP_SECONDS = 24 * 3600


@app.get("/b/{link_id}")
def beacon(link_id: str, request: Request, session: Session = Depends(get_session)):
    link = session.get(Link, link_id)
    cookie_name = f"v_{link_id}"
    already_counted = request.cookies.get(cookie_name) == "1"
    if link is not None and not already_counted:
        link.views += 1
        session.add(LinkEvent(link_id=link.id, kind="view"))
        session.commit()
    resp = Response(PIXEL_GIF, media_type="image/gif",
                    headers={"Cache-Control": "no-store"})
    if link is not None and not already_counted:
        resp.set_cookie(cookie_name, "1", max_age=DEDUP_SECONDS,
                        httponly=True, samesite="lax", secure=True)
    return resp


@app.get("/go/{link_id}")
def go(link_id: str, request: Request, session: Session = Depends(get_session)):
    demo_art = demo_mod.DEMO_BY_ID.get(link_id)
    if demo_art is not None:
        # Demo buy button — real Amazon URL with the dummy tag, no counting.
        return RedirectResponse(demo_art["amazon_url"], status_code=302,
                                headers={"Cache-Control": "no-store"})
    link = session.get(Link, link_id)
    if link is None or link.revoked:
        return HTMLResponse(page("Not found", "<div class='wrap'><h1>Link not "
                                 "found</h1></div>"), 404)
    cookie_name = f"c_{link_id}"
    already_counted = request.cookies.get(cookie_name) == "1"
    if not already_counted:
        link.clicks += 1
        session.add(LinkEvent(link_id=link.id, kind="click"))
        session.commit()
    # The redirect to Amazon ALWAYS happens regardless of dedup — only the
    # click COUNT is deduped, never the actual navigation.
    resp = RedirectResponse(link.tagged_url, status_code=302,
                            headers={"Cache-Control": "no-store"})
    if not already_counted:
        resp.set_cookie(cookie_name, "1", max_age=DEDUP_SECONDS,
                        httponly=True, samesite="lax", secure=True)
    return resp


# ------------------------------------------------- dev/test create form (GET /)


@app.get("/tester", response_class=HTMLResponse)
def index(session: Session = Depends(get_session), error: str = "",
          created: str = "", src: str = ""):
    rows = session.execute(
        select(Link).order_by(Link.created_at.desc()).limit(50)
    ).scalars().all()
    table = ""
    if rows:
        body_rows = "".join(
            f"<tr><td><img src='{esc(r.product.image_url)}' alt=''></td>"
            f"<td><a href='{esc(article_base(r.marketplace))}/p/{r.id}/{r.slug}' target='_blank'>"
            f"{esc(r.product.title[:60])}</a><br><span class='pill'>{r.id} · "
            f"{r.marketplace} · {esc(r.product.source)}</span></td>"
            f"<td>{r.views}</td><td>{r.clicks}</td>"
            f"<td><a href='/go/{r.id}' target='_blank'>test →</a></td></tr>"
            for r in rows
        )
        table = ("<div class='card'><h2>Links</h2><br><table>"
                 "<tr><th></th><th>PRODUCT</th><th>VIEWS</th><th>CLICKS</th>"
                 f"<th></th></tr>{body_rows}</table></div>")
    msg = ""
    if error:
        msg = f"<div class='err'>Failed: {esc(error)}</div>"
    if created:
        msg = (f"<div class='okmsg'>Created (<b>{esc(src)}</b>): "
               f"<a href='{esc(created)}' target='_blank'>{esc(created)}</a></div>")
    key_field = ("<input name='key' placeholder='Service key' required>"
                 if SERVICE_KEY else "")
    body = f"""
<header><div class='brand'><div class='logo'>B</div>Beast Affiliates — link
tester</div><a href='/health'>health</a></header>
<div class='wrap'>
  {msg}
  <div class='card'>
    <h2>Create a hub link</h2><br>
    <form class='create' method='post' action='/create-test'>
      {key_field}
      <input name='url' placeholder='Amazon product URL' required>
      <input name='tag' placeholder='Affiliate tag (optional)'>
      <input name='store' placeholder='Store name (optional)'>
      <button>Create link</button>
    </form>
  </div>
  {table}
</div>"""
    return HTMLResponse(page("Beast Affiliates — tester", body))


@app.post("/create-test")
async def create_test(request: Request, session: Session = Depends(get_session)):
    form = parse_qs((await request.body()).decode())
    get = lambda k: form.get(k, [""])[0].strip()  # noqa: E731
    if SERVICE_KEY and get("key") != SERVICE_KEY:
        return RedirectResponse("/?error=wrong%20service%20key", status_code=303)
    try:
        link, article_url = service.create_link(
            session, url=get("url"), tag=get("tag"),
            store_name=get("store") or DEFAULT_STORE_NAME,
        )
    except service.LinkCreationError as e:
        return RedirectResponse(f"/?error={quote(str(e))}", status_code=303)
    return RedirectResponse(
        f"/?created={quote(f'/p/{link.id}/{link.slug}')}"
        f"&src={link.product.source}",
        status_code=303,
    )
