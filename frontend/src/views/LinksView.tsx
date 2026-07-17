import { useEffect, useState } from "react";
import { api } from "../api";
import type { LinkOut } from "../types";

const COUNTRIES = ["", "US", "UK", "CA", "DE", "FR", "IT", "ES", "NL", "AU"];
const RANGES: [string, number][] = [
  ["All time", 0],
  ["Last 7 days", 7],
  ["Last 30 days", 30],
];

export default function LinksView() {
  const [links, setLinks] = useState<LinkOut[]>([]);
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [days, setDays] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState("");

  const load = () => {
    setLoading(true);
    api
      .links(q, country, days)
      .then(setLinks)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  };

  // Debounce the text filter; country/range apply immediately.
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, country, days]);

  const copy = async (url: string, id: string) => {
    await navigator.clipboard.writeText(url);
    setCopied(id);
    setTimeout(() => setCopied(""), 1500);
  };

  const revoke = async (id: string) => {
    if (!confirm("Revoke this link? Its article page will stop working.")) return;
    try {
      await api.revoke(id);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="grid" style={{ gap: 20 }}>
      <div className="row spread">
        <h2 className="display-md" style={{ fontSize: 28 }}>Your Links</h2>
        <span className="muted caption">{links.length} shown</span>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="card rise" style={{ padding: 18 }}>
        <div className="row">
          <input
            placeholder="Search product title…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1, minWidth: 200 }}
          />
          <select value={country} onChange={(e) => setCountry(e.target.value)}>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>{c || "All countries"}</option>
            ))}
          </select>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {RANGES.map(([label, v]) => (
              <option key={v} value={v}>{label}</option>
            ))}
          </select>
          {(q || country || days) && (
            <button className="pill pill-secondary pill-sm" onClick={() => { setQ(""); setCountry(""); setDays(0); }}>
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="card rise rise-1" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Product</th>
                <th>Created</th>
                <th>Views</th>
                <th>Clicks</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {links.map((l) => (
                <tr key={l.id} style={l.revoked ? { opacity: 0.5 } : undefined}>
                  <td style={{ width: 54 }}>
                    {l.image_url ? <img className="thumb" src={l.image_url} alt="" /> : <span className="chip">{l.marketplace}</span>}
                  </td>
                  <td style={{ maxWidth: 340 }}>
                    <a href={l.article_url} target="_blank" rel="noreferrer" style={{ color: "var(--ink)", fontWeight: 600, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {l.title}
                    </a>
                    <span className="caption muted">{l.marketplace} · {l.id}{l.revoked ? " · revoked" : ""}</span>
                  </td>
                  <td className="caption muted" style={{ whiteSpace: "nowrap" }}>
                    {new Date(l.created_at).toLocaleDateString()}
                  </td>
                  <td>{l.views}</td>
                  <td>{l.clicks}</td>
                  <td>
                    <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                      <button className="pill pill-secondary pill-sm" onClick={() => copy(l.article_url, l.id)}>
                        {copied === l.id ? "Copied ✓" : "Copy"}
                      </button>
                      {!l.revoked && (
                        <button className="pill pill-danger" onClick={() => revoke(l.id)}>
                          Revoke
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && links.length === 0 && (
          <p className="muted" style={{ padding: 32, textAlign: "center" }}>
            No links match. Share an Amazon link with the bot on WhatsApp to create one.
          </p>
        )}
        {loading && <p className="muted" style={{ padding: 32, textAlign: "center" }}>Loading…</p>}
      </div>
    </div>
  );
}
