import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setDemoMode } from "./api";
import type { Me } from "./types";
import AuthView from "./views/AuthView";
import OverviewView from "./views/OverviewView";
import EarningsView from "./views/EarningsView";
import WhatsAppView from "./views/WhatsAppView";
import ProfileView from "./views/ProfileView";

type Tab = "overview" | "earnings" | "whatsapp" | "profile";

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  // Not-logged-in visitors explore the real portal in demo mode; the Login
  // button switches to the auth flow.
  const [showAuth, setShowAuth] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");
  const [me, setMe] = useState<Me | null>(null);
  const [popup, setPopup] = useState(false);

  const demo = !authed && !showAuth;

  // Toggle the api layer between real endpoints and dummy demo data.
  // Set synchronously during render (not in an effect) so it is already in
  // effect before child views mount and fire their data calls — otherwise
  // the first view (Overview) would call the real endpoint and 401.
  setDemoMode(demo);

  const refreshMe = useCallback(() => {
    api.me().then(setMe).catch(() => {});
  }, []);

  useEffect(() => {
    const onLogout = () => setAuthed(false);
    window.addEventListener("portal-logout", onLogout);
    return () => window.removeEventListener("portal-logout", onLogout);
  }, []);

  useEffect(() => {
    if (authed || demo) refreshMe();
    else setMe(null);
  }, [authed, demo, refreshMe]);

  // Demo login popup every 2 minutes; closing hides it until the next tick.
  useEffect(() => {
    if (!demo) return;
    const t = setInterval(() => setPopup(true), 120000);
    return () => clearInterval(t);
  }, [demo]);

  if (!authed && showAuth) {
    return (
      <AuthView
        onAuthed={() => {
          setShowAuth(false);
          setAuthed(true);
        }}
        onBack={() => setShowAuth(false)}
      />
    );
  }

  const signOut = () => {
    setToken(null);
    setAuthed(false);
    setTab("overview");
  };
  const goLogin = () => {
    setPopup(false);
    setShowAuth(true);
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
          {demo ? (
            <button className="pill pill-primary pill-sm" onClick={goLogin}>
              Log in / Sign up
            </button>
          ) : (
            <button className="pill pill-secondary pill-sm" onClick={signOut}>
              Sign out
            </button>
          )}
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

      {demo && popup && (
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
              <button className="pill pill-primary" style={{ width: "100%" }} onClick={goLogin}>
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
