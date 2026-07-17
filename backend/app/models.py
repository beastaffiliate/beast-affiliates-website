"""DB models: cached products (per marketplace+ASIN), user links, events."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Product(Base):
    """One row per (marketplace, ASIN) — the article-content cache shared by
    every link to the same product. Text only; images referenced by URL
    (R2 copy comes in a later step, url kept source-agnostic)."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("marketplace", "asin", name="uq_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(4), index=True)
    asin: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[str] = mapped_column(String(8), default="")
    price: Mapped[str] = mapped_column(String(64), default="")
    bullets_json: Mapped[str] = mapped_column(Text, default="[]")
    source: Mapped[str] = mapped_column(String(16))  # paapi | scrape | message
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    links: Mapped[list["Link"]] = relationship(back_populates="product")


class Link(Base):
    """One row per generated hub link — personal to a sender/user even when
    the article content (product row) is shared."""

    __tablename__ = "links"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)  # short slug id
    slug: Mapped[str] = mapped_column(Text)  # seo part of the url
    marketplace: Mapped[str] = mapped_column(String(4), index=True)
    asin: Mapped[str] = mapped_column(String(16))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sender: Mapped[str] = mapped_column(String(32), default="", index=True)  # E.164, phase 2
    store_name: Mapped[str] = mapped_column(String(120), default="")
    tag: Mapped[str] = mapped_column(String(120), default="")
    tagged_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    views: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    revoked: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="links")


class LinkEvent(Base):
    """Raw view/click events for the portal's per-day analytics."""

    __tablename__ = "link_events"
    __table_args__ = (Index("ix_event_link_ts", "link_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link_id: Mapped[str] = mapped_column(ForeignKey("links.id"))
    kind: Mapped[str] = mapped_column(String(8))  # view | click
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
