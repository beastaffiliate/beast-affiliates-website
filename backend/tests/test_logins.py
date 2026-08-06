"""Credentials behind the admin Logins tab.

The rule being protected: login still verifies against the PBKDF2 hash, and the
readable copy exists only so the admin can re-send a password it issued. The
copy must disappear the moment the user sets their own, or the tab would show a
password that no longer works.

Needs a local server started WITH a CREDENTIAL_KEY:

    CREDENTIAL_KEY=$(python -c "from cryptography.fernet import Fernet; \
        print(Fernet.generate_key().decode())") \
        python -m uvicorn main:app --port 4200
    python tests/test_logins.py
"""

import json
import os
import secrets
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.getenv("SITE_BASE", "http://127.0.0.1:4200")

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


def row_for(username):
    _, d = call("GET", "/api/admin/logins")
    return next((r for r in d["accounts"] if r["username"] == username), None), d


suffix = secrets.token_hex(3)
user = f"logintest{suffix}"
number = "+9230055" + secrets.choice("0123456789") * 5
FIRST_PW = "adminchosen123"

# 0. storage has to actually be on, or every later case passes vacuously
_, d0 = call("GET", "/api/admin/logins")
check("CREDENTIAL_KEY is configured for this run", d0.get("storage_enabled") is True,
      "start the server with CREDENTIAL_KEY set, or the rest proves nothing")

# 1. an admin-created account is readable back
s, _ = call("POST", "/api/admin/accounts",
            {"whatsapp_number": number, "username": user, "password": FIRST_PW})
check("admin can create the account", s == 200, s)
row, _ = row_for(user)
check("the issued password reads back exactly", row and row["password"] == FIRST_PW,
      row)

# 2. it is the ciphertext that is stored, not the password — a caller with only
#    the database (no key) must not be able to read it. Proxy for that here:
#    the API never echoes password_enc under any name.
_, listing = call("GET", "/api/admin/logins")
check("no ciphertext field leaks to the client",
      all("password_enc" not in r for r in listing["accounts"]), listing["accounts"][:1])

# 3. login still works on the hash
s, login = call("POST", "/portal/login", {"username": user, "password": FIRST_PW})
check("the issued password actually logs in", s == 200 and login.get("token"), login)
token = login.get("token", "")

# 4. the user changes their own password -> the admin copy is dropped
NEW_PW = "userchosen456"
s, _ = call("PUT", "/portal/password", {"current": FIRST_PW, "new": NEW_PW}, token)
check("user can change their own password", s == 200, s)
row, _ = row_for(user)
check("admin copy is cleared once the user sets their own",
      row is not None and row["password"] == "", row)
check("cleared copy reports nothing stored, not an unreadable one",
      row is not None and row["has_stored"] is False,
      "has_stored must be False here, or the tab blames a key rotation")

# 5. and the tab must not be showing a password that no longer works
s, _ = call("POST", "/portal/login", {"username": user, "password": FIRST_PW})
check("the old password no longer logs in", s == 401, s)
s, _ = call("POST", "/portal/login", {"username": user, "password": NEW_PW})
check("the user's new password does", s == 200, s)

# 6. a reset re-arms the copy, so the admin can hand over credentials again
s, reset = call("POST", f"/api/admin/accounts/{row['account_id']}/reset-password")
check("admin can reset the password", s == 200 and reset.get("temp_password"), reset)
temp = reset.get("temp_password", "")
row, _ = row_for(user)
check("reset password is readable in the tab", row and row["password"] == temp, row)
s, _ = call("POST", "/portal/login", {"username": user, "password": temp})
check("reset password logs in", s == 200, s)

# 7. the backup must not carry readable passwords out of the building
s, backup = call("GET", "/api/admin/backup")
accs = backup.get("portal_accounts", []) if s == 200 else []
mine = next((a for a in accs if a["username"] == user), None)
check("backup export omits the readable password",
      mine is not None and "password_enc" not in mine and "password" not in mine,
      mine)
check("backup still carries the hash for restore",
      mine is not None and mine.get("password_hash", "").count("$") == 1, mine)

# cleanup
if row:
    call("DELETE", f"/api/admin/accounts/{row['account_id']}")

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
