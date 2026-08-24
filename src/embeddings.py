"""Embedding and indexing: turns influencer profiles and brand briefs into
vectors, so retrieval.py can do semantic search over them."""

import numpy as np

from . import config
from .models import Influencer

BATCH_SIZE = 50

# Cache the Sentence Transformer model
_sentence_transformer = None


def get_sentence_transformer() -> "SentenceTransformer":
    """Get or create the cached Sentence Transformer model.

    Import is deferred to avoid loading heavy deps (torch, transformers)
    at module import time -- only loads when first embedding is requested.
    """
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer
        print(f"Loading Sentence Transformer: {config.LOCAL_EMBED_MODEL}")
        _sentence_transformer = SentenceTransformer(config.LOCAL_EMBED_MODEL)
    return _sentence_transformer


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    """Embed texts locally with Sentence Transformers (no API involved)."""
    return embed_texts_local(texts)


def embed_texts_local(texts: list[str]) -> list[np.ndarray]:
    """Embed texts using Sentence Transformer model."""
    model = get_sentence_transformer()
    # Sentence Transformers returns numpy array of shape (len(texts), embedding_dim)
    embeddings = model.encode(texts, show_progress_bar=False)
    # Convert to list of individual numpy arrays for compatibility
    if len(embeddings.shape) == 1:
        return [embeddings]
    return [embeddings[i] for i in range(len(embeddings))]


def index_influencers(influencers: list[Influencer]) -> None:
    """Populate the .embedding field on every influencer, in this process.
    Vectors are persisted to Postgres/pgvector by vector_store.replace_influencers,
    so this only runs on generation/reindex, not on every query."""
    for start in range(0, len(influencers), BATCH_SIZE):
        batch = influencers[start:start + BATCH_SIZE]
        vectors = embed_texts([inf.corpus_text() for inf in batch])
        for inf, vec in zip(batch, vectors):
            inf.embedding = vec
