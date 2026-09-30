from __future__ import annotations

from . import vector_store
from .embeddings import get_cached_query_vector
from .gemini_client import get_client
from .models import Brief, Influencer
from .ranking import rank_candidates
from .retrieval import hybrid_retrieve


def retrieve_candidates(
    brief: Brief,
    top_k: int,
    query_vec=None,
) -> list[Influencer]:
    if query_vec is None:
        query_vec = get_cached_query_vector(brief.query_text())
    with vector_store.get_connection() as conn:
        return hybrid_retrieve(conn, brief, top_k=top_k, query_vec=query_vec)


def rank_match(
    brief: Brief,
    candidates: list[Influencer],
    top_n: int,
    client=None,
) -> list[dict]:
    if client is None:
        client = get_client()
    return rank_candidates(client, brief, candidates, top_n=top_n)
