from __future__ import annotations

import argparse
import logging
import signal
import threading

from psycopg.errors import UniqueViolation

from api.jobs.postgres import PostgresJobManager
from api.repositories.postgres_run_repository import PostgresRunRepository
from api.schemas.models import MatchParams
from api.serialization import build_run_record
from src import config
from src.gemini_client import get_client
from src.match_service import rank_match, retrieve_candidates
from src.models import Brief

logger = logging.getLogger(__name__)


def process_job(job: dict, jobs: PostgresJobManager, runs: PostgresRunRepository, client) -> None:
    brief = Brief(**job["brief"])
    params = MatchParams(**job["params"])
    job_id = job["id"]
    jobs.update(job_id, stage="retrieval")
    candidates = retrieve_candidates(brief, top_k=params.top_k)
    if not candidates:
        jobs.update(
            job_id,
            status="succeeded",
            stage="complete",
            outcome="no_results",
            progress={"retrieved_candidate_count": 0},
        )
        return
    jobs.update(job_id, stage="ranking", progress={"retrieved_candidate_count": len(candidates)})
    ranked = rank_match(brief, candidates, top_n=params.top_n, client=client)
    jobs.update(job_id, stage="persisting")
    record = build_run_record(
        {
            "brief": brief,
            "params": {"top_k": params.top_k, "top_n": params.top_n},
            "candidates": candidates,
            "ranked": ranked,
        },
        job_id,
    )
    record["owner_id"] = job["owner_id"]
    try:
        saved = runs.create(record, owner_id=job["owner_id"])
    except UniqueViolation:
        saved = runs.get(job_id, owner_id=job["owner_id"])
        if saved is None:
            raise
    jobs.update(
        job_id,
        status="succeeded",
        stage="complete",
        outcome="match",
        run_id=saved["id"],
    )


def run_worker(once: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    jobs = PostgresJobManager()
    runs = PostgresRunRepository()
    if config.RUN_SCHEMA_ON_STARTUP:
        jobs.ensure_schema()
    stop = threading.Event()
    client = None

    def request_stop(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stop.is_set():
        jobs.requeue_stale(config.STALE_JOB_AFTER_SECONDS)
        job = jobs.claim_next()
        if job is None:
            if once:
                return
            stop.wait(2)
            continue
        try:
            if client is None:
                client = get_client()
            process_job(job, jobs, runs, client)
        except Exception:
            logger.exception("Worker failed job %s", job["id"])
            jobs.update(
                job["id"],
                status="failed",
                stage="failed",
                error="The match could not be completed. Please try again.",
            )
        if once:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run durable influencer match jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    args = parser.parse_args()
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
