"""Hybrid retrieval: metadata filters plus semantic search.

The platform filter and the pgvector search run as a single Postgres query
(see vector_store.search). This module embeds the brief's own words (cached)
and searches.

An earlier version added a lexical term-overlap prior on top of the vector
score. Measured against the free-text golden cases it was net-neutral (mean
p@10 0.393 pure similarity vs 0.387 with the prior), because the bonus was
capped far below the similarity gaps between neighbouring candidates and so
could only reorder near-ties. It was removed rather than kept as a knob.
Literal term matching still earns its place as human-readable evidence on
each result (see src.text_match and src.formatting).
"""

import psycopg

from . import config, vector_store
from .embeddings import get_cached_query_vector
from .models import Brief, Influencer


def similarity_sort(candidates: list[Influencer]) -> list[Influencer]:
    """Return a new list ordered by vector similarity, descending.

    A missing similarity counts as 0 so creators that fall outside the
    embedding path still sort last instead of raising.
    """
    return sorted(candidates, key=lambda inf: -(inf.similarity or 0.0))


def hybrid_retrieve(
    conn: psycopg.Connection,
    brief: Brief,
    top_k: int = 10,
    table: str = vector_store.DEFAULT_TABLE,
    query_vec=None,
) -> list[Influencer]:
    if query_vec is None:
        query_vec = get_cached_query_vector(brief.query_text())
    candidates = vector_store.search(
        conn,
        query_embedding=query_vec,
        platform=brief.platform,
        top_k=top_k,
        table=table,
    )
    return similarity_sort(candidates)[:top_k]
