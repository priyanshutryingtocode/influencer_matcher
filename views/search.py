"""Search page: brief form, staged pipeline run, shortlist grid, CSV export."""

import streamlit as st

from src.data_generator import NICHES, PLATFORMS
from src.models import Brief
from views import cards, run_store
from views.shared import get_indexed_count, run_pipeline


def render_search() -> None:
    st.subheader("Find creators for a brand brief")
    st.caption("Postgres/pgvector retrieval + Gemini reasoning. Runs are saved locally to .runs/.")

    indexed_count = get_indexed_count()
    if indexed_count is None:
        st.stop()
    if indexed_count == 0:
        st.info("No creators indexed yet. Contact your administrator to add creators to the database.")
        st.stop()
    st.sidebar.caption(f"{indexed_count} creators indexed")

    col_brief, col_settings = st.columns([3, 2], vertical_alignment="bottom")
    with col_brief:
        niche = st.selectbox("Niche", list(NICHES.keys()))
        platform = st.segmented_control("Platform", ["Any", *PLATFORMS], selection_mode="single", default="Any")
        audience = st.text_input("Target audience", "Gen Z, sustainability-minded")
        vibe = st.text_area("Vibe / tone", "warm, low-key, not overly polished")
    with col_settings:
        top_k = st.slider("Candidates to retrieve", 5, 30, 10)
        top_n = st.slider("Final shortlist size", 1, max(top_k, 1), min(5, top_k))
        run = st.button("Run match", type="primary", use_container_width=True)

    if not run:
        st.info("Set a brief above and click **Run match**.")
        return

    brief = Brief(niche=niche, platform=platform or "Any", audience=audience, vibe=vibe)
    status = st.status("Running match…", expanded=True)
    with status:
        st.write("Retrieving candidates (Postgres + pgvector)…")
        result = run_pipeline(brief, top_k=top_k, top_n=top_n)
        if result is None:
            status.update(label="No results", state="error")
            st.warning("No creators found for that platform. Try 'Any' platform, or check the database is indexed.")
            return
        st.write(f"Retrieved {len(result['candidates'])} candidates — ranking with Gemini…")
    status.update(label="Match complete", state="complete", expanded=False)

    ranked, candidates = result["ranked"], result["candidates"]
    cards.render_run_warnings(ranked, candidates, niche)

    candidates_by_id = {c.id: c for c in candidates}
    st.subheader(f"Top {len(ranked)} matches")
    st.caption("Fit is AI-assessed by the ranking model, cross-checked against niche match.")

    cols = st.columns(min(len(ranked), 3) or 1)
    for i, entry in enumerate(ranked):
        with cols[i % len(cols)]:
            cards.render_result_card(candidates_by_id[entry["id"]], entry, brief, rank=i + 1)

    try:
        run_id = run_store.save_run(brief, ranked, candidates, params=result["params"])
        st.session_state["last_run_id"] = run_id
        st.sidebar.toast("Run saved to history", icon="\U0001F4BE")
    except OSError as e:
        st.sidebar.warning(f"Could not save this run to history: {e}")

    csv_data = run_store.build_csv({"candidates": candidates, "ranked": ranked})
    st.download_button(
        "\U0001F4E5 Export CSV",
        data=csv_data,
        file_name=(
            f"shortlist-{run_store.slugify(niche)}-"
            f"{run_store.slugify(platform or 'Any')}.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )


if __name__ == "__main__":
    render_search()
