import { useEffect, useState } from "react";
import { api } from "../api";
import type { MyEarnings } from "../types";

const KIND_LABEL: Record<string, string> = {
  earning: "Earning",
  bonus: "Bonus",
  adjustment: "Adjustment",
};

function fmtRs(n: number) {
  return "Rs " + n.toLocaleString();
}

export default function EarningsView() {
  const [data, setData] = useState<MyEarnings | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.earnings().then(setData).catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!data) return <div className="loading">Loading…</div>;

  return (
    <div className="grid" style={{ gap: 24 }}>
      <div>
        <h2 className="display-md" style={{ fontSize: 28 }}>Earnings</h2>
        <p className="muted caption">
          Your commission share, managed and paid out by the Beast Affiliates team.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 20,
        }}
      >
        <div className="card stat-green rise" style={{ padding: 24 }}>
          <span className="eyebrow">Total earned</span>
          <div className="stat-number" style={{ fontSize: 38 }}>{fmtRs(data.earned)}</div>
        </div>
        <div className="card stat-blue rise rise-1" style={{ padding: 24 }}>
          <span className="eyebrow">Paid out</span>
          <div className="stat-number" style={{ fontSize: 38 }}>{fmtRs(data.paid)}</div>
        </div>
        <div className="card stat-peach rise rise-2" style={{ padding: 24 }}>
          <span className="eyebrow">Pending balance</span>
          <div className="stat-number" style={{ fontSize: 38 }}>{fmtRs(data.balance)}</div>
        </div>
      </div>

      <div className="banner banner-ok" style={{ marginBottom: 0 }}>
        Payouts are processed from <strong>{fmtRs(data.min_payout)}</strong> —
        once your pending balance reaches that amount, the team sends your money
        to the bank account saved in your Profile.
      </div>

      <div className="grid grid-2">
        <div className="card rise rise-3">
          <h3 className="heading" style={{ marginBottom: 12 }}>Earnings history</h3>
          {data.entries.length === 0 ? (
            <p className="muted caption">
              Nothing yet — earnings appear here after the team records your
              commissions. Keep sharing links!
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Period</th>
                    <th>Amount</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {data.entries.map((e, i) => (
                    <tr key={i}>
                      <td>
                        <span className="chip">{KIND_LABEL[e.kind] ?? e.kind}</span>
                      </td>
                      <td>{e.label}</td>
                      <td style={{ color: e.amount < 0 ? "var(--error)" : "var(--success)", fontWeight: 700 }}>
                        {e.amount < 0 ? "−" : "+"}{fmtRs(Math.abs(e.amount))}
                      </td>
                      <td className="caption muted" style={{ whiteSpace: "nowrap" }}>
                        {new Date(e.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card rise rise-4">
          <h3 className="heading" style={{ marginBottom: 12 }}>Payout history</h3>
          {data.payouts.length === 0 ? (
            <p className="muted caption">
              No payouts yet — they'll appear here once you reach the minimum
              payout amount.
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Amount</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {data.payouts.map((p, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 700 }}>{fmtRs(p.amount)}</td>
                      <td className="caption muted" style={{ whiteSpace: "nowrap" }}>
                        {new Date(p.paid_at).toLocaleDateString()}
                        {p.note ? <span className="muted"> — {p.note}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
