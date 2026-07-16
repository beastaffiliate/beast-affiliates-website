"""PA-API v5 GetItems client with stdlib AWS SigV4 signing (no SDK).

One call per (marketplace, ASIN); results are cached in the products table by
the service layer, so PA-API's 1 req/sec starter limit is never a bottleneck.
Raises PaapiError on any failure — callers fall back to scraping.
"""

import datetime
import hashlib
import hmac
import json

import httpx

from .config import MARKETPLACES, paapi_credentials

RESOURCES = [
    "ItemInfo.Title",
    "ItemInfo.Features",
    "Images.Primary.Large",
    "Offers.Listings.Price",
]

TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"
SERVICE = "ProductAdvertisingAPI"


class PaapiError(Exception):
    pass


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def get_item(marketplace: str, asin: str, timeout: float = 10.0) -> dict:
    """Fetch product data. Returns {title, image_url, price, bullets, partner_tag}."""
    creds = paapi_credentials(marketplace)
    if creds is None:
        raise PaapiError(f"no PA-API credentials configured for {marketplace}")
    mk = MARKETPLACES[marketplace]
    host, region = mk["paapi_host"], mk["region"]

    payload = json.dumps(
        {
            "ItemIds": [asin],
            "Resources": RESOURCES,
            "PartnerTag": creds["partner_tag"],
            "PartnerType": "Associates",
            "Marketplace": mk["site"],
        },
        separators=(",", ":"),
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_headers = (
        f"content-encoding:amz-1.0\nhost:{host}\nx-amz-date:{amz_date}\nx-amz-target:{TARGET}\n"
    )
    signed_headers = "content-encoding;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = (
        f"POST\n/paapi5/getitems\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    scope = f"{date_stamp}/{region}/{SERVICE}/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n{scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )
    k = _sign(("AWS4" + creds["secret_key"]).encode(), date_stamp)
    k = _sign(k, region)
    k = _sign(k, SERVICE)
    k = _sign(k, "aws4_request")
    signature = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()

    headers = {
        "Content-Encoding": "amz-1.0",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Amz-Date": amz_date,
        "X-Amz-Target": TARGET,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={creds['access_key']}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }

    try:
        r = httpx.post(
            f"https://{host}/paapi5/getitems",
            content=payload,
            headers=headers,
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise PaapiError(f"request failed: {e}")

    try:
        data = r.json()
    except ValueError:
        raise PaapiError(f"non-JSON response HTTP {r.status_code}")
    if r.status_code != 200 or "Errors" in data:
        err = (data.get("Errors") or [{}])[0]
        raise PaapiError(
            f"HTTP {r.status_code} {err.get('Code', '')}: {err.get('Message', '')[:200]}"
        )

    items = (data.get("ItemsResult") or {}).get("Items") or []
    if not items:
        raise PaapiError("empty ItemsResult")
    item = items[0]

    info = item.get("ItemInfo") or {}
    title = ((info.get("Title") or {}).get("DisplayValue") or "").strip()
    if not title:
        raise PaapiError("item has no title")
    bullets = (info.get("Features") or {}).get("DisplayValues") or []
    image = (((item.get("Images") or {}).get("Primary") or {}).get("Large") or {}).get("URL", "")
    price = ""
    listings = (item.get("Offers") or {}).get("Listings") or []
    if listings:
        price = ((listings[0].get("Price") or {}).get("DisplayAmount") or "")

    return {
        "title": title,
        "image_url": image,
        "price": price,
        "bullets": bullets[:6],
        "partner_tag": creds["partner_tag"],
    }
