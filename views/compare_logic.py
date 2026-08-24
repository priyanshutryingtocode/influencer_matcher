"""Pure comparison math for the Compare page -- no Streamlit imports,
so it stays unit-testable and independent of rendering."""


def summarize_run(run: dict) -> dict:
    """Aggregate stats over a run's ranked shortlist.

    Only ranked entries count toward engagement/follower aggregates --
    that's what the user actually received -- while on-niche counts use
    the full retrieved candidate pool (matching how evaluate.py reports
    retrieval precision)."""
    from statistics import median

    candidates_by_id = {c.id: c for c in run["candidates"]}
    ranked_infs = [candidates_by_id[e["id"]] for e in run["ranked"]]
    brief_niche = run["brief"].niche

    n_strong = sum(1 for e in run["ranked"] if e.get("fit") == "strong")
    n_weak = sum(1 for e in run["ranked"] if e.get("fit") == "weak")
    return {
        "n_results": len(ranked_infs),
        "avg_engagement": (
            sum(i.engagement for i in ranked_infs) / len(ranked_infs)
            if ranked_infs else 0.0
        ),
        "median_followers": median(i.followers for i in ranked_infs) if ranked_infs else 0,
        "n_on_niche": sum(1 for i in ranked_infs if i.niche == brief_niche),
        "n_strong": n_strong,
        "n_weak": n_weak,
    }


def shared_creator_ids(run_a: dict, run_b: dict) -> set[int]:
    """Ids appearing on both shortlists (ranked results, not just pools)."""
    ids_a = {e["id"] for e in run_a["ranked"]}
    ids_b = {e["id"] for e in run_b["ranked"]}
    return ids_a & ids_b


def compare_runs(run_a: dict, run_b: dict) -> dict:
    return {
        "summary_a": summarize_run(run_a),
        "summary_b": summarize_run(run_b),
        "shared_ids": shared_creator_ids(run_a, run_b),
    }
