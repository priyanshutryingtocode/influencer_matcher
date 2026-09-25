import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultCard } from "./ResultCard";
import type { Brief, CreatorSnapshot, RankedCreator } from "../types";

const brief: Brief = { niche: "Fitness", platform: "TikTok", audience: "millennials", vibe: "high energy" };
const creator: CreatorSnapshot = {
  id: 1,
  creator_key: "TikTok:@fit1",
  handle: "@fit1",
  name: "Fit One",
  niche: "Fitness",
  secondary_niches: [],
  platform: "TikTok",
  city: "Austin",
  country: "USA",
  language: "English",
  followers: 10_000,
  engagement_pct: 5,
  average_views: 20_000,
  average_likes: 500,
  average_comments: 20,
  verified: true,
  posts_per_week: 4,
  account_age_years: 3,
  content_style: "Educational",
  audience_age: "18-24",
  audience_gender: "55% Female",
  audience_country: "USA",
  brand_collaborations: ["Nike"],
  tags: ["gym"],
  bio: "Lifting daily.",
  similarity: 0.91,
};
const entry: RankedCreator = {
  id: 1,
  creator_key: "TikTok:@fit1",
  rank: 1,
  fit: "strong",
  source: "llm",
  rationale: "Direct niche match.",
  evidence: ["Exact niche match"],
};

describe("ResultCard", () => {
  it("renders a ranked ledger row with provenance", () => {
    render(<ResultCard creator={creator} entry={entry} brief={brief} />);
    expect(screen.getByText("01")).toBeTruthy();
    expect(screen.getByText("@fit1")).toBeTruthy();
    expect(screen.getByText("Gemini ranked")).toBeTruthy();
    expect(screen.getByText("Evidence")).toBeTruthy();
  });
});
