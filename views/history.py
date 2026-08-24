"""History page: browse, reopen, and delete saved runs (local .runs/ files)."""

import streamlit as st

from views import cards, run_store


def _format_saved_at(iso: str) -> str:
    try:
        return iso.replace("T", " ") + " UTC"
    except AttributeError:
        return iso or "unknown time"


def render_history() -> None:
    st.subheader("Run history")
    st.caption("Shortlists are saved locally under .runs/ each time you run a match.")

    runs = run_store.list_runs()
    if not runs:
        st.info("No saved runs yet — run a match on the **Search** page first.")
        return

    for meta in runs:
        with st.container(border=True):
            top = st.columns([3, 1, 1])
            with top[0]:
                st.markdown(f"**{_format_saved_at(meta['saved_at'])}**")
                st.caption(
                    f"{meta['niche']} · {meta['platform']} · "
                    f"{meta['n_results']} results · \U0001F7E2 {meta['n_strong']} strong"
                )
            with top[2]:
                confirm = st.checkbox("Confirm", key=f"confirm-{meta['run_id']}")
                if st.button(
                    "Delete",
                    key=f"delete-{meta['run_id']}",
                    disabled=not confirm,
                    use_container_width=True,
                ):
                    run_store.delete_run(meta["run_id"])
                    st.rerun()

            saved = run_store.load_run(meta["run_id"])
            if saved is None:
                st.error("This run's file is missing or corrupt and can't be displayed.")
                continue

            brief = saved["brief"]
            candidates_by_id = {c.id: c for c in saved["candidates"]}
            with st.expander("View shortlist"):
                st.caption(
                    f"Audience: {brief.audience or '—'} · Vibe: {brief.vibe or '—'}"
                )
                cols = st.columns(min(len(saved["ranked"]), 3) or 1)
                for i, entry in enumerate(saved["ranked"]):
                    inf = candidates_by_id.get(entry["id"])
                    if inf is None:
                        continue
                    with cols[i % len(cols)]:
                        cards.render_result_card(inf, entry, brief, rank=i + 1)


if __name__ == "__main__":
    render_history()
