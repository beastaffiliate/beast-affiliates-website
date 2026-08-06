import { useState } from "react";
import { api, setToken } from "../api";

// Sign-in only. Portal accounts are created by the admin (Portal
// administration -> Accounts), so there is no number step and no self-signup:
// asking for a WhatsApp number first only made signing in slower. The API
// enforces the same thing — see ALLOW_SELF_SIGNUP in the backend config.
export default function AuthView({
  onAuthed,
  onBack,
}: {
  onAuthed: () => void;
  onBack?: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const doLogin = async () => {
    setError("");
    setBusy(true);
    try {
      const res = await api.login(username, password);
      setToken(res.token);
      onAuthed();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mesh-canvas">
      <div style={{ width: "100%", maxWidth: 460 }}>
        <div style={{ textAlign: "center", marginBottom: 24 }} className="rise">
          <div className="row" style={{ justifyContent: "center", gap: 10 }}>
            <img src="/logo-icon.png" alt="" className="brand-logo" style={{ height: 42, width: 42 }} />
            <div className="wordmark" style={{ fontSize: 30 }}>
              Beast Affiliates
            </div>
          </div>
          <p className="muted caption" style={{ marginTop: 4 }}>
            Share links. Track clicks. Earn commissions.
          </p>
          {onBack && (
            <button
              className="pill pill-secondary pill-sm"
              style={{ marginTop: 12 }}
              onClick={onBack}
            >
              ← Back to site
            </button>
          )}
        </div>

        <div className="card rise rise-1" style={{ boxShadow: "rgba(0,0,0,0.1) 0 0 32px 0", border: 0 }}>
          {error && <div className="banner banner-error">{error}</div>}

          <span className="eyebrow">Sign in</span>
          <h2 className="display-md" style={{ fontSize: 26, margin: "8px 0 20px" }}>
            Welcome back
          </h2>
          <div style={{ display: "grid", gap: 14 }}>
            <label className="field">
              Username
              <input
                value={username}
                autoFocus
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doLogin()}
              />
            </label>
            <label className="field">
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doLogin()}
              />
            </label>
            <button className="pill pill-primary" onClick={doLogin} disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </div>
          <p className="muted caption" style={{ marginTop: 16, marginBottom: 0 }}>
            Don't have an account yet? Ask the Beast Affiliates team to set one
            up for you.
          </p>
        </div>
      </div>
    </div>
  );
}
