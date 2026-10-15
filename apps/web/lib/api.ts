import type { AuditLogItem, Device, EventList, EventRecord, Job, Review, Site, TokenResponse, User } from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Cannot reach the API. Check that the backend is running and NEXT_PUBLIC_API_BASE_URL is correct.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Preserve a useful status-based message for non-JSON responses.
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  apiBase: API_BASE,
  bootstrap: (body: { organization_name: string; email: string; password: string }, token: string) =>
    request<TokenResponse>("/auth/bootstrap", undefined, {
      method: "POST",
      headers: { "X-Bootstrap-Token": token },
      body: JSON.stringify(body),
    }),
  login: (email: string, password: string) => request<TokenResponse>("/auth/login", undefined, { method: "POST", body: JSON.stringify({ email, password }) }),
  me: (token: string) => request<User>("/auth/me", token),
  events: (token: string, params = "") => request<EventList>(`/events${params ? `?${params}` : ""}`, token),
  event: (token: string, id: string) => request<EventRecord>(`/events/${encodeURIComponent(id)}`, token),
  eventSnapshotUrl: (id: string) => `${API_BASE}/events/${encodeURIComponent(id)}/snapshot`,
  eventVideoUrl: (id: string) => `${API_BASE}/events/${encodeURIComponent(id)}/video`,
  review: (token: string, id: string, decision: string, note: string) => request<Review>(`/events/${encodeURIComponent(id)}/reviews`, token, { method: "POST", body: JSON.stringify({ decision, note: note || null }) }),
  reviews: (token: string, id: string) => request<Review[]>(`/events/${encodeURIComponent(id)}/reviews`, token),
  sites: (token: string) => request<Site[]>("/sites", token),
  createSite: (token: string, body: { name: string; description?: string }) => request<Site>("/sites", token, { method: "POST", body: JSON.stringify(body) }),
  devices: (token: string) => request<Device[]>("/devices", token),
  createDevice: (token: string, body: { name: string; device_type: string; site_id?: string | null }) => request<Device>("/devices", token, { method: "POST", body: JSON.stringify(body) }),
  heartbeat: (token: string, id: string, status: string) => request<Device>(`/devices/${encodeURIComponent(id)}/heartbeat`, token, { method: "POST", body: JSON.stringify({ status, details: { via: "operator-dashboard" } }) }),
  jobs: (token: string) => request<Job[]>("/analysis/jobs", token),
  jobMediaUrl: (id: string) => `${API_BASE}/analysis/jobs/${encodeURIComponent(id)}/media`,
  enqueueVideo: (token: string, file: File, siteId?: string) => {
    const form = new FormData();
    form.set("file", file);
    const suffix = siteId ? `?site_id=${encodeURIComponent(siteId)}` : "";
    return request<Job>(`/analysis/jobs${suffix}`, token, { method: "POST", body: form });
  },
  retryJob: (token: string, id: string) => request<Job>(`/analysis/jobs/${encodeURIComponent(id)}/retry`, token, { method: "POST" }),
  users: (token: string) => request<User[]>("/users", token),
  createUser: (token: string, body: { email: string; password: string; role: string }) => request<User>("/users", token, { method: "POST", body: JSON.stringify(body) }),
  setUserActive: (token: string, id: string, isActive: boolean) => request<User>(`/users/${encodeURIComponent(id)}/active`, token, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }),
  auditLogs: (token: string, params = "") => request<AuditLogItem[]>(`/audit-logs${params ? `?${params}` : ""}`, token),
};
