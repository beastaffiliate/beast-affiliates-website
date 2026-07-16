"""Amazon URL parsing + canonical tagged-link building.

Mirrors the bot backend's rewriter behavior (canonical /dp/<ASIN>?tag= form,
KEEP_PARAMS preserved) so the article's buy button lands on exactly the same
URL the bot would have replied with directly.
"""

import re
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from .config import DOMAIN_TO_CODE, MARKETPLACES

ASIN_PATH_RE = re.compile(
    r"/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})(?=[/?]|$)", re.I
)
KEEP_PARAMS = {"th", "psc", "smid", "m"}


def detect(url: str) -> tuple[str, str] | None:
    """Return (marketplace_code, ASIN) for a direct Amazon product URL,
    or None when the URL isn't an Amazon product page we can identify."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    code = next(
        (c for domain, c in DOMAIN_TO_CODE if host == domain or host.endswith("." + domain)),
        None,
    )
    if code is None:
        return None
    m = ASIN_PATH_RE.search(parts.path or "")
    if not m:
        return None
    return code, m.group(1).upper()


def canonical_tagged_url(original_url: str, marketplace: str, asin: str, tag: str) -> str:
    """Short canonical affiliate URL: https://www.<domain>/dp/<ASIN>?<kept>&tag=."""
    parts = urlsplit(original_url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() in KEEP_PARAMS
    ]
    if tag:
        kept.append(("tag", tag))
    query = urlencode(kept, quote_via=quote)
    domain = MARKETPLACES[marketplace]["domain"]
    return f"https://www.{domain}/dp/{asin}" + (f"?{query}" if query else "")
