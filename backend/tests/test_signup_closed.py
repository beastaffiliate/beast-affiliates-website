"""Self-signup is closed (client decision 2026-08-06): portal accounts are
created by the admin only, and the login page asks for nothing but a username
and a password.

The point of these cases is that closing the SCREEN is not closing the door —
POST /portal/signup has to refuse on its own, or anyone who knows the endpoint
can still claim an unclaimed number. Run against a local server:

    python -m uvicorn main:app --port 4200
    python tests/test_signup_closed.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.getenv("SITE_BASE", "http://127.0.0.1:4200")

passed = failed = 0


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body or b"{}")
        except ValueError:
            return e.code, {"raw": body.decode(errors="replace")}


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    print(("PASS " if cond else "FAIL ") + f" {name}" + ("" if cond else f"  {detail}"))


# 1. the number-check step is gone from the API, not just the UI
s, r = post("/portal/check", {"whatsapp_number": "+923111592151"})
check("POST /portal/check is refused", s == 403, f"{s} {r}")

# 2. and so is the signup that actually creates the row
s, r = post(
    "/portal/signup",
    {"whatsapp_number": "+923111592151", "username": "sneaky", "password": "hunter2hunter2"},
)
check("POST /portal/signup is refused", s == 403, f"{s} {r}")

# 3. the refusal tells the user what to do instead of just failing
detail = str(r.get("detail", ""))
check(
    "refusal explains accounts are admin-created",
    "admin" in detail.lower(),
    detail,
)

# 4. an unregistered number gets the same answer as a registered one, so the
#    endpoint cannot be used to probe which numbers exist
s2, r2 = post("/portal/signup", {"whatsapp_number": "+10000000000",
                                 "username": "probe", "password": "hunter2hunter2"})
check(
    "closed signup leaks nothing about which numbers are registered",
    (s2, str(r2.get("detail", ""))) == (s, detail),
    f"{s2} {r2}",
)

# 5. login itself is untouched — the whole point is that it still works, and
#    that it fails on bad credentials rather than on a missing number step
s, r = post("/portal/login", {"username": "nobody-here", "password": "wrongwrong"})
check("POST /portal/login still reachable (401, not 403)", s == 401, f"{s} {r}")

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
