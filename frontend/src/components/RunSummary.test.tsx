import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SummaryMetrics, formatFollowers } from "./RunSummary";

describe("RunSummary", () => {
  it("renders a compact quality strip", () => {
    render(
      <SummaryMetrics
        summary={{
          n_results: 5,
          n_ranked_on_niche: 4,
          n_strong: 3,
          n_weak: 1,
          avg_engagement_pct: 4.2,
          median_followers: 12_000,
        }}
      />,
    );
    expect(screen.getByText("3/5")).toBeTruthy();
    expect(screen.getByText("4.2%")).toBeTruthy();
    expect(screen.getByText("12K")).toBeTruthy();
  });

  it("formats follower counts", () => {
    expect(formatFollowers(999)).toBe("999");
    expect(formatFollowers(12_000)).toBe("12K");
    expect(formatFollowers(1_250_000)).toBe("1.3M");
  });
});
