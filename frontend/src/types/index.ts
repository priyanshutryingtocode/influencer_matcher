export type FitLevel = "strong" | "partial" | "weak" | "unknown";
export type RankingSource = "llm" | "filled" | "fallback";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Brief {
  niche: string;
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
  progress: Record<string, number>;
  run_id: string | null;
  outcome: "match" | "no_results" | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreatorSnapshot {
  id: number;
  creator_key: string;
  handle: string;
  name: string;
  niche: string;
  secondary_niches: string[];
  platform: string;
  city: string;
  country: string;
  language: string;
  followers: number;
  engagement_pct: number;
  average_views: number;
  average_likes: number;
  average_comments: number;
  verified: boolean;
  posts_per_week: number;
  account_age_years: number;
  content_style: string;
  audience_age: string;
  audience_gender: string;
  audience_country: string;
  brand_collaborations: string[];
  tags: string[];
  bio: string;
  similarity: number | null;
}

export interface RankedCreator {
  id: number;
  creator_key: string;
  rank: number;
  fit: FitLevel;
  source: RankingSource;
  rationale: string;
  evidence: string[];
}

export interface Warning {
  code: string;
  severity: "info" | "warning" | "error";
  message: string;
  details: Record<string, unknown>;
}

export interface RunSummary {
  n_results: number;
  n_ranked_on_niche: number;
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
  schema_version: string;
  run_id: string;
  created_at: string;
  brief: Brief;
  params: MatchParams;
  pipeline: Record<string, unknown>;
  warnings: Warning[];
  summary: RunSummary;
  candidates: CreatorSnapshot[];
  ranked: RankedCreator[];
}

export interface Comparison {
  run_ids: string[];
  summary_a: RunSummary;
  summary_b: RunSummary;
  shared_creators: Array<{ id: number; creator_key: string; handle: string }>;
}

export interface Meta {
  niches: string[];
  platforms: string[];
  defaults: {
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
    audience_max_length: number;
    vibe_max_length: number;
  };
  index: {
    status: "ready" | "unavailable";
    count: number;
    embedding_model: string;
    embed_dimensions: number;
  };
  ranking: {
    model: string;
    fit_levels: FitLevel[];
  };
}
