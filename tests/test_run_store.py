"""Tests for views.run_store: persistence round-trips, safety, CSV export."""

import json

import pytest

from src.models import Brief, Influencer
from views import run_store


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
    candidates = [make_influencer(i) for i in range(n)]
    ranked = [
        {"id": i, "fit": "strong", "rationale": f"r{i}", "source": "llm"}
        for i in range(n)
    ]
    return {
        "brief": Brief(niche=niche, platform=platform, audience="gen z", vibe="warm"),
        "params": {"top_k": 10, "top_n": n},
        "candidates": candidates,
        "ranked": ranked,
    }


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(run_store, "RUNS_DIR", tmp_path / ".runs")
    return run_store.RUNS_DIR


def test_save_list_load_roundtrip():
    run = make_run()
    run_id = run_store.save_run(run["brief"], run["ranked"], run["candidates"], run["params"])

    metas = run_store.list_runs()
    assert len(metas) == 1
    assert metas[0]["run_id"] == run_id
    assert metas[0]["niche"] == "Fitness"
    assert metas[0]["n_results"] == 3
    assert metas[0]["n_strong"] == 3

    loaded = run_store.load_run(run_id)
    assert loaded is not None
    assert loaded["brief"].niche == "Fitness"
    assert loaded["brief"].platform == "Any"
    assert [c.id for c in loaded["candidates"]] == [0, 1, 2]
    assert loaded["ranked"] == run["ranked"]
    assert loaded["params"] == {"top_k": 10, "top_n": 3}

    inf = loaded["candidates"][0]
    assert inf.handle == "@c0"
    assert inf.similarity == pytest.approx(0.8123)
    assert inf.embedding is None  # embeddings are never persisted


def test_saved_json_excludes_embedding():
    run = make_run()
    run_id = run_store.save_run(run["brief"], run["ranked"], run["candidates"])
    raw = json.loads((run_store.RUNS_DIR / f"{run_id}.json").read_text(encoding="utf-8"))
    assert all("embedding" not in c for c in raw["candidates"])


def test_list_runs_newest_first_and_delete():
    # ids as save_run would produce them (slugified lowercase)
    ids = ["20260101-000000-fitness-tiktok", "20260102-000000-yoga-any"]
    saved_ats = ["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"]
    run_store.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    for run_id, saved_at in zip(ids, saved_ats):
        payload = {
            "version": 1, "run_id": run_id,
            "saved_at": saved_at,
            "params": {}, "brief": {"niche": "Fitness", "platform": "Any"},
            "candidates": [], "ranked": [],
        }
        (run_store.RUNS_DIR / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    assert [m["run_id"] for m in run_store.list_runs()] == list(reversed(ids))

    assert run_store.delete_run(ids[0]) is True
    assert run_store.delete_run(ids[0]) is False  # already gone
    remaining = run_store.list_runs()
    assert len(remaining) == 1 and remaining[0]["run_id"] == ids[1]


def test_load_run_rejects_traversal_and_missing(tmp_path):
    assert run_store.load_run("../../etc/passwd") is None
    assert run_store.load_run("no-such-run") is None
    assert run_store.delete_run("../escape") is False


def test_corrupt_files_skipped_not_fatal(runs_dir):
    runs_dir.mkdir(parents=True)
    (runs_dir / "bad1-Fitness-Any.json").write_text("{not json", encoding="utf-8")
    (runs_dir / "bad2-Fitness-Any.json").write_text('{"brief": 1}', encoding="utf-8")

    assert run_store.list_runs() == []
    assert run_store.load_run("bad1-Fitness-Any") is None


def test_build_csv_contents():
    run = make_run(n=2)
    csv_text = run_store.build_csv({"candidates": run["candidates"], "ranked": run["ranked"]})
    lines = csv_text.strip().splitlines()

    assert lines[0].split(",")[0] == "rank"
    assert len(lines) == 3

    import csv as _csv
    rows = list(_csv.DictReader(csv_text.splitlines()))
    assert rows[1]["handle"] == "@c1"
    assert rows[1]["followers"] == "50000"
    assert rows[1]["tags"] == "gym|HIIT"
    assert rows[1]["brand_collaborations"] == "Nike"
    assert rows[1]["semantic_similarity"] == "0.8123"
