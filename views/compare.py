"""Compare page: side-by-side shortlists from two saved runs."""

import streamlit as st

from views import cards, compare_logic, run_store


def _run_label(meta: dict) -> str:
    return f"{meta['saved_at'].replace('T', ' ')} — {meta['niche']} / {meta['platform']}"


def _summary_row(summary: dict) -> None:
    cols = st.columns(5)
    cols[0].metric("Results", summary["n_results"])
    cols[1].metric("On-niche", summary["n_on_niche"])
    cols[2].metric("Strong fits", summary["n_strong"])
    cols[3].metric("Avg engagement", f"{summary['avg_engagement']:.1f}%")
    cols[4].metric("Median followers", cards.format_followers(summary["median_followers"]))


def render_compare() -> None:
    st.subheader("Compare runs")
    st.caption("Pick two saved runs to see their shortlists side by side.")

    runs = run_store.list_runs()
    if len(runs) < 2:
        st.info("Save at least two runs (via **Search**) to compare them.")
        return

    labels = {_run_label(m): m["run_id"] for m in runs}
    col_a, col_b = st.columns(2)
    with col_a:
        label_a = st.selectbox("Run A", list(labels), index=0)
    with col_b:
        default_b = 1 if len(labels) > 1 else 0
        label_b = st.selectbox("Run B", list(labels), index=default_b)

    if label_a == label_b:
        st.warning("Pick two different runs to compare.")
        return

    run_a = run_store.load_run(labels[label_a])
    run_b = run_store.load_run(labels[label_b])
    if run_a is None or run_b is None:
        st.error("One of the selected runs could not be loaded (missing or corrupt file).")
        return

    diff = compare_logic.compare_runs(run_a, run_b)
    shared_ids = diff["shared_ids"]

    left, right = st.columns(2)
    left.markdown(f"### A · {label_a}")
    right.markdown(f"### B · {label_b}")

    left_container = left.container(border=True)
    right_container = right.container(border=True)
    with left_container:
        _summary_row(diff["summary_a"])
    with right_container:
        _summary_row(diff["summary_b"])

    if shared_ids:
        st.success(f"{len(shared_ids)} creator(s) appear on both shortlists (marked \U0001F501).")

    def _render_side(run: dict) -> None:
        brief = run["brief"]
        candidates_by_id = {c.id: c for c in run["candidates"]}
        for i, entry in enumerate(run["ranked"]):
            inf = candidates_by_id.get(entry["id"])
            if inf is None:
                continue
            cards.render_result_card(
                inf, entry, brief, rank=i + 1,
                highlight=entry["id"] in shared_ids,
            )

    with left:
        _render_side(run_a)
    with right:
        _render_side(run_b)


if __name__ == "__main__":
    render_compare()
