import { useEffect, useState } from "react";
import { api } from "../api";
import type { DemoData } from "../types";

/** Public homepage for not-logged-in visitors: an explorable demo of the
 *  portal filled with dummy data + a grid of demo articles that open. A
 *  login popup reappears every 2 minutes. All data here is fake and never
 *  touches the database or admin. */
export default function PublicDemo({ onLogin }: { onLogin: () => void }) {
  const [data, setData] = useState<DemoData | null>(null);
  const [popup, setPopup] = useState(false);

  useEffect(() => {
    api.demo().then(setData).catch(() => {});
  }, []);

  // Login popup every 2 minutes; closing it hides until the next interval.
  useEffect(() => {
    const t = setInterval(() => setPopup(true), 120000);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <nav className="nav">
        <div className="brand-mark">
          <img src="/logo-icon.png" alt="" className="brand-logo" />
          <span className="wordmark">Beast Affiliates</span>
        </div>
        <button className="pill pill-primary pill-sm" onClick={onLogin}>
          Log in / Sign up
        </button>
      </nav>

      <main className="shell view-enter">
        <div className="demo-banner">
          👋 You're viewing a live demo with sample data.{" "}
          <a href="#" onClick={(e) => { e.preventDefault(); onLogin(); }}>
            Log in
          </a>{" "}
          to see your own dashboard.
        </div>

        {!data ? (
          <p className="muted">Loading…</p>
        ) : (
          <div className="grid" style={{ gap: 24 }}>
            <div>
              <h1 className="display" style={{ marginBottom: 4 }}>
                Turn every link into earnings
              </h1>
              <p className="muted">
                Share Amazon products on WhatsApp, we generate clean product
                pages, and you earn commission on every sale. Here's what your
                dashboard looks like.
              </p>
            </div>

            <div
              className="grid"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}
            >
              {(
                [
                  ["Views", data.overview.totals.views, "", "stat-blue"],
                  ["Clicks", data.overview.totals.clicks, "", "stat-green"],
                  ["Orders", data.overview.totals.orders, "", "stat-violet"],
                  ["Links", data.overview.totals.links, "", "stat-cream"],
                  ["Conversion", data.overview.totals.conversion, "%", "stat-peach"],
                ] as [string, number, string, string][]
              ).map(([label, value, suffix, variant]) => (
                <div key={label} className={`card ${variant} rise`} style={{ padding: 24 }}>
                  <span className="eyebrow">{label}</span>
                  <div className="stat-number">
                    {value}
                    {suffix}
                  </div>
                </div>
              ))}
            </div>

            <div className="card rise rise-1">
              <h3 className="heading" style={{ marginBottom: 8 }}>7-Day Trend</h3>
              <TrendChart series={data.overview.series} />
            </div>

            <div>
              <div className="row spread" style={{ marginBottom: 12 }}>
                <h2 className="display-md" style={{ fontSize: 26 }}>Featured products</h2>
                <span className="muted caption">Tap any product to open its page</span>
              </div>
              <div
                className="grid"
                style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))" }}
              >
                {data.articles.map((a) => (
                  <a
                    key={a.id}
                    className="acard"
                    href={`/p/${a.id}/${a.slug}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className="aimg">
                      <img src={a.image_url} alt="" loading="lazy" />
                    </div>
                    <div className="abody">
                      <span className="chip" style={{ alignSelf: "flex-start" }}>
                        {a.marketplace}
                        {a.rating ? ` · ★ ${a.rating}` : ""}
                      </span>
                      <span className="atitle">{a.title}</span>
                      <span className="aview">View product</span>
                    </div>
                  </a>
                ))}
              </div>
            </div>

            <div className="card card-aubergine rise rise-2" style={{ textAlign: "center" }}>
              <h2 className="display-md" style={{ color: "#fff", fontSize: 26 }}>
                Ready to start earning?
              </h2>
              <p className="muted" style={{ margin: "8px 0 18px" }}>
                Already registered with our WhatsApp bot? Log in with your number.
              </p>
              <button className="pill pill-secondary" onClick={onLogin}>
                Log in / Sign up
              </button>
            </div>
          </div>
        )}
      </main>

      <footer className="footer-band">
        <strong>Beast Affiliates</strong> · share links, earn commissions ·
        © 2026 All rights reserved
      </footer>

      {popup && (
        <div className="modal-overlay" onClick={() => setPopup(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setPopup(false)} aria-label="Close">
              ×
            </button>
            <div style={{ textAlign: "center" }}>
              <img src="/logo-icon.png" alt="" style={{ height: 46, marginBottom: 10 }} />
              <h3 className="heading" style={{ marginBottom: 6 }}>
                Access your dashboard
              </h3>
              <p className="muted caption" style={{ marginBottom: 20 }}>
                Log in to create links, track your clicks and orders, and see
                your earnings.
              </p>
              <button
                className="pill pill-primary"
                style={{ width: "100%" }}
                onClick={() => { setPopup(false); onLogin(); }}
              >
                Log in / Sign up
              </button>
              <button
                className="pill pill-secondary pill-sm"
                style={{ marginTop: 10 }}
                onClick={() => setPopup(false)}
              >
                Keep browsing
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function TrendChart({ series }: { series: { date: string; views: number; clicks: number }[] }) {
  const width = 640;
  const height = 170;
  const pad = 26;
  const max = Math.max(1, ...series.flatMap((d) => [d.views, d.clicks]));
  const x = (i: number) => pad + (i * (width - 2 * pad)) / Math.max(1, series.length - 1);
  const y = (v: number) => height - pad - (v / max) * (height - 2 * pad);
  const path = (k: "views" | "clicks") =>
    series.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d[k])}`).join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto" }}>
      {[0.5, 1].map((f) => (
        <line key={f} x1={pad} x2={width - pad} y1={y(max * f)} y2={y(max * f)} stroke="var(--hairline)" />
      ))}
      <path d={path("views")} fill="none" stroke="var(--link-blue)" strokeWidth="2.5" />
      <path d={path("clicks")} fill="none" stroke="#22c05c" strokeWidth="2.5" />
      {series.map((d, i) => (
        <text key={d.date} x={x(i)} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--ink-mute)">
          {d.date}
        </text>
      ))}
    </svg>
  );
}
