"""Streamlit interface for the influencer matcher.

Run with:
    streamlit run app.py

Pages live in views/; this file is just navigation + chrome.
"""

import streamlit as st

from views import compare, history, search

st.set_page_config(page_title="Influencer Matcher", page_icon="\U0001F3AF", layout="wide")

with st.sidebar:
    st.markdown("## \U0001F3AF Influencer Matcher")
    st.caption("RAG-powered creator matching:\nPostgres/pgvector retrieval + Gemini reasoning")

page = st.navigation([
    st.Page(search.render_search, title="Search", icon="\U0001F50D", default=True),
    st.Page(history.render_history, title="History", icon="\U0001F5C2\uFE0F"),
    st.Page(compare.render_compare, title="Compare", icon="\u2696\uFE0F"),
])
page.run()
