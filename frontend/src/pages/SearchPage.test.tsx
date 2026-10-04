import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SearchPage } from "./SearchPage";
import type { Meta } from "../types";

const apiMocks = vi.hoisted(() => ({
  getMeta: vi.fn(),
  getRun: vi.fn(),
  createMatchJob: vi.fn(),
  downloadRun: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: apiMocks,
  ApiError: class ApiError extends Error {},
}));

const matchJobState = vi.hoisted(() => ({
  job: null as { status: string; stage: string; outcome: string | null; run_id: string | null } | null,
  error: null as string | null,
  isRunning: false,
  start: vi.fn(),
}));

function makeJob(stage: string, status = "running") {
  return { status, stage, outcome: null, run_id: null } as {
    status: string;
    stage: string;
    outcome: string | null;
    run_id: string | null;
  };
}

function sampleRun() {
  return {
    run_id: "run-1",
    created_at: "2026-01-01T00:00:00Z",
    brief: { goal: "high-energy at-home strength training", platform: "Any", audience: "", vibe: "" },
    summary: { n_results: 1, avg_match_pct: 70, n_strong: 1, n_weak: 0, avg_engagement_pct: 4, median_followers: 1000 },
    warnings: [],
    candidates: [],
    ranked: [],
  };
}

vi.mock("../hooks/useMatchJob", () => ({
  useMatchJob: () => ({
    job: matchJobState.job,
    error: matchJobState.error,
    isRunning: matchJobState.isRunning,
    start: matchJobState.start,
  }),
}));

function makeMeta(overrides: Partial<Meta> = {}): Meta {
  return {
    platforms: ["Any", "Instagram", "TikTok"],
    defaults: { goal: "", audience: "", vibe: "", top_k: 10, top_n: 5 },
    limits: {
      top_k_min: 1, top_k_max: 50, top_n_min: 1, top_n_max: 50,
      goal_min_length: 8, goal_max_length: 600,
      audience_max_length: 300, vibe_max_length: 500,
    },
    index: { status: "ready", count: 500, embedding_model: "gemini-embedding-001", embed_dimensions: 768 },
    ranking: { model: "gemini-2.5-flash-lite", fit_levels: ["strong", "partial", "weak", "unknown"] },
    ...overrides,
  } as Meta;
}

function renderPage() {
  return render(
    <MemoryRouter>
      <SearchPage />
    </MemoryRouter>,
  );
}

