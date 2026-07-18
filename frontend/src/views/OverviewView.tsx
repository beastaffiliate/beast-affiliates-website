import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Overview, SeriesDay } from "../types";
import LinksView from "./LinksView";

/** Animated count-up for the big aubergine stat numerals (client-side only). */
function CountUp({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [shown, setShown] = useState(0);
  const ref = useRef<number>(0);
  useEffect(() => {
    const start = performance.now();
    const from = ref.current;
    const duration = 700;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.round((from + (value - from) * eased) * 10) / 10);
      if (p < 1) raf = requestAnimationFrame(tick);
      else ref.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return (
    <span className="stat-number">
      {Number.isInteger(value) ? Math.round(shown) : shown}
      {suffix}
    </span>
  );
}

/** Hand-rolled 7-day trend chart — no chart library, animated line draw. */
function TrendChart({ series }: { series: SeriesDay[] }) {
  const width = 640;
  const height = 180;
  const pad = 24;
  const max = Math.max(1, ...series.flatMap((d) => [d.views, d.clicks]));
  const x = (i: number) => pad + (i * (width - 2 * pad)) / Math.max(1, series.length - 1);
  const y = (v: number) => height - pad - (v / max) * (height - 2 * pad);
  const path = (key: "views" | "clicks") =>
    series.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d[key])}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto" }}>
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <line
          key={f}
          x1={pad}
          x2={width - pad}
          y1={y(max * f)}
          y2={y(max * f)}
          stroke="var(--hairline)"
          strokeWidth="1"
        />
      ))}
      <path className="chart-line" d={path("views")} stroke="var(--primary)" />
      <path className="chart-line" d={path("clicks")} stroke="var(--link-blue)" style={{ animationDelay: "0.45s" }} />
      {series.map((d, i) => (
        <text
          key={d.date}
          x={x(i)}
          y={height - 6}
          textAnchor="middle"
          fontSize="10"
          fill="var(--ink-mute)"
        >
          {d.date.slice(5)}
        </text>
      ))}
    </svg>
  );
}

export default function OverviewView() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  useEffect(() => {
    api.overview().then(setData).catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!data) return <p className="muted">Loading…</p>;

  const copy = async (url: string, id: string) => {
    await navigator.clipboard.writeText(url);
    setCopied(id);
    setTimeout(() => setCopied(""), 1500);
  };

  return (
    <div className="grid" style={{ gap: 24 }}>
      <div className="grid grid-4">
        {(
          [
            ["Views", data.totals.views, ""],
            ["Clicks", data.totals.clicks, ""],
            ["Links", data.totals.links, ""],
            ["Conversion", data.totals.conversion, "%"],
          ] as [string, number, string][]
        ).map(([label, value, suffix], i) => (
          <div key={label} className={`card rise rise-${i + 1}`} style={{ padding: 24 }}>
            <span className="eyebrow">{label}</span>
            <div>
              <CountUp value={value} suffix={suffix} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-2">
        <div className="card rise rise-2">
          <div className="row spread" style={{ marginBottom: 8 }}>
            <h3 className="heading">7-Day Trend</h3>
            <span className="caption muted">
              <span style={{ color: "var(--primary)" }}>●</span> Views&nbsp;&nbsp;
              <span style={{ color: "var(--link-blue)" }}>●</span> Clicks
            </span>
          </div>
          <TrendChart series={data.series} />
        </div>

        <div className="card card-aubergine rise rise-3" style={{ padding: 32 }}>
          <span className="eyebrow" style={{ color: "var(--on-aubergine-mute)" }}>
            Today
          </span>
          {(
            [
              ["Views", data.today.views],
              ["Clicks", data.today.clicks],
              ["New Links", data.today.links],
            ] as [string, number][]
          ).map(([label, v]) => (
            <div key={label} className="row spread" style={{ padding: "10px 0", borderBottom: "1px solid var(--primary-tint)" }}>
              <span className="muted">{label}</span>
              <strong style={{ fontSize: 22 }}>{v}</strong>
            </div>
          ))}
          <div style={{ marginTop: 18 }}>
            <span className="eyebrow" style={{ color: "var(--on-aubergine-mute)" }}>
              Last 7 days
            </span>
            <div className="row spread" style={{ padding: "10px 0" }}>
              <span className="muted">Views · Clicks</span>
              <strong style={{ fontSize: 22 }}>
                {data.week.views} · {data.week.clicks}
              </strong>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card rise rise-4">
          <h3 className="heading" style={{ marginBottom: 10 }}>Best Performers</h3>
          {data.top.length === 0 && (
            <p className="muted caption">Share your first link via WhatsApp to see stats here.</p>
          )}
          {data.top.map((l, i) => (
            <div key={l.id} className="list-item">
              <span className="muted" style={{ width: 18, fontWeight: 700 }}>{i + 1}</span>
              {l.image_url ? <img src={l.image_url} alt="" /> : <span className="chip">{l.marketplace}</span>}
              <div style={{ flex: 1, minWidth: 0 }}>
                <a href={l.article_url} target="_blank" rel="noreferrer" style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--ink)", fontWeight: 600 }}>
                  {l.title}
                </a>
                <span className="caption muted">{l.clicks} clicks · {l.views} views</span>
              </div>
            </div>
          ))}
        </div>

        <div className="card rise rise-5">
          <h3 className="heading" style={{ marginBottom: 10 }}>Recent Links</h3>
          {data.recent.map((l) => (
            <div key={l.id} className="list-item">
              <span className="chip">{l.marketplace}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 14.5 }}>
                  {l.title}
                </span>
                <span className="caption muted">{l.views} views · {l.clicks} clicks</span>
              </div>
              <button className="pill pill-secondary pill-sm" onClick={() => copy(l.article_url, l.id)}>
                {copied === l.id ? "Copied ✓" : "Copy"}
              </button>
            </div>
          ))}
          {data.recent.length === 0 && (
            <p className="muted caption">No links yet.</p>
          )}
        </div>
      </div>

      {/* Your Links lives here (owner decision) — full-width section below
          Best Performers, not a separate tab. */}
      <LinksView />
    </div>
  );
}
