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

import re

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import DateTime, Integer, String, Text, select
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
    # Profile photo as a small data-URL (client resizes to ~128px before upload).
    avatar: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Public store page (/u/<slug>).
    store_slug: Mapped[str | None] = mapped_column(String(48), nullable=True, unique=True)
    store_enabled: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Payout details (consumed by the earnings phase later).
    bank: Mapped[str] = mapped_column(String(64), default="", server_default="")
    account_title: Mapped[str] = mapped_column(String(120), default="", server_default="")
    account_number: Mapped[str] = mapped_column(String(64), default="", server_default="")
    # Admin suspension: blocks login without freeing the number for re-claim.
    disabled: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Earnings share %. NULL -> the global default rate applies.
    commission_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Purchases attributed to this user's links — admin-entered (Amazon does
    # not tell us this; the admin reads it from their dashboard). Shown in the
    # user's Overview alongside views/clicks.
    orders: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class WaLinkCode(Base):
    """Short-lived single-use codes for linking extra WhatsApp numbers.
    Generated in the portal; claimed by the BOT backend when an unregistered
    number sends the code on WhatsApp."""

    __tablename__ = "wa_link_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[int] = mapped_column(Integer, default=0)


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
CODE_TTL_SECONDS = 180
BOT_WA_NUMBER = os.getenv("BOT_WA_NUMBER", "+923489712640")
MAX_WA_NUMBERS = 3  # primary + 2 linked


# Startup DDL for databases created before these columns existed (create_all
# never alters existing tables). Postgres understands IF NOT EXISTS; the
# SQLite fallback retries without it and swallows duplicate-column errors.
PORTAL_MIGRATIONS = [
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS avatar TEXT DEFAULT ''",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS store_slug VARCHAR(48)",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS store_enabled INTEGER DEFAULT 0",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS bank VARCHAR(64) DEFAULT ''",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS account_title VARCHAR(120) DEFAULT ''",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS account_number VARCHAR(64) DEFAULT ''",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS disabled INTEGER DEFAULT 0",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS commission_rate INTEGER",
    "ALTER TABLE portal_accounts ADD COLUMN IF NOT EXISTS orders INTEGER DEFAULT 0",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_portal_store_slug ON portal_accounts (store_slug)",
]


def run_portal_migrations(engine) -> None:
    from sqlalchemy import text as sql_text

    for ddl in PORTAL_MIGRATIONS:
        try:
            with engine.begin() as conn:
                conn.execute(sql_text(ddl))
        except Exception:
            try:
                with engine.begin() as conn:
                    conn.execute(sql_text(ddl.replace(" IF NOT EXISTS", "")))
            except Exception:
                pass  # column/index already exists (SQLite path)


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
    if account.disabled:
        raise HTTPException(status_code=401, detail="Account disabled")
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
    """Best-effort normalize a user-typed WhatsApp number to the E.164 form
    the bot database stores (e.g. '+923111592151'). Handles:
      - already E.164, any country: '+923141789562', '+447352089145'
      - Pakistani local format with trunk 0: '03111592151' -> '+92...'
        (this platform's userbase; other countries must include their code)
      - international dialing prefix: '00923111592151' -> '+92...'
      - bare digits already including a country code: '923111592151' -> '+92...'
    """
    number = re.sub(r"[^\d+]", "", raw.strip())
    if not number:
        return ""
    if number.startswith("00"):
        return "+" + number[2:]
    if number.startswith("+"):
        return number
    if number.startswith("0"):
        return "+92" + number[1:]
    return "+" + number


async def _body(request: Request) -> dict:
    try:
        return json.loads(await request.body() or b"{}")
    except ValueError:
        return {}


