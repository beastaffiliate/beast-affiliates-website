"""Return orders, and the payout model that draws the dashboard down.

The behaviour under test is the client's own worked example: 90 orders / 90
shipped / 10,000 PKR, admin pays 60 orders and 8,600 PKR, user should then see
30 / 30 / 1,400. Everything shown is derived, so the checks that matter most
are the ones proving nothing was overwritten: re-entering the Amazon total does
not resurrect paid orders, and deleting a payout puts them back.

Run against an isolated database so real data is never touched:

    DATABASE_URL="sqlite:///./earn_test.db" python -m uvicorn main:app --port 4201
    python tests/test_earnings_payouts.py
"""

import json
import os
import secrets
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.getenv("SITE_BASE", "http://127.0.0.1:4201")

passed = failed = 0


def call(method, path, payload=None, token=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        method=method,
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


def admin():
    _, d = call("GET", f"/api/admin/earnings/{ACC}")
    return d


def user():
    _, d = call("GET", "/portal/earnings", token=TOKEN)
    return d


# ------------------------------------------------------------------ fixture
suffix = secrets.token_hex(3)
USERNAME = f"earn{suffix}"
NUMBER = "+92300" + "".join(secrets.choice("0123456789") for _ in range(7))
PW = "earnpass1234"

s, acc = call("POST", "/api/admin/accounts",
              {"whatsapp_number": NUMBER, "username": USERNAME, "password": PW})
check("fixture account created", s == 200, acc)
ACC = acc["id"]
_, login = call("POST", "/portal/login", {"username": USERNAME, "password": PW})
TOKEN = login.get("token", "")

# rate 100% keeps the arithmetic in the test about payouts, not commission.
# Asserted, because a fixture that fails quietly turns every later figure into
# a puzzle — this endpoint is a PUT and a POST here just 405s.
s, r = call("PUT", f"/api/admin/earnings/{ACC}/rate", {"rate": 100})
check("fixture rate set to 100%", s == 200 and r.get("rate") == 100, f"{s} {r}")
s, _ = call("POST", f"/api/admin/accounts/{ACC}/orders", {"orders": 90})
check("fixture orders set", s == 200, s)
s, _ = call("POST", f"/api/admin/accounts/{ACC}/shipped-orders", {"shipped_orders": 90})
check("fixture shipped set", s == 200, s)
s, _ = call("POST", f"/api/admin/earnings/{ACC}/entries",
            {"kind": "earning", "label": "July 2026", "gross_amount": 10000})
check("fixture earnings added", s == 200)

u = user()
check("before payout: 90 orders", u["orders"] == 90, u)
check("before payout: 90 shipped", u["shipped_orders"] == 90, u)
check("before payout: 10,000 earnings", u["current_earnings"] == 10000, u)

# --------------------------------------------------- the client's example
s, _ = call("POST", f"/api/admin/earnings/{ACC}/payouts",
            {"amount": 8600, "orders_paid": 60, "note": "Aug payout"})
check("payout of 8,600 over 60 orders accepted", s == 200)

u = user()
check("after payout: 30 orders", u["orders"] == 30, u)
check("after payout: 30 shipped", u["shipped_orders"] == 30, u)
check("after payout: 1,400 earnings", u["current_earnings"] == 1400, u)

# ------------------------------------------- the three figures are GONE
check("lifetime earned is not sent to the user", "earned" not in u, list(u))
check("paid total is not sent to the user", "paid" not in u, list(u))
check("pending balance is not sent to the user", "balance" not in u, list(u))
check("payout history carries the paid orders",
      u["payouts"] and u["payouts"][0]["orders_paid"] == 60, u["payouts"])
check("payout history carries the amount and date",
      u["payouts"][0]["amount"] == 8600 and u["payouts"][0]["paid_at"], u["payouts"])

# ------------------------------------------------------------ return orders
s, ret = call("POST", f"/api/admin/earnings/{ACC}/entries",
              {"kind": "return", "label": "Returned item", "net_amount": -500,
               "orders_count": 1})
check("return entry accepted", s == 200, ret)

u = user()
check("return orders counted", u["return_orders"] == 1, u)
check("return deducted from earnings (1400-500)", u["current_earnings"] == 900, u)
check("return does NOT reduce total orders", u["orders"] == 30, u)
check("return does NOT reduce shipped orders", u["shipped_orders"] == 30, u)

# a return typed as a positive number must still reduce earnings
s, _ = call("POST", f"/api/admin/earnings/{ACC}/entries",
            {"kind": "return", "label": "Second return", "net_amount": 300,
             "orders_count": 2})
u = user()
check("a return entered as +300 still subtracts", u["current_earnings"] == 600, u)
check("return orders accumulate (1+2)", u["return_orders"] == 3, u)

# ------------------------------------------- nothing is destructively stored
a = admin()
check("admin still sees the Amazon total that was typed",
      a["orders_entered"] == 90 and a["shipped_entered"] == 90, a)

# re-entering the true Amazon total must not resurrect the paid orders
call("POST", f"/api/admin/accounts/{ACC}/orders", {"orders": 90})
u = user()
check("re-entering the Amazon total keeps 30 outstanding", u["orders"] == 30, u)

# a later month's orders add on top, still net of what was paid
call("POST", f"/api/admin/accounts/{ACC}/orders", {"orders": 120})
u = user()
check("new orders land on top of the paid-down figure (120-60)",
      u["orders"] == 60, u)

# ------------------------------------------------------- overdraw is refused
s, err = call("POST", f"/api/admin/earnings/{ACC}/payouts",
              {"amount": 100, "orders_paid": 999})
check("cannot pay more orders than are outstanding", s == 422, f"{s} {err}")
check("the refusal says how many are left",
      "60" in str(err.get("detail", "")), err)

# ------------------------------------------------------- deleting a payout
a = admin()
payout_id = a["payouts"][0]["id"]
s, _ = call("DELETE", f"/api/admin/earnings/{ACC}/payouts/{payout_id}")
check("payout deleted", s == 200)
u = user()
check("deleting a payout returns the orders (120)", u["orders"] == 120, u)
check("deleting a payout returns the money (10000-800)",
      u["current_earnings"] == 9200, u)

# --------------------------------- switching a return away clears its count
a = admin()
ret_entry = next(e for e in a["entries"] if e["kind"] == "return")
s, _ = call("PUT", f"/api/admin/earnings/{ACC}/entries/{ret_entry['id']}",
            {"kind": "adjustment", "net_amount": -500})
check("return can be edited into an adjustment", s == 200)
u = user()
check("its units stop counting as returns",
      u["return_orders"] == 3 - ret_entry["orders_count"], u)

# ------------------------------------------------- user still sees no gross
u = user()
check("no gross amount leaks to the user",
      all("gross" not in k for e in u["entries"] for k in e), u["entries"][:1])
check("no commission rate leaks to the user",
      all("rate" not in k for k in u), list(u))

# ------------------------------- deleting an account takes its money with it
# Orphaned earnings rows are joined by account_id with no foreign key, so if
# they survive a delete they reattach to whoever is issued that id next — which
# a restore-from-backup can cause, because it resets the sequences.
before = admin()
check("account has money rows before deletion",
      before["entries_count"] > 0, before["entries_count"])

s, _ = call("DELETE", f"/api/admin/accounts/{ACC}")
check("account deleted", s == 200, s)

s, gone = call("GET", f"/api/admin/earnings/{ACC}")
check("the account is really gone", s == 404, f"{s} {gone}")

# recreate on the same id path and prove nothing was inherited
s, acc2 = call("POST", "/api/admin/accounts",
               {"whatsapp_number": NUMBER, "username": USERNAME + "b",
                "password": PW})
check("the number can be reused after deletion", s == 200, acc2)
_, fresh = call("GET", f"/api/admin/earnings/{acc2['id']}")
check("a re-created account inherits NO earnings",
      fresh.get("entries_count") == 0 and fresh.get("balance") == 0, fresh)
check("and inherits no payout history", not fresh.get("payouts"), fresh.get("payouts"))
check("and inherits no return orders", fresh.get("return_orders") == 0, fresh)

call("DELETE", f"/api/admin/accounts/{acc2['id']}")

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
