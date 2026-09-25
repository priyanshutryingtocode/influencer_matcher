import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

describe("api.probeBackend", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("resolves when the liveness endpoint responds", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.probeBackend()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/health/live"),
      expect.objectContaining({ signal: expect.anything() }),
    );
  });

  it("rejects when the backend responds with an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 }));

    await expect(api.probeBackend()).rejects.toThrow(/responded with an error/);
  });

  it("rejects with a retryable message when the cold start exceeds the timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
          }),
      ),
    );

    const pending = api.probeBackend();
    const assertion = expect(pending).rejects.toThrow(/too long to start/);
    await vi.advanceTimersByTimeAsync(120_000);

    await assertion;
  });
});
