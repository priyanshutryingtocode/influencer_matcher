import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComparePage } from "./ComparePage";

const { apiMocks, ApiErrorMock } = vi.hoisted(() => {
  class ApiError extends Error {}
  return {
    ApiErrorMock: ApiError,
    apiMocks: { listRuns: vi.fn(), compareRuns: vi.fn(), getRun: vi.fn() },
  };
});

vi.mock("../api/client", () => ({
  api: apiMocks,
  ApiError: ApiErrorMock,
}));

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

function comparison() {
  return {
    summary_a: { n_results: 1, avg_match_pct: 70, n_strong: 1, n_weak: 0, avg_engagement_pct: 4, median_followers: 1000 },
    summary_b: { n_results: 1, avg_match_pct: 70, n_strong: 1, n_weak: 0, avg_engagement_pct: 4, median_followers: 1000 },
    shared_creators: [],
    only_in_a: [],
    only_in_b: [],
  };
}

function renderPage() {
  return render(<ComparePage />);
}

describe("ComparePage", () => {
  beforeEach(() => {
    apiMocks.listRuns.mockReset();
    apiMocks.compareRuns.mockReset();
    apiMocks.getRun.mockReset();
  });

  afterEach(() => cleanup());

  it("prompts for two runs when the archive is empty", async () => {
    apiMocks.listRuns.mockResolvedValue({ items: [], next_cursor: null });
    renderPage();

    await waitFor(() => expect(screen.getByText(/Two runs make a comparison/)).toBeTruthy());
  });

  it("reports a failed archive load with its own retry, not the comparison's", async () => {
    apiMocks.listRuns.mockRejectedValue(new ApiErrorMock("backend asleep"));
    renderPage();

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("backend asleep"));
    // A list failure must not read as a comparison problem.
    expect(screen.queryByText(/Comparison issue/)).toBeNull();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("reloads the archive when the list retry is pressed", async () => {
    apiMocks.listRuns.mockRejectedValueOnce(new ApiErrorMock("backend asleep"));
    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy());

    apiMocks.listRuns.mockResolvedValue({ items: [], next_cursor: null });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(screen.getByText(/Two runs make a comparison/)).toBeTruthy());
    expect(apiMocks.listRuns).toHaveBeenCalledTimes(2);
  });

  it("falls back to a readable message when the failure is not an ApiError", async () => {
    apiMocks.listRuns.mockRejectedValue(new TypeError("network"));
    renderPage();

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Could not load saved runs."));
  });

  it("compares the two most recent runs automatically", async () => {
    apiMocks.listRuns.mockResolvedValue({ items: [listItem("a", "first"), listItem("b", "second")], next_cursor: null });
    apiMocks.compareRuns.mockResolvedValue(comparison());
    apiMocks.getRun.mockImplementation((runId: string) => Promise.resolve(detail(runId)));
    renderPage();

    await waitFor(() => expect(apiMocks.compareRuns).toHaveBeenCalledWith("a", "b"));
    await waitFor(() => expect(screen.getByText(/Shared creators/)).toBeTruthy());
  });

  /* One `error` slot served both fetches, so a failed comparison could render
   * the archive-failure panel that offers a retry which refetches the list --
   * the user was sent to fix the thing that was already working. */
  it("reports a failed comparison separately, with a retry that re-compares", async () => {
    apiMocks.listRuns.mockResolvedValue({ items: [listItem("a", "first"), listItem("b", "second")], next_cursor: null });
    apiMocks.compareRuns.mockRejectedValue(new ApiErrorMock("comparison exploded"));
    apiMocks.getRun.mockImplementation((runId: string) => Promise.resolve(detail(runId)));
    renderPage();

    await waitFor(() => expect(screen.getByText(/Comparison issue/)).toBeTruthy());
    expect(screen.getByRole("alert").textContent).toContain("comparison exploded");
    expect(apiMocks.listRuns).toHaveBeenCalledTimes(1);

    apiMocks.compareRuns.mockResolvedValue(comparison());
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(apiMocks.compareRuns).toHaveBeenCalledTimes(2));
    // The retry re-ran the comparison, not the archive.
    expect(apiMocks.listRuns).toHaveBeenCalledTimes(1);
  });

  it("shows a hint instead of a stale comparison when both selects hold one run", async () => {
    apiMocks.listRuns.mockResolvedValue({ items: [listItem("a", "first"), listItem("b", "second")], next_cursor: null });
    apiMocks.compareRuns.mockResolvedValue(comparison());
    apiMocks.getRun.mockImplementation((runId: string) => Promise.resolve(detail(runId)));
    renderPage();
    await waitFor(() => expect(screen.getByText(/Shared creators/)).toBeTruthy());

    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "b" } });

    await waitFor(() => expect(screen.getByText(/Choose two different runs/)).toBeTruthy());
    expect(screen.queryByText(/Shared creators/)).toBeNull();
  });
});
