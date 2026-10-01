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
/** Cold-start budget for waking a sleeping free-tier service. */
const backendWakeTimeoutMs = 120_000;
/** A local API answers in milliseconds, so a long wait there is always a
 *  misconfiguration rather than a cold start. */
const localWakeTimeoutMs = 10_000;

/** A free-tier instance sleeps after 15 minutes idle and needs roughly a minute
 *  to come back, so an unbounded fetch leaves the user on a spinner with
 *  nothing to retry. Every request carries a ceiling and turns a hang into a
 *  message that names the likely cause. */
const defaultRequestTimeoutMs = 30_000;
/** Run detail and CSV export are the two reads that can outrun the default. */
const slowRequestTimeoutMs = 90_000;

function wakeTimeoutMs(): number {
  return import.meta.env.DEV ? localWakeTimeoutMs : backendWakeTimeoutMs;
}

function apiTargetLabel(): string {
  return baseUrl || "the Vite dev proxy";
}


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

interface RequestOptions {
  /** Abort after this long. Defaults to a fixed ceiling per endpoint. */
  timeoutMs?: number;
  /** Caller-owned cancellation, e.g. when a component unmounts. */
  signal?: AbortSignal;
}

function timeoutMessage(timeoutMs: number): string {
  return `The backend at ${apiTargetLabel()} did not respond within ${Math.round(timeoutMs / 1000)}s. `
    + "It may have gone to sleep -- the status pill in the top bar wakes it.";
}

async function request<T>(path: string, init?: RequestInit, options: RequestOptions = {}): Promise<T> {
  const headers = await authenticatedHeaders(init);
  const timeoutMs = options.timeoutMs ?? defaultRequestTimeoutMs;
  const controller = new AbortController();
  const onCallerAbort = () => controller.abort();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // Checked before subscribing: awaiting the auth headers above is async, so a
  // caller can have aborted during it, and subscribing to an already-aborted
  // signal never fires -- the request would then run to the full timeout.
  if (options.signal?.aborted) {
    clearTimeout(timer);
    throw new DOMException("Aborted", "AbortError");
  }
  options.signal?.addEventListener("abort", onCallerAbort);

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      // A caller-cancelled request is not a failure to report; let it through so
      // the caller's own staleness check discards it.
      if (options.signal?.aborted) throw error;
      throw new ApiError(timeoutMessage(timeoutMs), 408, null);
    }
    throw new ApiError(`The backend at ${apiTargetLabel()} could not be reached. Is it running?`, 0, null);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onCallerAbort);
  }

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

async function probeBackend(timeoutMs = wakeTimeoutMs()): Promise<void> {
  const target = apiTargetLabel();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}/health/live`, { signal: controller.signal });
    if (!response.ok) throw new ApiError(`The backend at ${target} responded with an error.`, response.status, null);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        `The backend at ${target} did not respond within ${Math.round(timeoutMs / 1000)}s. Is it running?`,
        408,
        null,
      );
    }
    throw new ApiError(`The backend at ${target} could not be reached. Is it running?`, 0, null);
  } finally {
    clearTimeout(timer);
  }
}

async function downloadFile(path: string, filename: string) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), slowRequestTimeoutMs);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      headers: await authenticatedHeaders(),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(timeoutMessage(slowRequestTimeoutMs), 408, null);
    }
    throw new ApiError(`The backend at ${apiTargetLabel()} could not be reached. Is it running?`, 0, null);
  } finally {
    clearTimeout(timer);
  }
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
  createMatchJob: (brief: Brief, params: MatchParams, options?: RequestOptions) =>
    request<MatchJob>("/api/v1/match-jobs", {
      method: "POST",
      body: JSON.stringify({ brief, params }),
    }, options),
  getMatchJob: (jobId: string, options?: RequestOptions) =>
    request<MatchJob>(`/api/v1/match-jobs/${jobId}`, undefined, options),
  listRuns: (cursor?: string) => {
    const query = new URLSearchParams({ limit: "100" });
    if (cursor) query.set("cursor", cursor);
    return request<RunListResponse>(`/api/v1/runs?${query.toString()}`);
  },
  getRun: (runId: string, options?: RequestOptions) =>
    request<RunDetail>(`/api/v1/runs/${runId}`, undefined, { timeoutMs: slowRequestTimeoutMs, ...options }),
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
