import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Me } from "../types";

const BANKS = [
  "Easypaisa", "JazzCash", "NayaPay", "SadaPay",
  "HBL — Habib Bank", "UBL — United Bank", "MCB Bank", "Meezan Bank",
  "Bank Alfalah", "Allied Bank", "National Bank of Pakistan", "Askari Bank",
  "Bank AL Habib", "Faysal Bank", "JS Bank", "Soneri Bank",
  "Standard Chartered", "BankIslami", "Dubai Islamic Bank", "Al Baraka Bank",
  "Habib Metropolitan Bank", "Bank of Punjab", "Bank of Khyber", "Sindh Bank",
  "Summit Bank", "Silkbank", "MCB Islamic Bank", "U Microfinance Bank",
  "Mobilink Microfinance Bank", "Khushhali Microfinance Bank",
];

interface Props {
  me: Me | null;
  refreshMe: () => void;
}

export default function ProfileView({ me, refreshMe }: Props) {
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const flash = (kind: "ok" | "error", text: string) => {
    setMsg({ kind, text });
    window.scrollTo({ top: 0, behavior: "smooth" });
    setTimeout(() => setMsg(null), 3500);
  };

  if (!me) return <div className="loading">Loading…</div>;

  return (
    <div className="centered grid" style={{ gap: 20 }}>
      <h2 className="display-md" style={{ fontSize: 28 }}>Profile</h2>
      {msg && (
        <div className={`banner banner-${msg.kind === "ok" ? "ok" : "error"}`}>
          {msg.text}
        </div>
      )}
      <PersonalCard me={me} refreshMe={refreshMe} flash={flash} />
      <ReplyCard me={me} refreshMe={refreshMe} flash={flash} />
      <StoreCard me={me} refreshMe={refreshMe} flash={flash} />
      <PayoutCard me={me} refreshMe={refreshMe} flash={flash} />
      <PasswordCard flash={flash} />
    </div>
  );
}

type CardProps = Props & { flash: (k: "ok" | "error", t: string) => void };

/* ------------------------------------------------------ personal info */

