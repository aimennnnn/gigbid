// Thin fetch wrapper around the generated types in ./api/schema.d.ts (generated; do not hand-edit that file).
import type { components } from "./api/schema";

export type S = components["schemas"];
export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const KEY = "gigbid_session";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export type SessionInfo = { token: string; user: string; onboarded: boolean };

export function session(): SessionInfo | null {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? "null");
  } catch {
    return null;
  }
}

export function saveSession(s: SessionInfo | null) {
  if (s) window.localStorage.setItem(KEY, JSON.stringify(s));
  else window.localStorage.removeItem(KEY);
}

function headers(json: boolean): HeadersInit {
  const s = session();
  return { ...(json ? { "Content-Type": "application/json" } : {}), ...(s ? { Authorization: `Bearer ${s.token}` } : {}) };
}

function degraded(on: boolean) {
  window.dispatchEvent(new CustomEvent("gigbid:degraded", { detail: on }));
}

/** Call the API. `json` is sent as the body. 503 from the marketplace turns the degraded banner on. */
export async function api<T>(path: string, opts: { method?: string; json?: unknown } = {}): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${API}/api${path}`, {
      method: opts.method ?? (opts.json === undefined ? "GET" : "POST"),
      headers: headers(opts.json !== undefined),
      body: opts.json === undefined ? undefined : JSON.stringify(opts.json),
    });
  } catch {
    throw new ApiError(0, "The GigBid API is not reachable. Is it running on " + API + "?");
  }
  if (r.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    saveSession(null);
    window.location.href = "/login";
  }
  if (r.status === 503) degraded(true);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : r.statusText;
    throw new ApiError(r.status, detail);
  }
  return r.status === 204 ? (undefined as T) : ((await r.json()) as T);
}

/** Read a run's Server-Sent Events with fetch (so the session header can be sent). Resolves when the stream ends. */
export async function streamRun(thread: string, after: number, onStep: (e: S["RunEvent"]) => void, signal?: AbortSignal) {
  const r = await fetch(`${API}/api/runs/${encodeURIComponent(thread)}/stream?after=${after}`, { headers: headers(false), signal });
  if (!r.ok || !r.body) throw new ApiError(r.status, "could not open the run stream");
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const data = block.split("\n").find((l) => l.startsWith("data: "));
      if (data) onStep(JSON.parse(data.slice(6)));
    }
  }
}

export const threadOf = (user: string, jobId: string) => `${user}:${jobId}`;
export const money = (n?: number | null) => (n == null ? "-" : "$" + Math.round(n).toLocaleString("en-US"));
export const pct = (n?: number | null) => (n == null ? "-" : Math.round(n * 100) + "%");
