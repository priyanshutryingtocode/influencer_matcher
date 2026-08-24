"""Helpers shared across the Streamlit view modules: cached clients, DB
access, and the pipeline call extracted from the old single-file app so
pages stay thin and app.py stays free of circular imports."""

import streamlit as st

from src import vector_store
from src.gemini_client import get_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import hybrid_retrieve


@st.cache_resource
def get_gemini_client():
    return get_client()


def get_indexed_count() -> int | None:
    """Return the number of indexed profiles, or None if the database is
    unreachable (after rendering an error banner).

    Connects fresh each call rather than caching the DB connection --
    a cached connection shared across every Streamlit session isn't safe
    to use concurrently, and this is just a cheap COUNT query. Callers
    decide whether to st.stop() (search needs the DB; history/compare
    work from local files and never ask)."""
    try:
        with vector_store.get_connection() as conn:
            vector_store.init_schema(conn)
            return vector_store.count_influencers(conn)
    except Exception as e:
        st.error(f"Could not connect to the database. Check DATABASE_URL in your .env.\n\n{e}")
        return None


def run_pipeline(brief: Brief, top_k: int, top_n: int) -> dict | None:
    """Retrieve + rank for one brief. Returns a run dict, or None when
    retrieval came back empty (caller shows the 'try Any platform' hint)."""
    client = get_gemini_client()
    with vector_store.get_connection() as conn:
        candidates = hybrid_retrieve(conn, brief, top_k=top_k)
    if not candidates:
        return None
    ranked = rank_candidates(client, brief, candidates, top_n=top_n)
    return {
        "brief": brief,
        "params": {"top_k": top_k, "top_n": top_n},
        "candidates": candidates,
        "ranked": ranked,
    }