function PersonalCard({ me, refreshMe, flash }: CardProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const onPick = async (file: File) => {
    setBusy(true);
    try {
      const dataUrl = await resizeImage(file, 160);
      await api.putAvatar(dataUrl);
      refreshMe();
      flash("ok", "Profile photo updated.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card accent-purple rise">
      <h3 className="heading" style={{ marginBottom: 18 }}>Personal Information</h3>
      <div className="row" style={{ gap: 18, marginBottom: 18 }}>
        {me!.avatar ? (
          <img className="avatar avatar-lg" src={me!.avatar} alt="" />
        ) : (
          <span className="avatar avatar-lg">{me!.username[0]?.toUpperCase()}</span>
        )}
        <div>
          <strong style={{ fontSize: 18 }}>{me!.name || me!.username}</strong>
          <p className="caption muted">@{me!.username}</p>
          <button
            className="pill pill-secondary pill-sm"
            style={{ marginTop: 8 }}
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            {busy ? "Uploading…" : me!.avatar ? "Change photo" : "Add photo"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && onPick(e.target.files[0])}
          />
        </div>
      </div>
      <div className="form-2">
        <label className="field">
          Name
          <input value={me!.name} disabled />
        </label>
        <label className="field">
          WhatsApp Number
          <input value={me!.whatsapp_number} disabled />
        </label>
      </div>
      <p className="caption muted" style={{ marginTop: 10 }}>
        Name and number are managed by the admin — contact them to change these.
      </p>
    </div>
  );
}

function resizeImage(file: File, size: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const scale = Math.max(size / img.width, size / img.height);
      canvas.width = Math.min(size, Math.round(img.width * scale));
      canvas.height = Math.min(size, Math.round(img.height * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("Could not read image"));
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => reject(new Error("Could not read image"));
    img.src = URL.createObjectURL(file);
  });
}

/* -------------------------------------------------------- reply prefs */

function ReplyCard({ me, refreshMe, flash }: CardProps) {
  const [storeName, setStoreName] = useState(me!.store_name);
  const [pref, setPref] = useState<"direct" | "hub">(me!.link_preference);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.updateProfile({ store_name: storeName, link_preference: pref });
      refreshMe();
      flash("ok", "Reply settings saved.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card accent-blue rise rise-1">
      <h3 className="heading" style={{ marginBottom: 18 }}>WhatsApp Replies</h3>
      <div style={{ display: "grid", gap: 16 }}>
        <label className="field">
          Store name (shown in your article headers)
          <input
            placeholder="e.g. Tehman Deals"
            value={storeName}
            onChange={(e) => setStoreName(e.target.value)}
          />
        </label>
        <label className="field">
          Link preference — what the bot replies with
          <select value={pref} onChange={(e) => setPref(e.target.value as "direct" | "hub")}>
            <option value="direct">Direct Amazon link</option>
            <option value="hub">Hub article page</option>
          </select>
        </label>
        <div>
          <button className="pill pill-primary" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------- store page */

function StoreCard({ me, refreshMe, flash }: CardProps) {
  const [slug, setSlug] = useState(me!.store_slug);
  const [avail, setAvail] = useState<null | boolean>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const origin = window.location.origin;
  const liveUrl = `${origin}/u/${me!.store_slug}`;

  useEffect(() => {
    setAvail(null);
    setReason("");
    const clean = slug.trim().toLowerCase();
    if (!clean || clean === me!.store_slug) return;
    const t = setTimeout(async () => {
      try {
        const res = await api.storeCheck(clean);
        setAvail(res.available);
        setReason(res.reason ?? "");
      } catch {
        /* ignore */
      }
    }, 350);
    return () => clearTimeout(t);
  }, [slug, me]);

  const saveSlug = async () => {
    setBusy(true);
    try {
      await api.putStore({ slug: slug.trim().toLowerCase() });
      refreshMe();
      flash("ok", "Slug saved. Enable your page to make it public.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = async () => {
    setBusy(true);
    try {
      await api.putStore({ enabled: !me!.store_enabled });
      refreshMe();
      flash("ok", me!.store_enabled ? "Store page disabled." : "Your page is live!");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card accent-green rise rise-2">
      <h3 className="heading" style={{ marginBottom: 6 }}>Public store page</h3>
      <p className="caption muted" style={{ marginBottom: 16 }}>
        A personal page you can share with your audience — it shows your latest
        products, filterable by today, yesterday, or this week.
      </p>

      <label className="field" style={{ marginBottom: 6 }}>
        Choose your slug (3–40 characters, lowercase, hyphens allowed)
        <div className="slug-row">
          <span className="caption muted slug-prefix" style={{ whiteSpace: "nowrap" }}>
            {origin.replace(/^https?:\/\//, "")}/u/
          </span>
          <input
            placeholder="e.g. tehman-deals"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />
          <button
            className="pill pill-primary pill-sm"
            onClick={saveSlug}
            disabled={busy || !slug.trim() || slug.trim().toLowerCase() === me!.store_slug}
          >
            Save slug
          </button>
        </div>
      </label>
      {avail === true && <p className="caption" style={{ color: "var(--success)" }}>✓ Available</p>}
      {avail === false && (
        <p className="caption" style={{ color: "var(--error)" }}>
          ✗ {reason || "Taken — try another"}
        </p>
      )}

      {me!.store_slug ? (
        <div
          className="banner"
          style={{
            marginTop: 14,
            marginBottom: 0,
            background: me!.store_enabled ? "#ecf7f3" : "#f8fafc",
            border: `1px solid ${me!.store_enabled ? "#bfe3d6" : "var(--hairline)"}`,
          }}
        >
          <div className="row spread">
            <span className="caption" style={{ wordBreak: "break-all" }}>
              {me!.store_enabled ? (
                <>
                  ✓ Your page is <strong>live</strong>:{" "}
                  <a href={liveUrl} target="_blank" rel="noreferrer">{liveUrl}</a>
                </>
              ) : (
                <>Your page is <strong>disabled</strong>.</>
              )}
            </span>
            <span className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
              {me!.store_enabled && (
                <button
                  className="pill pill-secondary pill-sm"
                  onClick={async () => {
                    await navigator.clipboard.writeText(liveUrl);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1500);
                  }}
                >
                  {copied ? "Copied ✓" : "Copy link"}
                </button>
              )}
              <button
                className={`pill pill-sm ${me!.store_enabled ? "pill-danger" : "pill-primary"}`}
                onClick={toggle}
                disabled={busy}
              >
                {me!.store_enabled ? "Disable page" : "Enable page"}
              </button>
            </span>
          </div>
        </div>
      ) : (
        <p className="caption muted" style={{ marginTop: 12 }}>
          Save a slug above to enable your page.
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- payout */

function PayoutCard({ me, refreshMe, flash }: CardProps) {
  const [bank, setBank] = useState(me!.bank);
  const [title, setTitle] = useState(me!.account_title);
  const [number, setNumber] = useState(me!.account_number);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.putPayout({ bank, account_title: title, account_number: number });
      refreshMe();
      flash("ok", "Payout details saved.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card accent-peach rise rise-3">
      <h3 className="heading" style={{ marginBottom: 6 }}>Payout Settings</h3>
      <p className="caption muted" style={{ marginBottom: 16 }}>
        Where your commission payouts will be sent.
      </p>
      <span className="eyebrow">Bank account</span>
      <div
        className="form-3" style={{ marginTop: 10 }}
      >
        <label className="field">
          Bank *
          <select value={bank} onChange={(e) => setBank(e.target.value)}>
            <option value="">Select Bank</option>
            {BANKS.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Account Title *
          <input
            placeholder="Name on account"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="field">
          Account Number / IBAN *
          <input
            placeholder="03XX-XXXXXXX or PK..."
            value={number}
            onChange={(e) => setNumber(e.target.value)}
          />
        </label>
      </div>
      <div style={{ marginTop: 16 }}>
        <button
          className="pill pill-primary"
          onClick={save}
          disabled={busy || !bank || !title.trim() || !number.trim()}
        >
          {busy ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- password */

function PasswordCard({ flash }: { flash: (k: "ok" | "error", t: string) => void }) {
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.changePassword(curPw, newPw);
      setCurPw("");
      setNewPw("");
      flash("ok", "Password changed.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card accent-lavender rise rise-4">
      <h3 className="heading" style={{ marginBottom: 18 }}>Change password</h3>
      <div className="form-2">
        <label className="field">
          Current password
          <input type="password" value={curPw} onChange={(e) => setCurPw(e.target.value)} />
        </label>
        <label className="field">
          New password (min 8 characters)
          <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
        </label>
      </div>
      <div style={{ marginTop: 16 }}>
        <button
          className="pill pill-outline"
          onClick={save}
          disabled={busy || !curPw || !newPw}
        >
          {busy ? "Updating…" : "Update password"}
        </button>
      </div>
    </div>
  );
}
