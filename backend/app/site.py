"""Public marketing website (server-rendered) shared by both domains.

Served at /, /articles, /about, /contact, /privacy, /terms. Because it lives
in the backend, beastassociate.com gets it natively and beastaffiliates.com
proxies the same pages — one implementation, no duplicated copy. The brand
palette/name varies slightly per host (owner asked for "little UI change").

The affiliate portal itself is the React SPA at /dashboard.
"""

import html as htmllib
import os
import re
from urllib.parse import quote

# ---------------------------------------------------------------- branding
# `us` decides which marketplaces' articles a domain lists: the affiliates
# domain shows US articles, the associate domain shows every other country —
# mirroring where each article physically lives (see config.article_base).

BRANDS = {
    "affiliates": {
        "name": "Beast Affiliates",
        "accent": "#4a154b",
        "accent_dark": "#611f69",
        "accent_soft": "#f6ecf7",
        "tagline": "Product recommendations and buying guides to help you shop smarter.",
        "us": True,
        "site_key": "",
    },
    "associate": {
        "name": "Beast Associate",
        "accent": "#1f4e79",
        "accent_dark": "#163a5a",
        "accent_soft": "#eaf1f8",
        "tagline": "Independent product research and buying guides for online shoppers.",
        "us": False,
    },
    # US sites the admin can publish a user's articles to. No sign-in anywhere
    # on these: the dashboard lives on beastaffiliates.com and these are read
    # only as product-guide sites, so advertising a login would lead nowhere
    # useful for their visitors.
    "finds": {
        "name": "Beast Finds",
        "accent": "#0f6b5c",
        "accent_dark": "#0a4f45",
        "accent_soft": "#e8f4f1",
        "site_key": "beastfinds",
        "tagline": "Hand-picked product finds, researched and explained.",
        "us": True,
        "login": False,
    },
    "cart": {
        "name": "Beast Cart",
        "accent": "#a8541a",
        "accent_dark": "#7d3e13",
        "accent_soft": "#fbf0e7",
        "site_key": "beastscart",
        "tagline": "Honest buying guides to help you fill your cart with confidence.",
        "us": True,
        "login": False,
    },
    "deal": {
        "name": "Beast Deals",
        "accent": "#2f3d8f",
        "accent_dark": "#232d6b",
        "accent_soft": "#eceff9",
        "site_key": "beastsdeal",
        "tagline": "Deals worth knowing about, checked before we share them.",
        "us": True,
        "login": False,
    },
}

# Which brand a request belongs to, by host. Replaces a substring check that
# only ever had to tell two domains apart.
HOST_BRANDS = [
    ("beastassociate", "associate"),
    ("beastfinds", "finds"),
    ("beastscart", "cart"),
    ("beastsdeal", "deal"),
    ("beastaffiliates", "affiliates"),
]

CATEGORIES = {
    "DEMO01": "Home & Everyday",
    "DEMO02": "Electronics & Gadgets",
    "DEMO03": "Phones & Accessories",
    "DEMO04": "Audio & Headphones",
    "DEMO05": "Gaming & Entertainment",
    "DEMO06": "Computers & Laptops",
}

NAV = [("/", "Home"), ("/articles", "Articles & Guides"),
       ("/about", "About"), ("/contact", "Contact")]

# Each new site orders its own nav, so they do not read as the same template
# with the colours swapped.
NAV_BY_BRAND = {
    "finds": [("/", "Home"), ("/articles", "Guides"), ("/about", "How we work"),
              ("/contact", "Contact")],
    "cart": [("/", "Home"), ("/articles", "Shop guides"), ("/contact", "Contact"),
             ("/about", "About us")],
    "deal": [("/articles", "Today's picks"), ("/", "Home"), ("/about", "About"),
             ("/contact", "Contact")],
}

# The number and greeting live in config so the marketing pages and the article
# pages cannot drift apart, and so neither one can be repointed at the bot's own
# number by editing the wrong setting.
from .config import whatsapp_url  # noqa: E402

# What the green tab says. Not "bot": this number is answered by a person.
WA_LABEL = "For Premium Products"


def nav_for(brand: dict) -> list[tuple[str, str]]:
    key = next((k for k, v in BRANDS.items() if v is brand), "")
    return NAV_BY_BRAND.get(key, NAV)


# ------------------------------------------------------------------- logos
# Drawn rather than shipped as image files: sharp at any size, tinted from the
# brand's own accent, and nothing extra for the page to download. Each mark is
# deliberately a different shape so the three sites are told apart at a glance.
_LOGO_SHAPES = {
    # a lens — "finds"
    "finds": ('<circle cx="14" cy="14" r="8.5" fill="none" stroke="currentColor" '
              'stroke-width="3.2"/><path d="M20.4 20.4L27 27" stroke="currentColor" '
              'stroke-width="3.6" stroke-linecap="round"/>'),
    # a basket — "cart"
    "cart": ('<path d="M5 9h20l-2.4 12.4a2 2 0 0 1-2 1.6H9.4a2 2 0 0 1-2-1.6L5 9z" '
             'fill="none" stroke="currentColor" stroke-width="3"/>'
             '<path d="M11 9V6.5a4 4 0 0 1 8 0V9" fill="none" stroke="currentColor" '
             'stroke-width="3" stroke-linecap="round"/>'),
    # a price tag — "deals"
    "deal": ('<path d="M16.5 4H26v9.5L13.4 26.1a2 2 0 0 1-2.8 0l-6.7-6.7a2 2 0 0 1 '
             '0-2.8L16.5 4z" fill="none" stroke="currentColor" stroke-width="3" '
             'stroke-linejoin="round"/><circle cx="21" cy="9" r="2.4" '
             'fill="currentColor"/>'),
}


