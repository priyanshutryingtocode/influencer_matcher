import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ResultCard } from "./ResultCard";
import type { Brief, CreatorSnapshot, RankedCreator } from "../types";

const brief: Brief = { goal: "high-energy strength training for beginners", platform: "TikTok", audience: "", vibe: "" };
const creator: CreatorSnapshot = {
  id: 1,
  creator_key: "TikTok:@fit1",
  handle: "@fit1",
  name: "Fit One",
  platform: "TikTok",
  city: "Austin",
  language: "English",
  followers: 10_000,
  engagement_pct: 5,
  verified: true,
  content_style: "Educational",
  audience_age: "18-24",
  audience_gender: "55% Female",
  brand_collaborations: ["Nike"],
  tags: ["gym", "lifting", "protein", "extra", "cut"],
  similarity: 0.91,
  reach_ratio: 0.62,
  sponsored_ratio: 0.08,
  growth_trend: "rising",
  audience_top_countries: ["USA", "Canada"],
};
const entry: RankedCreator = {
  id: 1,
  creator_key: "TikTok:@fit1",
  rank: 1,
  fit: "strong",
  source: "llm",
  rationale: "Trains at home for beginners.",
  evidence: ["Brief terms found in profile: gym"],
  grounding: [{ field: "tags", quote: "gym" }],
  fallback_reason: "",
};

describe("ResultCard", () => {
  afterEach(cleanup);

  it("renders the rank, identity, fit and evidence", () => {
    render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(screen.getByText("01")).toBeTruthy();
    expect(screen.getByText("@fit1")).toBeTruthy();
    expect(screen.getByText("Strong")).toBeTruthy();
    expect(screen.getByText("Profile details")).toBeTruthy();
  });

  it("puts the similarity beside the fit label instead of a third metric", () => {
    render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(screen.getByText("91.0%")).toBeTruthy();
    expect(screen.queryByText("Match")).toBeNull();
  });

  it("does not label rows that were normally ranked", () => {
    render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(screen.queryByText("Gemini ranked")).toBeNull();
  });

  it("shows the reason's citations beside the field they came from", () => {
    const { container } = render(
      <ResultCard
        creator={creator}
        entry={{ ...entry, grounding: [
          { field: "tags", quote: "gym" },
          { field: "brand_collaborations", quote: "Nike" },
        ] }}
        brief={brief}
      />,
    );

    expect(screen.getByText("Topics")).toBeTruthy();
    expect(screen.getByText("Brand partners")).toBeTruthy();
    // The quote must be visible without expanding anything.
    expect(container.textContent).toContain("Nike");
  });

  it("marks a reason the server could not confirm", () => {
    render(
      <ResultCard
        creator={creator}
        entry={{ ...entry, source: "llm_unverified", grounding: [], rationale: "Retrieved for profile similarity." }}
        brief={brief}
      />,
    );

    expect(screen.getByText("Reason not confirmed")).toBeTruthy();
    expect(screen.getByText("Retrieved for profile similarity.")).toBeTruthy();
  });

  it("explains a row that came from a fallback", () => {
    render(<ResultCard creator={creator} entry={{ ...entry, source: "fallback" }} brief={brief} />);

    expect(screen.getByText("Retrieval fallback")).toBeTruthy();
  });

  it("omits missing attributes instead of printing filler text", () => {
    const sparse: CreatorSnapshot = {
      ...creator,
      city: "",
      content_style: "",
      language: "",
      audience_age: "",
      audience_gender: "",
      brand_collaborations: [],
      tags: [],
    };
    const { container } = render(<ResultCard creator={sparse} entry={entry} brief={brief} />);

    expect(container.textContent).not.toMatch(/unavailable|unknown/i);
  });

  it("caps the tag list so the row stays scannable", () => {
    render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(screen.getByText(/gym\s+·\s+lifting\s+·\s+protein/)).toBeTruthy();
    expect(screen.queryByText(/extra/)).toBeNull();
  });

  it("shows reach, sponsorship and growth in the details panel", () => {
    const { container } = render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(container.textContent).toContain("Sponsored: 8%");
    expect(container.textContent).toContain("Growth: rising");
  });

  /* Reach as a share of followers used to live only under "Profile details" --
   * the one check the row exists to answer, behind a click. */
  it("surfaces reach rate without opening anything", () => {
    const { container } = render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(screen.getByText("Reach rate")).toBeTruthy();
    expect(container.textContent).toContain("62%");
    expect(container.textContent).toContain("of followers");
    // No longer duplicated in the disclosure.
    expect(container.textContent).not.toContain("Reach vs followers");
  });

  it("omits signals that are absent rather than showing zero", () => {
    const { container } = render(
      <ResultCard
        creator={{ ...creator, reach_ratio: 0, sponsored_ratio: 0, growth_trend: "", audience_top_countries: [] }}
        entry={entry}
        brief={brief}
      />,
    );

    expect(screen.queryByText("Reach rate")).toBeNull();
    expect(container.textContent).not.toContain("Sponsored");
    expect(container.textContent).not.toContain("Growth:");
  });

  it("renders a dash when similarity is unknown", () => {
    render(<ResultCard creator={{ ...creator, similarity: null }} entry={entry} brief={brief} />);

    expect(screen.getByText("—")).toBeTruthy();
  });
   /* The reason reached this component and was dropped. The backend persists it
   * precisely because a spent daily quota and a truncated response call for
   * different advice from the reader. */
  it("shows why a row fell back, without the machine-readable tag", () => {
    render(
      <ResultCard
        creator={creator}
        entry={{ ...entry, source: "fallback", fallback_reason: "daily_quota: The counter resets at midnight Pacific." }}
        brief={brief}
      />,
    );

    expect(screen.getByText("Retrieval fallback")).toBeTruthy();
    expect(screen.getByText("The counter resets at midnight Pacific.")).toBeTruthy();
    expect(screen.queryByText(/daily_quota/)).toBeNull();
  });

  it("leaves an untagged fallback reason intact", () => {
    render(
      <ResultCard
        creator={creator}
        entry={{ ...entry, source: "fallback", fallback_reason: "Response stopped early: finish_reason=MAX_TOKENS" }}
        brief={brief}
      />,
    );

    expect(screen.getByText("Response stopped early: finish_reason=MAX_TOKENS")).toBeTruthy();
  });

  it("omits the reason when a normally ranked row has none", () => {
    const { container } = render(<ResultCard creator={creator} entry={entry} brief={brief} />);

    expect(container.querySelector(".source-detail")).toBeNull();
  });

  /* Platform is a hard filter on a filtered run, so naming it on every row is
   * noise. On an "Any" brief it is the only thing telling you which platform a
   * creator is on. */
  it("shows the platform on an Any brief and omits it when filtered", () => {
    const { container, rerender } = render(
      <ResultCard creator={creator} entry={entry} brief={{ ...brief, platform: "Any" }} />,
    );
    expect(container.textContent).toContain("TikTok · Austin · Educational");

    rerender(<ResultCard creator={creator} entry={entry} brief={brief} />);
    expect(container.textContent).not.toContain("TikTok · Austin");
  });

  it("names the similarity metric for assistive tech, not just a bare percent", () => {
    render(<ResultCard creator={creator} entry={entry} brief={brief} />);

      expect(screen.getByText("Cosine similarity to your brief: 91.0%")).toBeTruthy();
      // The visible number is hidden from AT, so the value is not read twice.
      expect(screen.getByText("91.0%").getAttribute("aria-hidden")).toBe("true");
  });
});
