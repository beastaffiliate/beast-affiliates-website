import { useEffect, useState } from "react";
import { api } from "../api";
import type { WaStatus } from "../types";

/** WhatsApp Quick Links — green accents are deliberate here (WhatsApp
    identity), an exception to the aubergine-only accent rule. */
export default function WhatsAppView() {
  const [status, setStatus] = useState<WaStatus | null>(null);
  const [error, setError] = useState("");
  const [code, setCode] = useState<{ value: string; left: number } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.waStatus().then(setStatus).catch((e) => setError((e as Error).message));

  useEffect(() => {
    load();
  }, []);

  // Countdown tick for an active code.
  useEffect(() => {
    if (!code) return;
    const t = setInterval(() => {
      setCode((c) => (c && c.left > 1 ? { ...c, left: c.left - 1 } : null));
    }, 1000);
    return () => clearInterval(t);
  }, [code]);

  // While a code is active, poll status so a successful link on the phone
  // shows up here without a manual refresh.
  useEffect(() => {
    if (!code) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [code]);

  if (error) return <div className="banner banner-error">{error}</div>;
  if (!status) return <div className="loading">Loading…</div>;

  const total = 1 + status.linked.length;
  const slotsLeft = status.max - total;
  const waLink = (text: string) =>
    `https://wa.me/${status.bot_number.replace(/[^0-9]/g, "")}?text=${encodeURIComponent(text)}`;

  const generate = async () => {
    setBusy(true);
    try {
      const res = await api.waCode();
      setCode({ value: res.code, left: res.expires_in });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const unlink = async (number: string) => {
    if (!confirm(`Unlink ${number}? The bot will stop replying to it.`)) return;
    try {
      await api.waUnlink(number);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const fmt = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="centered grid" style={{ gap: 20 }}>
      <div>
        <h2 className="display-md" style={{ fontSize: 28 }}>WhatsApp Quick Links</h2>
        <p className="muted caption">
          Link your WhatsApp numbers to create affiliate links by simply sending
          the bot Amazon URLs.
        </p>
      </div>

      <div className="form-2">
        <div className="card rise wa-card-green">
          <span className="eyebrow" style={{ color: "#0d7a43" }}>Status</span>
          <h3 className="heading" style={{ color: "#0d7a43" }}>Linked</h3>
          <p className="caption" style={{ color: "#1b5e3a" }}>
            You can send Amazon URLs directly on WhatsApp.
          </p>
        </div>
        <div className="card rise rise-1">
          <span className="eyebrow">Linked accounts</span>
          <h3 className="heading">{total}/{status.max}</h3>
          <p className="caption muted">
            {slotsLeft > 0 ? `${slotsLeft} slot${slotsLeft === 1 ? "" : "s"} available` : "No slots left"}
          </p>
        </div>
      </div>

      <div className="card rise rise-1">
        <div className="row spread" style={{ marginBottom: 10 }}>
          <h3 className="heading">Linked Accounts</h3>
          <span className="chip" style={{ background: "#e7f6ec", color: "#0d7a43" }}>
            {total} active
          </span>
        </div>
        <div className="list-item">
          <span className="wa-badge">✓</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <strong>{status.primary}</strong>
            <span className="caption muted" style={{ display: "block" }}>
              Primary — registered by admin
            </span>
          </div>
        </div>
        {status.linked.map((n) => (
          <div key={n} className="list-item">
            <span className="wa-badge">✓</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong>{n}</strong>
              <span className="caption muted" style={{ display: "block" }}>Linked number</span>
            </div>
            <button className="pill pill-danger" onClick={() => unlink(n)}>
              Unlink
            </button>
          </div>
        ))}
      </div>

      <div className="card rise rise-2">
        <h3 className="heading" style={{ marginBottom: 4 }}>Add another WhatsApp account</h3>
        <p className="caption muted" style={{ marginBottom: 16 }}>
          Keep personal and team numbers separate while sending affiliate-ready
          Amazon links from each linked account.
        </p>

        {slotsLeft <= 0 ? (
          <p className="caption muted">
            You've linked the maximum of {status.max} numbers. Unlink one to add
            another.
          </p>
        ) : code ? (
          <div style={{ display: "grid", gap: 14 }}>
            <div>
              <span className="eyebrow">1 · Copy this code</span>
              <div className="wa-code">
                <span>{code.value.split("").join(" ")}</span>
                <span className="chip">{fmt(code.left)}</span>
              </div>
            </div>
            <div>
              <span className="eyebrow">2 · Send it to the bot from the NEW number</span>
              <div className="row" style={{ marginTop: 8 }}>
                <a
                  className="pill pill-wa"
                  href={waLink(code.value)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open WhatsApp Chat
                </a>
                <button
                  className="pill pill-secondary pill-sm"
                  onClick={async () => {
                    await navigator.clipboard.writeText(code.value);
                  }}
                >
                  Copy code
                </button>
              </div>
              <p className="caption muted" style={{ marginTop: 6 }}>
                Make sure you send it from the number you want to link — not
                your already-linked one.
              </p>
            </div>
            <div>
              <span className="eyebrow">3 · Done</span>
              <p className="caption muted">
                The bot replies "✅ Linked!" and the number appears above within
                a few seconds.
              </p>
            </div>
            <div>
              <button className="pill pill-secondary pill-sm" onClick={() => setCode(null)}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "8px 0 4px" }}>
            <button className="pill pill-wa" onClick={generate} disabled={busy}>
              {busy ? "Generating…" : "Generate Linking Code"}
            </button>
            <p className="caption muted" style={{ marginTop: 10 }}>
              You can link up to {status.max} WhatsApp accounts
            </p>
          </div>
        )}
      </div>

      <div className="card rise rise-3 wa-card-green">
        <h3 className="heading" style={{ color: "#0d7a43", marginBottom: 10 }}>
          How it works
        </h3>
        <ol style={{ marginLeft: 20, display: "grid", gap: 8, color: "#1b5e3a" }}>
          <li>Generate a linking code above</li>
          <li>
            Send the code to our WhatsApp:{" "}
            <a
              className="pill pill-wa pill-sm"
              style={{ display: "inline-block", marginLeft: 6 }}
              href={waLink("")}
              target="_blank"
              rel="noreferrer"
            >
              {status.bot_number}
            </a>
          </li>
          <li>Once linked, send any Amazon URL from that number to get your links</li>
        </ol>
      </div>
    </div>
  );
}