def _user_links(session: Session, number: str) -> list[Link]:
    return (
        session.execute(
            select(Link)
            .where(Link.sender == number, Link.revoked == 0)
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
    if account.disabled:
        raise HTTPException(403, "This account has been disabled — contact the admin")
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
        "avatar": account.avatar,
        "store_slug": account.store_slug or "",
        "store_enabled": bool(account.store_enabled),
        "bank": account.bank,
        "account_title": account.account_title,
        "account_number": account.account_number,
    }


@router.put("/avatar")
async def set_avatar(
    request: Request,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    avatar = str((await _body(request)).get("avatar", ""))
    if avatar and not avatar.startswith("data:image/"):
        raise HTTPException(422, "Invalid image")
    if len(avatar) > 300_000:
        raise HTTPException(422, "Image too large — try a smaller photo")
    account.avatar = avatar
    session.add(account)
    session.commit()
    return {"ok": True}


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$")


@router.get("/store/check")
def store_check(
    slug: str,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    slug = slug.strip().lower()
    if not SLUG_RE.match(slug):
        return {"available": False, "reason": "3–40 chars, lowercase letters, numbers, hyphens"}
    taken = session.execute(
        select(PortalAccount).where(
            PortalAccount.store_slug == slug, PortalAccount.id != account.id
        )
    ).scalar_one_or_none()
    return {"available": taken is None}


@router.put("/store")
async def update_store(
    request: Request,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    body = await _body(request)
    if "slug" in body:
        slug = str(body["slug"]).strip().lower()
        if not SLUG_RE.match(slug):
            raise HTTPException(422, "Slug: 3–40 chars, lowercase letters, numbers, hyphens")
        taken = session.execute(
            select(PortalAccount).where(
                PortalAccount.store_slug == slug, PortalAccount.id != account.id
            )
        ).scalar_one_or_none()
        if taken is not None:
            raise HTTPException(409, "That slug is taken")
        account.store_slug = slug
    if "enabled" in body:
        if not account.store_slug:
            raise HTTPException(422, "Save a slug first")
        account.store_enabled = 1 if body["enabled"] else 0
    session.add(account)
    session.commit()
    return {"store_slug": account.store_slug or "",
            "store_enabled": bool(account.store_enabled)}


@router.post("/wa/code")
def generate_wa_code(
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    """New linking code (invalidates the account's previous unused codes)."""
    for old in session.execute(
        select(WaLinkCode).where(
            WaLinkCode.account_id == account.id, WaLinkCode.used == 0
        )
    ).scalars():
        old.used = 1
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    session.add(
        WaLinkCode(
            account_id=account.id,
            code=code,
            expires_at=datetime.utcnow() + timedelta(seconds=CODE_TTL_SECONDS),
        )
    )
    session.commit()
    return {"code": code, "expires_in": CODE_TTL_SECONDS}


@router.get("/wa/status")
def wa_status(
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    linked: list[str] = []
    try:
        if BOT_API_URL:
            r = httpx.get(
                f"{BOT_API_URL}/service/users/{account.whatsapp_number}/linked",
                headers={"X-Service-Key": BOT_SERVICE_KEY},
                timeout=10,
            )
            if r.status_code == 200:
                linked = r.json().get("linked", [])
    except httpx.HTTPError:
        pass  # show primary only; portal stays usable
    return {
        "primary": account.whatsapp_number,
        "linked": linked,
        "max": MAX_WA_NUMBERS,
        "bot_number": BOT_WA_NUMBER,
    }


@router.delete("/wa/linked/{number}")
def wa_unlink(
    number: str,
    account: PortalAccount = Depends(current_account),
):
    try:
        r = httpx.delete(
            f"{BOT_API_URL}/service/users/{account.whatsapp_number}/linked/{number}",
            headers={"X-Service-Key": BOT_SERVICE_KEY},
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Could not unlink — try again later")
    if r.status_code == 404:
        raise HTTPException(404, "That number is not linked")
    if r.status_code not in (200, 204):
        raise HTTPException(503, "Could not unlink — try again later")
    return {"ok": True}


@router.put("/payout")
async def update_payout(
    request: Request,
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    body = await _body(request)
    bank = str(body.get("bank", "")).strip()[:64]
    title = str(body.get("account_title", "")).strip()[:120]
    number = str(body.get("account_number", "")).strip()[:64]
    if not (bank and title and number):
        raise HTTPException(422, "Bank, account title and account number are all required")
    account.bank, account.account_title, account.account_number = bank, title, number
    session.add(account)
    session.commit()
    return {"bank": bank, "account_title": title, "account_number": number}


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
            "orders": account.orders,
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


# ======================================================================
# Admin service endpoints — called ONLY by the bot backend (the admin
# dashboard's gateway), guarded by the same shared SERVICE_KEY as the
# mint API. Never exposed to browsers directly.
# ======================================================================

admin_router = APIRouter(prefix="/api/admin", tags=["portal-admin"])


def require_service_key(x_service_key: str = Header(default="")) -> None:
    if SERVICE_KEY and x_service_key != SERVICE_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")


@admin_router.get("/accounts", dependencies=[Depends(require_service_key)])
def admin_list_accounts(session: Session = Depends(get_session)):
    accounts = session.execute(
        select(PortalAccount).order_by(PortalAccount.created_at.desc())
    ).scalars().all()
    out = []
    for a in accounts:
        links = _user_links(session, a.whatsapp_number)
        out.append({
            "id": a.id,
            "username": a.username,
            "whatsapp_number": a.whatsapp_number,
            "created_at": a.created_at.isoformat(),
            "disabled": bool(a.disabled),
            "avatar": a.avatar,
            "store_slug": a.store_slug or "",
            "store_enabled": bool(a.store_enabled),
            "bank": a.bank,
            "account_title": a.account_title,
            "account_number": a.account_number,
            "links": len(links),
            "views": sum(l.views for l in links),
            "clicks": sum(l.clicks for l in links),
            "orders": a.orders,
        })
    return {"accounts": out}


@admin_router.post(
    "/accounts/{account_id}/orders", dependencies=[Depends(require_service_key)]
)
async def admin_set_orders(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    body = await _body(request)
    orders = int(body.get("orders", 0))
    if orders < 0:
        raise HTTPException(422, "Orders cannot be negative")
    account.orders = orders
    session.commit()
    return {"orders": account.orders}


@admin_router.post(
    "/accounts/{account_id}/reset-password",
    dependencies=[Depends(require_service_key)],
)
def admin_reset_password(account_id: int, session: Session = Depends(get_session)):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    temp = "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))
    account.password_hash = hash_password(temp)
    session.commit()
    return {"temp_password": temp, "username": account.username}


@admin_router.post(
    "/accounts/{account_id}/disabled",
    dependencies=[Depends(require_service_key)],
)
async def admin_set_disabled(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    body = await _body(request)
    account.disabled = 1 if body.get("disabled") else 0
    session.commit()
    return {"disabled": bool(account.disabled)}


@admin_router.delete(
    "/accounts/{account_id}", dependencies=[Depends(require_service_key)]
)
def admin_delete_account(account_id: int, session: Session = Depends(get_session)):
    """Deletes the portal account (number becomes claimable again).
    The user's links/articles are intentionally kept."""
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    session.delete(account)
    session.commit()
    return {"ok": True}


@admin_router.get(
    "/accounts/{account_id}/links", dependencies=[Depends(require_service_key)]
)
def admin_account_links(account_id: int, session: Session = Depends(get_session)):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    links = _user_links(session, account.whatsapp_number)
    return {
        "links": [
            {
                "id": l.id, "marketplace": l.marketplace,
                "title": l.product.title, "views": l.views, "clicks": l.clicks,
                "created_at": l.created_at.isoformat(),
                "article_url": _article_url(l),
            }
            for l in links
        ]
    }


@admin_router.get("/performance", dependencies=[Depends(require_service_key)])
def admin_performance(days: int = 30, session: Session = Depends(get_session)):
    """Cross-user analytics for the admin Performance tab.
    days<=0 means all time (the daily series then covers the last 90 days)."""
    cutoff = None if days <= 0 else datetime.utcnow() - timedelta(days=days)
    series_days = days if 0 < days <= 90 else 90

    accounts = session.execute(select(PortalAccount)).scalars().all()
    account_by_number = {a.whatsapp_number: a for a in accounts}

    links = session.execute(
        select(Link).where(Link.sender.in_(list(account_by_number)), Link.revoked == 0)
    ).scalars().all() if account_by_number else []
    link_owner = {l.id: l.sender for l in links}

    ev_query = select(LinkEvent).where(LinkEvent.link_id.in_(list(link_owner)))
    if cutoff is not None:
        ev_query = ev_query.where(LinkEvent.ts >= cutoff)
    events = session.execute(ev_query).scalars().all() if link_owner else []

    per_user = {
        n: {"username": a.username, "whatsapp_number": n,
            "views": 0, "clicks": 0, "links": 0}
        for n, a in account_by_number.items()
    }
    for l in links:
        if cutoff is None or l.created_at >= cutoff:
            per_user[l.sender]["links"] += 1
    day_list = [
        (datetime.utcnow() - timedelta(days=i)).date()
        for i in range(series_days - 1, -1, -1)
    ]
    series = {d.isoformat(): {"views": 0, "clicks": 0} for d in day_list}
    for e in events:
        owner = link_owner.get(e.link_id)
        if owner:
            per_user[owner]["views" if e.kind == "view" else "clicks"] += 1
        key = e.ts.date().isoformat()
        if key in series:
            series[key]["views" if e.kind == "view" else "clicks"] += 1

    return {
        "per_user": sorted(per_user.values(), key=lambda u: -u["clicks"]),
        "series": [{"date": d, **v} for d, v in series.items()],
    }



# ======================================================================
# Earnings (admin-managed, PKR only). The admin reads per-tracking-ID
# totals from their own Amazon dashboard and records entries here; users
# see ONLY their computed share — never the gross amount or their rate.
# ======================================================================

class PortalSetting(Base):
    __tablename__ = "portal_settings"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


SETTING_DEFAULTS = {"default_rate": "20", "min_payout": "1000"}


def get_setting(session: Session, key: str) -> str:
    row = session.get(PortalSetting, key)
    return row.value if row else SETTING_DEFAULTS[key]


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(PortalSetting, key)
    if row is None:
        session.add(PortalSetting(key=key, value=value))
    else:
        row.value = value


class EarningsEntry(Base):
    """One admin-entered earning line. kind:
    'earning'    — gross PKR x frozen rate -> net share
    'bonus'      — net entered directly (e.g. referral bonus)
    'adjustment' — net entered directly, may be negative (returns etc.)"""

    __tablename__ = "earnings_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(12))
    gross_amount: Mapped[int] = mapped_column(Integer, default=0)
    rate_applied: Mapped[int] = mapped_column(Integer, default=0)
    net_amount: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PayoutRecord(Base):
    __tablename__ = "payout_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(220), default="")  # snapshot
    note: Mapped[str] = mapped_column(String(200), default="")
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Referral(Base):
    """A reward the admin grants a referrer for bringing in another person.
    The referred party is either a portal account or a free-text name.
    The amount is added to the REFERRER's earnings/balance."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_account_id: Mapped[int] = mapped_column(Integer, index=True)
    referred_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referred_name: Mapped[str] = mapped_column(String(120), default="")
    amount: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _effective_rate(session: Session, account: PortalAccount) -> int:
    if account.commission_rate is not None:
        return account.commission_rate
    return int(get_setting(session, "default_rate"))


def _referral_total(session: Session, account_id: int) -> int:
    rows = session.execute(
        select(Referral).where(Referral.referrer_account_id == account_id)
    ).scalars().all()
    return sum(r.amount for r in rows)


def _earnings_summary(session: Session, account: PortalAccount) -> dict:
    entries = session.execute(
        select(EarningsEntry).where(EarningsEntry.account_id == account.id)
    ).scalars().all()
    payouts = session.execute(
        select(PayoutRecord).where(PayoutRecord.account_id == account.id)
    ).scalars().all()
    referrals = _referral_total(session, account.id)
    earned = sum(e.net_amount for e in entries) + referrals
    paid = sum(p.amount for p in payouts)
    return {"earned": earned, "paid": paid, "balance": earned - paid,
            "entries_count": len(entries), "referral_total": referrals}


# ----------------------------------------------------- admin (service key)


@admin_router.get("/earnings", dependencies=[Depends(require_service_key)])
def admin_earnings_overview(session: Session = Depends(get_session)):
    accounts = session.execute(
        select(PortalAccount).order_by(PortalAccount.username)
    ).scalars().all()
    rows = []
    for a in accounts:
        summary = _earnings_summary(session, a)
        rows.append({
            "account_id": a.id,
            "username": a.username,
            "whatsapp_number": a.whatsapp_number,
            "rate": _effective_rate(session, a),
            "custom_rate": a.commission_rate,
            **summary,
        })
    return {
        "settings": {
            "default_rate": int(get_setting(session, "default_rate")),
            "min_payout": int(get_setting(session, "min_payout")),
        },
        "users": rows,
    }


@admin_router.put("/earnings/settings", dependencies=[Depends(require_service_key)])
async def admin_earnings_settings(
    request: Request, session: Session = Depends(get_session)
):
    body = await _body(request)
    if "default_rate" in body:
        rate = int(body["default_rate"])
        if not 0 <= rate <= 100:
            raise HTTPException(422, "Rate must be 0-100")
        set_setting(session, "default_rate", str(rate))
    if "min_payout" in body:
        mp = int(body["min_payout"])
        if mp < 0:
            raise HTTPException(422, "Minimum payout cannot be negative")
        set_setting(session, "min_payout", str(mp))
    session.commit()
    return {
        "default_rate": int(get_setting(session, "default_rate")),
        "min_payout": int(get_setting(session, "min_payout")),
    }


@admin_router.put(
    "/earnings/{account_id}/rate", dependencies=[Depends(require_service_key)]
)
async def admin_set_rate(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    body = await _body(request)
    rate = body.get("rate", None)
    if rate is None:
        account.commission_rate = None  # revert to default
    else:
        rate = int(rate)
        if not 0 <= rate <= 100:
            raise HTTPException(422, "Rate must be 0-100")
        account.commission_rate = rate
    session.commit()
    return {"rate": _effective_rate(session, account),
            "custom_rate": account.commission_rate}


@admin_router.get(
    "/earnings/{account_id}", dependencies=[Depends(require_service_key)]
)
def admin_earnings_detail(account_id: int, session: Session = Depends(get_session)):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    entries = session.execute(
        select(EarningsEntry)
        .where(EarningsEntry.account_id == account.id)
        .order_by(EarningsEntry.created_at.desc())
    ).scalars().all()
    payouts = session.execute(
        select(PayoutRecord)
        .where(PayoutRecord.account_id == account.id)
        .order_by(PayoutRecord.paid_at.desc())
    ).scalars().all()
    return {
        "username": account.username,
        "rate": _effective_rate(session, account),
        "custom_rate": account.commission_rate,
        "payout_method": " | ".join(
            x for x in (account.bank, account.account_title, account.account_number) if x
        ),
        **_earnings_summary(session, account),
        "entries": [
            {"id": e.id, "kind": e.kind, "gross_amount": e.gross_amount,
             "rate_applied": e.rate_applied, "net_amount": e.net_amount,
             "label": e.label, "note": e.note,
             "created_at": e.created_at.isoformat()}
            for e in entries
        ],
        "payouts": [
            {"id": p.id, "amount": p.amount, "method": p.method,
             "note": p.note, "paid_at": p.paid_at.isoformat()}
            for p in payouts
        ],
        "referrals": _referrals_for(session, account.id),
    }


def _referral_name(session: Session, ref: "Referral") -> str:
    if ref.referred_account_id is not None:
        acc = session.get(PortalAccount, ref.referred_account_id)
        if acc is not None:
            return f"@{acc.username}"
    return ref.referred_name or "(unknown)"


def _referrals_for(session: Session, account_id: int) -> list[dict]:
    rows = session.execute(
        select(Referral)
        .where(Referral.referrer_account_id == account_id)
        .order_by(Referral.created_at.desc())
    ).scalars().all()
    return [
        {"id": r.id, "referred_name": _referral_name(session, r),
         "amount": r.amount, "note": r.note,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]


@admin_router.post(
    "/earnings/{account_id}/referrals", dependencies=[Depends(require_service_key)]
)
async def admin_add_referral(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    referrer = session.get(PortalAccount, account_id)
    if referrer is None:
        raise HTTPException(404, "Referrer account not found")
    body = await _body(request)
    amount = int(body.get("amount", 0))
    if amount <= 0:
        raise HTTPException(422, "Referral amount (PKR) must be positive")
    referred_account_id = body.get("referred_account_id")
    referred_name = str(body.get("referred_name", "")).strip()[:120]
    if referred_account_id is not None:
        referred_account_id = int(referred_account_id)
        if session.get(PortalAccount, referred_account_id) is None:
            raise HTTPException(404, "Referred account not found")
    elif not referred_name:
        raise HTTPException(422, "Pick a referred user or enter a name")
    ref = Referral(
        referrer_account_id=account_id,
        referred_account_id=referred_account_id,
        referred_name=referred_name,
        amount=amount,
        note=str(body.get("note", "")).strip()[:200],
    )
    session.add(ref)
    session.commit()
    return {"id": ref.id, "amount": amount}


@admin_router.delete(
    "/earnings/{account_id}/referrals/{referral_id}",
    dependencies=[Depends(require_service_key)],
)
def admin_delete_referral(
    account_id: int, referral_id: int, session: Session = Depends(get_session)
):
    ref = session.get(Referral, referral_id)
    if ref is None or ref.referrer_account_id != account_id:
        raise HTTPException(404, "Referral not found")
    session.delete(ref)
    session.commit()
    return {"ok": True}


@admin_router.post(
    "/earnings/{account_id}/entries", dependencies=[Depends(require_service_key)]
)
async def admin_add_entry(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    body = await _body(request)
    kind = str(body.get("kind", "earning"))
    label = str(body.get("label", "")).strip()[:80]
    note = str(body.get("note", "")).strip()[:200]
    if kind not in ("earning", "bonus", "adjustment"):
        raise HTTPException(422, "Invalid kind")
    if not label:
        raise HTTPException(422, "Label is required (e.g. 'July 2026')")
    if kind == "earning":
        gross = int(body.get("gross_amount", 0))
        if gross <= 0:
            raise HTTPException(422, "Gross amount (PKR) must be positive")
        rate = _effective_rate(session, account)
        net = round(gross * rate / 100)
    else:
        gross, rate = 0, 0
        net = int(body.get("net_amount", 0))
        if net == 0:
            raise HTTPException(422, "Amount cannot be zero")
        if kind == "bonus" and net < 0:
            raise HTTPException(422, "Bonus must be positive")
    entry = EarningsEntry(
        account_id=account.id, kind=kind, gross_amount=gross,
        rate_applied=rate, net_amount=net, label=label, note=note,
    )
    session.add(entry)
    session.commit()
    return {"id": entry.id, "net_amount": net, "rate_applied": rate}


@admin_router.put(
    "/earnings/{account_id}/entries/{entry_id}",
    dependencies=[Depends(require_service_key)],
)
async def admin_update_entry(
    account_id: int,
    entry_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Edit an existing entry in place — kind, label, gross, rate, share and
    date. Share is normally gross x rate, but it is stored as sent so the
    admin can record what Amazon actually paid when the two disagree."""
    entry = session.get(EarningsEntry, entry_id)
    if entry is None or entry.account_id != account_id:
        raise HTTPException(404, "Entry not found")
    body = await _body(request)

    kind = str(body.get("kind", entry.kind))
    if kind not in ("earning", "bonus", "adjustment"):
        raise HTTPException(422, "Invalid kind")

    if "label" in body:
        label = str(body["label"]).strip()[:80]
        if not label:
            raise HTTPException(422, "Label is required (e.g. 'July 2026')")
        entry.label = label
    if "note" in body:
        entry.note = str(body["note"]).strip()[:200]
    if "created_at" in body and str(body["created_at"]).strip():
        raw = str(body["created_at"]).strip()
        try:
            entry.created_at = datetime.fromisoformat(
                raw if len(raw) > 10 else raw + "T00:00:00"
            )
        except ValueError:
            raise HTTPException(422, "Date must be YYYY-MM-DD")

    if kind == "earning":
        gross = int(body["gross_amount"]) if "gross_amount" in body else entry.gross_amount
        rate = int(body["rate_applied"]) if "rate_applied" in body else entry.rate_applied
        if gross <= 0:
            raise HTTPException(422, "Gross amount (PKR) must be positive")
        if not 0 <= rate <= 100:
            raise HTTPException(422, "Rate must be between 0 and 100")
        net = int(body["net_amount"]) if "net_amount" in body else round(gross * rate / 100)
        if net < 0:
            raise HTTPException(422, "Share cannot be negative")
        entry.gross_amount, entry.rate_applied, entry.net_amount = gross, rate, net
    else:
        # Bonus/adjustment carry a direct amount; gross and rate don't apply.
        net = int(body["net_amount"]) if "net_amount" in body else entry.net_amount
        if net == 0:
            raise HTTPException(422, "Amount cannot be zero")
        if kind == "bonus" and net < 0:
            raise HTTPException(422, "Bonus must be positive")
        entry.gross_amount, entry.rate_applied, entry.net_amount = 0, 0, net

    entry.kind = kind
    session.commit()
    return {"id": entry.id, "kind": entry.kind, "gross_amount": entry.gross_amount,
            "rate_applied": entry.rate_applied, "net_amount": entry.net_amount,
            "label": entry.label, "note": entry.note,
            "created_at": entry.created_at.isoformat()}


@admin_router.delete(
    "/earnings/{account_id}/entries/{entry_id}",
    dependencies=[Depends(require_service_key)],
)
def admin_delete_entry(
    account_id: int, entry_id: int, session: Session = Depends(get_session)
):
    entry = session.get(EarningsEntry, entry_id)
    if entry is None or entry.account_id != account_id:
        raise HTTPException(404, "Entry not found")
    session.delete(entry)
    session.commit()
    return {"ok": True}


@admin_router.post(
    "/earnings/{account_id}/payouts", dependencies=[Depends(require_service_key)]
)
async def admin_add_payout(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    account = session.get(PortalAccount, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    body = await _body(request)
    amount = int(body.get("amount", 0))
    if amount <= 0:
        raise HTTPException(422, "Amount (PKR) must be positive")
    method = " | ".join(
        x for x in (account.bank, account.account_title, account.account_number) if x
    )
    payout = PayoutRecord(
        account_id=account.id, amount=amount, method=method,
        note=str(body.get("note", "")).strip()[:200],
    )
    session.add(payout)
    session.commit()
    return {"id": payout.id}


@admin_router.delete(
    "/earnings/{account_id}/payouts/{payout_id}",
    dependencies=[Depends(require_service_key)],
)
def admin_delete_payout(
    account_id: int, payout_id: int, session: Session = Depends(get_session)
):
    payout = session.get(PayoutRecord, payout_id)
    if payout is None or payout.account_id != account_id:
        raise HTTPException(404, "Payout not found")
    session.delete(payout)
    session.commit()
    return {"ok": True}


# ------------------------------------------------------------ user-facing


@router.get("/earnings")
def my_earnings(
    session: Session = Depends(get_session),
    account: PortalAccount = Depends(current_account),
):
    """The user's view: net share only — no gross amounts, no rate."""
    summary = _earnings_summary(session, account)
    entries = session.execute(
        select(EarningsEntry)
        .where(EarningsEntry.account_id == account.id)
        .order_by(EarningsEntry.created_at.desc())
    ).scalars().all()
    payouts = session.execute(
        select(PayoutRecord)
        .where(PayoutRecord.account_id == account.id)
        .order_by(PayoutRecord.paid_at.desc())
    ).scalars().all()
    return {
        "earned": summary["earned"],
        "paid": summary["paid"],
        "balance": summary["balance"],
        "min_payout": int(get_setting(session, "min_payout")),
        "referrals": [
            {"referred_name": r["referred_name"], "amount": r["amount"],
             "created_at": r["created_at"]}
            for r in _referrals_for(session, account.id)
        ],
        "entries": [
            {"kind": e.kind, "amount": e.net_amount, "label": e.label,
             "created_at": e.created_at.isoformat()}
            for e in entries
        ],
        "payouts": [
            {"amount": p.amount, "paid_at": p.paid_at.isoformat(), "note": p.note}
            for p in payouts
        ],
    }


@admin_router.put(
    "/earnings/{account_id}/referrals/{referral_id}",
    dependencies=[Depends(require_service_key)],
)
async def admin_update_referral(
    account_id: int,
    referral_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Referral rewards change over time, so the admin can edit the amount,
    note, date and who was referred without deleting the record."""
    ref = session.get(Referral, referral_id)
    if ref is None or ref.referrer_account_id != account_id:
        raise HTTPException(404, "Referral not found")
    body = await _body(request)

    if "amount" in body:
        amount = int(body["amount"])
        if amount <= 0:
            raise HTTPException(422, "Referral amount (PKR) must be positive")
        ref.amount = amount
    if "note" in body:
        ref.note = str(body["note"]).strip()[:200]
    if "created_at" in body and str(body["created_at"]).strip():
        raw = str(body["created_at"]).strip()
        try:
            ref.created_at = datetime.fromisoformat(
                raw if len(raw) > 10 else raw + "T00:00:00"
            )
        except ValueError:
            raise HTTPException(422, "Date must be YYYY-MM-DD")
    if "referred_account_id" in body or "referred_name" in body:
        rid = body.get("referred_account_id")
        name = str(body.get("referred_name", "")).strip()[:120]
        if rid:
            rid = int(rid)
            if session.get(PortalAccount, rid) is None:
                raise HTTPException(404, "Referred account not found")
            if rid == account_id:
                raise HTTPException(422, "A user cannot refer themselves")
            ref.referred_account_id, ref.referred_name = rid, ""
        elif name:
            ref.referred_account_id, ref.referred_name = None, name
        else:
            raise HTTPException(422, "Pick a referred user or enter a name")

    session.commit()
    return {"id": ref.id, "amount": ref.amount, "note": ref.note,
            "referred_name": _referral_name(session, ref),
            "created_at": ref.created_at.isoformat()}


@admin_router.post("/accounts", dependencies=[Depends(require_service_key)])
async def admin_create_account(
    request: Request, session: Session = Depends(get_session)
):
    """Admin creates a portal account on a user's behalf (credentials shared
    with them separately). Self-signup still works for anyone not yet created."""
    body = await _body(request)
    number = _norm_number(str(body.get("whatsapp_number", "")))
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))

    if len(number) < 6:
        raise HTTPException(422, "A valid WhatsApp number is required")
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

    account = PortalAccount(
        whatsapp_number=number, username=username,
        password_hash=hash_password(password),
    )
    session.add(account)
    session.commit()
    return {"id": account.id, "username": account.username,
            "whatsapp_number": account.whatsapp_number}
