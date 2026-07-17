import { useEffect, useState } from "react";
import { api } from "../api";
import type { Me } from "../types";

export default function ProfileView() {
  const [me, setMe] = useState<Me | null>(null);
  const [storeName, setStoreName] = useState("");
  const [pref, setPref] = useState<"direct" | "hub">("direct");
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [savingPw, setSavingPw] = useState(false);

  useEffect(() => {
    api.me().then((m) => {
      setMe(m);
      setStoreName(m.store_name);
      setPref(m.link_preference);
    });
  }, []);

  const flash = (kind: "ok" | "error", text: string) => {
    setMsg({ kind, text });
    setTimeout(() => setMsg(null), 3000);
  };

  const saveProfile = async () => {
    setSavingProfile(true);
    try {
      const res = await api.updateProfile({ store_name: storeName, link_preference: pref });
      setStoreName(res.store_name);
      setPref(res.link_preference);
      flash("ok", "Profile saved.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async () => {
    setSavingPw(true);
    try {
      await api.changePassword(curPw, newPw);
      setCurPw("");
      setNewPw("");
      flash("ok", "Password changed.");
    } catch (e) {
      flash("error", (e as Error).message);
    } finally {
      setSavingPw(false);
    }
  };

  if (!me) return <p className="muted">Loading…</p>;

  return (
    <div className="grid" style={{ gap: 20, maxWidth: 720 }}>
      <h2 className="display-md" style={{ fontSize: 28 }}>Profile</h2>
      {msg && <div className={`banner banner-${msg.kind === "ok" ? "ok" : "error"}`}>{msg.text}</div>}

      <div className="card rise">
        <h3 className="heading" style={{ marginBottom: 4 }}>Account</h3>
        <p className="caption muted" style={{ marginBottom: 18 }}>
          {me.name} · {me.whatsapp_number} · @{me.username}
        </p>

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
          <p className="caption muted" style={{ marginTop: -6 }}>
            {pref === "hub"
              ? "The bot replies with a link to your product article page. The buy button on it goes to Amazon with your tag."
              : "The bot replies with a clean tagged Amazon link directly."}
          </p>

          <div>
            <button className="pill pill-primary" onClick={saveProfile} disabled={savingProfile}>
              {savingProfile ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>

      <div className="card rise rise-1">
        <h3 className="heading" style={{ marginBottom: 18 }}>Change password</h3>
        <div style={{ display: "grid", gap: 16 }}>
          <label className="field">
            Current password
            <input type="password" value={curPw} onChange={(e) => setCurPw(e.target.value)} />
          </label>
          <label className="field">
            New password (min 8 characters)
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
          </label>
          <div>
            <button
              className="pill pill-outline"
              onClick={savePassword}
              disabled={savingPw || !curPw || !newPw}
            >
              {savingPw ? "Updating…" : "Update password"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
