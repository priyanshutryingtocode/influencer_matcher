from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.jobs.manager import JobManager, JobQueueFullError
from api.repositories.postgres_run_repository import InvalidCursor, PostgresRunRepository
from api.schemas.models import (
    ComparisonRequest,
    ComparisonResponse,
    MatchJobRequest,
    MatchJobResponse,
    MetaResponse,
    RunDetail,
    RunListResponse,
)
from api.serialization import run_detail, run_list_item
from api.services.compare_service import compare_runs
from api.services.csv_export import build_csv
from src import config, vector_store
from src.data_generator import NICHES, PLATFORMS

logger = logging.getLogger(__name__)


def create_app(
    repository=None,
    job_manager=None,
    initialize_database: bool = True,
    indexed_count: int | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        repo = application.state.run_repository
        manager = application.state.job_manager
        application.state.db_ready = False
        application.state.database_available = False
        application.state.indexed_count = indexed_count or 0
        application.state.index_checked_at = 0.0
        application.state.startup_error = None
        if initialize_database:
            repo = repo or PostgresRunRepository()
            application.state.run_repository = repo
            try:
                application.state.indexed_count = await asyncio.to_thread(_initialize_database, repo)
                application.state.database_available = True
                application.state.index_checked_at = time.monotonic()
                application.state.db_ready = application.state.indexed_count > 0
            except Exception as exc:
                application.state.database_available = False
                application.state.startup_error = type(exc).__name__
                logger.warning("API startup dependency check failed: %s", type(exc).__name__)
        else:
            application.state.database_available = repo is not None
            application.state.db_ready = application.state.database_available and application.state.indexed_count > 0
        if manager is None and repo is not None:
            manager = JobManager(
                repo,
                indexed_count_provider=lambda: application.state.indexed_count,
            )
            application.state.job_manager = manager
        if initialize_database:
            threading.Thread(target=_warm_embedding_model, name="embedding-warmup", daemon=True).start()
        yield
        if manager is not None:
            manager.shutdown()

    application = FastAPI(
        title="Influencer Matcher API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.run_repository = repository
    application.state.job_manager = job_manager
    application.state.db_ready = False
    application.state.database_available = repository is not None
    application.state.indexed_count = indexed_count or 0
    application.state.index_checked_at = 0.0
    application.state.startup_error = None
    application.state.uses_database = initialize_database

    origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.get("loc", []))
            message = first.get("msg", "Invalid request.")
            if location:
                message = f"{location}: {message}"
        else:
            message = "Invalid request."
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "VALIDATION_ERROR", "message": message}},
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled API error: %s", type(exc).__name__)
        response = JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "INTERNAL_ERROR",
                    "message": "The API could not complete the request.",
                }
            },
        )
        origin = request.headers.get("origin")
        if origin and origin in origins:
            response.headers["access-control-allow-origin"] = origin
            response.headers["vary"] = "Origin"
        return response

    @application.get("/health/live")
    def live():
        return {"status": "ok"}

    @application.get("/health/ready")
    def ready(request: Request):
        _refresh_index_state(request)
        if not request.app.state.database_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "DATABASE_UNAVAILABLE", "message": "The creator database is unavailable."},
            )
        if not request.app.state.db_ready or request.app.state.indexed_count <= 0:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "NOT_READY", "message": "The creator index is not ready."},
            )
        return {
            "status": "ready",
            "database": True,
            "indexed_creator_count": request.app.state.indexed_count,
            "embedding_model": config.LOCAL_EMBED_MODEL,
        }

    @application.get("/api/v1/meta", response_model=MetaResponse)
    def meta(request: Request):
        _refresh_index_state(request)
        ready_state = request.app.state.db_ready
        return {
            "niches": list(NICHES),
            "platforms": ["Any", *PLATFORMS],
            "defaults": {
                "audience": "Gen Z",
                "vibe": "warm, friendly",
                "top_k": config.DEFAULT_TOP_K_RETRIEVAL,
                "top_n": config.DEFAULT_TOP_N_RANKED,
            },
            "limits": {
                "top_k_min": 1,
                "top_k_max": config.MAX_TOP_K,
                "top_n_min": 1,
                "top_n_max": config.MAX_TOP_K,
                "audience_max_length": 300,
                "vibe_max_length": 500,
            },
            "index": {
                "status": "ready" if ready_state else "unavailable",
                "count": request.app.state.indexed_count,
                "embedding_model": config.LOCAL_EMBED_MODEL,
                "embed_dimensions": config.EMBED_DIMENSIONS,
            },
            "ranking": {
                "model": config.GEN_MODEL,
                "fit_levels": ["strong", "partial", "weak", "unknown"],
            },
        }

    @application.post(
        "/api/v1/match-jobs",
        response_model=MatchJobResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_match_job(payload: MatchJobRequest, request: Request):
        _validate_brief(payload.brief.niche, payload.brief.platform)
        _refresh_index_state(request)
        if not request.app.state.database_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "DATABASE_UNAVAILABLE", "message": "The creator database is unavailable."},
            )
        if not request.app.state.db_ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "INDEX_NOT_READY", "message": "Index the creators before matching."},
            )
        manager = request.app.state.job_manager
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "WORKER_UNAVAILABLE", "message": "The match worker is unavailable."},
            )
        try:
            return manager.submit(payload.brief.to_domain(), payload.params)
        except JobQueueFullError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "MATCH_QUEUE_FULL", "message": "The match queue is full. Try again shortly."},
            ) from exc

    @application.get("/api/v1/match-jobs/{job_id}", response_model=MatchJobResponse)
    def get_match_job(job_id: UUID, request: Request):
        job = request.app.state.job_manager.get(job_id) if request.app.state.job_manager else None
        if job is None:
            raise _not_found("MATCH_JOB_NOT_FOUND", "Match job not found.")
        return job

    @application.get("/api/v1/runs", response_model=RunListResponse)
    def list_runs(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = None,
    ):
        try:
            records, next_cursor = _repository(request).list(limit=limit, cursor=cursor)
        except InvalidCursor as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_CURSOR", "message": str(exc)},
            ) from exc
        return {
            "items": [run_list_item(record) for record in records],
            "next_cursor": next_cursor,
        }

    @application.get("/api/v1/runs/{run_id}/export.csv")
    def export_run(run_id: UUID, request: Request):
        record = _repository(request).get(run_id)
        if record is None:
            raise _not_found("RUN_NOT_FOUND", "Run not found.")
        return Response(
            content=build_csv(record),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="shortlist-{run_id}.csv"'},
        )

    @application.get("/api/v1/runs/{run_id}", response_model=RunDetail)
    def get_run(run_id: UUID, request: Request):
        record = _repository(request).get(run_id)
        if record is None:
            raise _not_found("RUN_NOT_FOUND", "Run not found.")
        return run_detail(record)

    @application.delete("/api/v1/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_run(run_id: UUID, request: Request):
        if not _repository(request).delete(run_id):
            raise _not_found("RUN_NOT_FOUND", "Run not found.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.post("/api/v1/comparisons", response_model=ComparisonResponse)
    def compare(payload: ComparisonRequest, request: Request):
        repository = _repository(request)
        run_a = repository.get(payload.run_id_a)
        run_b = repository.get(payload.run_id_b)
        if run_a is None or run_b is None:
            raise _not_found("RUN_NOT_FOUND", "One or both runs were not found.")
        return compare_runs(run_a, run_b)

    return application


def _initialize_database(repository) -> int:
    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)
        count = vector_store.count_influencers(conn)
    repository.ensure_schema()
    return count


def _refresh_index_state(request: Request) -> None:
    application = request.app
    if not application.state.uses_database:
        return
    now = time.monotonic()
    if application.state.index_checked_at and now - application.state.index_checked_at < 5:
        return
    try:
        with vector_store.get_connection() as conn:
            application.state.indexed_count = vector_store.count_influencers(conn)
        application.state.database_available = True
        application.state.index_checked_at = now
        application.state.startup_error = None
        application.state.db_ready = application.state.indexed_count > 0
    except Exception as exc:
        application.state.database_available = False
        application.state.index_checked_at = now
        application.state.db_ready = False
        application.state.startup_error = type(exc).__name__


def _warm_embedding_model() -> None:
    try:
        from src.embeddings import get_sentence_transformer

        get_sentence_transformer()
    except Exception as exc:
        logger.warning("Embedding warmup failed: %s", type(exc).__name__)


def _repository(request: Request):
    repository = request.app.state.run_repository
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "HISTORY_UNAVAILABLE", "message": "Run history is unavailable."},
        )
    return repository


def _validate_brief(niche: str, platform: str) -> None:
    if niche not in NICHES:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_NICHE", "message": "Choose a supported niche."},
        )
    if platform not in {"Any", *PLATFORMS}:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_PLATFORM", "message": "Choose a supported platform."},
        )


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": code, "message": message},
    )


app = create_app()
