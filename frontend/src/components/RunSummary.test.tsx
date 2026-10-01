import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SIMILARITY_EXPLANATION, SummaryMetrics, formatFollowers } from "./RunSummary";

function sampleSummary() {
  return {
    n_results: 5,
    avg_match_pct: 68.4,
    n_strong: 3,
    n_weak: 1,
    avg_engagement_pct: 4.2,
    median_followers: 12_000,
  };
}

describe("RunSummary", () => {
  afterEach(() => cleanup());

  it("renders a compact quality strip", () => {
    render(<SummaryMetrics summary={sampleSummary()} />);
    expect(screen.getByText("3/5")).toBeTruthy();
    expect(screen.getByText("68.4%")).toBeTruthy();
    expect(screen.getByText("4.2%")).toBeTruthy();
    expect(screen.getByText("12K")).toBeTruthy();
  });

  it("labels the cosine score as similarity rather than a match", () => {
    render(<SummaryMetrics summary={sampleSummary()} />);
    expect(screen.getByRole("button", { name: /Avg similarity/ })).toBeTruthy();
    expect(screen.getByText("cosine vs. brief")).toBeTruthy();
    // "Avg match" reads as a fit score, which the number is not.
    expect(screen.queryByText("Avg match")).toBeNull();
    expect(screen.queryByText("semantic score")).toBeNull();
  });

  /* The explanation used to live in a title= attribute on the <dt>, which no
   * keyboard user could reach and no touch user could see at all. These pin the
   * disclosure so the caveat cannot quietly go back to being hover-only. */
  it("keeps the similarity caveat collapsed until it is asked for", () => {
    render(<SummaryMetrics summary={sampleSummary()} />);
    const toggle = screen.getByRole("button", { name: /Avg similarity/ });

    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(toggle.getAttribute("title")).toBeNull();
    expect(screen.queryByText(SIMILARITY_EXPLANATION)).toBeNull();
  });

  it("reveals the caveat on demand and says what it does not mean", () => {
    render(<SummaryMetrics summary={sampleSummary()} />);
    const toggle = screen.getByRole("button", { name: /Avg similarity/ });

    fireEvent.click(toggle);

    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    const body = screen.getByText(SIMILARITY_EXPLANATION);
    expect(toggle.getAttribute("aria-controls")).toBe(body.id);
    expect(SIMILARITY_EXPLANATION).toMatch(/not a fit score/i);
  });

  /* The strip is now built from a cell list, so the labels are data rather
   * than markup. These pin the copy and the one cell that is special. */
  it("renders every metric label, with exactly one disclosure", () => {
    const { container } = render(<SummaryMetrics summary={sampleSummary()} />);

    for (const label of ["Quality", "Avg similarity", "Avg engagement", "Median reach", "Needs review"]) {
      expect(container.textContent).toContain(label);
    }
    expect(container.querySelectorAll(".summary-explain-toggle")).toHaveLength(1);
  });

  it("keeps the strong-fit count visually primary", () => {
    const { container } = render(<SummaryMetrics summary={sampleSummary()} />);

    expect(container.querySelector(".summary-item-primary")).toBeTruthy();
    expect(container.querySelector(".summary-item-primary")?.textContent).toContain("3/5");
  });

  it("formats follower counts", () => {
    expect(formatFollowers(999)).toBe("999");
    expect(formatFollowers(12_000)).toBe("12K");
    expect(formatFollowers(1_250_000)).toBe("1.3M");
  });
});
