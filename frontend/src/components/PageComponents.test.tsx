import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";
import { PageIntro } from "./PageIntro";
import { ResultList } from "./ResultList";
import { ErrorNote, InfoNote } from "./SystemNote";
import { RunContext } from "./RunContext";
import type { Brief, CreatorSnapshot, RankedCreator, RunDetail } from "../types";

afterEach(cleanup);

const brief: Brief = { goal: "high-energy strength training for beginners", platform: "TikTok", audience: "", vibe: "" };

function creator(id: number, key: string): CreatorSnapshot {
  return {
    id,
    creator_key: key,
    handle: key.split(":")[1],
    name: "",
    platform: "TikTok",
    city: "Austin",
    language: "English",
    followers: 1000 * id,
    engagement_pct: 4,
    verified: false,
    content_style: "Educational",
    audience_age: "18-24",
    audience_gender: "50% Female",
    brand_collaborations: [],
    tags: [],
    similarity: 0.5,
    reach_ratio: 0.2,
    sponsored_ratio: 0.05,
    growth_trend: "steady",
    audience_top_countries: ["USA"],
  };
}

function ranked(id: number, key: string, rank: number): RankedCreator {
  return { id, creator_key: key, rank, fit: "strong", source: "llm", rationale: "", evidence: [], grounding: [], fallback_reason: "" };
}

describe("PageIntro", () => {
  it("renders the eyebrow, title and description", () => {
    render(<PageIntro eyebrow="New match" title="Search" description="A brief in, a list out." />);

    expect(screen.getByText("New match")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: "Search" })).toBeTruthy();
    expect(screen.getByText("A brief in, a list out.")).toBeTruthy();
  });

  it("omits the meta slot when nothing needs saying", () => {
    const { container } = render(<PageIntro eyebrow="e" title="t" description="d" />);

    expect(container.querySelector(".page-intro-meta")).toBeNull();
  });

  it("renders a single meta item when given one", () => {
    const { container } = render(
      <PageIntro eyebrow="e" title="t" description="d" meta={<span>1,000 creators</span>} />,
    );

    expect(container.querySelectorAll(".page-intro-meta")).toHaveLength(1);
    expect(screen.getByText("1,000 creators")).toBeTruthy();
  });
});

describe("ErrorNote", () => {
  it("announces itself as an alert with its own title", () => {
    render(<ErrorNote title="Archive issue">Could not load runs.</ErrorNote>);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Archive issue");
    expect(alert.textContent).toContain("Could not load runs.");
  });
});

const runFor = (brief: Brief, createdAt = "2026-09-27T10:00:00Z") =>
  ({ run_id: "r1", brief, created_at: createdAt, candidates: [], ranked: [], summary: {
    n_results: 0, avg_match_pct: 0, n_strong: 0, n_weak: 0,
    avg_engagement_pct: 0, median_followers: 0,
  }, warnings: [] }) as unknown as RunDetail;

