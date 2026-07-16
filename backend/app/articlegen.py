"""Template-based article copy from product data (deterministic, no LLM)."""

import re


def make_slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return "-".join(slug.split("-")[:8]) or "product"


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".")
    return (text[0].upper() + text[1:] + ".") if text else ""


def generate_copy(title: str, bullets: list[str], price: str = "") -> dict:
    short = title.split(",")[0].strip()
    if bullets:
        para1 = " ".join(_sentence(b) for b in bullets[:2])
        para2 = " ".join(_sentence(b) for b in bullets[2:4])
    else:
        para1 = (
            f"Based on the product listing, {short} targets buyers who want "
            "reliable everyday performance without overpaying."
        )
        para2 = ""
    if price:
        para2 = (para2 + f" Listed at {price} at the time of writing — check the "
                 "product page for the current price.").strip()

    pros = [b if len(b) <= 90 else b[:87] + "…" for b in bullets[:3]] or [
        "Straightforward, no-frills option for its category"
    ]
    cons = [
        "Prices and availability can change quickly on Amazon",
        "May not meet professional or heavy-duty requirements",
    ]
    ideal = [
        f"Shoppers looking for {short.lower()[:60]}",
        "Buyers who prefer ordering through Amazon with fast shipping",
        "Anyone comparing options before committing to a bigger purchase",
    ]
    tips = [
        "Check the size/specification table on Amazon before ordering",
        "Read the most recent reviews — products get revised over time",
        "Confirm the return policy for your region at checkout",
    ]
    return {"para1": para1, "para2": para2, "pros": pros, "cons": cons,
            "ideal": ideal, "tips": tips}
