from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, model_validator

from src import config

FitLevel = Literal["strong", "partial", "weak", "unknown"]
# `llm_unverified` is an LLM reason that survived with no citation the server
# could confirm. The UI marks it so a reader knows the claim is unsupported.
RankingSource = Literal["llm", "llm_unverified", "filled", "fallback"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class BriefPayload(BaseModel):
    """A free-text brand brief.

    The length floor lives on the write path (`_validate_brief`), not here, so
    runs stored before the move to free text - whose "niche" was sometimes a
    four-character vertical - still validate when they are read back. The
    `niche` alias keeps those records readable and is dropped on output.
    """

    goal: str = Field(
        default="",
        max_length=config.MAX_GOAL_LENGTH,
        validation_alias=AliasChoices("goal", "niche"),
    )
    platform: str = Field(default="Any", min_length=1, max_length=50)
    audience: str = Field(default="", max_length=config.AUDIENCE_MAX_LENGTH)
    vibe: str = Field(default="", max_length=config.VIBE_MAX_LENGTH)

    def to_domain(self):
        from src.models import Brief

        return Brief(
            goal=self.goal,
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
    """A creator as stored on a run.

    Fields 0-16 are what the profile states. From `content_style` down they are
    inferred signals, which live in their own table and refresh on a different
    cadence; they are flattened into the snapshot so a stored run stays a
    complete record of what was known at match time.
    """

    id: int
    creator_key: str
    handle: str
    name: str = ""
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
    # Stored and displayable, but deliberately not citable: these are not in
    # corpus_text, so retrieval never searched on them and a reason must not
    # claim them.
    reach_ratio: float = 0.0
    sponsored_ratio: float = 0.0
    growth_trend: str = ""
    audience_top_countries: list[str] = Field(default_factory=list)


class Grounding(BaseModel):
    """One claim a ranking reason rests on, and the profile field that backs it.

    `field` is a key of `src.ranking.GROUNDABLE_FIELDS` and `quote` is a
    verbatim substring of that field on the stored creator. Both are checked
    server-side before they reach this model, so a client can treat a grounding
    entry as fact rather than as a model's assertion.
    """

    field: str
    quote: str


class RankedCreator(BaseModel):
    id: int
    creator_key: str
    rank: int
    fit: FitLevel
    source: RankingSource
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    grounding: list[Grounding] = Field(default_factory=list)
    # Why the model did not rank this entry, when `source` is a fallback. Kept
    # on the record rather than only in the log: a run re-read later needs to be
    # able to say whether ranking was skipped for a spent quota or an outage,
    # because those call for different advice.
    fallback_reason: str = ""


class Warning(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    n_results: int
    avg_match_pct: float
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
    run_id: UUID
    created_at: datetime
    brief: BriefPayload
    params: MatchParams
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


class MetaDefaults(BaseModel):
    """Prefill values the Search form starts from.

    Typed rather than `dict[str, Any]`. That was the defect that let a missing
    `goal` key ship: the frontend type promised it, the backend silently omitted
    it, and neither side noticed because a dict validates nothing.
    """

    goal: str = ""
    audience: str = ""
    vibe: str = ""
    top_k: int = config.DEFAULT_TOP_K_RETRIEVAL
    top_n: int = config.DEFAULT_TOP_N_RANKED


class MetaLimits(BaseModel):
    top_k_min: int
    top_k_max: int
    top_n_min: int
    top_n_max: int
    goal_min_length: int
    goal_max_length: int
    audience_max_length: int
    vibe_max_length: int


class MetaIndex(BaseModel):
    status: Literal["ready", "unavailable", "reindex_required"]
    count: int
    embedding_model: str
    embed_dimensions: int
    memory_rss_mb: float | None = None


class MetaRanking(BaseModel):
    model: str
    fit_levels: list[FitLevel]


class MetaResponse(BaseModel):
    platforms: list[str]
    defaults: MetaDefaults
    limits: MetaLimits
    index: MetaIndex
    ranking: MetaRanking
