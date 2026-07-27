"""Streamlit interface for the influencer matcher.

Run with:
    streamlit run app.py
"""

import streamlit as st

from src import config, vector_store
from src.data_generator import NICHES, PLATFORMS, generate_influencers
from src.embeddings import index_influencers
from src.formatting import format_followers
from src.gemini_client import get_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import hybrid_retrieve

st.set_page_config(page_title="Influencer Matcher", page_icon="🎯", layout="wide")


@st.cache_resource
def get_gemini_client():
    return get_client()


def get_indexed_count() -> int:
    """Connects fresh each call rather than caching the DB connection --
    a cached connection shared across every Streamlit session isn't safe to
    use concurrently, and this is just a cheap COUNT query."""
    try:
        with vector_store.get_connection() as conn:
            vector_store.init_schema(conn)
            return vector_store.count_influencers(conn)
    except Exception as e:
        st.error(f"Could not connect to the database. Check DATABASE_URL in your .env.\n\n{e}")
        st.stop()


st.title("🎯 Influencer Matcher")
st.caption("RAG-powered creator matching: Postgres/pgvector retrieval + Gemini reasoning")

indexed_count = get_indexed_count()

with st.sidebar:
    st.subheader("Database")
    st.metric("Indexed creators", indexed_count)
    build_count = st.number_input(
        "Profiles to generate", min_value=10, max_value=config.MAX_INFLUENCER_COUNT, value=config.DEFAULT_INFLUENCER_COUNT, step=10
    )
    build_label = "Rebuild database" if indexed_count else "Build database"
    if st.button(build_label, use_container_width=True):
        client = get_gemini_client()
        with st.spinner("Generating synthetic profiles..."):
            influencers = generate_influencers(count=build_count)
        with st.spinner(f"Embedding {len(influencers)} profiles with Gemini..."):
            index_influencers(client, influencers)
        with st.spinner("Replacing profiles in the database..."):
            with vector_store.get_connection() as conn:
                vector_store.init_schema(conn)
                vector_store.replace_influencers(conn, influencers)
        st.success(f"Indexed {len(influencers)} profiles.")
        st.rerun()

    st.divider()

    st.subheader("Brand brief")
    niche = st.selectbox("Niche", list(NICHES.keys()))
    platform = st.selectbox("Platform", ["Any", *PLATFORMS])
    budget_max = st.slider("Budget per creator (max $)", 200, 20000, 5000, step=100)
    audience = st.text_input("Target audience", "Gen Z, sustainability-minded")
    vibe = st.text_area("Vibe / tone", "warm, low-key, not overly polished")
    top_k = st.slider("Candidates to retrieve", 5, 30, 10)
    top_n = st.slider("Final shortlist size", 1, top_k, min(5, top_k))
    run = st.button("Run match", type="primary", use_container_width=True)

if indexed_count == 0:
    st.info("No creators indexed yet. Use **Build database** in the sidebar first.")
    st.stop()

if not run:
    st.info("Set a brief in the sidebar and click **Run match**.")
    st.stop()

client = get_gemini_client()
brief = Brief(niche=niche, platform=platform, budget_max=budget_max, audience=audience, vibe=vibe)

with st.spinner("Retrieving candidates (Postgres + pgvector)..."):
    with vector_store.get_connection() as conn:
        candidates = hybrid_retrieve(client, conn, brief, top_k=top_k)

if not candidates:
    st.warning("No creators fit that budget/platform combination. Try raising the budget.")
    st.stop()

st.caption(f"{len(candidates)} candidates passed filters + retrieval")

with st.spinner("Ranking with Gemini..."):
    ranked = rank_candidates(
        client,
        brief,
        candidates,
        top_n=top_n,
        on_fallback=lambda: st.warning("Gemini ranking was unavailable; showing the best semantic matches instead."),
    )

candidates_by_id = {c.id: c for c in candidates}

st.subheader(f"Top {len(ranked)} matches")
cols = st.columns(min(len(ranked), 3) or 1)
for i, entry in enumerate(ranked):
    inf = candidates_by_id[entry["id"]]
    col = cols[i % len(cols)]
    with col:
        with st.container(border=True):
            st.markdown(f"**#{i + 1} · {inf.handle}**")
            st.caption(f"{inf.niche} · {inf.platform} · {inf.city}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Followers", format_followers(inf.followers))
            m2.metric("Engagement", f"{inf.engagement}%")
            m3.metric("Rate", f"${inf.rate}")
            st.write(" ".join(f"`{t}`" for t in inf.tags))
            st.info(entry["rationale"])
