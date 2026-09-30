import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SearchPage } from "./SearchPage";
import type { Meta } from "../types";

const apiMocks = vi.hoisted(() => ({
  getMeta: vi.fn(),
  getRun: vi.fn(),
  createMatchJob: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: apiMocks,
  ApiError: class ApiError extends Error {},
}));

const vi_mock_useMatchJob = vi.hoisted(() => ({
  useMatchJob: () => ({ job: null, error: null, isRunning: false, start: vi.fn() }),
}));

vi.mock("../hooks/useMatchJob", () => vi_mock_useMatchJob);

function makeMeta(overrides: Partial<Meta> = {}): Meta {
  return {
    platforms: ["Any", "Instagram", "TikTok"],
    defaults: { goal: "", audience: "Gen Z", vibe: "warm", top_k: 10, top_n: 5 },
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
});
