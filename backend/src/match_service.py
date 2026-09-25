from __future__ import annotations

from typing import TypedDict

from . import vector_store
from .embeddings import get_cached_query_vector
from .gemini_client import get_client
from .models import Brief, Influencer
from .ranking import rank_candidates
from .retrieval import hybrid_retrieve


class MatchResult(TypedDict):
    brief: Brief
    params: dict[str, int]
    candidates: list[Influencer]
    ranked: list[dict]


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


def run_match(
    brief: Brief,
    top_k: int,
    top_n: int,
    client=None,
) -> MatchResult | None:
    candidates = retrieve_candidates(brief, top_k)
    if not candidates:
        return None
    ranked = rank_match(brief, candidates, top_n, client=client)
    return {
        "brief": brief,
        "params": {"top_k": top_k, "top_n": top_n},
        "candidates": candidates,
        "ranked": ranked,
    }
