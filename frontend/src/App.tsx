import { useEffect, useState } from "react";
import { getToken, setToken } from "./api";
import AuthView from "./views/AuthView";
import OverviewView from "./views/OverviewView";
import ProfileView from "./views/ProfileView";

type Tab = "overview" | "profile";

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    const onLogout = () => setAuthed(false);
    window.addEventListener("portal-logout", onLogout);
    return () => window.removeEventListener("portal-logout", onLogout);
  }, []);

  if (!authed) return <AuthView onAuthed={() => setAuthed(true)} />;

  const signOut = () => {
    setToken(null);
    setAuthed(false);
  };

  return (
    <>
      <nav className="nav">
        <span className="wordmark">Beast Affiliates</span>
        <div className="nav-tabs">
          {(
            [
              ["overview", "Overview"],
              ["profile", "Profile"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              className={`nav-tab ${tab === key ? "active" : ""}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <button className="pill pill-secondary pill-sm" onClick={signOut}>
          Sign out
        </button>
      </nav>

      <main className="shell view-enter" key={tab}>
        {tab === "overview" && <OverviewView />}
        {tab === "profile" && <ProfileView />}
      </main>

      <footer className="footer-band">
        <strong>Beast Affiliates</strong> · share links, earn commissions ·
        © 2026 All rights reserved
      </footer>
    </>
  );
}
