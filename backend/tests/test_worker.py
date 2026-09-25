from uuid import uuid4

import worker
from src.models import Brief, Influencer


class FakeJobs:
    def __init__(self):
        self.updates = []

    def update(self, job_id, **changes):
        self.updates.append((job_id, changes))


class FakeRuns:
    def create(self, record, owner_id=None):
        assert owner_id
        record["id"] = record["id"]
        return {"id": record["id"]}


def test_worker_processes_and_persists_job(monkeypatch):
    candidate = Influencer(
        id=1,
        handle="@fit1",
        name="Fit One",
        niche="Fitness",
        platform="TikTok",
        city="Austin",
        followers=10_000,
        engagement=5.0,
        similarity=0.9,
    )
    result = {
        "brief": Brief(niche="Fitness", platform="TikTok"),
        "params": {"top_k": 2, "top_n": 1},
        "candidates": [candidate],
        "ranked": [{"id": 1, "fit": "strong", "source": "llm", "rationale": "Direct fit."}],
    }
    monkeypatch.setattr(worker, "retrieve_candidates", lambda brief, top_k: result["candidates"])
    monkeypatch.setattr(worker, "rank_match", lambda brief, candidates, top_n, client: result["ranked"])
    jobs = FakeJobs()
    runs = FakeRuns()
    job_id = uuid4()
    worker.process_job(
        {
            "id": job_id,
            "owner_id": str(uuid4()),
            "brief": {"niche": "Fitness", "platform": "TikTok", "audience": "", "vibe": ""},
            "params": {"top_k": 2, "top_n": 1},
        },
        jobs,
        runs,
        object(),
    )
    assert jobs.updates[-1][1]["status"] == "succeeded"
    assert jobs.updates[-1][1]["run_id"] is not None
