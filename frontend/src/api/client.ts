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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
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

export const api = {
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
  exportUrl: (runId: string) => `${baseUrl}/api/v1/runs/${runId}/export.csv`,
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
