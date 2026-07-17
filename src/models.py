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
    rate: int
    tags: list = field(default_factory=list)
    bio: str = ""
    embedding: np.ndarray = None

    def corpus_text(self) -> str:
        """Text representation used for embedding (the RAG 'document')."""
        return (
            f"Creator {self.handle} on {self.platform}, based in {self.city}. "
            f"Niche: {self.niche}. Topics: {', '.join(self.tags)}. {self.bio}"
        )


@dataclass
class Brief:
    niche: str
    platform: str  # "Any" or one of the values in data_generator.PLATFORMS
    budget_max: int
    audience: str = ""
    vibe: str = ""

    def query_text(self) -> str:
        """Text representation used as the retrieval query (the RAG 'query')."""
        return (
            f"Looking for a {self.niche} creator. Target audience: {self.audience}. "
            f"Vibe / tone: {self.vibe}."
        )
