"""Embedding and indexing: turns influencer profiles and brand briefs into
vectors, so retrieval.py can do semantic search over them."""

import numpy as np
from google import genai
from google.genai import types

from . import config
from .models import Influencer

BATCH_SIZE = 50  # keep requests under the API's per-call size limits


def embed_texts(client: genai.Client, texts: list[str], task_type: str) -> list[np.ndarray]:
    """Embed a batch of texts.

    task_type is "RETRIEVAL_DOCUMENT" when embedding the influencer corpus,
    and "RETRIEVAL_QUERY" when embedding a brand brief -- Gemini's embedding
    model uses this to optimize the vector for its role in the search.
    """
    result = client.models.embed_content(
        model=config.EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=config.EMBED_DIMENSIONS,
        ),
    )
    return [np.array(e.values) for e in result.embeddings]


def index_influencers(client: genai.Client, influencers: list[Influencer]) -> None:
    """Populate the .embedding field on every influencer, in this process.
    In production you'd persist these in a vector database (Pinecone,
    Weaviate, pgvector) instead of recomputing them on every run."""
    for start in range(0, len(influencers), BATCH_SIZE):
        batch = influencers[start:start + BATCH_SIZE]
        vectors = embed_texts(
            client,
            [inf.corpus_text() for inf in batch],
            task_type="RETRIEVAL_DOCUMENT",
        )
        for inf, vec in zip(batch, vectors):
            inf.embedding = vec


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
