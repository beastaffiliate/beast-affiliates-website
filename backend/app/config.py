"""Environment config + marketplace registry.

All secrets come from env vars (Vercel project settings in prod, .env locally).
Never hardcode credentials here.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # pragma: no cover
    pass

# ---------------------------------------------------------------- marketplaces
# PA-API v5 endpoints per marketplace (host + AWS signing region + site name).
MARKETPLACES: dict[str, dict] = {
    "US": {"domain": "amazon.com", "paapi_host": "webservices.amazon.com", "region": "us-east-1", "site": "www.amazon.com"},
    "UK": {"domain": "amazon.co.uk", "paapi_host": "webservices.amazon.co.uk", "region": "eu-west-1", "site": "www.amazon.co.uk"},
    "CA": {"domain": "amazon.ca", "paapi_host": "webservices.amazon.ca", "region": "us-east-1", "site": "www.amazon.ca"},
    "DE": {"domain": "amazon.de", "paapi_host": "webservices.amazon.de", "region": "eu-west-1", "site": "www.amazon.de"},
    "FR": {"domain": "amazon.fr", "paapi_host": "webservices.amazon.fr", "region": "eu-west-1", "site": "www.amazon.fr"},
    "IT": {"domain": "amazon.it", "paapi_host": "webservices.amazon.it", "region": "eu-west-1", "site": "www.amazon.it"},
    "ES": {"domain": "amazon.es", "paapi_host": "webservices.amazon.es", "region": "eu-west-1", "site": "www.amazon.es"},
    "NL": {"domain": "amazon.nl", "paapi_host": "webservices.amazon.nl", "region": "eu-west-1", "site": "www.amazon.nl"},
    "AU": {"domain": "amazon.com.au", "paapi_host": "webservices.amazon.com.au", "region": "us-west-2", "site": "www.amazon.com.au"},
}

# Longest domain first so amazon.com.au never matches amazon.com.
DOMAIN_TO_CODE: list[tuple[str, str]] = sorted(
    ((m["domain"], code) for code, m in MARKETPLACES.items()),
    key=lambda t: -len(t[0]),
)


def paapi_credentials(code: str) -> dict | None:
    """PA-API creds for a marketplace from env, or None if not configured."""
    access = os.getenv(f"PAAPI_{code}_ACCESS_KEY")
    secret = os.getenv(f"PAAPI_{code}_SECRET_KEY")
    partner_tag = os.getenv(f"PAAPI_{code}_PARTNER_TAG")
    if access and secret and partner_tag:
        return {"access_key": access, "secret_key": secret, "partner_tag": partner_tag}
    return None


# ------------------------------------------------------------------- articles
# Domain routing: US articles on the portal domain, all other marketplaces on
# the second domain. Override per environment (.env locally points both at
# localhost so links are clickable in dev).
ARTICLE_BASE_US = os.getenv("ARTICLE_BASE_US", "https://beastaffiliates.com")
ARTICLE_BASE_INTL = os.getenv("ARTICLE_BASE_INTL", "https://beastassocoate.com")


def article_base(marketplace_code: str) -> str:
    return ARTICLE_BASE_US if marketplace_code == "US" else ARTICLE_BASE_INTL


# ------------------------------------------------------------------- security
# Shared secret for server-to-server calls (bot backend -> POST /api/links).
# If unset (local dev), the API is open and a warning is logged at startup.
SERVICE_KEY = os.getenv("SERVICE_KEY", "")

DATABASE_URL = os.getenv("DATABASE_URL", "")

DEFAULT_STORE_NAME = os.getenv("DEFAULT_STORE_NAME", "Beast Affiliates")
