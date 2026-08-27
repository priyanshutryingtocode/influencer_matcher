"""Embedding and indexing: turns influencer profiles and brand briefs into
vectors, so retrieval.py can do semantic search over them."""

import hashlib
import threading
from collections import OrderedDict

import numpy as np

from . import config
from .models import Influencer

BATCH_SIZE = 50

# Cache the Sentence Transformer model. Loading is check-then-set over a
# module global, so the double-checked lock keeps concurrent Streamlit
# threads (and the app-shell warmup thread) from loading twice.
_sentence_transformer = None
_model_lock = threading.Lock()


def get_sentence_transformer() -> "SentenceTransformer":
    """Get or create the cached Sentence Transformer model.

    Import is deferred to avoid loading heavy deps (torch, transformers)
    at module import time -- only loads when first embedding is requested.
    """
    global _sentence_transformer
    if _sentence_transformer is None:
        with _model_lock:
            if _sentence_transformer is None:
                from sentence_transformers import SentenceTransformer
                print(f"Loading Sentence Transformer: {config.LOCAL_EMBED_MODEL}")
                _sentence_transformer = SentenceTransformer(config.LOCAL_EMBED_MODEL)
                _check_dimensions(_sentence_transformer)
    return _sentence_transformer


def _check_dimensions(model) -> None:
    """Fail loudly if the configured model's output width doesn't match the
    VECTOR(...) column -- pgvector would reject every insert otherwise."""
    # Probe without prefix is fine; dimension is same with/without.
    probe = np.asarray(model.encode(["dim"], show_progress_bar=False))
    if probe.shape[-1] != config.EMBED_DIMENSIONS:
        raise RuntimeError(
            f"{config.LOCAL_EMBED_MODEL} produces {probe.shape[-1]}-dim vectors "
            f"but EMBED_DIMENSIONS={config.EMBED_DIMENSIONS}. Update "
            f"EMBED_DIMENSIONS (requires a --reindex) or pick a matching model."
        )


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    """Embed texts locally with Sentence Transformers (no API involved)."""
    texts = [config.EMBED_PASSAGE_PREFIX + t for t in texts]
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


# --- query-vector cache -----------------------------------------------------
# Retrieval embeds one query per search; repeat briefs (common in demos and
# when tweaking sliders) can skip the encode entirely. Small LRU keyed by
# text hash so identical queries share vectors.
_QUERY_CACHE_SIZE = 128
_query_cache: OrderedDict[str, np.ndarray] = OrderedDict()
_query_cache_lock = threading.Lock()


def get_cached_query_vector(text: str) -> np.ndarray:
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with _query_cache_lock:
        cached = _query_cache.get(key)
        if cached is not None:
            _query_cache.move_to_end(key)
            return cached
    vec = embed_texts([config.EMBED_QUERY_PREFIX + text])[0]
    with _query_cache_lock:
        _query_cache[key] = vec
        while len(_query_cache) > _QUERY_CACHE_SIZE:
            _query_cache.popitem(last=False)
    return vec


def index_influencers(influencers: list[Influencer]) -> None:
    """Populate the .embedding field on every influencer, in this process.
    Vectors are persisted to Postgres/pgvector by vector_store.replace_influencers,
    so this only runs on generation/reindex, not on every query."""
    for start in range(0, len(influencers), BATCH_SIZE):
        batch = influencers[start:start + BATCH_SIZE]
        vectors = embed_texts([inf.corpus_text() for inf in batch])
        for inf, vec in zip(batch, vectors):
            inf.embedding = vec
