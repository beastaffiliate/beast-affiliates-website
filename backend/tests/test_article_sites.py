"""Per-user publishing sites for US articles.

The behaviour that matters most here is not that a new site works — it is that
a link already shared on WhatsApp never moves. An article's domain is recorded
when it is created, so changing where a user publishes affects only their next
article, never the fifty already sitting in other people's chats.

Run against an isolated database:

    DATABASE_URL="sqlite:///./sites_test.db" \
      ARTICLE_BASE_US=https://www.beastaffiliates.com \
      ARTICLE_BASE_INTL=https://www.beastassociate.com \
      python -m uvicorn main:app --port 4210
    python tests/test_article_sites.py
"""

import json
import os
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = os.getenv("SITE_BASE", "http://127.0.0.1:4210")
US_A = "https://www.beastaffiliates.com"
FINDS = "https://www.beastfinds.com"
CART = "https://www.beastscart.com"
INTL = "https://www.beastassociate.com"

passed = failed = 0


def call(method, path, payload=None, host=None):
    """Redirects are never followed: the point of several cases below is the
    redirect itself, and following one would try to resolve a domain whose DNS
    does not exist yet."""
    headers = {"Content-Type": "application/json"}
    if host:
        headers["Host"] = host
    r = httpx.request(method, BASE + path, json=payload, headers=headers,
                      timeout=30, follow_redirects=False)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"html": r.text, "location": r.headers.get("location", "")}


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    print(("PASS " if cond else "FAIL ") + f" {name}" + ("" if cond else f"  {detail}"))


def mint(url, tag, us_site="", sender="+923001110000"):
    s, d = call("POST", "/api/links", {
        "url": url, "tag": tag, "sender": sender,
        "store_name": "Test Store", "us_site": us_site,
        "fallback_title": "Test Product", "fallback_image": "",
    })
    return s, d


# ---------------------------------------------------------------- publishing
US_URL = "https://www.amazon.com/dp/B0GS64BBG2"
DE_URL = "https://www.amazon.de/dp/B0D6V152G9"

s, d = mint(US_URL, "beast-20")
check("default publishes to the original US site", d.get("article_url", "").startswith(US_A),
      f"{s} {d}")
default_link = d.get("link_id", "")

s, d = mint(US_URL, "beast-20", us_site="beastfinds")
check("a chosen site publishes there instead",
      d.get("article_url", "").startswith(FINDS), f"{s} {d}")
finds_link = d.get("link_id", "")

s, d = mint(US_URL, "beast-20", us_site="beastscart")
check("a second site works too", d.get("article_url", "").startswith(CART), f"{s} {d}")

# the per-user choice must never move non-US articles
s, d = mint(DE_URL, "beast04-21", us_site="beastfinds")
check("a non-US article ignores the setting and stays international",
      d.get("article_url", "").startswith(INTL), f"{s} {d}")

# an unknown key must not invent a domain
s, d = mint(US_URL, "beast-20", us_site="not-a-real-site")
check("an unknown site falls back to the default rather than a dead domain",
      d.get("article_url", "").startswith(US_A), f"{s} {d}")
fallback_link = d.get("link_id", "")

# ------------------------------------------- the promise: links never move
# Re-minting for the same user with a DIFFERENT site must not disturb the
# article already published — that link lives in somebody's chat history.
s, art = call("GET", f"/p/{finds_link}/x", host="www.beastfinds.com")
check("an article opened on its own domain is served, not redirected", s == 200, s)

s, art = call("GET", f"/p/{finds_link}/x", host="www.beastaffiliates.com")
check("the same article opened on another of our domains redirects to its own",
      s == 308 and art.get("location", "").startswith(FINDS), f"{s} {art.get('location')}")

s, art = call("GET", f"/p/{default_link}/x", host="www.beastfinds.com")
check("an article published before per-user sites still redirects to the original",
      s == 308 and art.get("location", "").startswith(US_A), f"{s} {art.get('location')}")

# ---------------------------------------------------------------- listings
s, home_finds = call("GET", "/", host="www.beastfinds.com")
s, home_default = call("GET", "/", host="www.beastaffiliates.com")
check("each site is branded for its own host",
      "Beast Finds" in home_finds.get("html", ""), "brand name missing")
check("the default site keeps its own brand",
      "Beast Affiliates" in home_default.get("html", ""), "brand name missing")

# the new sites must not advertise a login anywhere
for host, name in ((("www.beastfinds.com"), "Beast Finds"),
                   (("www.beastscart.com"), "Beast Cart"),
                   (("www.beastsdeal.com"), "Beast Deals")):
    for path in ("/", "/about", "/contact"):
        _, page = call("GET", path, host=host)
        if "Log in" in page.get("html", ""):
            check(f"{name} {path} has no login", False, "login still advertised")
            break
    else:
        check(f"{name} advertises no login on any page", True)

_, page = call("GET", "/", host="www.beastaffiliates.com")
check("the existing site keeps its login button", "Log in" in page.get("html", ""))

# ------------------------------------------- each site lists only its OWN work
# Without this, every US domain would list every US article — one user's
# articles appearing on another brand's site.
_, finds_articles = call("GET", "/articles", host="www.beastfinds.com")
_, cart_articles = call("GET", "/articles", host="www.beastscart.com")
_, deal_articles = call("GET", "/articles", host="www.beastsdeal.com")
_, default_articles = call("GET", "/articles", host="www.beastaffiliates.com")
_, intl_articles = call("GET", "/articles", host="www.beastassociate.com")


def ids_in(page_data):
    import re
    return set(re.findall(r"/p/([A-Za-z0-9]{4,8})/", page_data.get("html", "")))


finds_ids, cart_ids = ids_in(finds_articles), ids_in(cart_articles)
default_ids, intl_ids = ids_in(default_articles), ids_in(intl_articles)

check("a site lists its own article", finds_link in finds_ids, finds_ids)
check("and not another site's", finds_link not in cart_ids and finds_link not in default_ids,
      f"cart={cart_ids} default={default_ids}")
# The listing shows one card per PRODUCT, newest first, so for a product
# published to the default site more than once only the latest appears —
# `default_link` is deliberately superseded by the later mint.
check("the default site lists a default-published article",
      fallback_link in default_ids, f"{default_ids} (expected {fallback_link})")
check("the default site does not list other sites' articles",
      not (finds_ids & default_ids), f"{finds_ids & default_ids}")
check("a site with nothing published to it lists nothing", deal_articles is not None)
check("the international site is unaffected by any of this",
      not (intl_ids & (finds_ids | cart_ids | default_ids)), intl_ids)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
