import threading

import pytest

from api.jobs.manager import JobQueueFullError, JobManager
from api.schemas.models import MatchParams
from src.models import Brief


class EmptyRepository:
    def create(self, record):
        return record


def test_job_queue_rejects_work_when_all_jobs_are_live():
    started = threading.Event()
    release = threading.Event()
    max_jobs = 3

    def matcher(job_id, brief, params):
        started.set()
        release.wait(timeout=2)
        return None

    manager = JobManager(EmptyRepository(), matcher=matcher, max_workers=1, max_jobs=max_jobs)
    brief = Brief(goal="at-home strength training for gen z", platform="Any")
    params = MatchParams(top_k=3, top_n=1)
    manager.submit(brief, params)
    assert started.wait(timeout=2)
    for _ in range(max_jobs - 1):
        manager.submit(brief, params)
    with pytest.raises(JobQueueFullError):
        manager.submit(brief, params)
    release.set()
    manager.shutdown()
