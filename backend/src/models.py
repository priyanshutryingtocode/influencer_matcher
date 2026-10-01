"""Core data structures shared across the pipeline."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class CreatorSignals:
    """Inferred, third-party characteristics, kept out of the searchable row.

    `influencers` holds what a creator's own profile states: handle, reach,
    topics, bio. Everything here is an estimate made *about* that profile by an
    analytics provider, so it belongs in its own table with its own lifecycle.
    The split matters for two reasons: a signal can be refreshed without
    re-embedding a profile, and a reason can say "inferred audience 25-34"
    rather than implying the creator declared it.

    Fields are set in the same order the ranking prompt may cite them, and
    `Influencer.corpus_text` still reads them, so moving them between tables
    did not change the embedded text -- which is what keeps every cached
    vector valid across the split.
    """

    creator_id: int
    content_style: str = ""
    audience_age: str = ""
    audience_gender: str = ""
    audience_country: str = ""
    brand_collaborations: list[str] = field(default_factory=list)
    # views / followers. The honest measure of whether reach is real: a
    # follower count can be large while actual reach stays small.
    reach_ratio: float = 0.0
    # Share of posts that are paid, 0..1.
    sponsored_ratio: float = 0.0
    growth_trend: str = ""
    audience_top_countries: list[str] = field(default_factory=list)


@dataclass
class Influencer:
    id: int
    handle: str
    platform: str
    city: str
    followers: int
    engagement: float
    tags: list = field(default_factory=list)
    bio: str = ""
    embedding: np.ndarray = None
    similarity: float | None = None
    name: str = ""
    country: str = ""
    language: str = ""
    average_views: int = 0
    average_likes: int = 0
    average_comments: int = 0
    verified: bool = False
    posts_per_week: int = 0
    account_age_years: int = 0
    # Populated from the creator_signals row on read; see CreatorSignals.
    content_style: str = ""
    audience_age: str = ""
    audience_gender: str = ""
    audience_country: str = ""
    brand_collaborations: list[str] = field(default_factory=list)
    reach_ratio: float = 0.0
    sponsored_ratio: float = 0.0
    growth_trend: str = ""
    audience_top_countries: list[str] = field(default_factory=list)

    def signals(self) -> CreatorSignals:
        """The signal row for this creator, as stored."""
        return CreatorSignals(
            creator_id=self.id,
            content_style=self.content_style,
            audience_age=self.audience_age,
            audience_gender=self.audience_gender,
            audience_country=self.audience_country,
            brand_collaborations=list(self.brand_collaborations),
            reach_ratio=self.reach_ratio,
            sponsored_ratio=self.sponsored_ratio,
            growth_trend=self.growth_trend,
            audience_top_countries=list(self.audience_top_countries),
        )

    def corpus_text(self) -> str:
        """The text this creator is embedded as, and the text a reason may cite.

        This is the single source of truth for what a profile "says". It
        deliberately includes every field the ranking model is allowed to cite
        as evidence, so retrieval can match on it and a grounded reason can
        quote it. Changing this invalidates every cached vector.

        The signal fields are emitted in `corpus_text` from this row either way,
        which is what let those columns move to `creator_signals` without
        invalidating a single cached vector. Retrieval reads them through the
        LEFT JOIN in `vector_store.search`, not through an accessor.
        """
        facts = [
            f"Creator {self.handle} on {self.platform}, based in {self.city}, {self.country}.",
            f"Topics: {', '.join(self.tags)}.",
        ]
        if self.content_style:
            facts.append(f"Content style: {self.content_style}.")
        audience = ", ".join(p for p in (self.audience_age, self.audience_gender, self.audience_country) if p)
        if audience:
            facts.append(f"Audience: {audience}.")
        if self.brand_collaborations:
            facts.append(f"Past brand partners: {', '.join(self.brand_collaborations)}.")
        if self.bio:
            facts.append(self.bio)
        return " ".join(facts)


@dataclass
class Brief:
    goal: str
    platform: str
    audience: str = ""
    vibe: str = ""

    def query_text(self) -> str:
        """Text embedded as the retrieval query (the RAG 'query').

        This is the brand's own words, not a templated scaffold. Platform is
        omitted because it is already a hard metadata filter, so repeating it
        here would only dilute the topical signal.
        """
        parts = [self.goal.strip()]
        if self.audience.strip():
            parts.append(f"Target audience: {self.audience.strip()}.")
        if self.vibe.strip():
            parts.append(f"Tone: {self.vibe.strip()}.")
        return " ".join(parts)