def logo_mark(brand: dict, size: int = 34) -> str:
    """The site's logo. Brands with a drawn mark get their own shape; the two
    original sites keep the Beast image they already had."""
    key = next((k for k, v in BRANDS.items() if v is brand), "")
    shape = _LOGO_SHAPES.get(key)
    if not shape:
        return f'<img src="/favicon.png" alt="" style="height:{size}px;width:{size}px">'
    return (
        f'<svg viewBox="0 0 32 32" width="{size}" height="{size}" role="img" '
        f'aria-label="{esc(brand["name"])}" style="flex-shrink:0">{shape}</svg>'
    )


def brand_for(host: str, override: str = "") -> dict:
    key = override
    if not key:
        h = (host or "").lower()
        key = next((k for frag, k in HOST_BRANDS if frag in h), "affiliates")
    return BRANDS.get(key, BRANDS["affiliates"])


def shows_login(brand: dict) -> bool:
    """Whether this site advertises the partner dashboard at all.

    The three US publishing sites do not: their visitors are shoppers, and the
    dashboard lives on beastaffiliates.com. Sending them to a login they cannot
    use would be a dead end, so the partner sections are dropped rather than
    left pointing somewhere unhelpful."""
    return brand.get("login", True) is not False


def login_url(host: str) -> str:
    h = (host or "").lower()
    if "localhost" in h or "127.0.0.1" in h:
        return "http://localhost:5173/dashboard"
    if "beastaffiliates" in h:
        return "/dashboard"
    return "https://www.beastaffiliates.com/dashboard"


# WhatsApp's mark, drawn inline so the button needs no image and stays crisp.
WA_GLYPH = (
    '<svg viewBox="0 0 32 32" width="17" height="17" aria-hidden="true">'
    '<path fill="currentColor" d="M16 3C8.8 3 3 8.8 3 16c0 2.3.6 4.5 1.7 6.4L3 29l6.8-1.8'
    'A13 13 0 1 0 16 3zm0 23.6c-2 0-4-.5-5.7-1.6l-.4-.2-4 1 1.1-3.9-.3-.4A10.6 10.6 0 1 1 '
    '16 26.6zm6-7.9c-.3-.2-1.9-1-2.2-1.1-.3-.1-.5-.2-.7.2s-.8 1-1 1.2-.4.2-.7 0a8.7 8.7 0 '
    '0 1-4.3-3.7c-.3-.6.3-.5.9-1.7.1-.2 0-.4 0-.6l-1-2.3c-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1-.9.4'
    '-.3.4-1.2 1.2-1.2 2.8s1.2 3.3 1.4 3.5c.2.2 2.4 3.7 5.9 5.1 2.2.9 3 1 4.1.8.7-.1 1.9-.8 '
    '2.2-1.6.3-.8.3-1.4.2-1.6-.1-.2-.3-.2-.6-.4z"/></svg>'
)


def esc(v) -> str:
    return htmllib.escape(str(v or ""))


# -------------------------------------------------------------------- CSS

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--accent:%(accent)s;--accent-dark:%(accent_dark)s;--accent-soft:%(accent_soft)s;
 --ink:#1b2130;--mute:#5b6577;--line:#e6e8ee;--bg:#fff}
html{scroll-behavior:smooth}
body{font:16px/1.65 'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
img{max-width:100%%}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}

/* header */
header.site{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.92);
 backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.hrow{display:flex;align-items:center;gap:18px;padding:14px 0}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;
 color:var(--accent);letter-spacing:-.3px;flex-shrink:0}
.logo img{height:34px;width:34px;object-fit:contain}
nav.main{display:flex;gap:4px;margin-left:auto;flex-wrap:wrap}
nav.main a{padding:9px 14px;border-radius:8px;color:var(--ink);font-weight:600;font-size:14.5px}
nav.main a:hover{background:var(--accent-soft);color:var(--accent);text-decoration:none}
nav.main a.on{background:var(--accent);color:#fff}
.btn{display:inline-block;border-radius:10px;font-weight:700;font-size:14.5px;
 padding:11px 20px;border:2px solid var(--accent);transition:.18s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-dark);border-color:var(--accent-dark);text-decoration:none}
