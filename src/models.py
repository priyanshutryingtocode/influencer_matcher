"""Core data structures shared across the pipeline."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Influencer:
    id: int
    handle: str
    niche: str
    platform: str
    city: str
    followers: int
    engagement: float
    tags: list = field(default_factory=list)
    bio: str = ""
    embedding: np.ndarray = None
    similarity: float | None = None
    name: str = ""
    secondary_niches: list[str] = field(default_factory=list)
    country: str = ""
    language: str = ""
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
    brand_collaborations: list[str] = field(default_factory=list)

    def corpus_text(self) -> str:
        return (
            f"Creator {self.handle} on {self.platform}, based in {self.city}. "
            f"Niche: {self.niche}. Topics: {', '.join(self.tags)}. {self.bio}"
        )


@dataclass
class Brief:
    niche: str
    platform: str  # "Any" or one of PLATFORMS
    audience: str = ""
    vibe: str = ""

    def query_text(self) -> str:
        """Text representation used as the retrieval query (the RAG 'query').
        Niche is included here (not enforced as a hard filter) since it's a
        semantic signal, not a strict eligibility criterion the way platform
        is."""
        return (
            f"Looking for a {self.niche} creator. Target audience: {self.audience}. "
            f"Vibe / tone: {self.vibe}."
        )
