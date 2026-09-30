import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SIMILARITY_EXPLANATION, SummaryMetrics, formatFollowers } from "./RunSummary";

describe("RunSummary", () => {
  afterEach(() => cleanup());

  it("renders a compact quality strip", () => {
    render(
      <SummaryMetrics
        summary={{
          n_results: 5,
          avg_match_pct: 68.4,
          n_strong: 3,
          n_weak: 1,
          avg_engagement_pct: 4.2,
          median_followers: 12_000,
        }}
      />,
    );
    expect(screen.getByText("3/5")).toBeTruthy();
    expect(screen.getByText("68.4%")).toBeTruthy();
    expect(screen.getByText("4.2%")).toBeTruthy();
    expect(screen.getByText("12K")).toBeTruthy();
  });

  it("labels the cosine score as similarity rather than a match", () => {
    render(
      <SummaryMetrics
        summary={{
          n_results: 5,
          avg_match_pct: 68.4,
          n_strong: 3,
          n_weak: 1,
          avg_engagement_pct: 4.2,
          median_followers: 12_000,
        }}
      />,
    );
    expect(screen.getByText("Avg similarity")).toBeTruthy();
    expect(screen.getByText("cosine vs. brief")).toBeTruthy();
    // "Avg match" reads as a fit score, which the number is not.
    expect(screen.queryByText("Avg match")).toBeNull();
    expect(screen.queryByText("semantic score")).toBeNull();
  });

  it("explains what the similarity number does and does not mean", () => {
    render(
      <SummaryMetrics
        summary={{
          n_results: 5,
          avg_match_pct: 68.4,
          n_strong: 3,
          n_weak: 1,
          avg_engagement_pct: 4.2,
          median_followers: 12_000,
        }}
      />,
    );
    const labelled = screen.getByText("Avg similarity");
    expect(labelled.getAttribute("title")).toBe(SIMILARITY_EXPLANATION);
    expect(SIMILARITY_EXPLANATION).toMatch(/not a fit score/i);
  });

  it("formats follower counts", () => {
    expect(formatFollowers(999)).toBe("999");
    expect(formatFollowers(12_000)).toBe("12K");
    expect(formatFollowers(1_250_000)).toBe("1.3M");
  });
});
