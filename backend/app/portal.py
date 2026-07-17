"""User portal: accounts, auth, and dashboard data APIs.

Signup flow (owner's chosen design): user enters their WhatsApp number ->
we ask the BOT backend (server-to-server, shared key) whether it's a
registered bot user -> if yes and unclaimed, a one-time signup creates the
portal account (username + password chosen by the user) -> afterwards
login only. Profile changes (store name, link preference) are proxied to
the bot backend, which stays the single owner of user data.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import SERVICE_KEY
from .database import Base, get_session
from .models import Link, LinkEvent

BOT_API_URL = os.getenv("BOT_API_URL", "").rstrip("/")
BOT_SERVICE_KEY = os.getenv("BOT_SERVICE_KEY", "")
PORTAL_SECRET = os.getenv("PORTAL_SECRET", "") or (SERVICE_KEY + ":portal")
TOKEN_TTL_HOURS = 12

router = APIRouter(prefix="/portal", tags=["portal"])


class PortalAccount(Base):
    __tablename__ = "portal_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    whatsapp_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ------------------------------------------------------------------ passwords

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(digest.hex(), expected)


# -------------------------------------------------------------------- tokens

def make_token(username: str) -> str:
    expires = int(time.time()) + TOKEN_TTL_HOURS * 3600
    body = f"{username}:{expires}"
    sig = hmac.new(PORTAL_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{body}:{sig}".encode()).decode()


def read_token(token: str) -> str | None:
    try:
        body = base64.urlsafe_b64decode(token.encode()).decode()
        username, expires, sig = body.rsplit(":", 2)
        check = hmac.new(
            PORTAL_SECRET.encode(), f"{username}:{expires}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, check) or int(expires) < time.time():
            return None
        return username
    except Exception:
        return None


def current_account(
    session: Session = Depends(get_session),
    authorization: str = Header(default=""),
) -> PortalAccount:
    token = authorization.removeprefix("Bearer ").strip()
    username = read_token(token) if token else None
    account = (
        session.execute(
            select(PortalAccount).where(PortalAccount.username == username)
        ).scalar_one_or_none()
        if username
        else None
    )
    if account is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return account


# ---------------------------------------------------- bot backend (S2S) calls

class BotUnavailable(Exception):
    pass


def bot_get_user(number: str) -> dict | None:
    """None = number not registered with the bot; raises BotUnavailable on
    config/connectivity problems so the UI can say 'try again later'."""
    if not BOT_API_URL:
        raise BotUnavailable("portal not configured (BOT_API_URL missing)")
    try:
        r = httpx.get(
            f"{BOT_API_URL}/service/users/{number}",
            headers={"X-Service-Key": BOT_SERVICE_KEY},
            timeout=10,
        )
    except httpx.HTTPError as e:
        raise BotUnavailable(str(e))
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise BotUnavailable(f"bot backend HTTP {r.status_code}")
    return r.json()


def bot_update_preferences(number: str, payload: dict) -> dict:
    try:
        r = httpx.put(
            f"{BOT_API_URL}/service/users/{number}/preferences",
            headers={"X-Service-Key": BOT_SERVICE_KEY},
            json=payload,
            timeout=10,
        )
    except httpx.HTTPError as e:
        raise BotUnavailable(str(e))
    if r.status_code != 200:
        raise BotUnavailable(f"bot backend HTTP {r.status_code}")
    return r.json()


# --------------------------------------------------------------------- helpers

def _norm_number(raw: str) -> str:
    number = raw.strip().replace(" ", "").replace("-", "")
    if number and not number.startswith("+"):
        number = "+" + number
    return number


async def _body(request: Request) -> dict:
    try:
        return json.loads(await request.body() or b"{}")
    except ValueError:
        return {}


def _user_links(session: Session, number: str) -> list[Link]:
    return (
        session.execute(
            select(Link)
            .where(Link.sender == number)
            .order_by(Link.created_at.desc())
        ).scalars().all()
    )


# ---------------------------------------------------------------------- auth


@router.post("/check")
async def check_number(request: Request, session: Session = Depends(get_session)):
    number = _norm_number((await _body(request)).get("whatsapp_number", ""))
    if len(number) < 6:
        raise HTTPException(422, "Enter a valid WhatsApp number")
    claimed = session.execute(
        select(PortalAccount).where(PortalAccount.whatsapp_number == number)
    ).scalar_one_or_none()
    if claimed is not None:
        return {"status": "claimed", "username_hint": claimed.username[:2] + "***"}
    try:
        bot_user = bot_get_user(number)
    except BotUnavailable:
        raise HTTPException(503, "Portal is temporarily unavailable — try again later")
    if bot_user is None:
        return {"status": "unregistered"}
    return {"status": "unclaimed", "name": bot_user.get("name", "")}


@router.post("/signup")
async def signup(request: Request, session: Session = Depends(get_session)):
    body = await _body(request)
    number = _norm_number(body.get("whatsapp_number", ""))
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    if not (3 <= len(username) <= 32) or not username.replace("_", "").isalnum():
        raise HTTPException(422, "Username: 3-32 letters, numbers or underscores")
    if len(password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")

    if session.execute(
        select(PortalAccount).where(PortalAccount.whatsapp_number == number)
    ).scalar_one_or_none():
        raise HTTPException(409, "This number already has a portal account")
    if session.execute(
        select(PortalAccount).where(PortalAccount.username == username)
    ).scalar_one_or_none():
        raise HTTPException(409, "Username is taken")

    try:
        bot_user = bot_get_user(number)
    except BotUnavailable:
        raise HTTPException(503, "Portal is temporarily unavailable — try again later")
    if bot_user is None:
        raise HTTPException(403, "This number is not registered with the bot")

    account = PortalAccount(
        whatsapp_number=number, username=username,
        password_hash=hash_password(password),
    )
    session.add(account)
    session.commit()
    return {"token": make_token(username), "username": username,
            "name": bot_user.get("name", "")}


@router.post("/login")
async def login(request: Request, session: Session = Depends(get_session)):
    body = await _body(request)
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    account = session.execute(
        select(PortalAccount).where(PortalAccount.username == username)
    ).scalar_one_or_none()
    if account is None or not verify_password(password, account.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return {"token": make_token(username), "username": username}


# ------------------------------------------------------------------- profile


@router.get("/me")
def me(account: PortalAccount = Depends(current_account)):
    try:
        bot_user = bot_get_user(account.whatsapp_number) or {}
    except BotUnavailable:
        bot_user = {}
    return {
        "username": account.username,
        "whatsapp_number": account.whatsapp_number,
        "name": bot_user.get("name", ""),
        "store_name": bot_user.get("store_name", ""),
        "link_preference": bot_user.get("link_preference", "direct"),
    }


@router.put("/profile")
async def update_profile(
    request: Request, account: PortalAccount = Depends(current_account)
):
    body = await _body(request)
    payload = {}
    if "link_preference" in body:
        if body["link_preference"] not in ("direct", "hub"):
            raise HTTPException(422, "Invalid link preference")
        payload["link_preference"] = body["link_preference"]
    if "store_name" in body:
        payload["store_name"] = str(body["store_name"])[:120]
    if not payload:
        raise HTTPException(422, "Nothing to update")
    try:
        updated = bot_update_preferences(account.whatsapp_number, payload)
    except BotUnavailable:
        raise HTTPException(503, "Could not save — try again later")
    return {"store_name": updated.get("store_name", ""),
            "link_preference": updated.get("link_preference", "direct")}


@router.put("/password")
async def change_password(
    request: Request,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    body = await _body(request)
    current, new = str(body.get("current", "")), str(body.get("new", ""))
    if not verify_password(current, account.password_hash):
        raise HTTPException(401, "Current password is wrong")
    if len(new) < 8:
        raise HTTPException(422, "New password must be at least 8 characters")
    account.password_hash = hash_password(new)
    session.add(account)
    session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- dashboard


@router.get("/overview")
def overview(
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    links = _user_links(session, account.whatsapp_number)
    link_ids = [l.id for l in links]
    total_views = sum(l.views for l in links)
    total_clicks = sum(l.clicks for l in links)

    since = datetime.utcnow() - timedelta(days=7)
    events = (
        session.execute(
            select(LinkEvent).where(LinkEvent.link_id.in_(link_ids), LinkEvent.ts >= since)
        ).scalars().all()
        if link_ids
        else []
    )
    # Per-day series for the last 7 days (aggregated in Python — tiny volumes,
    # and it sidesteps SQLite/Postgres date-function differences).
    days = [(datetime.utcnow() - timedelta(days=i)).date() for i in range(6, -1, -1)]
    series = {d.isoformat(): {"views": 0, "clicks": 0, "links": 0} for d in days}
    for e in events:
        key = e.ts.date().isoformat()
        if key in series:
            series[key]["views" if e.kind == "view" else "clicks"] += 1
    for l in links:
        key = l.created_at.date().isoformat()
        if key in series:
            series[key]["links"] += 1

    today = datetime.utcnow().date()
    today_views = sum(1 for e in events if e.kind == "view" and e.ts.date() == today)
    today_clicks = sum(1 for e in events if e.kind == "click" and e.ts.date() == today)
    week_views = sum(v["views"] for v in series.values())
    week_clicks = sum(v["clicks"] for v in series.values())

    def link_out(l: Link) -> dict:
        return {
            "id": l.id, "slug": l.slug, "marketplace": l.marketplace,
            "title": l.product.title, "image_url": l.product.image_url,
            "views": l.views, "clicks": l.clicks,
            "created_at": l.created_at.isoformat(),
            "article_url": _article_url(l),
        }

    top = sorted(links, key=lambda l: l.clicks, reverse=True)[:5]
    return {
        "totals": {
            "views": total_views, "clicks": total_clicks, "links": len(links),
            "conversion": round(100 * total_clicks / total_views, 1) if total_views else 0.0,
        },
        "today": {"views": today_views, "clicks": today_clicks,
                  "links": sum(1 for l in links if l.created_at.date() == today)},
        "week": {"views": week_views, "clicks": week_clicks},
        "series": [{"date": d, **v} for d, v in series.items()],
        "top": [link_out(l) for l in top],
        "recent": [link_out(l) for l in links[:6]],
    }


def _article_url(link: Link) -> str:
    from .config import article_base

    return f"{article_base(link.marketplace)}/p/{link.id}/{link.slug}"


@router.get("/links")
def list_links(
    q: str = "",
    country: str = "",
    days: int = 0,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    links = _user_links(session, account.whatsapp_number)
    if country:
        links = [l for l in links if l.marketplace == country.upper()]
    if q:
        needle = q.lower()
        links = [l for l in links if needle in l.product.title.lower()]
    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        links = [l for l in links if l.created_at >= cutoff]
    return [
        {
            "id": l.id, "slug": l.slug, "marketplace": l.marketplace,
            "title": l.product.title, "image_url": l.product.image_url,
            "views": l.views, "clicks": l.clicks, "revoked": bool(l.revoked),
            "created_at": l.created_at.isoformat(), "article_url": _article_url(l),
            "tagged_url": l.tagged_url,
        }
        for l in links
    ]


@router.post("/links/{link_id}/revoke")
def revoke_link(
    link_id: str,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    link = session.get(Link, link_id)
    if link is None or link.sender != account.whatsapp_number:
        raise HTTPException(404, "Link not found")
    link.revoked = 1
    session.commit()
    return {"ok": True}
