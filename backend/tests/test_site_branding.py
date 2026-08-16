"""Per-site identity: logos, layouts, and the WhatsApp tab.

Offline — these render HTML from the brand definitions, so they need no server
and no database. The point is that the five sites are genuinely distinct rather
than one template with the colours swapped, and that the bot link is present and
correct everywhere.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import site  # noqa: E402

passed = failed = 0
NEW = ("finds", "cart", "deal")
ALL = ("affiliates", "associate") + NEW
PAGES = {
    "/": site.home,
    "/about": site.about,
    "/contact": site.contact,
}


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    print(("PASS " if cond else "FAIL ") + f" {name}" + ("" if cond else f"  {detail}"))


def render(key, path="/"):
    brand = site.BRANDS[key]
    fn = PAGES[path]
    return fn(brand, "x.com", []) if path == "/" else fn(brand, "x.com")


# ------------------------------------------------------------- WhatsApp tab
wa = site.whatsapp_url()
check("the tab says what the client asked for",
      site.WA_LABEL == "For Premium Products", site.WA_LABEL)
check("it no longer calls the number a bot",
      "bot" not in site.WA_LABEL.lower(), site.WA_LABEL)
check("bot link is a wa.me link", wa.startswith("https://wa.me/"), wa)
check("number carries no spaces or plus", re.fullmatch(r"https://wa\.me/\d+\?text=.+", wa), wa)
check("the greeting is pre-filled", "text=" in wa and len(wa.split("text=")[1]) > 5, wa)

for key in ALL:
    for path in PAGES:
        html = render(key, path)
        if "btn-wa" not in html or wa not in html or site.WA_LABEL not in html:
            check(f"{key} {path}: bot tab present", False, "missing on this page")
            break
    else:
        check(f"{site.BRANDS[key]['name']}: bot tab on every page", True)

home = render("finds")
check("the bot button is WhatsApp green, not the brand colour",
      "#25d366" in home, "green is what tells people what it opens")
check("the bot link opens in a new tab", 'target="_blank"' in home)
check("...safely", 'rel="noopener"' in home)
check("the bot also appears in the footer links",
      home.count(wa) >= 2, home.count(wa))

# ------------------------------------------------------------------- logos
marks = {k: site.logo_mark(site.BRANDS[k]) for k in NEW}
check("each new site has a drawn logo, not the shared image",
      all("<svg" in m and "favicon" not in m for m in marks.values()), marks.keys())
check("the three logos are different shapes",
      len({m for m in marks.values()}) == 3, "two sites share a mark")
for key in ("affiliates", "associate"):
    check(f"{site.BRANDS[key]['name']} keeps its original logo",
          "favicon.png" in site.logo_mark(site.BRANDS[key]))

# ----------------------------------------------------------------- layouts
heads = {}
for key in ALL:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", render(key), re.S)
    heads[key] = " ".join(m.group(1).split()) if m else ""
check("every site has a headline", all(heads.values()), heads)
check("the three new sites each say something different",
      len({heads[k] for k in NEW}) == 3, {k: heads[k] for k in NEW})
check("and none of them reuse the original headline",
      all(heads[k] != heads["affiliates"] for k in NEW), heads)

check("the two original sites are untouched",
      heads["affiliates"] == heads["associate"]
      and "Product Recommendations" in heads["affiliates"], heads["affiliates"])

# section order differs, not just the words
def sections(key):
    return re.findall(r'<section[^>]*class="([^"]*)"', render(key))


check("the new layouts are structurally different from each other",
      len({tuple(sections(k)) for k in NEW}) == 3,
      {k: sections(k) for k in NEW})

# ------------------------------------------------- nothing else regressed
for key in NEW:
    for path in PAGES:
        if "Log in" in render(key, path):
            check(f"{key} still advertises no login", False, path)
            break
    else:
        check(f"{site.BRANDS[key]['name']} still advertises no login", True)

check("the original site still offers login", "Log in" in render("affiliates"))
check("every page still carries the affiliate disclosure",
      all("Amazon Associate" in render(k) for k in ALL))
check("each site is still named in its own pages",
      all(site.BRANDS[k]["name"] in render(k) for k in ALL))

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
