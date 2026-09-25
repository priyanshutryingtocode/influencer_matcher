from datetime import datetime, timezone
from uuid import uuid4

from api.serialization import build_run_record
from api.services.compare_service import compare_runs, summarize_run
from src.models import Brief, Influencer


def make_influencer(id_: int, niche: str) -> Influencer:
    return Influencer(
        id=id_, handle=f"@c{id_}", name=f"Creator {id_}", niche=niche,
        secondary_niches=[], platform="Instagram", city="Austin",
        country="USA", language="English", followers=50_000, engagement=5.5,
        similarity=0.8, tags=[], bio="",
    )


def make_run(niche, fits, niches):
    assert len(fits) <= len(niches)
    brief = Brief(niche=niche, platform="Any")
    result = {
        "brief": brief,
        "params": {"top_k": 10, "top_n": max(1, len(fits))},
        "candidates": [make_influencer(i, niches[i]) for i in range(len(niches))],
        "ranked": [
            {"id": i, "fit": fit, "rationale": "", "source": "llm"}
            for i, fit in enumerate(fits)
        ],
    }
    record = build_run_record(result, uuid4(), indexed_count=10)
    now = datetime.now(timezone.utc)
    record["created_at"] = now
    record["updated_at"] = now
    return record


def test_summarize_run_stats():
    run = make_run(
        niche="Fitness",
        fits=["strong", "partial", "weak"],
        niches=["Fitness", "Fitness", "Gaming"],
    )
    summary = summarize_run(run)
    assert summary["n_results"] == 3
    assert summary["n_ranked_on_niche"] == 2
    assert summary["n_strong"] == 1 and summary["n_weak"] == 1
    assert summary["avg_engagement_pct"] == 5.5
    assert summary["median_followers"] == 50_000


def test_shared_creators_only_counts_ranked_results():
    run_a = make_run("Fitness", ["strong"], ["Fitness", "Yoga"])
    run_b = make_run("Fitness", ["strong"], ["Yoga", "Fitness"])
    comparison = compare_runs(run_a, run_b)
    assert comparison["shared_creators"] == [
        {"id": 0, "creator_key": "Instagram:@c0", "handle": "@c0"}
    ]


def test_legacy_creator_keys_compare_with_normalized_keys():
    legacy = make_run("Fitness", ["strong"], ["Fitness"])
    for creator in legacy["result"]["candidates"]:
        creator["creator_key"] = creator["handle"]
    for entry in legacy["result"]["ranked"]:
        entry["creator_key"] = entry["id"]
    current = make_run("Fitness", ["strong"], ["Fitness"])
    comparison = compare_runs(legacy, current)
    assert comparison["shared_creators"][0]["creator_key"] == "Instagram:@c0"


def test_compare_runs_shape():
    run_a = make_run("Fitness", ["strong", "partial"], ["Fitness", "Yoga"])
    run_b = make_run("Yoga", ["partial", "strong"], ["Yoga", "Fitness"])
    comparison = compare_runs(run_a, run_b)
    assert len(comparison["shared_creators"]) == 2
    assert comparison["summary_a"]["n_strong"] == 1
    assert comparison["summary_b"]["n_strong"] == 1
