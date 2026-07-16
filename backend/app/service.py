"""Core service: per-ASIN product cache + link creation.

Data source chain per product: cache -> PA-API -> scrape. Message-content
fallback (sender's image/caption) arrives with bot integration in phase 2 —
callers can pass fallback_title/image to cover products neither source returns.
"""

import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import amazon_url, articlegen, paapi, scraper
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
        return product

    data, source = None, ""
    try:
        data, source = paapi.get_item(marketplace, asin), "paapi"
    except paapi.PaapiError:
        product_url = f"https://www.{MARKETPLACES[marketplace]['domain']}/dp/{asin}"
        try:
            data, source = scraper.scrape_product(product_url), "scrape"
        except scraper.ScrapeError:
            if fallback_title:
                data = {"title": fallback_title, "image_url": fallback_image,
                        "price": "", "bullets": []}
                source = "message"
            else:
                raise LinkCreationError(
                    f"no product data for {marketplace}/{asin} (PA-API and scrape failed)"
                )

    product = Product(
        marketplace=marketplace,
        asin=asin,
        title=data["title"],
        image_url=data.get("image_url", ""),
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
