import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import type { Me } from "./types";
import AuthView from "./views/AuthView";
import PublicDemo from "./views/PublicDemo";
import OverviewView from "./views/OverviewView";
import EarningsView from "./views/EarningsView";
import WhatsAppView from "./views/WhatsAppView";
import ProfileView from "./views/ProfileView";

type Tab = "overview" | "earnings" | "whatsapp" | "profile";

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  // Not-logged-in visitors see the public demo by default; the Login button
  // switches to the real auth flow.
  const [showAuth, setShowAuth] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");
  const [me, setMe] = useState<Me | null>(null);

  const refreshMe = useCallback(() => {
    api.me().then(setMe).catch(() => {});
  }, []);

  useEffect(() => {
    const onLogout = () => setAuthed(false);
    window.addEventListener("portal-logout", onLogout);
    return () => window.removeEventListener("portal-logout", onLogout);
  }, []);

  useEffect(() => {
    if (authed) refreshMe();
    else setMe(null);
  }, [authed, refreshMe]);

  if (!authed) {
    return showAuth ? (
      <AuthView onAuthed={() => setAuthed(true)} onBack={() => setShowAuth(false)} />
    ) : (
      <PublicDemo onLogin={() => setShowAuth(true)} />
    );
  }

  const signOut = () => {
    setToken(null);
    setAuthed(false);
  };

  return (
    <>
      <nav className="nav">
        <div className="brand-mark">
          <img src="/logo-icon.png" alt="" className="brand-logo" />
          <span className="wordmark">Beast Affiliates</span>
        </div>
        <div className="nav-tabs">
          {(
            [
              ["overview", "Overview"],
              ["earnings", "Earnings"],
              ["whatsapp", "WhatsApp Linking"],
              ["profile", "Profile"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              className={`nav-tab ${key === "whatsapp" ? "wa-tab" : ""} ${tab === key ? "active" : ""}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
          {me && (
            <button
              className="row"
              style={{ gap: 8, background: "transparent", flexWrap: "nowrap" }}
              onClick={() => setTab("profile")}
              title="Profile"
            >
              {me.avatar ? (
                <img className="avatar" src={me.avatar} alt="" />
              ) : (
                <span className="avatar">{me.username[0]?.toUpperCase()}</span>
              )}
              <strong style={{ fontSize: 14 }}>{me.username}</strong>
            </button>
          )}
          <button className="pill pill-secondary pill-sm" onClick={signOut}>
            Sign out
          </button>
        </div>
      </nav>

      <main className="shell view-enter" key={tab}>
        {tab === "overview" && <OverviewView />}
        {tab === "earnings" && <EarningsView />}
        {tab === "whatsapp" && <WhatsAppView />}
        {tab === "profile" && <ProfileView me={me} refreshMe={refreshMe} />}
      </main>

      <footer className="footer-band">
        <strong>Beast Affiliates</strong> · share links, earn commissions ·
        © 2026 All rights reserved
      </footer>
    </>
  );
}
