"""Offline test for the auto-report-0.1 record-keeper (in-memory SQLite).

Proves the importer uses the STORED US rate, is ADDITIVE ONLY (creates new
earnings entries, adds order counts on top of the manual figure), refuses a
duplicate date, and never touches pre-existing earnings.
"""
import os
import sys

os.environ["AUTO_REPORT"] = "true"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.database import Base  # noqa: E402
from app import portal  # noqa: E402

engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
s = sessionmaker(bind=engine)()

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    print(("PASS " if cond else "FAIL ") + f" {name}" + ("" if cond else f"  {detail}"))


def status_of(fn):
    try:
        fn()
        return None
    except Exception as ex:
        return getattr(ex, "status_code", None)


alice = portal.PortalAccount(whatsapp_number="+900001", username="alice",
                             password_hash="x", commission_rate=70)
bob = portal.PortalAccount(whatsapp_number="+900002", username="bob",
                           password_hash="x")  # no rate -> default 20
s.add_all([alice, bob])
s.commit()

# a pre-existing MANUAL earning for alice that must stay untouched
manual = portal.EarningsEntry(account_id=alice.id, kind="bonus", gross_amount=0,
                              rate_applied=0, net_amount=5000, orders_count=0,
                              label="manual bonus")
s.add(manual)
s.commit()
manual_id = manual.id

body = portal._ReportBody(report_date="2026-09-03", entries=[
    portal._ReportEntryIn(account_id=alice.id, earnings_usd_cents=1162, ordered=15, shipped=15, returned=0),
    portal._ReportEntryIn(account_id=bob.id, earnings_usd_cents=2680, ordered=21, shipped=21, returned=4),
])

# --- the import uses the STORED rate; without one it refuses ---
check("rate is 0 until set", portal._get_usd_rate(s) == 0.0)
check("preview refuses when no rate is set (422)",
      status_of(lambda: portal.admin_report_preview(body, s)) == 422)
portal.admin_report_set_rate(portal._RateBody(rate=280.0), s)
check("rate is now 280", portal._get_usd_rate(s) == 280.0)

# --- preview (must not write) ---
pv = portal.admin_report_preview(body, s)
check("preview uses stored rate: alice net = 70% of 3254 = 2278",
      any(u["username"] == "alice" and u["net_pkr"] == 2278 and u["gross_pkr"] == 3254 for u in pv["users"]), pv["users"])
check("preview: bob net = 20% (default) of 7504 = 1501",
      any(u["username"] == "bob" and u["net_pkr"] == 1501 for u in pv["users"]))
check("preview reports the applied rate", pv["fx_rate"] == 280.0)
check("preview: not already imported", pv["already_imported"] is False)
check("preview writes nothing", s.query(portal.ReportImport).count() == 0 and s.query(portal.EarningsEntry).count() == 1)

# --- record (writes) ---
res = portal.admin_report_record(body, s)
check("record created 2 earnings entries", res["earnings_entries_created"] == 2, res)
report_entries = s.execute(select(portal.EarningsEntry).where(portal.EarningsEntry.note == "auto-report")).scalars().all()
by_acc = {e.account_id: e for e in report_entries}
check("alice report entry: net 2278, kind earning, dated label",
      by_acc[alice.id].net_amount == 2278 and by_acc[alice.id].kind == "earning" and "US report 2026-09-03" in by_acc[alice.id].label)
check("bob report entry: net 1501", by_acc[bob.id].net_amount == 1501)
check("ledger row recorded for the date", s.query(portal.ReportImport).filter_by(report_date="2026-09-03").count() == 1)

# --- additive order counts + untouched manual ---
summ = portal._earnings_summary(s, alice)
check("alice current_orders = manual(0) + report(15)", summ["current_orders"] == 15, summ)
check("alice balance = manual 5000 + report 2278 = 7278 (additive)", summ["balance"] == 7278, summ)
m = s.get(portal.EarningsEntry, manual_id)
check("pre-existing manual entry is UNTOUCHED", m is not None and m.net_amount == 5000 and m.kind == "bonus")

# --- duplicate date refused ---
check("re-importing the same date is refused (409 duplicate alert)",
      status_of(lambda: portal.admin_report_record(body, s)) == 409)

# --- dates endpoint (for the calendar) ---
check("dates endpoint lists the imported date", portal.admin_report_dates("US", s)["dates"] == ["2026-09-03"])

# --- US rate fixer: updating it changes the rate for future reports ---
portal.admin_report_set_rate(portal._RateBody(rate=278.5), s)
check("rate updates and reads back",
      portal.admin_report_get_rate(s)["rate"] == 278.5 and portal._get_usd_rate(s) == 278.5)
check("a non-positive rate is refused (422)",
      status_of(lambda: portal.admin_report_set_rate(portal._RateBody(rate=0), s)) == 422)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
