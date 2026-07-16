"""Fallback product scraper (used when PA-API is unavailable/unconfigured).

Regex extraction proven in the local prototype: title, hi-res image, rating,
feature bullets. Raises ScrapeError with a human-readable reason on failure.
"""

import html as htmllib
import re

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class ScrapeError(Exception):
    pass


def _strip_tags(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def scrape_product(url: str, timeout: float = 20.0) -> dict:
    try:
        r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=timeout)
    except httpx.HTTPError as e:
        raise ScrapeError(f"fetch failed: {e}")
    if r.status_code != 200:
        raise ScrapeError(f"Amazon returned HTTP {r.status_code}")
    text = r.text
    if "captcha" in text[:30000].lower():
        raise ScrapeError("Amazon served a CAPTCHA page (bot detection)")

    m = re.search(r'id="productTitle"[^>]*>\s*(.*?)\s*</span>', text, re.S)
    title = _strip_tags(m.group(1)) if m else None
    if not title:
        m = re.search(r'<meta name="title" content="([^"]+)"', text)
        title = htmllib.unescape(m.group(1)) if m else None
    if not title:
        raise ScrapeError("could not find a product title in the page")

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

    bullets: list[str] = []
    m = re.search(r'id="feature-bullets".*?</ul>', text, re.S)
    if m:
        for raw in re.findall(
            r'<span class="a-list-item"[^>]*>\s*(.*?)\s*</span>', m.group(0), re.S
        ):
            cleaned = _strip_tags(raw)
            if cleaned and "hide" not in cleaned.lower()[:8]:
                bullets.append(cleaned)

    return {"title": title, "image_url": image, "price": "", "bullets": bullets[:6]}
