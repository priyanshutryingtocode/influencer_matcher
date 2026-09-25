import threading

import pytest

from api.jobs.manager import JobQueueFullError, JobManager, JobRateLimitError, MAX_JOBS
from api.schemas.models import MatchParams
from src.models import Brief


class EmptyRepository:
    def create(self, record):
        return record


def test_job_queue_rejects_work_when_all_jobs_are_live():
    started = threading.Event()
    release = threading.Event()

    def matcher(job_id, brief, params):
        started.set()
        release.wait(timeout=2)
        return None

    manager = JobManager(EmptyRepository(), matcher=matcher, max_workers=1)
    brief = Brief(niche="Fitness", platform="Any")
    params = MatchParams(top_k=3, top_n=1)
    manager.submit(brief, params)
    assert started.wait(timeout=2)
    for _ in range(MAX_JOBS - 1):
        manager.submit(brief, params)
    with pytest.raises(JobQueueFullError):
        manager.submit(brief, params)
    release.set()
    manager.shutdown()


def test_job_manager_enforces_per_owner_rate_limit():
    manager = JobManager(
        EmptyRepository(),
        matcher=lambda job_id, brief, params: None,
        max_jobs=4,
        max_jobs_per_owner_per_hour=1,
    )
    brief = Brief(niche="Fitness", platform="Any")
    params = MatchParams(top_k=3, top_n=1)
    manager.submit(brief, params, owner_id="owner-1")
    with pytest.raises(JobRateLimitError):
        manager.submit(brief, params, owner_id="owner-1")
    manager.shutdown()
