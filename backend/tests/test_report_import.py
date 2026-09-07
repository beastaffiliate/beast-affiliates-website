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
                             password_hash="x", commission_rate=70,
                             orders=10, shipped_orders=8)  # pre-existing manual counts
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
check("preview: day has no reports yet", pv["existing_reports"] == 0 and pv["report_seq"] == 1, pv)
check("preview: no overlap warning on a fresh day", pv["already_paid_users"] == [])
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
check("alice current_orders = manual(10) + report(15) = 25 (additive)", summ["current_orders"] == 25, summ)
check("alice current_shipped = manual(8) + report(15) = 23 (additive)", summ["current_shipped"] == 23, summ)
check("alice balance = manual 5000 + report 2278 = 7278 (additive)", summ["balance"] == 7278, summ)
m = s.get(portal.EarningsEntry, manual_id)
check("pre-existing manual entry is UNTOUCHED", m is not None and m.net_amount == 5000 and m.kind == "bonus")

# --- exact re-upload of the SAME report is refused (hash guard) ---
check("re-uploading the identical report is refused (409 exact duplicate)",
      status_of(lambda: portal.admin_report_record(body, s)) == 409)

# --- multiple reports per day: numbering + overlap warning ---
pv2 = portal.admin_report_preview(body, s)
check("preview: day already has 1 report, this would be Report 2",
      pv2["existing_reports"] == 1 and pv2["report_seq"] == 2, pv2)
check("preview flags users already paid earlier today (soft overlap warning)",
      pv2["already_paid_users"] == ["alice", "bob"], pv2["already_paid_users"])

# a DIFFERENT report (different rows) for the same day IS allowed, as Report 2
body2 = portal._ReportBody(report_date="2026-09-03", entries=[
    portal._ReportEntryIn(account_id=bob.id, earnings_usd_cents=500, ordered=3, shipped=3, returned=0),
])
res2 = portal.admin_report_record(body2, s)
check("a different report for the same day records as Report 2", res2["report_seq"] == 2, res2)
check("bob's Report 2 earning is ADDITIVE (a 2nd auto-report entry)",
      s.query(portal.EarningsEntry).filter(
          portal.EarningsEntry.account_id == bob.id,
          portal.EarningsEntry.note == "auto-report").count() == 2)
# order counts stack across BOTH reports for the same user (Report 1: 21/21, Report 2: 3/3)
bob_summ = portal._earnings_summary(s, bob)
check("bob current_orders stacks across reports = 21 + 3 = 24", bob_summ["current_orders"] == 24, bob_summ)
check("bob current_shipped stacks across reports = 21 + 3 = 24", bob_summ["current_shipped"] == 24, bob_summ)
check("Report 2 label carries its number",
      s.execute(select(portal.EarningsEntry).where(
          portal.EarningsEntry.label == "US report 2026-09-03 (Report 2)")).scalars().first() is not None)

# --- dates endpoint (for the calendar): counts reports per day ---
d = portal.admin_report_dates("US", s)
check("dates endpoint lists the day", d["dates"] == ["2026-09-03"])
check("dates endpoint counts 2 reports that day", d["counts"] == {"2026-09-03": 2}, d)

# --- calendar reset: LEDGER ONLY (clears calendar, keeps earnings balances) ---
bal_before = portal._earnings_summary(s, alice)["balance"]
rst = portal.admin_report_reset("US", s)
check("reset removed both import ledger rows", rst["imports_removed"] == 2, rst)
check("reset cleared the calendar (no dates)", portal.admin_report_dates("US", s)["dates"] == [])
check("reset left every earnings entry in place (money untouched)",
      s.query(portal.EarningsEntry).count() == 4)  # manual + Report1 alice/bob + Report2 bob
check("reset kept alice's balance identical", portal._earnings_summary(s, alice)["balance"] == bal_before)
check("reset dropped ONLY the report-derived order counts (manual 10 remains)",
      portal._earnings_summary(s, alice)["current_orders"] == 10)
check("after reset the same date is importable again", portal.admin_report_record(body, s)["ok"] is True)
portal.admin_report_reset("US", s)  # tidy up so later assertions are clean

# --- US rate fixer: updating it changes the rate for future reports ---
portal.admin_report_set_rate(portal._RateBody(rate=278.5), s)
check("rate updates and reads back",
      portal.admin_report_get_rate(s)["rate"] == 278.5 and portal._get_usd_rate(s) == 278.5)
check("a non-positive rate is refused (422)",
      status_of(lambda: portal.admin_report_set_rate(portal._RateBody(rate=0), s)) == 422)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