describe("RunContext", () => {
  it("summarises the brief and triggers the export", () => {
    const onExport = vi.fn();
    render(<RunContext run={runFor(brief)} label="Shortlist" onExport={onExport} />);

    expect(screen.getByText(/^Shortlist \//)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("high-energy strength training for beginners");
    expect(screen.getByText(/TikTok/)).toBeTruthy();

    screen.getByRole("button", { name: "Export CSV" }).click();
    expect(onExport).toHaveBeenCalledOnce();
  });

  /* A double-click used to fire two downloads: the button was never disabled
   * and the page held no in-flight state for it. */
  it("disables the export button while a download is in flight", () => {
    const onExport = vi.fn();
    render(<RunContext run={runFor(brief)} label="Shortlist" exporting onExport={onExport} />);

    const button = screen.getByRole("button", { name: "Exporting..." });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.getAttribute("aria-busy")).toBe("true");

    fireEvent.click(button);
    expect(onExport).not.toHaveBeenCalled();
  });

  it("offers an action slot on an error note", () => {
    const onRetry = vi.fn();
    render(
      <ErrorNote title="Connection issue" action={<button type="button" onClick={onRetry}>Retry</button>}>
        The backend did not respond.
      </ErrorNote>,
    );

    expect(screen.getByText("The backend did not respond.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  /* The tone used to be a per-call-site decision, so a failure could ship as
   * role="status" and a piece of guidance as role="alert". One place decides
   * now, and these pin the mapping. */
  it("announces a failure and treats guidance as non-urgent", () => {
    const failure = render(
      <ErrorNote title="Request issue">The backend did not respond.</ErrorNote>,
    );
    expect(failure.getByRole("alert")).toBeTruthy();
    expect(failure.container.querySelector(".system-note-error")).toBeTruthy();
    failure.unmount();

    const info = render(<InfoNote title="No overlap">These runs do not share a creator.</InfoNote>);
    expect(info.container.querySelector(".system-note-info")).toBeTruthy();
    expect(info.queryByRole("alert")).toBeNull();
    expect(info.getByRole("status")).toBeTruthy();
  });

  it("shows the free-text goal and omits empty optional refinements", () => {
    render(
      <RunContext
        run={runFor({ goal: "at-home strength training for beginners", platform: "Any", audience: "", vibe: "" })}
        label="Run detail"
        onExport={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: /at-home strength training/ })).toBeTruthy();
    expect(screen.getByText(/Any/)).toBeTruthy();
    expect(screen.queryByText(/General audience/)).toBeNull();
    expect(screen.queryByText(/Versatile tone/)).toBeNull();
  });

  it("lists audience and tone when the brief supplied them", () => {
    render(
      <RunContext
        run={runFor({ goal: "a slow-fashion label", platform: "Instagram", audience: "Gen Z", vibe: "warm" })}
        label="Run detail"
        onExport={vi.fn()}
      />,
    );

    expect(screen.getByText(/Gen Z/)).toBeTruthy();
    expect(screen.getByText(/warm/)).toBeTruthy();
  });
});

describe("ResultList", () => {
  it("renders one row per ranked entry", () => {
    render(
      <ResultList
        run={{
          brief,
          candidates: [creator(1, "TikTok:@a"), creator(2, "TikTok:@b")],
          ranked: [ranked(1, "TikTok:@a", 1), ranked(2, "TikTok:@b", 2)],
        }}
      />,
    );

    expect(screen.getByText("@a")).toBeTruthy();
    expect(screen.getByText("@b")).toBeTruthy();
  });

  it("skips an entry whose creator snapshot is missing", () => {
    render(
      <ResultList
        run={{ brief, candidates: [creator(1, "TikTok:@a")], ranked: [ranked(1, "TikTok:@a", 1), ranked(9, "TikTok:@gone", 2)] }}
      />,
    );

    expect(screen.getByText("@a")).toBeTruthy();
    expect(screen.queryByText("@gone")).toBeNull();
  });

  /* An empty ranked list, or one where every snapshot failed the join, used to
   * render a bordered box with nothing inside it. */
  it("explains an empty shortlist instead of rendering an empty box", () => {
    render(<ResultList run={{ brief, candidates: [], ranked: [] }} />);

    expect(screen.getByText(/no creators in this shortlist/i)).toBeTruthy();
  });

  it("distinguishes a missing snapshot from a genuinely empty shortlist", () => {
    render(
      <ResultList run={{ brief, candidates: [], ranked: [ranked(9, "TikTok:@gone", 1)] }} />,
    );

    expect(screen.getByText(/creator details are no longer available/i)).toBeTruthy();
  });

  /* The four empty states were open-coded with drifting structure. One now
   * renders all of them, and this pins the optional parts actually staying
   * optional -- a missing index or body must not leave a blank tag behind. */
  it("omits the index and body when they are not given", () => {
    const { container } = render(<EmptyState title="Opening shortlist" busy />);

    expect(screen.getByRole("heading", { name: "Opening shortlist" })).toBeTruthy();
    expect(container.querySelector(".empty-index")).toBeNull();
    expect(container.querySelector(".empty-steps")).toBeNull();
  });

  it("renders the index, body and steps it is given, and marks a busy state", () => {
    const { container } = render(
      <EmptyState index="READY" title="Set a brief." body="Retrieval stays visible." steps={["Prepare", "Rank"]} />,
    );

    expect(container.querySelector(".empty-index")?.textContent).toBe("READY");
    expect(screen.getByText("Retrieval stays visible.")).toBeTruthy();
    expect(container.querySelectorAll(".empty-steps span")).toHaveLength(2);
    expect(container.querySelector(".empty-state")?.getAttribute("aria-busy")).toBeNull();
  });

  it("announces a busy state without over-announcing a settled one", () => {
    const { container, unmount } = render(<EmptyState title="Opening" busy />);
    expect(container.querySelector(".empty-state")?.getAttribute("aria-busy")).toBe("true");
    expect(container.querySelector(".empty-state")?.getAttribute("aria-live")).toBe("polite");
    unmount();

    const settled = render(<EmptyState index="SELECT" title="Choose a saved run" />);
    expect(settled.container.querySelector(".empty-state")?.getAttribute("aria-busy")).toBeNull();
  });

  it("highlights only the creators named by the key set", () => {
    const { container } = render(
      <ResultList
        run={{
          brief,
          candidates: [creator(1, "TikTok:@a"), creator(2, "TikTok:@b")],
          ranked: [ranked(1, "TikTok:@a", 1), ranked(2, "TikTok:@b", 2)],
        }}
        highlightKeys={new Set(["TikTok:@b"])}
      />,
    );

    const highlighted = container.querySelectorAll(".result-row-highlight");
    expect(highlighted).toHaveLength(1);
    expect(highlighted[0].textContent).toContain("@b");
  });
});
