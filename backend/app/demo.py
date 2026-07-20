"""Hardcoded demo articles for the public (not-logged-in) homepage.

Fully isolated: NO database rows. Served at /p/DEMOxx URLs and listed by
GET /api/demo. Never touch portal_accounts/links, so nothing here can ever
appear in the admin dashboard or any user analytics. Buy button uses the
'dummy-tag' affiliate tag.
"""

DEMO_ARTICLES = [
    {
        "id": "DEMO01",
        "slug": "amazon-basics-48-pack-aa-alkaline",
        "title": "Amazon Basics 48-Pack AA Alkaline High-Performance Batteries, 1.5 Volt, 10-Year Shelf Life, Long-lasting, No L",
        "image_url": "https://m.media-amazon.com/images/I/81iJ+tnLADL._AC_SL1500_.jpg",
        "rating": "4.8",
        "price": "",
        "bullets": [
            "IN THE BOX: 48-pack of 1.5 volt AA alkaline batteries for reliable performance across a wide range of devices",
            "DEVICE COMPATIBLE: Ideal battery for game controllers, toys, flashlights, digital cameras, clocks, and more",
            "DESIGNED TO LAST: 10-year leak-free shelf life; store for emergencies or use right away",
            "EASY USE & STORAGE: Ships in Certified Frustration-Free Packaging; easy to open and store extras for later use",
            "SINGLE USE: These batteries are NOT rechargeable; for rechargeable options, check out Amazon Basics rechargeable batteries"
        ],
        "asin": "B00MNV8E0C",
        "amazon_url": "https://www.amazon.com/dp/B00MNV8E0C?tag=dummy-tag",
        "marketplace": "US"
    },
    {
        "id": "DEMO02",
        "slug": "echo-dot-3rd-gen-2018-release",
        "title": "Echo Dot (3rd Gen, 2018 release) - Smart speaker with Alexa - Charcoal",
        "image_url": "https://m.media-amazon.com/images/I/61MZfowYoaL._AC_SL1000_.jpg",
        "rating": "4.7",
        "price": "",
        "bullets": [
            "MEET ECHO DOT - Our most compact smart speaker that fits perfectly into small spaces.",
            "RICH AND LOUD SOUND - Better speaker quality than Echo Dot Gen 2 for richer and louder sound. Pair with a second Echo Dot for stereo sound.",
            "ALEXA HELPS YOU DO MORE WITH PRIME - Listen to millions of songs with Amazon Music, use your voice to for 2-day shipping, listen to audiobooks on Audible, and much more.",
            "MAKE YOUR LIFE EASIER - Alexa can set timers, check the weather, read the news, adjust thermostats, answer questions, and more to help with daily tasks.",
            "DESIGNED TO PROTECT YOUR PRIVACY – Built with multiple layers of privacy controls including the ability to delete your recordings, mute your mic, and more in-app privacy controls."
        ],
        "asin": "B07FZ8S74R",
        "amazon_url": "https://www.amazon.com/dp/B07FZ8S74R?tag=dummy-tag",
        "marketplace": "US"
    },
    {
        "id": "DEMO03",
        "slug": "apple-iphone-11-64gb-black-unlocked",
        "title": "Apple iPhone 11, 64GB, Black - Unlocked (Renewed)",
        "image_url": "https://m.media-amazon.com/images/I/61MG3m5FhIL._AC_SL1500_.jpg",
        "rating": "4.5",
        "price": "",
        "bullets": [
            "This phone is unlocked and compatible with any carrier of choice on GSM and CDMA networks (e.g. AT&T, T-Mobile, Sprint, Verizon, US Cellular, Cricket, Metro, Tracfone, Mint Mobile, etc.).",
            "Tested for battery health and guaranteed to have a minimum battery capacity of 80%.",
            "Successfully passed a full diagnostic test which ensures like-new functionality and removal of any prior-user personal information."
        ],
        "asin": "B07ZPKN6YR",
        "amazon_url": "https://www.amazon.com/dp/B07ZPKN6YR?tag=dummy-tag",
        "marketplace": "US"
    },
    {
        "id": "DEMO04",
        "slug": "apple-airpods-pro-2nd-gen-wireless",
        "title": "Apple AirPods Pro (2nd Gen) Wireless Earbuds, Up to 2X More Active Noise Cancelling, Adaptive Transparency, Pe",
        "image_url": "https://m.media-amazon.com/images/I/61f1YfTkTDL._AC_SL1500_.jpg",
        "rating": "4.7",
        "price": "",
        "bullets": [
            "RICHER AUDIO EXPERIENCE – The Apple-designed H2 chip pushes advanced audio performance even further, resulting in smarter noise cancellation and more immersive sound. The low-distortion, custom-built driver delivers crisp, clear high notes and deep, rich bass in stunning definition. So every sound is more vivid than ever..Note : If the size of the earbud tips does not match the size of your ear canals or the headset is not worn properly in your ears, you may not obtain the correct sound qualities or call performance. Change the earbud tips to ones that fit more snugly in your ear",
            "NEXT-LEVEL ACTIVE NOISE CANCELLATION – Up to 2x more Active Noise Cancellation than the previous AirPods Pro for dramatically less noise on your commute, or when you want to focus. Adaptive Transparency lets you comfortably hear the world around you, adjusting for intense noise—like sirens or construction—in real time.",
            "CUSTOMIZABLE FIT – Now with four pairs of silicone tips (XS, S, M, L) to fit a wider range of ears and provide all-day comfort. The tips create an acoustic seal to help keep out noise and secure AirPods Pro in place.",
            "SOUND ALL AROUND – Personalized Spatial Audio surrounds you in sound tuned just for you. It works with dynamic head tracking to immerse you deeper in music and movies.",
            "HIGHER LEVEL OF CONTROL – Now you can swipe the stem to adjust volume. Press it to play and pause music or to answer and end a call, or hold it to switch between Active Noise Cancellation and Adaptive Transparency."
        ],
        "asin": "B0BDHWDR12",
        "amazon_url": "https://www.amazon.com/dp/B0BDHWDR12?tag=dummy-tag",
        "marketplace": "US"
    },
    {
        "id": "DEMO05",
        "slug": "nintendo-switch-with-neon-blue-and",
        "title": "Nintendo Switch with Neon Blue and Neon Red Joy‑Con",
        "image_url": "https://m.media-amazon.com/images/I/51YXZgm0DbL._AC_SL1000_.jpg",
        "rating": "4.8",
        "price": "",
        "bullets": [
            "3 Play Styles: TV Mode, Tabletop Mode, Handheld Mode",
            "6.2-inch, multi-touch capacitive touch screen",
            "4.5-9+ Hours of Battery Life Will vary depending on software usage conditions",
            "Connects over Wi-Fi for multiplayer gaming; Up to 8 consoles can be connected for local wireless multiplayer",
            "Model number: HAC-001(-01)"
        ],
        "asin": "B07VGRJDFY",
        "amazon_url": "https://www.amazon.com/dp/B07VGRJDFY?tag=dummy-tag",
        "marketplace": "US"
    },
    {
        "id": "DEMO06",
        "slug": "2019-apple-macbook-pro-16-inch",
        "title": "2019 Apple MacBook Pro (16-inch, 16GB RAM, 1TB Storage, 2.3GHz Intel Core i9) - Space Gray",
        "image_url": "https://m.media-amazon.com/images/I/71pC69I3lzL._AC_SL1500_.jpg",
        "rating": "4.6",
        "price": "",
        "bullets": [
            "Ninth-generation 8-Core Intel Core i9 Processor",
            "Stunning 16-inch Retina Display with True Tone technology",
            "Touch Bar and Touch ID",
            "AMD Radeon Pro 5500M Graphics with GDDR6 memory",
            "Ultrafast SSD"
        ],
        "asin": "B081FZV45H",
        "amazon_url": "https://www.amazon.com/dp/B081FZV45H?tag=dummy-tag",
        "marketplace": "US"
    }
]

