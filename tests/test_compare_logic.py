"""Tests for views.compare_logic: run summaries and shared-id diffing."""

from src.models import Brief
from views import compare_logic

from tests.test_run_store import make_influencer


def make_run(niche, fits, niches):
    # Pool size follows `niches`; `fits` may be shorter (fewer ranked slots).
    assert len(fits) <= len(niches)
    candidates = [make_influencer(i, niche=niches[i]) for i in range(len(niches))]
    return {
        "brief": Brief(niche=niche, platform="Any"),
        "candidates": candidates,
        "ranked": [
            {"id": i, "fit": fit, "rationale": "", "source": "llm"}
            for i, fit in enumerate(fits)
        ],
    }


def test_summarize_run_stats():
    run = make_run(
        niche="Fitness",
        fits=["strong", "partial", "weak"],
        niches=["Fitness", "Fitness", "Gaming"],
    )
    s = compare_logic.summarize_run(run)
    assert s["n_results"] == 3
    assert s["n_on_niche"] == 2          # Gaming creator counted off-niche
    assert s["n_strong"] == 1 and s["n_weak"] == 1
    assert s["avg_engagement"] == 5.5    # all fixtures share engagement
    assert s["median_followers"] == 50_000


def test_shared_ids_only_counts_ranked():
    # Both runs retrieve the same two candidates but rank different ones --
    # pool overlap must NOT create shared creators.
    a = make_run("Fitness", ["strong"], ["Fitness", "Yoga"])  # ranks {0}
    b_run = make_run("Fitness", [], ["Fitness", "Yoga"])      # ranks nothing
    b_run["ranked"] = [{"id": 1, "fit": "strong", "rationale": "", "source": "llm"}]
    assert compare_logic.shared_creator_ids(a, b_run) == set()

    # Once both rank id 0, it is shared (id 1 still appears in b only).
    b_run["ranked"].insert(0, {"id": 0, "fit": "partial", "rationale": "", "source": "llm"})
    assert compare_logic.shared_creator_ids(a, b_run) == {0}
    assert compare_logic.compare_runs(a, b_run)["shared_ids"] == {0}


def test_compare_runs_shape():
    a = make_run("Fitness", ["strong", "partial"], ["Fitness", "Yoga"])
    b = make_run("Yoga", ["partial", "strong"], ["Yoga", "Fitness"])
    diff = compare_logic.compare_runs(a, b)
    assert diff["shared_ids"] == {0, 1}
    assert diff["summary_a"]["n_strong"] == 1
    assert diff["summary_b"]["n_strong"] == 1