.btn-ghost{background:#fff;color:var(--accent)}
.btn-ghost:hover{background:var(--accent-soft);text-decoration:none}
.btn-lg{padding:14px 26px;font-size:16px}
/* WhatsApp green, deliberately not the brand accent — the colour is what tells
   people what the button does before they read it. */
.btn-wa{background:#25d366;border-color:#25d366;color:#fff;display:inline-flex;
 align-items:center;gap:8px}
.btn-wa:hover{background:#1da851;border-color:#1da851;color:#fff;text-decoration:none}
.wa-ico{display:inline-flex}

/* disclosure strip */
.strip{background:var(--accent-soft);border-bottom:1px solid var(--line);
 text-align:center;padding:11px 22px;font-size:13.5px;color:var(--mute)}

/* hero */
.hero{position:relative;overflow:hidden;padding:70px 0 60px}
.hero:before,.hero:after{content:'';position:absolute;border-radius:50%%;filter:blur(70px);opacity:.5;z-index:0}
.hero:before{width:420px;height:420px;background:var(--accent-soft);top:-140px;left:-120px}
.hero:after{width:380px;height:380px;background:#fdf2e9;bottom:-160px;right:-100px}
.hero .wrap{position:relative;z-index:1}
.hgrid{display:grid;grid-template-columns:1.05fr .95fr;gap:48px;align-items:center}
h1{font-size:52px;line-height:1.08;letter-spacing:-1.4px;font-weight:800}
.lead{font-size:18px;color:var(--mute);margin:18px 0 26px;max-width:34em}
.cta-row{display:flex;gap:12px;flex-wrap:wrap}
.disc-box{margin-top:26px;border:1px solid var(--line);border-radius:12px;padding:16px 18px;
 background:#fff;font-size:13.5px;color:var(--mute);max-width:38em}
.disc-box b{color:var(--ink)}

/* feature cards */
.fcards{display:grid;gap:14px}
.fcard{border:1px solid var(--line);border-radius:14px;padding:20px 22px;background:#fff;
 display:flex;gap:16px;align-items:flex-start;transition:.18s}
.fcard:hover{box-shadow:0 8px 26px rgba(20,25,40,.08);transform:translateY(-2px)}
.fico{width:44px;height:44px;border-radius:11px;background:var(--accent-soft);color:var(--accent);
 display:grid;place-items:center;font-size:20px;flex-shrink:0}
.fcard h3{font-size:16.5px;margin-bottom:3px}
.fcard p{font-size:14px;color:var(--mute);line-height:1.55}

/* sections */
section.band{padding:64px 0;border-top:1px solid var(--line)}
section.band.soft{background:#fbfbfd}
.shead{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;
 flex-wrap:wrap;margin-bottom:26px}
h2{font-size:34px;letter-spacing:-.8px;line-height:1.15;font-weight:800}
.sub{color:var(--mute);margin-top:8px;max-width:52em}
h3{font-size:20px;letter-spacing:-.2px}

/* article cards */
.acards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:22px;
 align-items:stretch}
.acards>*{min-width:0}
.ac{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff;
 display:flex;flex-direction:column;transition:.18s}
.ac:hover{box-shadow:0 10px 30px rgba(20,25,40,.09);transform:translateY(-3px)}
/* flex-basis + min-height are both pinned: as a flex-column child the thumb's
   default min-height:auto lets a tall product image stretch the box and spill
   over the text below. overflow:hidden is the final guarantee. */
.ac .thumb{flex:0 0 190px;height:190px;min-height:190px;max-height:190px;
 display:flex;align-items:center;justify-content:center;padding:18px;background:#fff;
 border-bottom:1px solid var(--line);overflow:hidden}
.ac .thumb img{max-width:100%%;max-height:154px;width:auto;height:auto;
 object-fit:contain;transition:.2s}
.ac .thumb:hover img{transform:scale(1.05)}
.ac .body{padding:18px;display:flex;flex-direction:column;gap:10px;flex:1}
.ac h3{font-size:17px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;
 -webkit-box-orient:vertical;overflow:hidden}
.ac h3 a{color:var(--ink)}
.ac h3 a:hover{color:var(--accent);text-decoration:none}
.ac .actions{margin-top:auto;display:grid;gap:8px}
.ac .amz{text-align:center;border:2px solid var(--accent);color:var(--accent);
 border-radius:9px;padding:9px;font-weight:700;font-size:13.5px}
.ac .amz:hover{background:var(--accent-soft);text-decoration:none}
.ac p{font-size:14px;color:var(--mute);display:-webkit-box;-webkit-line-clamp:2;
 -webkit-box-orient:vertical;overflow:hidden}
.meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12.5px;color:var(--mute)}
.tag{background:var(--accent);color:#fff;border-radius:6px;padding:4px 10px;
 font-size:11.5px;font-weight:700}
.ac .go{background:var(--accent);color:#fff;text-align:center;
 border-radius:9px;padding:11px;font-weight:700;font-size:14px}
.ac .go:hover{background:var(--accent-dark);text-decoration:none}

/* prose (legal/about) */
.prose{max-width:62em}
.prose h2{font-size:26px;margin:34px 0 10px}
.prose h3{font-size:18px;margin:22px 0 6px}
.prose p,.prose li{color:#39424f;font-size:15.5px;margin-bottom:11px}
.prose ul{margin:0 0 14px 22px}
.prose .updated{color:var(--mute);font-size:14px;margin-bottom:8px}
.callout{background:var(--accent-soft);border-radius:12px;padding:18px 20px;margin:20px 0;font-size:15px}

/* contact */
.cgrid{display:grid;grid-template-columns:1.1fr .9fr;gap:30px;align-items:start}
.cbox{border:1px solid var(--line);border-radius:14px;padding:24px}
.field{display:block;margin-bottom:14px;font-size:14px;color:var(--mute);font-weight:600}
.field input,.field textarea{width:100%%;margin-top:6px;border:1px solid var(--line);
 border-radius:9px;padding:11px 13px;font:inherit;font-size:15px;color:var(--ink)}
.field textarea{min-height:130px;resize:vertical}
.field input:focus,.field textarea:focus{outline:none;border-color:var(--accent)}
.crow{display:flex;gap:13px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--line)}
.crow:last-child{border-bottom:0}
.crow .ci{width:38px;height:38px;border-radius:10px;background:var(--accent-soft);
 color:var(--accent);display:grid;place-items:center;flex-shrink:0}

/* cta band */
.ctaband{background:var(--accent);color:#fff;border-radius:20px;padding:46px;text-align:center;margin:56px 0}
.ctaband h2{color:#fff}
.ctaband p{color:rgba(255,255,255,.85);margin:10px auto 22px;max-width:40em}
.ctaband .btn{background:#fff;color:var(--accent);border-color:#fff}
.ctaband .btn:hover{background:#f2f2f5}

/* footer */
footer.site{background:#12151d;color:#aab2c0;margin-top:70px;padding:52px 0 26px;font-size:14.5px}
.fgrid{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:36px}
footer.site h4{color:#fff;font-size:15px;margin-bottom:14px}
footer.site a{color:#aab2c0;display:block;padding:5px 0}
footer.site a:hover{color:#fff}
.flogo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:19px;color:#fff;margin-bottom:14px}
.flogo img{height:32px;width:32px;object-fit:contain}
.fine{border-top:1px solid #262b36;margin-top:34px;padding-top:20px;text-align:center;font-size:13px;color:#79839a}

@media(max-width:900px){
 .hgrid,.cgrid{grid-template-columns:1fr}
 h1{font-size:38px;letter-spacing:-.8px}
 h2{font-size:27px}
 .fgrid{grid-template-columns:1fr;gap:26px}
 .hero{padding:44px 0 40px}
 section.band{padding:46px 0}
 .ctaband{padding:32px 22px}
 .hrow{flex-wrap:wrap;gap:10px}
 nav.main{order:3;width:100%%;margin-left:0}
 nav.main a{padding:8px 11px;font-size:13.5px}
}
"""


# ------------------------------------------------------------------ layout

def shell(brand: dict, host: str, title: str, body: str, active: str = "") -> str:
    items = nav_for(brand)
    nav = "".join(
        f"<a href='{p}' class='{'on' if p == active else ''}'>{esc(l)}</a>"
        for p, l in items
    )
    quick = "".join(f"<a href='{p}'>{esc(l)}</a>" for p, l in items)
    # Green on every site, brand colours notwithstanding: green IS the signal
    # that this opens WhatsApp, and recolouring it per brand would lose that.
    wa = (f'<a class="btn btn-wa" href="{whatsapp_url()}" target="_blank" '
          f'rel="noopener"><span class="wa-ico">{WA_GLYPH}</span>{WA_LABEL}</a>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | {esc(brand['name'])}</title>
<meta name="description" content="{esc(brand['tagline'])}">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{CSS % brand}</style></head><body>
<header class="site"><div class="wrap"><div class="hrow">
  <a class="logo" href="/">{logo_mark(brand)}{esc(brand['name'])}</a>
  <nav class="main">{nav}</nav>
  {wa}
  {f'<a class="btn btn-primary" href="{login_url(host)}">Log in</a>' if shows_login(brand) else ''}
</div></div></header>
<div class="strip">As an Amazon Associate we earn from qualifying purchases.
 <a href="/about#disclosure">Learn more →</a></div>
{body}
<footer class="site"><div class="wrap">
  <div class="fgrid">
    <div>
      <div class="flogo">{logo_mark(brand, 30)}{esc(brand['name'])}</div>
      <p>{esc(brand['tagline'])}</p>
      <p style="margin-top:14px;font-size:13px">
        <b style="color:#fff">Affiliate Disclosure:</b> As an Amazon Associate we earn
        from qualifying purchases. Purchases through our links are at no extra cost
        to you. Product availability and pricing are set by the retailer and may change.
      </p>
    </div>
    <div><h4>Quick Links</h4>{quick}
      <a href="{whatsapp_url()}" target="_blank" rel="noopener">{WA_LABEL}</a></div>
    <div><h4>Legal</h4>
      <a href="/privacy">Privacy Policy</a>
      <a href="/terms">Terms &amp; Conditions</a>
      <a href="/about#disclosure">Affiliate Disclosure</a>
      <a href="/contact">Contact Us</a>
    </div>
  </div>
  <div class="fine">© 2026 {esc(brand['name'])}. All rights reserved.
   Some product images and details are provided by Amazon and may change without notice.</div>
</div></footer></body></html>"""


def _card(a: dict) -> str:
    blurb = (a["bullets"][0] if a.get("bullets") else "")[:130]
    cat = CATEGORIES.get(a["id"], "Product Guide")
    # The whole card opens the guide (image, title, Read more all go to /p/).
    # Amazon is reached only through the explicit "View on Amazon" action here
    # and the buy button on the guide itself (/go/<id>, the creator's tag).
    return f"""<article class="ac">
  <a class="thumb" href="/p/{a['id']}/{a['slug']}" title="{esc(a['title'][:60])}">
    <img src="{esc(a['image_url'])}" alt="{esc(a['title'][:60])}" loading="lazy"></a>
  <div class="body">
    <div class="meta"><span class="tag">{esc(cat)}</span>
      {f"<span>★ {esc(a['rating'])}</span>" if a.get('rating') else ""}
      <span>· 2 min read</span></div>
    <h3><a href="/p/{a['id']}/{a['slug']}">{esc(a['title'][:78])}</a></h3>
    <p>{esc(blurb)}</p>
    <div class="actions">
      <a class="go" href="/p/{a['id']}/{a['slug']}">Read more →</a>
      <a class="amz" href="/go/{a['id']}" rel="nofollow sponsored" target="_blank">
        View on Amazon ↗</a>
    </div>
  </div></article>"""


# ------------------------------------------------------------------- pages

def _empty_state(brand: dict) -> str:
    return ("<p class='sub' style='margin:8px 0 0'>No product articles have been "
            "published on {name} yet — please check back soon.</p>").format(
        name=esc(brand["name"]))


def home(brand: dict, host: str, cards_data: list | None = None) -> str:
    """The landing page. The three newer sites each get their own composition
    rather than the same template in a different colour — different hero shape,
    different section order, different way of presenting the guides."""
    key = next((k for k, v in BRANDS.items() if v is brand), "")
    builder = {"finds": _home_finds, "cart": _home_cart, "deal": _home_deal}.get(key)
    if builder:
        return builder(brand, host, cards_data or [])
    cards_data = cards_data or []
    cards = "".join(_card(a) for a in cards_data) or _empty_state(brand)
    partner_band = f"""<div class="ctaband">
    <h2>Are you a partner?</h2>
    <p>Registered partners can log in to manage their product links, track clicks
       and orders, and view earnings.</p>
    <a class="btn btn-lg" href="{login_url(host)}">Log in to your dashboard</a>
  </div>""" if shows_login(brand) else ""
    body = f"""
<section class="hero"><div class="wrap"><div class="hgrid">
  <div>
    <h1>Product Recommendations &amp; Buying Guides</h1>
    <p class="lead">Explore product summaries, category guides and Amazon shopping
      references so you can compare features, check the details that matter, and
      decide with confidence before you buy.</p>
    <div class="cta-row">
      <a class="btn btn-primary btn-lg" href="/articles">Explore all guides →</a>
      <a class="btn btn-ghost btn-lg" href="/about">Learn more</a>
    </div>
    <div class="disc-box"><b>Affiliate Disclosure:</b> As an Amazon Associate we earn
      from qualifying purchases. Purchases through our links are at no extra cost to
      you. Product availability and pricing are subject to change.</div>
  </div>
  <div class="fcards">
    <div class="fcard"><div class="fico">🛡️</div><div>
      <h3>Product Recommendations</h3>
      <p>Browse hand-checked product picks organised by category, with the key
         specifications summarised in plain language.</p></div></div>
    <div class="fcard"><div class="fico">📈</div><div>
      <h3>Buying Guides</h3>
      <p>Read comparisons and practical guides that explain what to look for
         before choosing between similar products.</p></div></div>
    <div class="fcard"><div class="fico">⚡</div><div>
      <h3>Trusted Retailers</h3>
      <p>Product links take you to trusted retailers including Amazon, where you
         complete your purchase securely at the listed price.</p></div></div>
  </div>
</div></div></section>

<section class="band soft"><div class="wrap">
  <div class="shead"><div>
    <h2>Product Articles &amp; Buying Guides</h2>
    <p class="sub">Product comparisons and buyer-check guides based on listing
      details, specifications and category information.</p>
  </div><a class="btn btn-ghost" href="/articles">View all →</a></div>
  <div class="acards">{cards}</div>
</div></section>

<section class="band"><div class="wrap">
  <div class="shead"><div>
    <h2>How we put these guides together</h2>
    <p class="sub">A simple, transparent process — no sponsored placements.</p>
  </div></div>
  <div class="acards" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">
    <div class="fcard"><div class="fico">1</div><div><h3>We gather listing details</h3>
      <p>Specifications, features and category information are collected from the
         retailer's own product listing.</p></div></div>
    <div class="fcard"><div class="fico">2</div><div><h3>We summarise the essentials</h3>
      <p>Each guide highlights what the product does well, what to consider, and
         who it suits — in a consistent format.</p></div></div>
    <div class="fcard"><div class="fico">3</div><div><h3>You decide on the retailer</h3>
      <p>Prices and availability are always confirmed on the retailer's site,
         where your purchase is completed.</p></div></div>
  </div>
  {partner_band}
</div></section>"""
    return shell(brand, host, "Best Products & Deals", body, active="/")


# ------------------------------------------------- the three newer layouts
# Each is a different composition on purpose. They share shell(), so header,
# footer, palette and logo stay consistent within a site while the page itself
# reads as its own thing.


def _wa_band(label: str, line: str) -> str:
    """The bot call-to-action, repeated mid-page where a visitor has just read
    something and is deciding what to do next."""
    return f"""<section class="band"><div class="wrap">
  <div class="ctaband">
    <h2>{esc(label)}</h2>
    <p>{esc(line)}</p>
    <a class="btn btn-wa btn-lg" href="{whatsapp_url()}" target="_blank"
       rel="noopener"><span class="wa-ico">{WA_GLYPH}</span>{WA_LABEL}</a>
  </div>
</div></section>"""


def _home_finds(brand: dict, host: str, cards_data: list) -> str:
    """Centred and editorial: one statement, then straight into the guides."""
    cards = "".join(_card(a) for a in cards_data) or _empty_state(brand)
    body = f"""
<section class="hero"><div class="wrap" style="text-align:center;max-width:820px">
  <h1 style="font-size:46px">Things worth finding, checked before we share them</h1>
  <p class="lead" style="margin:20px auto 26px">Every guide starts from the
    retailer own listing: what the product is, what it does well, and what to
    look at twice before buying.</p>
  <div class="cta-row" style="justify-content:center">
    <a class="btn btn-primary btn-lg" href="/articles">Browse the guides</a>
    <a class="btn btn-wa btn-lg" href="{whatsapp_url()}" target="_blank"
       rel="noopener"><span class="wa-ico">{WA_GLYPH}</span>{WA_LABEL}</a>
  </div>
</div></section>

<section class="band soft"><div class="wrap">
  <div class="shead"><div><h2>Latest finds</h2>
    <p class="sub">Newest first, one guide per product.</p></div>
    <a class="btn btn-ghost" href="/articles">View all</a></div>
  <div class="acards">{cards}</div>
</div></section>

<section class="band"><div class="wrap">
  <div class="shead"><div><h2>How a find gets written up</h2></div></div>
  <div class="acards" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">
    <div class="fcard"><div class="fico">1</div><div><h3>Read the listing</h3>
      <p>Specifications and category details come from the retailer own page.</p></div></div>
    <div class="fcard"><div class="fico">2</div><div><h3>Write it plainly</h3>
      <p>What it does well, what to consider, and who it actually suits.</p></div></div>
    <div class="fcard"><div class="fico">3</div><div><h3>You buy at the shop</h3>
      <p>Price and availability are confirmed where the purchase happens.</p></div></div>
  </div>
  <div class="disc-box" style="max-width:none;margin-top:26px"><b>Affiliate
    Disclosure:</b> As an Amazon Associate we earn from qualifying purchases, at
    no extra cost to you.</div>
</div></section>
{_wa_band("Looking for something specific?",
          "Send the product to our WhatsApp bot and get a link straight back.")}"""
    return shell(brand, host, "Product finds and buying guides", body, active="/")


def _home_cart(brand: dict, host: str, cards_data: list) -> str:
    """Shop-shaped: the guides come first, the explanation afterwards."""
    cards = "".join(_card(a) for a in cards_data) or _empty_state(brand)
    body = f"""
<section class="band soft" style="border-top:0;padding-top:48px"><div class="wrap">
  <div style="font-weight:700;font-size:13px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--accent)">Buying guides</div>
  <h1 style="font-size:44px;margin-top:8px;max-width:18ch">Fill your cart with
    fewer regrets</h1>
  <p class="lead">Comparisons and plain-language guides, so you know what you are
    choosing between before spending anything.</p>
  <div class="cta-row">
    <a class="btn btn-primary btn-lg" href="/articles">Start browsing</a>
    <a class="btn btn-wa btn-lg" href="{whatsapp_url()}" target="_blank"
       rel="noopener"><span class="wa-ico">{WA_GLYPH}</span>{WA_LABEL}</a>
  </div>
</div></section>

<section class="band"><div class="wrap">
  <div class="shead"><div><h2>In the aisles right now</h2>
    <p class="sub">Recent write-ups across every category we cover.</p></div>
    <a class="btn btn-ghost" href="/articles">See everything</a></div>
  <div class="acards">{cards}</div>
</div></section>

{_wa_band("Cannot find it here?",
          "Message the bot with a product link and it sends one back, ready to share.")}

<section class="band soft"><div class="wrap"><div class="hgrid">
  <div>
    <h2>Why every guide reads the same way</h2>
    <p class="sub">A consistent shape means two products can be compared without
      rereading how each page is organised. No sponsored placements, and no
      rankings sold to a brand.</p>
    <div class="disc-box"><b>Affiliate Disclosure:</b> As an Amazon Associate we
      earn from qualifying purchases, at no extra cost to you.</div>
  </div>
  <div class="fcards">
    <div class="fcard"><div class="fico">📋</div><div><h3>Same sections, every guide</h3>
      <p>Details, what we like, what to consider, who it suits.</p></div></div>
    <div class="fcard"><div class="fico">🏬</div><div><h3>The shop sets the price</h3>
      <p>We never quote a price that could be stale by the time you read it.</p></div></div>
  </div>
</div></div></section>"""
    return shell(brand, host, "Buying guides and product comparisons", body, active="/")


def _home_deal(brand: dict, host: str, cards_data: list) -> str:
    """Bold and strip-led: a claim bar, then the picks."""
    cards = "".join(_card(a) for a in cards_data) or _empty_state(brand)
    body = f"""
<section class="hero" style="padding:54px 0 34px"><div class="wrap">
  <h1 style="font-size:50px;max-width:15ch">Deals worth a second look</h1>
  <p class="lead">Write-ups of products people are actually buying, with the detail
    the listing buries. Check it here, buy it at the shop.</p>
  <div class="cta-row">
    <a class="btn btn-primary btn-lg" href="/articles">Today picks</a>
    <a class="btn btn-wa btn-lg" href="{whatsapp_url()}" target="_blank"
       rel="noopener"><span class="wa-ico">{WA_GLYPH}</span>{WA_LABEL}</a>
  </div>
</div></section>

<section style="background:var(--accent);color:#fff;padding:18px 0">
  <div class="wrap" style="display:flex;gap:26px;flex-wrap:wrap;
    justify-content:center;font-weight:600;font-size:15px">
    <span>No sponsored rankings</span><span>&middot;</span>
    <span>Prices confirmed at the shop</span><span>&middot;</span>
    <span>Written from the real listing</span>
  </div>
</section>

<section class="band"><div class="wrap">
  <div class="shead"><div><h2>Picked recently</h2>
    <p class="sub">The newest write-ups, one per product.</p></div>
    <a class="btn btn-ghost" href="/articles">All picks</a></div>
  <div class="acards">{cards}</div>
  <div class="disc-box" style="max-width:none;margin-top:26px"><b>Affiliate
    Disclosure:</b> As an Amazon Associate we earn from qualifying purchases, at
    no extra cost to you. Availability and pricing are set by the retailer.</div>
</div></section>
{_wa_band("Want a link for something?",
          "Send it to the bot on WhatsApp and get one back in seconds.")}"""
    return shell(brand, host, "Deals and product picks", body, active="/")


def _pager(page: int, total_pages: int) -> str:
    if total_pages <= 1:
        return ""
    prev = (f"<a class='btn btn-ghost' href='/articles?page={page - 1}'>← Previous</a>"
            if page > 1 else "<span></span>")
    nxt = (f"<a class='btn btn-ghost' href='/articles?page={page + 1}'>Next →</a>"
           if page < total_pages else "<span></span>")
    return (
        "<div style='display:flex;justify-content:space-between;align-items:center;"
        f"gap:12px;margin-top:34px'>{prev}"
        f"<span style='color:var(--mute);font-size:14px'>Page {page} of {total_pages}"
        f"</span>{nxt}</div>"
    )


def articles(brand: dict, host: str, cards_data: list | None = None,
             page: int = 1, total_pages: int = 1) -> str:
    cards_data = cards_data or []
    cards = "".join(_card(a) for a in cards_data) or _empty_state(brand)
    body = f"""
<section class="band" style="border-top:0"><div class="wrap">
  <h1 style="font-size:40px">Articles &amp; Buying Guides</h1>
  <p class="sub" style="margin-bottom:26px">Every guide is based on the product
    listing's own specifications and category details. The most recent guides
    appear first.</p>
  <div class="acards">{cards}</div>
  {_pager(page, total_pages)}
</div></section>"""
    return shell(brand, host, "Articles & Buying Guides", body, active="/articles")


def about(brand: dict, host: str) -> str:
    partner_note = f"""<h2>For our partners</h2>
  <p>Registered partners use our dashboard to create product links, track views,
    clicks and orders, and view their earnings and payouts.
    <a href="{login_url(host)}">Log in here</a>.</p>""" if shows_login(brand) else ""
    body = f"""
<section class="band" style="border-top:0"><div class="wrap prose">
  <h1 style="font-size:40px">About {esc(brand['name'])}</h1>
  <p class="sub">{esc(brand['tagline'])}</p>

  <h2>What we do</h2>
  <p>{esc(brand['name'])} publishes product summaries and buying guides for items sold
    through major online retailers, primarily Amazon. Our goal is simple: gather the
    details that are scattered across a product listing — specifications, features,
    category context — and present them in a consistent, readable format so you can
    compare options quickly.</p>
  <p>We are a research and reference site. We do not sell products ourselves, we do
    not hold inventory, and we do not process payments. Every purchase happens on
    the retailer's own website, under their pricing, shipping and returns policies.</p>

  <h2>How our guides are made</h2>
  <ul>
    <li><b>Listing-based.</b> Each guide is built from the retailer's published
      product information, including specifications and feature descriptions.</li>
    <li><b>Consistent structure.</b> Every guide covers what the product does well,
      what to consider before buying, who it suits, and practical notes to check.</li>
    <li><b>No paid placement.</b> Brands cannot pay us to be featured or to change
      what a guide says.</li>
    <li><b>Kept current.</b> Listings change often. We refresh guides as details
      change, but the retailer's page is always the final authority.</li>
  </ul>

  <h2 id="disclosure">Affiliate disclosure</h2>
  <div class="callout"><b>As an Amazon Associate we earn from qualifying purchases.</b>
    {esc(brand['name'])} participates in the Amazon Associates Program, an affiliate
    advertising programme designed to provide a means for sites to earn advertising
    fees by advertising and linking to Amazon.</div>
  <p>When you click a product link on this site and complete a purchase, we may
    receive a small commission from the retailer. <b>This costs you nothing extra</b> —
    the price you pay is exactly the same as it would be otherwise.</p>
  <p>Earning a commission never changes what we write. Prices, availability and
    delivery terms shown on our pages may become out of date; please verify the
    current details on the retailer's page before purchasing.</p>

  {partner_note}

  <h2>Questions?</h2>
  <p>We're happy to hear from readers, partners and brands. Visit our
    <a href="/contact">contact page</a> and we'll get back to you.</p>
</div></section>"""
    return shell(brand, host, "About Us", body, active="/about")


def contact(brand: dict, host: str) -> str:
    partner_row = f"""<div class="crow"><div class="ci">🤝</div><div>
          <b>Partner support</b><br>
          <a href="{login_url(host)}">Log in to your dashboard</a>
          <div style="font-size:13.5px;color:var(--mute)">Account, links, earnings and payouts</div></div></div>""" if shows_login(brand) else ""
    body = f"""
<section class="band" style="border-top:0"><div class="wrap">
  <h1 style="font-size:40px">Contact Us</h1>
  <p class="sub" style="margin-bottom:30px">Questions about a guide, a correction,
    a partnership, or your partner account — send us a message and we'll reply,
    usually within two business days.</p>
  <div class="cgrid">
    <div class="cbox">
      <h3 style="margin-bottom:16px">Send a message</h3>
      <form action="mailto:support@beastaffiliates.com" method="post" enctype="text/plain">
        <label class="field">Your name<input name="name" placeholder="Full name" required></label>
        <label class="field">Email address<input type="email" name="email" placeholder="you@example.com" required></label>
        <label class="field">Subject<input name="subject" placeholder="How can we help?"></label>
        <label class="field">Message<textarea name="message" placeholder="Write your message…" required></textarea></label>
        <button class="btn btn-primary btn-lg" type="submit">Send message</button>
        <p style="font-size:12.5px;color:var(--mute);margin-top:12px">
          This opens your email app with the message ready to send.</p>
      </form>
    </div>
    <div>
      <div class="cbox">
        <div class="crow"><div class="ci">✉️</div><div>
          <b>Email</b><br><a href="mailto:support@beastaffiliates.com">support@beastaffiliates.com</a>
          <div style="font-size:13.5px;color:var(--mute)">General questions, corrections and partnerships</div></div></div>
        {partner_row}
        <div class="crow"><div class="ci">⏱️</div><div>
          <b>Response time</b><br>Within 2 business days
          <div style="font-size:13.5px;color:var(--mute)">Monday to Friday</div></div></div>
      </div>
      <div class="cbox" style="margin-top:18px">
        <h3 style="margin-bottom:8px">Before you write</h3>
        <p style="font-size:14.5px;color:var(--mute)">Questions about an <b>order,
          delivery or refund</b> must go to the retailer you purchased from — we are
          a research site and cannot access retailer orders. For anything about our
          content or your partner account, we're the right place.</p>
      </div>
    </div>
  </div>
</div></section>"""
    return shell(brand, host, "Contact Us", body, active="/contact")


def privacy(brand: dict, host: str) -> str:
    n = esc(brand["name"])
    body = f"""
<section class="band" style="border-top:0"><div class="wrap prose">
  <h1 style="font-size:40px">Privacy Policy</h1>
  <p class="updated">Last updated: 21 July 2026</p>
  <p>This policy explains what information {n} ("we", "us") collects when you use
    this website, why we collect it, and the choices you have. By using the site you
    agree to this policy.</p>

  <h2>1. Information we collect</h2>
  <h3>Information you give us</h3>
  <ul>
    <li><b>Contact messages.</b> If you email us or use the contact form, we receive
      your name, email address and the content of your message.</li>
    <li><b>Partner accounts.</b> If you are a registered partner, we hold your name,
      WhatsApp number, username, a securely hashed password, your store settings and
      the payout details you choose to enter.</li>
  </ul>
  <h3>Information collected automatically</h3>
  <ul>
    <li><b>Usage data.</b> Pages viewed and links clicked, so we can measure which
      guides are useful and report activity to partners.</li>
    <li><b>Technical data.</b> Basic request information such as browser type,
      device type and approximate region, as recorded by our hosting provider.</li>
  </ul>
  <p>We do <b>not</b> collect payment card details. We never see or store your
    payment information — purchases are completed entirely on the retailer's site.</p>

  <h2>2. Cookies and similar technologies</h2>
  <p>We use a small number of cookies:</p>
  <ul>
    <li><b>Essential cookies</b> keep partners signed in to the dashboard.</li>
    <li><b>Measurement cookies</b> let us count a visit or click once rather than
      repeatedly, so partner statistics are accurate.</li>
    <li><b>Retailer cookies.</b> When you follow a product link, the retailer
      (for example Amazon) may set its own cookies. These are governed by that
      retailer's privacy policy, not ours.</li>
  </ul>
  <p>You can block or delete cookies in your browser settings. Blocking essential
    cookies will prevent the partner dashboard from working.</p>

  <h2>3. How we use your information</h2>
  <ul>
    <li>To operate and improve the site and its content.</li>
    <li>To provide the partner dashboard, including link creation and statistics.</li>
    <li>To calculate and pay partner commissions and record payouts.</li>
    <li>To respond to your enquiries.</li>
    <li>To protect the site against abuse and comply with legal obligations.</li>
  </ul>
  <p>We do not sell your personal information, and we do not use your data for
    third-party advertising profiles.</p>

  <h2>4. The Amazon Associates Programme</h2>
  <p>{n} participates in the Amazon Associates Programme. When you click a product
    link, Amazon may record that the visit originated from us so that any qualifying
    purchase can be attributed. Amazon reports aggregate activity to us — such as
    clicks, ordered items and commissions — but <b>never</b> tells us who you are or
    what personal details you provided to them.</p>

  <h2>5. Sharing your information</h2>
  <p>We share information only with service providers who help us run the site, and
    only to the extent needed:</p>
  <ul>
    <li>Hosting and infrastructure providers.</li>
    <li>Database providers that store site content and partner records.</li>
  </ul>
  <p>We may also disclose information where required by law, or to protect our
    rights, safety, or the integrity of the service.</p>

  <h2>6. Data retention</h2>
  <p>Contact messages are kept only as long as needed to handle your enquiry.
    Partner account records, link data and earnings history are retained while the
    account is active and afterwards where needed for financial records.</p>

  <h2>7. Your rights</h2>
  <p>You may request access to the personal information we hold about you, ask us to
    correct it, or ask us to delete it. Partners can update most details in their
    dashboard. To make a request, contact us using the details below — we may need to
    verify your identity first.</p>

  <h2>8. Children</h2>
  <p>This site is not directed at children under 13, and we do not knowingly collect
    information from them.</p>

  <h2>9. External links</h2>
  <p>Our pages link to retailers and other third-party sites. We are not responsible
    for their content or privacy practices; please review their policies.</p>

  <h2>10. Changes to this policy</h2>
  <p>We may update this policy from time to time. Material changes will be reflected
    in the "last updated" date above.</p>

  <h2>11. Contact</h2>
  <p>Questions about this policy? Email
    <a href="mailto:support@beastaffiliates.com">support@beastaffiliates.com</a> or use
    our <a href="/contact">contact page</a>.</p>
</div></section>"""
    return shell(brand, host, "Privacy Policy", body)


def terms(brand: dict, host: str) -> str:
    n = esc(brand["name"])
    body = f"""
<section class="band" style="border-top:0"><div class="wrap prose">
  <h1 style="font-size:40px">Terms &amp; Conditions</h1>
  <p class="updated">Last updated: 21 July 2026</p>
  <p>These terms govern your use of {n}. By accessing or using this website you agree
    to them. If you do not agree, please do not use the site.</p>

  <h2>1. What this site is</h2>
  <p>{n} publishes product summaries, comparisons and buying guides. We are an
    independent research and reference site. <b>We are not a shop.</b> We do not sell
    products, hold stock, take payment, ship orders or handle returns. Every purchase
    is a contract between you and the retailer.</p>

  <h2>2. Affiliate relationship</h2>
  <div class="callout"><b>As an Amazon Associate we earn from qualifying purchases.</b></div>
  <p>Links on this site may be affiliate links. If you buy through them, we may earn a
    commission from the retailer at <b>no additional cost to you</b>. This relationship
    does not influence the substance of our guides.</p>

  <h2>3. Accuracy of information</h2>
  <p>Product details, specifications, prices and availability are drawn from retailer
    listings and can change at any time — sometimes within minutes. We make reasonable
    efforts to keep content current, but we do not warrant that any information is
    complete, accurate or up to date. <b>Always confirm the current details on the
    retailer's page before purchasing.</b></p>

  <h2>4. No professional advice</h2>
  <p>Our content is general information only. It is not professional, technical,
    medical, financial or legal advice, and should not be relied upon as such. You are
    responsible for deciding whether a product suits your needs.</p>

  <h2>5. Acceptable use</h2>
  <p>You agree not to:</p>
  <ul>
    <li>Use the site unlawfully or in a way that harms the site or other users.</li>
    <li>Attempt to gain unauthorised access to any part of the site or its systems.</li>
    <li>Scrape, copy or republish substantial parts of our content without permission.</li>
    <li>Interfere with the operation of the site, including automated abuse.</li>
  </ul>

  <h2>6. Partner accounts</h2>
  <p>Partner dashboard accounts are provided to registered partners only. You are
    responsible for keeping your credentials secure and for activity under your
    account. Commission rates, earnings and payout terms are agreed separately and are
    subject to the retailer programme's own rules; commissions may be adjusted or
    reversed if the retailer cancels, returns or invalidates an order. We may suspend
    or close accounts that breach these terms or are used fraudulently.</p>

  <h2>7. Intellectual property</h2>
  <p>The site's text, layout, branding and original content belong to {n}. Product
    names, images and trademarks belong to their respective owners; product images and
    details may be supplied by the retailer and remain the property of the rights
    holder.</p>

  <h2>8. Third-party sites</h2>
  <p>We link to third-party websites, including retailers. We do not control them and
    accept no responsibility for their content, products, terms or privacy practices.</p>

  <h2>9. Availability</h2>
  <p>We aim to keep the site available, but we do not guarantee uninterrupted access.
    The site may be unavailable for maintenance, updates or reasons outside our control,
    and we may modify or discontinue any part of it at any time.</p>

  <h2>10. Limitation of liability</h2>
  <p>To the fullest extent permitted by law, {n} is not liable for any indirect or
    consequential loss, or for any loss arising from your reliance on site content,
    from any purchase made through a retailer, or from the unavailability of the site.
    Nothing in these terms excludes liability that cannot lawfully be excluded.</p>

  <h2>11. Changes to these terms</h2>
  <p>We may update these terms from time to time. Continued use of the site after a
    change means you accept the revised terms.</p>

  <h2>12. Contact</h2>
  <p>Questions about these terms? Email
    <a href="mailto:support@beastaffiliates.com">support@beastaffiliates.com</a> or use
    our <a href="/contact">contact page</a>.</p>
</div></section>"""
    return shell(brand, host, "Terms & Conditions", body)
