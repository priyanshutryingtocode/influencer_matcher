"""Embedding and indexing: turns influencer profiles and brand briefs into
vectors, so retrieval.py can do semantic search over them."""

import numpy as np
from typing import Union

from . import config
from .models import Influencer

BATCH_SIZE = 50  # keep requests under the API's per-call size limits

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


def embed_texts_local(texts: list[str]) -> list[np.ndarray]:
    """Embed texts using Sentence Transformer model."""
    model = get_sentence_transformer()
    # Sentence Transformers returns numpy array of shape (len(texts), embedding_dim)
    embeddings = model.encode(texts, show_progress_bar=False)
    # Convert to list of individual numpy arrays for compatibility
    if len(embeddings.shape) == 1:
        return [embeddings]
    return [embeddings[i] for i in range(len(embeddings))]


def index_influencers(client: Union["SentenceTransformer", object], influencers: list[Influencer]) -> None:
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


# Legacy function for backward compatibility
def embed_texts(client: Union["SentenceTransformer", object], texts: list[str], task_type: str = None) -> list[np.ndarray]:
    """Embed texts using either Sentence Transformer (local) or Gemini API.

    task_type parameter is ignored for local Sentence Transformers as it uses
    a different approach. Maintained for API compatibility with existing code.
    """
    if config.EMBEDDING_BACKEND == "local":
        return embed_texts_local(texts)
    else:
        # If we keep Gemini backend support
        raise NotImplementedError("Gemini backend not implemented in this refactor")
