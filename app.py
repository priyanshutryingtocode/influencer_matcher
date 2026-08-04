"""Streamlit interface for the influencer matcher.

Run with:
    streamlit run app.py
"""

import streamlit as st

from src import config, vector_store
from src.data_generator import NICHES, PLATFORMS
from src.formatting import format_followers, match_evidence, niche_coverage
from src.gemini_client import get_client, get_embedding_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import hybrid_retrieve

st.set_page_config(page_title="Influencer Matcher", page_icon="\U0001F3AF", layout="wide")

FIT_STYLE = {
    "strong": ("\U0001F7E2", "Strong fit"),
    "partial": ("\U0001F7E1", "Partial fit"),
    "weak": ("\U0001F534", "Weak fit"),
    "unknown": ("\u26AA", "Fit unknown"),
}


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


st.title("\U0001F3AF Influencer Matcher")
st.caption("RAG-powered creator matching: Postgres/pgvector retrieval + Gemini reasoning")

indexed_count = get_indexed_count()

with st.sidebar:
    st.subheader("Brand brief")
    niche = st.selectbox("Niche", list(NICHES.keys()))
    platform = st.selectbox("Platform", ["Any", *PLATFORMS])
    audience = st.text_input("Target audience", "Gen Z, sustainability-minded")
    vibe = st.text_area("Vibe / tone", "warm, low-key, not overly polished")
    top_k = st.slider("Candidates to retrieve", 5, 30, 10)
    top_n = st.slider("Final shortlist size", 1, top_k, min(5, top_k))
    run = st.button("Run match", type="primary", use_container_width=True)

if indexed_count == 0:
    st.info("No creators indexed yet. Contact your administrator to add creators to the database.")
    st.stop()

if not run:
    st.info("Set a brief in the sidebar and click **Run match**.")
    st.stop()

if config.EMBEDDING_BACKEND == "local":
    st.sidebar.info("Using local embedding backend (Sentence Transformer)...")
else:
    st.sidebar.info("Using Gemini embedding backend...")

client = get_gemini_client()
brief = Brief(niche=niche, platform=platform, audience=audience, vibe=vibe)

with st.spinner("Retrieving candidates (Postgres + pgvector)..."):
    with vector_store.get_connection() as conn:
        candidates = hybrid_retrieve(get_embedding_client(), conn, brief, top_k=top_k)

if not candidates:
    st.warning("No creators found for that platform. Try 'Any' platform, or check the database is indexed.")
    st.stop()

matches, total = niche_coverage(candidates, niche)
st.caption(f"{total} candidates passed filters + retrieval")
if matches < total:
    st.warning(
        f"Only {matches}/{total} retrieved candidates are actually tagged **{niche}**. "
        f"The rest passed your platform filter but ranked in on vibe/audience similarity rather than "
        f"niche — check the fit badges on each card, or try a different platform."
    )

with st.spinner("Ranking with Gemini..."):
    ranked = rank_candidates(client, brief, candidates, top_n=top_n)

fallback_entries = [e for e in ranked if e.get("source") == "fallback"]
filled_entries = [e for e in ranked if e.get("source") == "filled"]
if fallback_entries:
    # The detailed reason (exception type/message) is already logged
    # server-side by ranking.py's logger.warning -- not shown here, since
    # raw exception text can leak internal request/network detail and
    # isn't actionable for the person using the app.
    st.error("Gemini ranking is temporarily unavailable, so this shortlist is retrieval order, not LLM-reasoned.")
elif filled_entries:
    st.info(
        f"The model only ranked {len(ranked) - len(filled_entries)} of {len(ranked)} requested slots; "
        f"the rest were filled from retrieval order (marked \u26AA below)."
    )

candidates_by_id = {c.id: c for c in candidates}

st.subheader(f"Top {len(ranked)} matches")
st.caption("Fit is AI-assessed by the ranking model, cross-checked against niche match.")
cols = st.columns(min(len(ranked), 3) or 1)
for i, entry in enumerate(ranked):
    inf = candidates_by_id[entry["id"]]
    fit = entry.get("fit", "unknown")
    fit_emoji, fit_label = FIT_STYLE.get(fit, FIT_STYLE["unknown"])
    col = cols[i % len(cols)]
    with col:
        with st.container(border=True):
            st.markdown(f"**#{i + 1} · {inf.handle}**  {fit_emoji} {fit_label}")
            st.caption(f"{inf.niche} · {inf.platform} · {inf.city}")
            m1, m2 = st.columns(2)
            m1.metric("Followers", format_followers(inf.followers))
            m2.metric("Engagement", f"{inf.engagement}%")
            if inf.similarity is not None:
                st.caption(f"Semantic relevance: {inf.similarity:.1%}")
            st.caption(
                f"{inf.content_style} | {inf.language} | audience: {inf.audience_age}, "
                f"{inf.audience_gender}, {inf.audience_country}"
            )
            st.write(" ".join(f"`{t}`" for t in inf.tags))
            if inf.brand_collaborations:
                st.caption("Past collaborations: " + ", ".join(inf.brand_collaborations))
            st.caption("Why retrieved: " + " | ".join(match_evidence(brief, inf)))
            if fit == "weak":
                st.warning(entry["rationale"])
            else:
                st.info(entry["rationale"])