describe("SearchPage", () => {
  beforeEach(() => {
    apiMocks.getMeta.mockReset();
    apiMocks.getRun.mockReset();
    apiMocks.downloadRun.mockReset();
    matchJobState.job = null;
    matchJobState.error = null;
    matchJobState.isRunning = false;
    matchJobState.start.mockReset();
  });

  afterEach(() => cleanup());

  it("renders a brief form once meta loads", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    await waitFor(() => expect(screen.getByLabelText(/promoting/i)).toBeTruthy());
    expect(screen.getByRole("button", { name: /run match/i })).toBeTruthy();
  });

  /** The regression this guards.
   *
   * The deployed API can be an older build than this frontend. When it
   * omitted `defaults.goal`, the merge stored `undefined` and the very next
   * render called `.trim()` on it -- "Cannot read properties of undefined"
   * blanking the whole page. A skewed backend must degrade to an empty form.
   */
  it("does not crash when the backend omits defaults.goal", async () => {
    const meta = makeMeta();
    // Exactly the older deployed shape: no `goal` key at all.
    delete (meta.defaults as Partial<typeof meta.defaults>).goal;
    apiMocks.getMeta.mockResolvedValue(meta);

    renderPage();

    const textarea = await screen.findByLabelText(/promoting/i);
    expect(textarea).toBeTruthy();
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("does not crash when the whole defaults object is missing", async () => {
    const meta = makeMeta();
    (meta as { defaults?: unknown }).defaults = undefined;
    apiMocks.getMeta.mockResolvedValue(meta);

    renderPage();

    const textarea = await screen.findByLabelText(/promoting/i);
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("fills the textarea from a suggestion chip", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    const textarea = (await screen.findByLabelText(/promoting/i)) as HTMLTextAreaElement;
    const chip = screen.getAllByRole("button", { name: /sourdough|at-home|travel/i })[0];
    fireEvent.click(chip);

    expect(textarea.value.length).toBeGreaterThan(0);
  });

  it("blocks submit while the goal is present but too short", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    const textarea = (await screen.findByLabelText(/promoting/i)) as HTMLTextAreaElement;
    const submit = screen.getByRole("button", { name: /run match/i }) as HTMLButtonElement;

    fireEvent.change(textarea, { target: { value: "yoga" } });
    expect(submit.disabled).toBe(true);

    fireEvent.change(textarea, { target: { value: "high-energy at-home strength training" } });
    expect(submit.disabled).toBe(false);
  });

  /** Documents a gap rather than endorsing it: the guard is
   *  `goalLength > 0 && tooShort`, so a completely empty form can still submit
   *  and is rejected server-side with GOAL_TOO_SHORT. Pinning current
   *  behaviour so a deliberate fix is a visible test change. */
  it("currently allows submitting an empty goal, which the API rejects", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    await screen.findByLabelText(/promoting/i);
    const submit = screen.getByRole("button", { name: /run match/i }) as HTMLButtonElement;
    expect(submit.disabled).toBe(false);
  });

  it("shows the minimum-length hint only when the goal is too short", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    const textarea = (await screen.findByLabelText(/promoting/i)) as HTMLTextAreaElement;
    expect(screen.queryByText(/add a little more detail/i)).toBeNull();

    fireEvent.change(textarea, { target: { value: "yoga" } });
    expect(screen.getByText(/add a little more detail/i)).toBeTruthy();
  });

  it("surfaces a meta failure as a note rather than an empty page", async () => {
    apiMocks.getMeta.mockRejectedValue(new Error("API unreachable"));
    renderPage();

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByText(/connection issue/i)).toBeTruthy();
  });

  /* A meta failure used to be a dead end: the form is gated on `meta`, so the
   * note was the entire page and there was no way back without a reload. */
  it("offers a retry when metadata fails, and recovers on the second attempt", async () => {
    apiMocks.getMeta.mockRejectedValueOnce(new Error("API unreachable"));
    renderPage();

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(await screen.findByRole("button", { name: /run match/i })).toBeTruthy();
    expect(apiMocks.getMeta).toHaveBeenCalledTimes(2);
  });

  /* The range inputs each wrapped their caption and live value in one <label>,
   * so the accessible name was "Candidates retrieved10" and changed mid-drag. */
  it("names the depth sliders without their live value", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    const slider = await screen.findByRole("slider", { name: "Candidates retrieved" });
    expect(slider.getAttribute("aria-valuetext")).toBe("10 creators");
    expect(screen.getByRole("slider", { name: "Final shortlist" })).toBeTruthy();
  });

  it("names the goal field from its caption, not the character counter", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    const textarea = await screen.findByLabelText(/promoting/i);
    expect(textarea.getAttribute("aria-labelledby")).toBe("goal-label");
    expect(textarea.getAttribute("aria-describedby")).toBe("goal-count");

    fireEvent.change(textarea, { target: { value: "high-energy at-home strength training" } });
    expect(screen.getByRole("textbox", { name: "What are you promoting?" })).toBeTruthy();
  });

  /* Every job is created `queued` (manager.py:55) and only advances to
   * `embedding` when a worker picks it up, so on a free tier that is where
   * every user's first poll lands. The old `findIndex` returned -1 there and
   * the state machine had no branch for a negative index, so all four steps
   * rendered pending: four grey bars under "Waiting to start". */
  it("shows a live pipeline while the job is still queued", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    matchJobState.job = makeJob("queued");
    matchJobState.isRunning = true;
    const { container } = renderPage();

    await screen.findByLabelText(/promoting/i);
    expect(container.querySelectorAll(".pipeline-step-active")).toHaveLength(1);
    expect(container.querySelectorAll(".pipeline-step-pending")).toHaveLength(3);
  });

  it("does not fabricate completed steps for a stage it cannot place", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    matchJobState.job = makeJob("some_future_stage");
    matchJobState.isRunning = true;
    const { container } = renderPage();

    await screen.findByLabelText(/promoting/i);
    // An unknown stage must not read as "almost finished" (which clamping to
    // the last index produced) nor as "nothing is happening".
    expect(container.querySelectorAll(".pipeline-step-complete")).toHaveLength(0);
    expect(container.querySelectorAll(".pipeline-step-active")).toHaveLength(1);
  });

  it("marks every earlier step complete as the run advances", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    matchJobState.job = makeJob("ranking");
    matchJobState.isRunning = true;
    const { container } = renderPage();

    await screen.findByLabelText(/promoting/i);
    expect(container.querySelectorAll(".pipeline-step-complete")).toHaveLength(2);
    expect(container.querySelectorAll(".pipeline-step-active")).toHaveLength(1);
    expect(container.querySelectorAll(".pipeline-step-pending")).toHaveLength(1);
  });

  it("marks the last step as the failure point when a run dies", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    matchJobState.job = makeJob("failed", "failed");
    matchJobState.error = "The backend rejected the request.";
    const { container } = renderPage();

    await screen.findByLabelText(/promoting/i);
    expect(container.querySelectorAll(".pipeline-step-error")).toHaveLength(1);
    expect(container.querySelectorAll(".pipeline-step-active")).toHaveLength(0);
  });

  /* useMatchJob nulls `job` on failure, so `!job && !run` was true again after
   * a failed run and the first-run "Set a brief." empty state rendered
   * underneath the error -- reading as if the app had ignored the brief. */
  it("does not show the first-run empty state after a failed run", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();
    const textarea = await screen.findByLabelText(/promoting/i);
    fireEvent.change(textarea, { target: { value: "high-energy at-home strength training" } });

    // The hook reports the failure by clearing `job` and setting `error`.
    matchJobState.error = "The match request failed.";
    fireEvent.click(screen.getByRole("button", { name: /run match/i }));

    expect(await screen.findByText(/match request failed/i)).toBeTruthy();
    expect(screen.queryByText(/Set a brief\./)).toBeNull();
  });

  it("still shows the empty state before anything has been submitted", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    renderPage();

    await screen.findByLabelText(/promoting/i);
    expect(screen.getByText(/Set a brief\./)).toBeTruthy();
  });

  /* The blank-gap regression.
   *
   * The job reports success before its shortlist is fetched. The empty state
   * rendered only when there was no job AND no run, and the results only when a
   * run had loaded, so that window rendered nothing at all -- a bare gap under
   * the pipeline for as long as the fetch took. */
  it("shows a loading state between a successful job and the loaded run", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    // Resolved but never settled, so the run stays unloaded.
    apiMocks.getRun.mockReturnValue(new Promise(() => {}));
    // A job exists without the user having pressed submit in this render, so
    // the workspace must trust the job, not the local submit flag.
    matchJobState.job = { status: "succeeded", stage: "complete", outcome: "match", run_id: "run-1" };
    renderPage();

    await screen.findByLabelText(/promoting/i);

    expect(await screen.findByText("Loading your shortlist")).toBeTruthy();
    expect(screen.queryByText("Set a brief.")).toBeNull();
  });

  /* The shortlist fetch was keyed on [status, run_id, outcome] -- all stable
   * once the job succeeds -- so a failure was terminal. The run exists; the
   * only recovery was a new match, which spends embedding and ranking quota to
   * re-read a record already stored. */
  it("offers a retry when the completed run cannot be loaded", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    // A plain Error, not the mocked ApiError, so the page takes its generic
    // branch -- the point here is that a failure is retryable at all.
    apiMocks.getRun.mockRejectedValueOnce(new Error("boom"));
    matchJobState.job = makeJob("complete", "succeeded");
    matchJobState.job.run_id = "run-1";
    renderPage();

    expect(await screen.findByText(/could not load the completed run/i)).toBeTruthy();
    expect(screen.queryByText("Loading your shortlist")).toBeNull();

    // The retry must re-read the run rather than ask for a whole new match.
    apiMocks.getRun.mockResolvedValue(sampleRun());
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(screen.getByRole("heading", { name: /high-energy at-home strength training/ })).toBeTruthy());
    expect(apiMocks.getRun).toHaveBeenCalledTimes(2);
    expect(matchJobState.start).not.toHaveBeenCalled();
  });

  it("clears a previous export failure when a later download succeeds", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    apiMocks.getRun.mockResolvedValue(sampleRun());
    apiMocks.downloadRun.mockRejectedValueOnce(new Error("Could not export the run."));
    matchJobState.job = makeJob("complete", "succeeded");
    matchJobState.job.run_id = "run-1";
    renderPage();

    // Scoped to the results heading: a suggestion chip carries similar wording.
    await screen.findByRole("heading", { name: /high-energy at-home strength training/ });
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    expect(await screen.findByText(/could not export/i)).toBeTruthy();

    apiMocks.downloadRun.mockResolvedValue(undefined);
    const button = await screen.findByRole("button", { name: "Export CSV" });
    fireEvent.click(button);

    await waitFor(() => expect(screen.queryByText(/could not export/i)).toBeNull());
  });

  it("does not show the loading state once the run has arrived", async () => {
    apiMocks.getMeta.mockResolvedValue(makeMeta());
    apiMocks.getRun.mockResolvedValue({
      run_id: "run-1",
      created_at: "2026-01-01T00:00:00Z",
      brief: { goal: "yoga for beginners", platform: "Any", audience: "", vibe: "" },
      summary: { n_results: 1, avg_match_pct: 70, n_strong: 1, n_weak: 0, avg_engagement_pct: 4, median_followers: 1000 },
      warnings: [],
      candidates: [],
      ranked: [],
    });
    matchJobState.job = { status: "succeeded", stage: "complete", outcome: "match", run_id: "run-1" };
    renderPage();

    await screen.findByLabelText(/promoting/i);
    await waitFor(() => expect(screen.getByText(/yoga for beginners/)).toBeTruthy());
    expect(screen.queryByText("Loading your shortlist")).toBeNull();
  });
});
