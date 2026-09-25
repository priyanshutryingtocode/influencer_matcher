from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable
from uuid import UUID, uuid4

from api.schemas.models import MatchJobResponse, MatchParams
from api.serialization import build_run_record
from src.gemini_client import get_client
from src.match_service import rank_match, retrieve_candidates
from src.models import Brief

logger = logging.getLogger(__name__)

MAX_JOBS = 128
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


class JobQueueFullError(RuntimeError):
    pass


class JobRateLimitError(RuntimeError):
    pass


class JobManager:
    def __init__(
        self,
        repository,
        matcher: Callable | None = None,
        client_factory: Callable | None = None,
        indexed_count_provider: Callable[[], int | None] | None = None,
        max_workers: int = 1,
        max_jobs: int = MAX_JOBS,
        max_jobs_per_owner_per_hour: int | None = None,
    ):
        self._repository = repository
        self._matcher = matcher or self._default_match
        self._client_factory = client_factory or get_client
        self._indexed_count_provider = indexed_count_provider or (lambda: None)
        self._max_jobs = max_jobs
        self._max_jobs_per_owner_per_hour = max_jobs_per_owner_per_hour
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="match-job")
        self._lock = RLock()
        self._jobs: dict[UUID, dict] = {}
        self._client = None

    def submit(self, brief: Brief, params: MatchParams, owner_id: str | None = None) -> MatchJobResponse:
        job_id = uuid4()
        now = _now()
        state = {
            "job_id": job_id,
            "owner_id": owner_id,
            "status": "queued",
            "stage": "queued",
            "progress": {},
            "run_id": None,
            "outcome": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._prune_locked()
            if owner_id and self._max_jobs_per_owner_per_hour is not None:
                cutoff = now - timedelta(hours=1)
                recent = sum(
                    1
                    for existing in self._jobs.values()
                    if existing.get("owner_id") == owner_id and existing["created_at"] >= cutoff
                )
                if recent >= self._max_jobs_per_owner_per_hour:
                    raise JobRateLimitError("The hourly match limit has been reached.")
            if len(self._jobs) >= self._max_jobs:
                raise JobQueueFullError("The match queue is full.")
            self._jobs[job_id] = state
        self._executor.submit(self._execute, job_id, brief, params, owner_id)
        return self.get(job_id)

    def get(self, job_id: UUID, owner_id: str | None = None) -> MatchJobResponse | None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None or (owner_id is not None and state.get("owner_id") != owner_id):
                return None
            return MatchJobResponse.model_validate({key: value for key, value in state.items() if key != "owner_id"})

    def shutdown(self) -> None:
        with self._lock:
            for state in self._jobs.values():
                if state["status"] == "queued":
                    state.update(
                        status="cancelled",
                        stage="cancelled",
                        error="The API shut down before this match started.",
                        updated_at=_now(),
                    )
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _execute(self, job_id: UUID, brief: Brief, params: MatchParams, owner_id: str | None) -> None:
        self._update(job_id, status="running", stage="embedding")
        try:
            result = self._matcher(job_id, brief, params)
            if result is None:
                self._update(
                    job_id,
                    status="succeeded",
                    stage="complete",
                    outcome="no_results",
                    progress={"retrieved_candidate_count": 0},
                )
                return
            self._update(job_id, stage="persisting")
            record = build_run_record(
                result,
                uuid4(),
                indexed_count=self._indexed_count_provider(),
            )
            record["owner_id"] = owner_id
            saved = self._repository.create(record)
            self._update(
                job_id,
                status="succeeded",
                stage="complete",
                outcome="match",
                run_id=saved["id"],
            )
        except Exception:
            logger.exception("Match job %s failed", job_id)
            self._update(
                job_id,
                status="failed",
                stage="failed",
                error="The match could not be completed. Check the API service and try again.",
            )

    def _default_match(self, job_id: UUID, brief: Brief, params: MatchParams):
        self._update(job_id, stage="retrieval")
        candidates = retrieve_candidates(brief, top_k=params.top_k)
        if not candidates:
            return None
        self._update(job_id, stage="ranking", progress={"retrieved_candidate_count": len(candidates)})
        ranked = rank_match(brief, candidates, top_n=params.top_n, client=self._get_client())
        return {
            "brief": brief,
            "params": {"top_k": params.top_k, "top_n": params.top_n},
            "candidates": candidates,
            "ranked": ranked,
        }

    def _get_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._client_factory()
        return self._client

    def _prune_locked(self) -> None:
        for job_id, state in list(self._jobs.items()):
            if len(self._jobs) < self._max_jobs:
                break
            if state["status"] in TERMINAL_STATUSES:
                self._jobs.pop(job_id, None)

    def _update(self, job_id: UUID, **changes) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.update(changes)
            state["updated_at"] = _now()


def _now() -> datetime:
    return datetime.now(timezone.utc)