DEMO_BY_ID = {a["id"]: a for a in DEMO_ARTICLES}


DEMO_OVERVIEW = {
    "totals": {"views": 1284, "clicks": 372, "orders": 41, "links": 58,
               "conversion": 29.0},
    "today": {"views": 47, "clicks": 12, "links": 3},
    "week": {"views": 318, "clicks": 96},
    "series": [
        {"date": d, "views": v, "clicks": c}
        for d, v, c in [
            ("07-14", 22, 6), ("07-15", 35, 9), ("07-16", 41, 13),
            ("07-17", 58, 18), ("07-18", 47, 15), ("07-19", 63, 21),
            ("07-20", 52, 14),
        ]
    ],
}


# ---- Full portal dataset for demo mode (every tab, dummy data) ----
_VC = [(312, 88), (240, 64), (198, 51), (156, 39), (97, 22), (63, 15)]
_DATES = ["2026-07-20", "2026-07-19", "2026-07-18", "2026-07-16",
          "2026-07-14", "2026-07-12"]

DEMO_LINKS = [
    {
        "id": a["id"], "slug": a["slug"], "marketplace": a["marketplace"],
        "title": a["title"], "image_url": a["image_url"],
        "views": v, "clicks": c, "revoked": False,
        "created_at": f"{d}T10:00:00",
        "article_url": f"/p/{a['id']}/{a['slug']}",
        "tagged_url": a["amazon_url"],
    }
    for a, (v, c), d in zip(DEMO_ARTICLES, _VC, _DATES)
]

