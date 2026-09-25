from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src import config

FitLevel = Literal["strong", "partial", "weak", "unknown"]
RankingSource = Literal["llm", "filled", "fallback"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class BriefPayload(BaseModel):
    niche: str = Field(min_length=1, max_length=100)
    platform: str = Field(default="Any", min_length=1, max_length=50)
    audience: str = Field(default="Gen Z", max_length=300)
    vibe: str = Field(default="", max_length=500)

    def to_domain(self):
        from src.models import Brief

        return Brief(
            niche=self.niche,
            platform=self.platform,
            audience=self.audience,
            vibe=self.vibe,
        )


class MatchParams(BaseModel):
    top_k: int = Field(default=config.DEFAULT_TOP_K_RETRIEVAL, ge=1, le=config.MAX_TOP_K)
    top_n: int = Field(default=config.DEFAULT_TOP_N_RANKED, ge=1, le=config.MAX_TOP_K)

    @model_validator(mode="before")
    @classmethod
    def apply_default_top_n(cls, data):
        if isinstance(data, dict) and "top_n" not in data:
            top_k = data.get("top_k", config.DEFAULT_TOP_K_RETRIEVAL)
            if isinstance(top_k, int):
                return {**data, "top_n": min(config.DEFAULT_TOP_N_RANKED, top_k)}
        return data

    @model_validator(mode="after")
    def validate_shortlist_size(self):
        if self.top_n > self.top_k:
            raise ValueError("top_n cannot be greater than top_k")
        return self


class MatchJobRequest(BaseModel):
    brief: BriefPayload
    params: MatchParams = Field(default_factory=MatchParams)


class MatchJobResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    stage: str
    progress: dict[str, Any] = Field(default_factory=dict)
    run_id: UUID | None = None
    outcome: Literal["match", "no_results"] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class CreatorSnapshot(BaseModel):
    id: int
    creator_key: str
    handle: str
    name: str = ""
    niche: str
    secondary_niches: list[str] = Field(default_factory=list)
    platform: str
    city: str
    country: str = ""
    language: str = ""
    followers: int
    engagement_pct: float
    average_views: int = 0
    average_likes: int = 0
    average_comments: int = 0
    verified: bool = False
    posts_per_week: int = 0
    account_age_years: int = 0
    content_style: str = ""
    audience_age: str = ""
    audience_gender: str = ""
    audience_country: str = ""
    brand_collaborations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    bio: str = ""
    similarity: float | None = None


class RankedCreator(BaseModel):
    id: int
    creator_key: str
    rank: int
    fit: FitLevel
    source: RankingSource
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)


class Warning(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    n_results: int
    n_ranked_on_niche: int
    n_strong: int
    n_weak: int
    avg_engagement_pct: float
    median_followers: int


class RunListItem(BaseModel):
    run_id: UUID
    created_at: datetime
    brief: BriefPayload
    n_results: int
    n_strong: int
    has_warnings: bool


class RunListResponse(BaseModel):
    items: list[RunListItem]
    next_cursor: str | None = None


class RunDetail(BaseModel):
    schema_version: str = "1.0"
    run_id: UUID
    created_at: datetime
    brief: BriefPayload
    params: MatchParams
    pipeline: dict[str, Any]
    warnings: list[Warning] = Field(default_factory=list)
    summary: RunSummary
    candidates: list[CreatorSnapshot]
    ranked: list[RankedCreator]


class ComparisonRequest(BaseModel):
    run_id_a: UUID
    run_id_b: UUID


class CreatorReference(BaseModel):
    id: int
    creator_key: str
    handle: str


class ComparisonResponse(BaseModel):
    run_ids: list[UUID]
    summary_a: RunSummary
    summary_b: RunSummary
    shared_creators: list[CreatorReference]


class MetaResponse(BaseModel):
    niches: list[str]
    platforms: list[str]
    defaults: dict[str, Any]
    limits: dict[str, Any]
    index: dict[str, Any]
    ranking: dict[str, Any]
