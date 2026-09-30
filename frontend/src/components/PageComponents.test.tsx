import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorNote } from "./ErrorNote";
import { PageIntro } from "./PageIntro";
import { ResultList } from "./ResultList";
import { RunContext } from "./RunContext";
import type { Brief, CreatorSnapshot, RankedCreator } from "../types";

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
    country: "USA",
    language: "English",
    followers: 1000 * id,
    engagement_pct: 4,
    average_views: 1,
    average_likes: 1,
    average_comments: 1,
    verified: false,
    posts_per_week: 2,
    account_age_years: 2,
    content_style: "Educational",
    audience_age: "18-24",
    audience_gender: "50% Female",
    audience_country: "USA",
    brand_collaborations: [],
    tags: [],
    bio: "",
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

describe("RunContext", () => {
  it("summarises the brief and triggers the export", () => {
    const onExport = vi.fn();
    render(<RunContext brief={brief} createdAt="2026-09-27T10:00:00Z" label="Shortlist" onExport={onExport} />);

    expect(screen.getByText(/^Shortlist \//)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("high-energy strength training for beginners");
    expect(screen.getByText(/TikTok/)).toBeTruthy();

    screen.getByRole("button", { name: "Export CSV" }).click();
    expect(onExport).toHaveBeenCalledOnce();
  });

  it("shows the free-text goal and omits empty optional refinements", () => {
    render(
      <RunContext
        brief={{ goal: "at-home strength training for beginners", platform: "Any", audience: "", vibe: "" }}
        createdAt="2026-09-27T10:00:00Z"
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
        brief={{ goal: "a slow-fashion label", platform: "Instagram", audience: "Gen Z", vibe: "warm" }}
        createdAt="2026-09-27T10:00:00Z"
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
