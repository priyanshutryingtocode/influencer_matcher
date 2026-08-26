"""Streamlit interface for the influencer matcher.

Run with:
    streamlit run app.py

Pages live in views/; this file is just navigation + chrome.
"""

import threading

import streamlit as st

from views import compare, history, search

st.set_page_config(page_title="Influencer Matcher", page_icon="\U0001F3AF", layout="wide")


def _warm_embedding_model() -> None:
    """Preload the Sentence Transformer in a background thread so the first
    search doesn't pay the multi-second model load. Failures are swallowed:
    a missing model/torch only matters once a search actually runs, and the
    lazy loader will surface the real error there."""
    try:
        from src.embeddings import get_sentence_transformer
        get_sentence_transformer()
    except Exception:
        pass


threading.Thread(target=_warm_embedding_model, daemon=True, name="embed-warmup").start()

with st.sidebar:
    st.markdown("## \U0001F3AF Influencer Matcher")
    st.caption("RAG-powered creator matching:\nPostgres/pgvector retrieval + Gemini reasoning")

page = st.navigation([
    st.Page(search.render_search, title="Search", icon="\U0001F50D", default=True),
    st.Page(history.render_history, title="History", icon="\U0001F5C2\uFE0F"),
    st.Page(compare.render_compare, title="Compare", icon="\u2696\uFE0F"),
])
page.run()
