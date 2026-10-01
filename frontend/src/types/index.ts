export type FitLevel = "strong" | "partial" | "weak" | "unknown";
export type RankingSource = "llm" | "llm_unverified" | "filled" | "fallback";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Brief {
  goal: string;
  platform: string;
  audience: string;
  vibe: string;
}

export interface MatchParams {
  top_k: number;
  top_n: number;
}

export interface MatchJob {
  job_id: string;
  status: JobStatus;
  stage: string;
  run_id: string | null;
  outcome: "match" | "no_results" | null;
  error: string | null;
}

export interface Grounding {
  /** Key of a profile field on the stored creator. */
  field: string;
  /** Verbatim substring of that field, checked server-side before display. */
  quote: string;
}

export interface CreatorSnapshot {
  id: number;
  creator_key: string;
  handle: string;
  name: string;
  platform: string;
  city: string;
  language: string;
  followers: number;
  engagement_pct: number;
  verified: boolean;
  content_style: string;
  audience_age: string;
  audience_gender: string;
  brand_collaborations: string[];
  tags: string[];
  similarity: number | null;
  /** Stored and displayable, but not quotable in a reason: these are not in
   *  the embedded profile text, so retrieval never searched on them. */
  reach_ratio: number;
  sponsored_ratio: number;
  growth_trend: string;
  audience_top_countries: string[];
}

export interface RankedCreator {
  id: number;
  creator_key: string;
  rank: number;
  fit: FitLevel;
  source: RankingSource;
  rationale: string;
  evidence: string[];
  /** Citations the server verified against the stored profile. */
  grounding: Grounding[];
  /** Why the model did not rank this entry. Prefixed with "daily_quota:" when
   *  the free ranking budget is spent, which is a different situation from an
   *  outage and needs different advice. */
  fallback_reason: string;
}

export interface Warning {
  code: string;
  severity: "info" | "warning" | "error";
  message: string;
  details: Record<string, unknown>;
}

export interface RunSummary {
  n_results: number;
  avg_match_pct: number;
  n_strong: number;
  n_weak: number;
  avg_engagement_pct: number;
  median_followers: number;
}

export interface RunListItem {
  run_id: string;
  created_at: string;
  brief: Brief;
  n_results: number;
  n_strong: number;
  has_warnings: boolean;
}

export interface RunListResponse {
  items: RunListItem[];
  next_cursor: string | null;
}

export interface RunDetail {
  run_id: string;
  created_at: string;
  brief: Brief;
  warnings: Warning[];
  summary: RunSummary;
  candidates: CreatorSnapshot[];
  ranked: RankedCreator[];
}

export interface Comparison {
  summary_a: RunSummary;
  summary_b: RunSummary;
  shared_creators: Array<{ id: number; creator_key: string; handle: string }>;
}

export interface Meta {
  platforms: string[];
  defaults: {
    goal: string;
    audience: string;
    vibe: string;
    top_k: number;
    top_n: number;
  };
  limits: {
    top_k_min: number;
    top_k_max: number;
    top_n_min: number;
    top_n_max: number;
    goal_min_length: number;
    goal_max_length: number;
    audience_max_length: number;
    vibe_max_length: number;
  };
  index: {
    status: "ready" | "unavailable" | "reindex_required";
    count: number;
  };
}
