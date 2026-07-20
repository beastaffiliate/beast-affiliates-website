"""Core service: per-ASIN product cache + link creation.

Data source chain per product: cache -> PA-API -> scrape. Message-content
fallback (sender's image/caption) arrives with bot integration in phase 2 —
callers can pass fallback_title/image to cover products neither source returns.
"""

import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import amazon_url, articlegen, config, paapi, scraper
from .config import MARKETPLACES, article_base
from .models import Link, Product

import json


class LinkCreationError(Exception):
    """Raised when no article can be made — bot must fall back to direct link."""


def _new_link_id(session: Session) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        candidate = "".join(random.choices(alphabet, k=5))
        if session.get(Link, candidate) is None:
            return candidate


def get_or_create_product(
    session: Session,
    marketplace: str,
    asin: str,
    fallback_title: str = "",
    fallback_image: str = "",
) -> Product:
    product = session.execute(
        select(Product).where(Product.marketplace == marketplace, Product.asin == asin)
    ).scalar_one_or_none()
    if product is not None:
        if not product.image_url:
            # Self-heal: earlier scrape got a degraded page (no image) — one
            # retry on next use upgrades the cached row for ALL its links.
            product_url = f"https://www.{MARKETPLACES[marketplace]['domain']}/dp/{asin}"
            try:
                fresh = scraper.scrape_product(product_url)
                if fresh.get("image_url"):
                    product.image_url = fresh["image_url"]
                    product.title = fresh["title"] or product.title
                    product.rating = fresh.get("rating") or product.rating
                    if fresh.get("bullets"):
                        product.bullets_json = json.dumps(fresh["bullets"])
                    session.flush()
            except scraper.ScrapeError:
                pass  # keep the imageless cached row; try again next time
        return product

    # Scrape-first (owner decision); PA-API only when USE_PAAPI=true.
    data, source, reasons = None, "", []
    if config.USE_PAAPI:
        try:
            data, source = paapi.get_item(marketplace, asin), "paapi"
        except paapi.PaapiError as e:
            reasons.append(f"paapi: {e}")
    if data is None:
        product_url = f"https://www.{MARKETPLACES[marketplace]['domain']}/dp/{asin}"
        try:
            data, source = scraper.scrape_product(product_url), "scrape"
        except scraper.ScrapeError as e:
            reasons.append(f"scrape: {e}")
    if data is None:
        if fallback_title:
            data = {"title": fallback_title, "image_url": fallback_image,
                    "price": "", "bullets": []}
            source = "message"
        else:
            raise LinkCreationError(
                f"no product data for {marketplace}/{asin} ({'; '.join(reasons)})"
            )

    product = Product(
        marketplace=marketplace,
        asin=asin,
        title=data["title"],
        image_url=data.get("image_url", ""),
        rating=data.get("rating", ""),
        price=data.get("price", ""),
        bullets_json=json.dumps(data.get("bullets", [])),
        source=source,
    )
    session.add(product)
    session.flush()
    return product


def create_link(
    session: Session,
    url: str,
    tag: str,
    store_name: str,
    sender: str = "",
    fallback_title: str = "",
    fallback_image: str = "",
) -> tuple[Link, str]:
    """Create a hub link for a direct Amazon product URL.
    Returns (link, absolute article URL). Raises LinkCreationError otherwise."""
    detected = amazon_url.detect(url)
    if detected is None:
        raise LinkCreationError("not a recognizable Amazon product URL (no ASIN)")
    marketplace, asin = detected

    # Product data is cached per (marketplace, ASIN) — scrape once, reuse for
    # everyone. The article/link ITSELF is always freshly created (owner
    # decision 2026-07-20: every send publishes a new article, no link dedup),
    # so its views/clicks start at zero and track that specific send.
    product = get_or_create_product(
        session, marketplace, asin, fallback_title, fallback_image
    )

    link = Link(
        id=_new_link_id(session),
        slug=articlegen.make_slug(product.title),
        marketplace=marketplace,
        asin=asin,
        product_id=product.id,
        sender=sender,
        store_name=store_name,
        tag=tag,
        tagged_url=amazon_url.canonical_tagged_url(url, marketplace, asin, tag),
    )
    session.add(link)
    session.commit()

    article_url = f"{article_base(marketplace)}/p/{link.id}/{link.slug}"
    return link, article_url
