import type { CheckStatus, LinkOut, Me, MyEarnings, Overview, WaStatus } from "./types";

// Same-origin in both dev and prod. In dev, vite.config proxies these paths
// to the local backend; in prod, vercel.json rewrites them to the backend
// project. No CORS anywhere.
const BASE = "";

// Demo mode: not-logged-in visitors explore the REAL portal filled with dummy
// data from /api/demo. Reads return that data; writes are no-ops (nothing
// saves) so they get the full experience without an account.
let demoMode = false;
let demoCache: Promise<Record<string, unknown>> | null = null;

export function setDemoMode(on: boolean) {
  demoMode = on;
  if (!on) demoCache = null;
}
function demoData(): Promise<Record<string, unknown>> {
  if (!demoCache) demoCache = fetch("/api/demo").then((r) => r.json());
  return demoCache;
}
function demoSlice<T>(key: string): Promise<T> {
  return demoData().then((d) => d[key] as T);
}

const TOKEN_KEY = "portal_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && !path.startsWith("/portal/login")) {
    setToken(null);
    window.dispatchEvent(new Event("portal-logout"));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data as T;
}

export const api = {
  check: (whatsapp_number: string) =>
    request<{ status: CheckStatus; name?: string; username_hint?: string }>(
      "/portal/check",
      { method: "POST", body: JSON.stringify({ whatsapp_number }) },
    ),
  signup: (whatsapp_number: string, username: string, password: string) =>
    request<{ token: string; username: string; name: string }>("/portal/signup", {
      method: "POST",
      body: JSON.stringify({ whatsapp_number, username, password }),
    }),
  login: (username: string, password: string) =>
    request<{ token: string; username: string }>("/portal/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => (demoMode ? demoSlice<Me>("me") : request<Me>("/portal/me")),
  overview: () =>
    demoMode ? demoSlice<Overview>("overview") : request<Overview>("/portal/overview"),
  links: (q: string, country: string, days: number) => {
    if (demoMode) return demoSlice<LinkOut[]>("links");
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (country) params.set("country", country);
    if (days) params.set("days", String(days));
    return request<LinkOut[]>(`/portal/links?${params.toString()}`);
  },
  revoke: (id: string) =>
    demoMode
      ? Promise.resolve({ ok: true })
      : request<{ ok: boolean }>(`/portal/links/${id}/revoke`, { method: "POST" }),
  updateProfile: (data: { store_name?: string; link_preference?: string }) =>
    demoMode
      ? Promise.resolve({
          store_name: data.store_name ?? "",
          link_preference: (data.link_preference ?? "hub") as "direct" | "hub",
        })
      : request<{ store_name: string; link_preference: "direct" | "hub" }>(
          "/portal/profile",
          { method: "PUT", body: JSON.stringify(data) },
        ),
  changePassword: (current: string, next: string) =>
    demoMode
      ? Promise.resolve({ ok: true })
      : request<{ ok: boolean }>("/portal/password", {
          method: "PUT",
          body: JSON.stringify({ current, new: next }),
        }),
  putAvatar: (avatar: string) =>
    demoMode
      ? Promise.resolve({ ok: true })
      : request<{ ok: boolean }>("/portal/avatar", {
          method: "PUT",
          body: JSON.stringify({ avatar }),
        }),
  storeCheck: (slug: string): Promise<{ available: boolean; reason?: string }> =>
    demoMode
      ? Promise.resolve({ available: true })
      : request<{ available: boolean; reason?: string }>(
          `/portal/store/check?slug=${encodeURIComponent(slug)}`,
        ),
  putStore: (data: { slug?: string; enabled?: boolean }) =>
    demoMode
      ? Promise.resolve({ store_slug: data.slug ?? "sami-deals", store_enabled: data.enabled ?? true })
      : request<{ store_slug: string; store_enabled: boolean }>("/portal/store", {
          method: "PUT",
          body: JSON.stringify(data),
        }),
  putPayout: (data: { bank: string; account_title: string; account_number: string }) =>
    demoMode
      ? Promise.resolve(data)
      : request<{ bank: string; account_title: string; account_number: string }>(
          "/portal/payout",
          { method: "PUT", body: JSON.stringify(data) },
        ),
  earnings: () =>
    demoMode ? demoSlice<MyEarnings>("earnings") : request<MyEarnings>("/portal/earnings"),

  waStatus: () =>
    demoMode ? demoSlice<WaStatus>("wa") : request<WaStatus>("/portal/wa/status"),
  waCode: () =>
    demoMode
      ? Promise.resolve({ code: "DEMOAB", expires_in: 180 })
      : request<{ code: string; expires_in: number }>("/portal/wa/code", {
          method: "POST",
        }),
  waUnlink: (number: string) =>
    demoMode
      ? Promise.resolve({ ok: true })
      : request<{ ok: boolean }>(`/portal/wa/linked/${encodeURIComponent(number)}`, {
          method: "DELETE",
        }),
};
