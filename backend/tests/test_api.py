import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from api.jobs.manager import JobManager
from api.main import create_app
from api.schemas.models import MatchJobResponse, MatchParams
from api.serialization import build_run_record
from src.models import Brief, Influencer


class MemoryRepository:
    def __init__(self):
        self.records = {}

    def ensure_schema(self):
        return None

    def create(self, record, owner_id=None):
        now = datetime.now(timezone.utc)
        saved = dict(record)
        saved["created_at"] = now
        saved["updated_at"] = now
        self.records[saved["id"]] = saved
        return saved

    def list(self, limit, cursor=None, owner_id=None):
        records = sorted(
            self.records.values(),
            key=lambda item: (item["created_at"], item["id"]),
            reverse=True,
        )
        return records[:limit], None

    def get(self, run_id, owner_id=None):
        return self.records.get(run_id)

    def delete(self, run_id, owner_id=None):
        return self.records.pop(run_id, None) is not None


class MemoryJobManager:
    def __init__(self):
        self.jobs = {}

    def submit(self, brief, params, owner_id=None):
        job_id = uuid4()
        now = datetime.now(timezone.utc)
        job = MatchJobResponse(
            job_id=job_id,
            status="queued",
            stage="queued",
            created_at=now,
            updated_at=now,
        )
        self.jobs[job_id] = job
        return job

    def get(self, job_id, owner_id=None):
        return self.jobs.get(job_id)

    def shutdown(self):
        return None


def make_result():
    brief = Brief(
        niche="Fitness",
        platform="TikTok",
        audience="busy millennials",
        vibe="high energy",
    )
    candidates = [
        Influencer(
            id=1,
            handle="@fit1",
            name="Fit One",
            niche="Fitness",
            secondary_niches=[],
            platform="TikTok",
            city="Austin",
            country="USA",
            language="English",
            followers=10_000,
            engagement=5.0,
            similarity=0.9,
            tags=["gym"],
            bio="Lifting daily.",
        ),
        Influencer(
            id=2,
            handle="@fit2",
            name="Fit Two",
            niche="Yoga",
            secondary_niches=["Fitness"],
            platform="TikTok",
            city="Austin",
            country="USA",
            language="English",
            followers=20_000,
            engagement=4.0,
            similarity=0.8,
            tags=["stretching"],
            bio="Movement and recovery.",
        ),
    ]
    return {
        "brief": brief,
        "params": {"top_k": 2, "top_n": 1},
        "candidates": candidates,
        "ranked": [{"id": 1, "fit": "strong", "source": "llm", "rationale": "Direct fit."}],
    }


def test_job_manager_persists_match():
    repository = MemoryRepository()
    manager = JobManager(
        repository,
        matcher=lambda job_id, brief, params: make_result(),
        indexed_count_provider=lambda: 10,
    )
    response = manager.submit(Brief(niche="Fitness", platform="TikTok"), MatchParams(top_k=2, top_n=1))
    for _ in range(50):
        current = manager.get(response.job_id)
        if current.status in {"succeeded", "failed"}:
            break
        time.sleep(0.01)
    assert current.status == "succeeded"
    assert current.outcome == "match"
    assert current.run_id in repository.records
    manager.shutdown()


def test_api_health_meta_and_match_job():
    repository = MemoryRepository()
    manager = MemoryJobManager()
    app = create_app(
        repository=repository,
        job_manager=manager,
        initialize_database=False,
        indexed_count=10,
    )
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").status_code == 200
        meta = client.get("/api/v1/meta")
        assert meta.status_code == 200
        assert "Fitness" in meta.json()["niches"]
        response = client.post(
            "/api/v1/match-jobs",
            json={
                "brief": {
                    "niche": "Fitness",
                    "platform": "TikTok",
                    "audience": "millennials",
                    "vibe": "high energy",
                },
                "params": {"top_k": 10, "top_n": 5},
            },
        )
        assert response.status_code == 202
        job = client.get(f"/api/v1/match-jobs/{response.json()['job_id']}")
        assert job.status_code == 200


def test_api_runs_export_compare_and_delete():
    repository = MemoryRepository()
    run_id = uuid4()
    repository.create(build_run_record(make_result(), run_id, indexed_count=10))
    app = create_app(
        repository=repository,
        job_manager=MemoryJobManager(),
        initialize_database=False,
        indexed_count=10,
    )
    with TestClient(app) as client:
        listed = client.get("/api/v1/runs")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["run_id"] == str(run_id)
        detail = client.get(f"/api/v1/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["ranked"][0]["creator_key"] == "TikTok:@fit1"
        exported = client.get(f"/api/v1/runs/{run_id}/export.csv")
        assert exported.status_code == 200
        assert "creator_key" in exported.text
        compared = client.post(
            "/api/v1/comparisons",
            json={"run_id_a": str(run_id), "run_id_b": str(run_id)},
        )
        assert compared.status_code == 200
        assert len(compared.json()["shared_creators"]) == 1
        assert client.delete(f"/api/v1/runs/{run_id}").status_code == 204
        assert client.get(f"/api/v1/runs/{run_id}").status_code == 404


def test_match_params_default_top_n_follows_top_k():
    from api.schemas.models import MatchParams

    assert MatchParams(top_k=1).top_n == 1


def test_api_normalizes_request_validation_errors():
    app = create_app(
        repository=MemoryRepository(),
        job_manager=MemoryJobManager(),
        initialize_database=False,
        indexed_count=10,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/match-jobs",
            json={
                "brief": {"niche": "Fitness", "platform": "Any"},
                "params": {"top_k": 2, "top_n": 3},
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
        assert "top_n" in response.json()["detail"]["message"]


def test_api_rejects_invalid_brief_when_not_ready():
    app = create_app(
        repository=MemoryRepository(),
        job_manager=MemoryJobManager(),
        initialize_database=False,
        indexed_count=0,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/match-jobs",
            json={"brief": {"niche": "Not a niche", "platform": "Any"}},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_NICHE"
        ready_response = client.post(
            "/api/v1/match-jobs",
            json={"brief": {"niche": "Fitness", "platform": "Any"}},
        )
        assert ready_response.status_code == 503
        assert ready_response.json()["detail"]["code"] == "INDEX_NOT_READY"
