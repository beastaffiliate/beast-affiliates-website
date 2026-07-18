import { useState } from "react";
import { api, setToken } from "../api";

type Step = "number" | "signup" | "login";

export default function AuthView({ onAuthed }: { onAuthed: () => void }) {
  const [step, setStep] = useState<Step>("number");
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setError("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const checkNumber = () =>
    run(async () => {
      const res = await api.check(number);
      if (res.status === "unregistered") {
        setError(
          "This number is not registered with the bot. Contact the admin to get registered first.",
        );
      } else if (res.status === "claimed") {
        setStep("login");
      } else {
        setName(res.name ?? "");
        setStep("signup");
      }
    });

  const doSignup = () =>
    run(async () => {
      const res = await api.signup(number, username, password);
      setToken(res.token);
      onAuthed();
    });

  const doLogin = () =>
    run(async () => {
      const res = await api.login(username, password);
      setToken(res.token);
      onAuthed();
    });

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
        </div>

        <div className="card rise rise-1" style={{ boxShadow: "rgba(0,0,0,0.1) 0 0 32px 0", border: 0 }}>
          {error && <div className="banner banner-error">{error}</div>}

          {step === "number" && (
            <>
              <span className="eyebrow">Step 1 of 2</span>
              <h2 className="display-md" style={{ fontSize: 26, margin: "8px 0 6px" }}>
                Enter your WhatsApp number
              </h2>
              <p className="muted caption" style={{ marginBottom: 20 }}>
                The same number you use with the bot.
              </p>
              <div style={{ display: "grid", gap: 14 }}>
                <input
                  placeholder="+92 300 1234567"
                  value={number}
                  autoFocus
                  onChange={(e) => setNumber(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && checkNumber()}
                />
                <button className="pill pill-primary" onClick={checkNumber} disabled={busy}>
                  {busy ? "Checking…" : "Continue"}
                </button>
                <button className="pill pill-secondary" onClick={() => { setError(""); setStep("login"); }}>
                  I already have an account
                </button>
              </div>
            </>
          )}

          {step === "signup" && (
            <>
              <span className="eyebrow">Step 2 of 2</span>
              <h2 className="display-md" style={{ fontSize: 26, margin: "8px 0 6px" }}>
                Welcome{name ? `, ${name}` : ""} 👋
              </h2>
              <p className="muted caption" style={{ marginBottom: 20 }}>
                Choose a username and password for your dashboard. One-time setup.
              </p>
              <div style={{ display: "grid", gap: 14 }}>
                <label className="field">
                  Username
                  <input
                    placeholder="e.g. tehman"
                    value={username}
                    autoFocus
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </label>
                <label className="field">
                  Password (min 8 characters)
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && doSignup()}
                  />
                </label>
                <button className="pill pill-primary" onClick={doSignup} disabled={busy}>
                  {busy ? "Creating…" : "Create my account"}
                </button>
                <button className="pill pill-secondary" onClick={() => { setError(""); setStep("number"); }}>
                  Back
                </button>
              </div>
            </>
          )}

          {step === "login" && (
            <>
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
                <button className="pill pill-secondary" onClick={() => { setError(""); setStep("number"); }}>
                  First time here? Start with your number
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