_TOTAL_V = sum(v for v, _ in _VC)
_TOTAL_C = sum(c for _, c in _VC)

DEMO_ME = {
    "username": "sami",
    "whatsapp_number": "+92 300 1234567",
    "name": "Sami",
    "store_name": "Sami Deals",
    "link_preference": "hub",
    "avatar": "",
    "store_slug": "sami-deals",
    "store_enabled": True,
    "bank": "Easypaisa",
    "account_title": "Sami",
    "account_number": "0300 1234567",
}

DEMO_EARNINGS = {
    "earned": 24800,
    "paid": 15000,
    "balance": 9800,
    "min_payout": 5000,
    "referrals": [
        {"referred_name": "@ahmed", "amount": 1000, "created_at": "2026-07-15T10:00:00"},
        {"referred_name": "Bilal", "amount": 500, "created_at": "2026-07-09T10:00:00"},
    ],
    "entries": [
        {"kind": "earning", "amount": 18500, "label": "July 2026", "created_at": "2026-07-18T10:00:00"},
        {"kind": "bonus", "amount": 800, "label": "Welcome bonus", "created_at": "2026-07-10T10:00:00"},
        {"kind": "adjustment", "amount": -500, "label": "Return clawback", "created_at": "2026-07-08T10:00:00"},
        {"kind": "earning", "amount": 4500, "label": "June 2026", "created_at": "2026-06-30T10:00:00"},
    ],
    "payouts": [
        {"amount": 15000, "paid_at": "2026-07-05T10:00:00", "note": "June payout"},
    ],
}

DEMO_WA = {
    "primary": "+92 300 1234567",
    "linked": ["+92 321 9876543"],
    "max": 3,
    "bot_number": "+923489712640",
}

DEMO_PORTAL = {
    "me": DEMO_ME,
    "overview": {
        "totals": {"views": _TOTAL_V, "clicks": _TOTAL_C, "orders": 41,
                   "links": len(DEMO_LINKS),
                   "conversion": round(100 * _TOTAL_C / _TOTAL_V, 1)},
        "today": {"views": 47, "clicks": 12, "links": 1},
        "week": {"views": 318, "clicks": 96},
        "series": DEMO_OVERVIEW["series"],
        "top": DEMO_LINKS[:5],
        "recent": DEMO_LINKS[:6],
    },
    "links": DEMO_LINKS,
    "earnings": DEMO_EARNINGS,
    "wa": DEMO_WA,
    "articles": [
        {"id": a["id"], "slug": a["slug"], "title": a["title"],
         "image_url": a["image_url"], "marketplace": a["marketplace"],
         "rating": a["rating"]}
        for a in DEMO_ARTICLES
    ],
}
