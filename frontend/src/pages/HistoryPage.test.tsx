import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HistoryPage } from "./HistoryPage";

const { apiMocks, ApiErrorMock, runsState } = vi.hoisted(() => {
  class ApiError extends Error {}
  return {
    ApiErrorMock: ApiError,
    apiMocks: { getRun: vi.fn(), downloadRun: vi.fn(), deleteRun: vi.fn() },
    runsState: {
      items: [] as unknown[],
      isLoading: false,
      isLoadingMore: false,
      hasMore: false,
      error: null as string | null,
      loadMore: vi.fn(),
      refresh: vi.fn(),
      remove: vi.fn(),
    },
  };
});

vi.mock("../api/client", () => ({
  api: apiMocks,
  ApiError: ApiErrorMock,
}));

vi.mock("../hooks/useRuns", () => ({ useRuns: () => runsState }));

function listItem(runId: string, goal: string) {
  return {
    run_id: runId,
    created_at: "2026-01-01T00:00:00Z",
    brief: { goal, platform: "Any", audience: "", vibe: "" },
    n_results: 1,
    n_strong: 1,
    has_warnings: false,
    summary: { n_results: 1, avg_match_pct: 70, n_strong: 1, n_weak: 0, avg_engagement_pct: 4, median_followers: 1000 },
  };
}

function detail(runId: string) {
  return {
    run_id: runId,
    created_at: "2026-01-01T00:00:00Z",
    brief: { goal: `goal for ${runId}`, platform: "Any", audience: "", vibe: "" },
    summary: { n_results: 1, avg_match_pct: 70, n_strong: 1, n_weak: 0, avg_engagement_pct: 4, median_followers: 1000 },
    warnings: [],
    candidates: [],
    ranked: [],
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HistoryPage />
    </MemoryRouter>,
  );
}

describe("HistoryPage", () => {
  beforeEach(() => {
    apiMocks.getRun.mockReset();
    apiMocks.downloadRun.mockReset();
    apiMocks.deleteRun.mockReset();
    runsState.items = [listItem("a", "first run"), listItem("b", "second run")];
    runsState.error = null;
    runsState.remove.mockReset();
    runsState.remove.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("opens a run when its ledger row is pressed", async () => {
    apiMocks.getRun.mockImplementation((runId: string) => Promise.resolve(detail(runId)));
    renderPage();

    fireEvent.click(screen.getByText("first run"));

    await waitFor(() => expect(apiMocks.getRun).toHaveBeenCalledWith("a", expect.anything()));
    await waitFor(() => expect(screen.getByRole("heading", { name: /goal for a/ })).toBeTruthy());
  });

  /* The old handler was `setSelected(await api.getRun(id))` with no guard, so
   * opening A then B let A's slower response land on top of B. Keying the fetch
   * off the selected id means the second click supersedes the first. */
  it("keeps the last-chosen run when an earlier request resolves later", async () => {
    let releaseA: (() => void) | null = null;
    apiMocks.getRun.mockImplementation((runId: string) => {
      if (runId === "a") return new Promise((resolve) => { releaseA = () => resolve(detail("a")); });
      return Promise.resolve(detail("b"));
    });
    renderPage();

    fireEvent.click(screen.getByText("first run"));
    fireEvent.click(screen.getByText("second run"));
    await waitFor(() => expect(screen.getByRole("heading", { name: /goal for b/ })).toBeTruthy());

    releaseA!();
    await waitFor(() => expect(screen.getByRole("heading", { name: /goal for b/ })).toBeTruthy());
    expect(screen.queryByRole("heading", { name: /goal for a/ })).toBeNull();
  });

  it("reports a failed open with an archive-flavoured message", async () => {
    apiMocks.getRun.mockRejectedValue(new ApiErrorMock("run record missing"));
    renderPage();

    fireEvent.click(screen.getByText("first run"));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("run record missing"));
  });

  /* Export failures used to be written into the same slot as the open-failure
   * message, so a failed download looked like a failed load. */
  it("reports a failed export separately from a failed open", async () => {
    apiMocks.getRun.mockImplementation((runId: string) => Promise.resolve(detail(runId)));
    apiMocks.downloadRun.mockRejectedValue(new ApiErrorMock("csv generation failed"));
    renderPage();

    fireEvent.click(screen.getByText("first run"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Export CSV" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() => expect(screen.getByText(/Export issue/)).toBeTruthy());
    expect(screen.getByRole("alert").textContent).toContain("csv generation failed");
  });

  it("disables the delete button while the delete is in flight", async () => {
    let release: (() => void) | null = null;
    runsState.remove.mockImplementation(() => new Promise<void>((resolve) => { release = resolve; }));
    renderPage();

    const button = screen.getByRole("button", { name: /Delete run: first run/ });
    fireEvent.click(button);

    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(true));
    expect(button.getAttribute("aria-busy")).toBe("true");
    // A second click while one is in flight would send a second DELETE.
    fireEvent.click(button);
    expect(runsState.remove).toHaveBeenCalledTimes(1);

    release!();
    await waitFor(() => expect(screen.getByRole("button", { name: /Delete run: first run/ })).toBeTruthy());
  });

  it("does not delete when the confirmation is declined", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /Delete run: first run/ }));

    expect(runsState.remove).not.toHaveBeenCalled();
  });
});
