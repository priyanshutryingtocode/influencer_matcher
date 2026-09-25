import csv
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from api.serialization import build_run_record, run_detail
from api.services.csv_export import build_csv
from src.models import Brief, Influencer


def make_influencer(id_: int, **overrides) -> Influencer:
    defaults = dict(
        id=id_, handle=f"@c{id_}", name=f"Creator {id_}", niche="Fitness",
        secondary_niches=["Yoga"], platform="TikTok", city="Austin",
        country="USA", language="English", followers=50_000, engagement=5.5,
        average_views=20_000, average_likes=2_500, average_comments=150,
        verified=False, posts_per_week=5, account_age_years=3,
        content_style="Educational", audience_age="18-24",
        audience_gender="60% Female", audience_country="USA",
        brand_collaborations=["Nike"], tags=["gym", "HIIT"],
        bio="Lifting daily.", similarity=0.8123,
    )
    defaults.update(overrides)
    return Influencer(**defaults)


def make_run(niche="Fitness", platform="Any", n=3) -> dict:
    brief = Brief(niche=niche, platform=platform, audience="gen z", vibe="warm")
    candidates = [make_influencer(i) for i in range(n)]
    ranked = [
        {"id": i, "fit": "strong", "rationale": f"r{i}", "source": "llm"}
        for i in range(n)
    ]
    return {
        "brief": brief,
        "params": {"top_k": 10, "top_n": n},
        "candidates": candidates,
        "ranked": ranked,
    }


def stored_run(n=3):
    record = build_run_record(make_run(n=n), uuid4(), indexed_count=10)
    now = datetime.now(timezone.utc)
    record["created_at"] = now
    record["updated_at"] = now
    return record


def test_run_record_keeps_snapshot_without_embeddings():
    record = stored_run()
    assert record["result"]["candidates"][0]["creator_key"] == "TikTok:@c0"
    assert "embedding" not in record["result"]["candidates"][0]
    detail = run_detail(record)
    assert detail.ranked[0].evidence
    assert detail.summary.n_results == 3


def test_legacy_run_detail_normalizes_creator_keys():
    record = stored_run(n=1)
    record["result"]["candidates"][0]["creator_key"] = "@c0"
    record["result"]["ranked"][0]["creator_key"] = "@c0"
    detail = run_detail(record)
    assert detail.candidates[0].creator_key == "TikTok:@c0"
    assert detail.ranked[0].creator_key == "TikTok:@c0"


def test_even_shortlist_summary_rounds_median_followers():
    run = make_run(n=2)
    run["candidates"][0].followers = 10_001
    run["candidates"][1].followers = 20_000
    record = build_run_record(run, uuid4(), indexed_count=10)
    assert record["summary"]["median_followers"] == 15_000


def test_build_csv_contents_and_formula_protection():
    run = make_run(n=2)
    record = build_run_record(run, uuid4(), indexed_count=10)
    record["created_at"] = datetime.now(timezone.utc)
    record["updated_at"] = record["created_at"]
    record["result"]["candidates"][0]["handle"] = "=danger"
    csv_text = build_csv(record)
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert rows[0]["handle"] == "'=danger"
    assert rows[1]["handle"] == "@c1"
    assert rows[0]["tags"] == "gym|HIIT"
    assert rows[0]["brand_collaborations"] == "Nike"
    assert rows[0]["semantic_similarity"] == "0.8123"
    assert rows[0]["evidence"]


@pytest.mark.parametrize("run_id", [uuid4(), uuid4()])
def test_run_records_have_unique_identifiers(run_id):
    record = build_run_record(make_run(n=1), run_id, indexed_count=10)
    assert record["id"] == run_id
