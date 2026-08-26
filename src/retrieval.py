"""Hybrid retrieval: metadata filters + semantic search.

Both halves run as a single Postgres query (see vector_store.search) --
this module embeds the brief's query text (cached), searches pgvector, then
applies a deterministic niche prior to the ordering.
"""

import psycopg

from . import vector_store
from .embeddings import get_cached_query_vector
from .models import Brief, Influencer


def niche_prior_sort(candidates: list[Influencer], niche: str) -> list[Influencer]:
    """Reorder retrieved candidates so creators whose primary or secondary
    niches include the brief's niche come first, similarity order preserved
    within each group (stable sort).

    This does not change *which* candidates were retrieved (pgvector's top_k
    already fixed that) -- only the order the LLM ranker sees them in, and
    the order used when shortlist slots get filled from retrieval. Zero API
    cost; evaluate.py's precision@k is order-independent and stays comparable."""
    def sort_key(inf: Influencer):
        on_niche = 0 if niche in {inf.niche, *inf.secondary_niches} else 1
        return (on_niche, -(inf.similarity or 0.0))

    return sorted(candidates, key=sort_key)


def hybrid_retrieve(
    conn: psycopg.Connection,
    brief: Brief,
    top_k: int = 10,
    table: str = vector_store.DEFAULT_TABLE,
) -> list[Influencer]:
    query_vec = get_cached_query_vector(brief.query_text())
    candidates = vector_store.search(
        conn,
        query_embedding=query_vec,
        platform=brief.platform,
        top_k=top_k,
        table=table,
    )
    return niche_prior_sort(candidates, brief.niche)
