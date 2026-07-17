"""Primary product-data scraper (owner decision: scrape-first, PA-API optional).

Regex extraction proven in the local prototype: title, hi-res image, feature
bullets. Hardened for primary duty: several attempts rotating realistic
browser identities (desktop Chrome / Firefox / mobile Safari) with a short
pause between tries — Amazon's bot detection often passes one identity while
blocking another. Raises ScrapeError with the per-attempt reasons on failure.
"""

import html as htmllib
import json
import random
import re
import time

import httpx

UA_PROFILES = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) "
            "Gecko/20100101 Firefox/127.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.8",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
            "Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    },
]

# Kept for other modules that import HEADERS (diagnostics, tests).
HEADERS = UA_PROFILES[0]


class ScrapeError(Exception):
    pass


def _strip_tags(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _clean_title(title: str) -> str:
    """Remove Amazon site chrome from <meta>/<title>-sourced titles:
    'Amazon.com: Product' (prefix) and 'Product : Amazon.co.uk: Category'
    (suffix) both reduce to just the product name."""
    title = re.sub(r"^\s*Amazon\.[a-z.]{2,7}\s*:\s*", "", title, flags=re.I)
    title = re.sub(r"\s*[:|]\s*Amazon\.[a-z.]{2,7}\s*:?.*$", "", title, flags=re.I)
    return title.strip()


def _attempt(url: str, headers: dict, timeout: float) -> dict:
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
    except httpx.HTTPError as e:
        raise ScrapeError(f"fetch failed: {e}")
    if r.status_code != 200:
        raise ScrapeError(f"HTTP {r.status_code}")
    text = r.text
    if "captcha" in text[:30000].lower():
        raise ScrapeError("CAPTCHA page")

    m = re.search(r'id="productTitle"[^>]*>\s*(.*?)\s*</span>', text, re.S)
    title = _strip_tags(m.group(1)) if m else None
    if not title:
        m = re.search(r'<meta name="title" content="([^"]+)"', text)
        title = _clean_title(htmllib.unescape(m.group(1))) if m else None
    if not title:
        m = re.search(r"<title>\s*(.*?)\s*</title>", text, re.S)
        candidate = _clean_title(_strip_tags(m.group(1))) if m else ""
        # Reject generic pages (error/captcha titles) — a real product title
        # is long; site chrome like "Something went wrong" is short.
        if len(candidate) >= 20:
            title = candidate
    if not title:
        raise ScrapeError("no product title in page")

    image = ""
    for pattern in (
        r'"hiRes":"(https://[^"]+)"',
        r'id="landingImage"[^>]+data-old-hires="([^"]+)"',
        r'"large":"(https://[^"]+)"',
        r'<meta property="og:image" content="([^"]+)"',
    ):
        m = re.search(pattern, text)
        if m:
            image = m.group(1)
            break
    if not image:
        # Mobile pages carry images only as data-a-dynamic-image (HTML-escaped
        # JSON of {url: [w, h]}) — take the largest by width.
        m = re.search(r'data-a-dynamic-image="([^"]+)"', text)
        if m:
            try:
                candidates = json.loads(htmllib.unescape(m.group(1)))
                image = max(candidates, key=lambda u: candidates[u][0])
            except (ValueError, TypeError, IndexError):
                pass

    m = re.search(r"([0-9.]+) out of 5 stars", text)
    rating = m.group(1) if m else ""

    bullets: list[str] = []
    m = re.search(r'id="feature-bullets".*?</ul>', text, re.S)
    if m:
        for raw in re.findall(
            r'<span class="a-list-item"[^>]*>\s*(.*?)\s*</span>', m.group(0), re.S
        ):
            cleaned = _strip_tags(raw)
            if cleaned and "hide" not in cleaned.lower()[:8]:
                bullets.append(cleaned)

    return {"title": title, "image_url": image, "rating": rating, "price": "",
            "bullets": bullets[:6]}


def _quality(result: dict) -> tuple:
    return (bool(result["image_url"]), len(result["bullets"]), bool(result["rating"]))


def scrape_product(url: str, timeout: float = 15.0) -> dict:
    """Try browser identities desktop-first (richest pages first); keep the
    best result seen and stop early when it has both image and bullets. The
    mobile identity is a last resort — its pages often lack our fields."""
    reasons: list[str] = []
    best: dict | None = None
    for i, headers in enumerate(UA_PROFILES):
        try:
            result = _attempt(url, headers, timeout)
        except ScrapeError as e:
            reasons.append(str(e))
            result = None
        if result is not None:
            if result["image_url"] and result["bullets"]:
                return result
            if best is None or _quality(result) > _quality(best):
                best = result
        if i < len(UA_PROFILES) - 1:
            time.sleep(random.uniform(0.5, 1.5))
    if best is not None:
        return best
    raise ScrapeError(" / ".join(reasons))
