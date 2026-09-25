import { supabase } from "../lib/supabase";
import type {
  Brief,
  Comparison,
  MatchJob,
  MatchParams,
  Meta,
  RunDetail,
  RunListResponse,
} from "../types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const isLocalHost = typeof window !== "undefined" && /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);
export const isApiConfigured = Boolean(baseUrl) || (import.meta.env.DEV && isLocalHost);
export const backendWakeTimeoutMs = 120_000;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function authenticatedHeaders(init?: RequestInit) {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (import.meta.env.PROD && !isApiConfigured) {
    throw new Error("VITE_API_BASE_URL is not configured for this deployment.");
  }
  const headers = await authenticatedHeaders(init);
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    throw new ApiError(errorMessage(payload), response.status, payload);
  }
  return payload as T;
}

async function probeBackend(timeoutMs = backendWakeTimeoutMs): Promise<void> {
  if (import.meta.env.PROD && !isApiConfigured) {
    throw new Error("VITE_API_BASE_URL is not configured for this deployment.");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}/health/live`, { signal: controller.signal });
    if (!response.ok) throw new ApiError("The backend responded with an error.", response.status, null);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The backend took too long to start. Try again in a moment.", 408, null);
    }
    throw new ApiError("The backend could not be reached.", 0, null);
  } finally {
    clearTimeout(timer);
  }
}

async function downloadFile(path: string, filename: string) {
  if (import.meta.env.PROD && !isApiConfigured) {
    throw new Error("VITE_API_BASE_URL is not configured for this deployment.");
  }
  const response = await fetch(`${baseUrl}${path}`, { headers: await authenticatedHeaders() });
  if (!response.ok) {
    const text = await response.text();
    let payload: unknown = text;
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
    throw new ApiError(errorMessage(payload), response.status, payload);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const api = {
  probeBackend: () => probeBackend(),
  getMeta: () => request<Meta>("/api/v1/meta"),
  createMatchJob: (brief: Brief, params: MatchParams) =>
    request<MatchJob>("/api/v1/match-jobs", {
      method: "POST",
      body: JSON.stringify({ brief, params }),
    }),
  getMatchJob: (jobId: string) => request<MatchJob>(`/api/v1/match-jobs/${jobId}`),
  listRuns: (cursor?: string) => {
    const query = new URLSearchParams({ limit: "100" });
    if (cursor) query.set("cursor", cursor);
    return request<RunListResponse>(`/api/v1/runs?${query.toString()}`);
  },
  getRun: (runId: string) => request<RunDetail>(`/api/v1/runs/${runId}`),
  deleteRun: (runId: string) => request<void>(`/api/v1/runs/${runId}`, { method: "DELETE" }),
  compareRuns: (runIdA: string, runIdB: string) =>
    request<Comparison>("/api/v1/comparisons", {
      method: "POST",
      body: JSON.stringify({ run_id_a: runIdA, run_id_b: runIdB }),
    }),
  downloadRun: (runId: string) => downloadFile(`/api/v1/runs/${runId}/export.csv`, `shortlist-${runId}.csv`),
};

function errorMessage(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (first && typeof first === "object" && "msg" in first && typeof first.msg === "string") {
        return first.msg;
      }
    }
    if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
      return detail.message;
    }
  }
  return "The request could not be completed.";
}
