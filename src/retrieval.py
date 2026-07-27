"""Hybrid retrieval: metadata filters + semantic search.

Both halves now run as a single Postgres query (see vector_store.search) --
this module's job is just to embed the brief's query text and hand it off.
"""

import psycopg
from google import genai

from . import vector_store
from .embeddings import embed_texts
from .models import Brief, Influencer


def hybrid_retrieve(
    client: genai.Client,
    conn: psycopg.Connection,
    brief: Brief,
    top_k: int = 10,
    table: str = vector_store.DEFAULT_TABLE,
) -> list[Influencer]:
    query_vec = embed_texts(client, [brief.query_text()], task_type="RETRIEVAL_QUERY")[0]
    return vector_store.search(
        conn,
        query_embedding=query_vec,
        budget_max=brief.budget_max,
        platform=brief.platform,
        top_k=top_k,
        table=table,
    )