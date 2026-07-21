import type { CheckStatus, LinkOut, Me, MyEarnings, Overview, WaStatus } from "./types";

// Same-origin in both dev and prod. In dev, vite.config proxies these paths
// to the local backend; in prod, vercel.json rewrites them to the backend
// project. No CORS anywhere.
const BASE = "";

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
  me: () => request<Me>("/portal/me"),
  overview: () => request<Overview>("/portal/overview"),
  links: (q: string, country: string, days: number) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (country) params.set("country", country);
    if (days) params.set("days", String(days));
    return request<LinkOut[]>(`/portal/links?${params.toString()}`);
  },
  revoke: (id: string) =>
    request<{ ok: boolean }>(`/portal/links/${id}/revoke`, { method: "POST" }),
  updateProfile: (data: { store_name?: string; link_preference?: string }) =>
    request<{ store_name: string; link_preference: "direct" | "hub" }>(
      "/portal/profile",
      { method: "PUT", body: JSON.stringify(data) },
    ),
  changePassword: (current: string, next: string) =>
    request<{ ok: boolean }>("/portal/password", {
      method: "PUT",
      body: JSON.stringify({ current, new: next }),
    }),
  putAvatar: (avatar: string) =>
    request<{ ok: boolean }>("/portal/avatar", {
      method: "PUT",
      body: JSON.stringify({ avatar }),
    }),
  storeCheck: (slug: string) =>
    request<{ available: boolean; reason?: string }>(
      `/portal/store/check?slug=${encodeURIComponent(slug)}`,
    ),
  putStore: (data: { slug?: string; enabled?: boolean }) =>
    request<{ store_slug: string; store_enabled: boolean }>("/portal/store", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  putPayout: (data: { bank: string; account_title: string; account_number: string }) =>
    request<{ bank: string; account_title: string; account_number: string }>(
      "/portal/payout",
      { method: "PUT", body: JSON.stringify(data) },
    ),
  earnings: () => request<MyEarnings>("/portal/earnings"),

  waStatus: () => request<WaStatus>("/portal/wa/status"),
  waCode: () =>
    request<{ code: string; expires_in: number }>("/portal/wa/code", {
      method: "POST",
    }),
  waUnlink: (number: string) =>
    request<{ ok: boolean }>(`/portal/wa/linked/${encodeURIComponent(number)}`, {
      method: "DELETE",
    }),
};
