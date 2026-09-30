from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import current_user_id
from api.jobs.manager import JobManager, JobQueueFullError
from api.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
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
from src.platforms import PLATFORMS

logger = logging.getLogger(__name__)


def create_app(
    repository=None,
    job_manager=None,
    initialize_database: bool = True,
    indexed_count: int | None = None,
) -> FastAPI:
    ip_rate_limiter = SlidingWindowRateLimiter(
        config.MAX_MATCH_JOBS_PER_IP_PER_HOUR,
        window_seconds=3600,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if config.APP_ENV in {"demo", "production"}:
            _validate_public_configuration()
        repo = application.state.run_repository
        manager = application.state.job_manager
        application.state.db_ready = False
        application.state.database_available = False
        application.state.index_model_mismatch = False
        application.state.indexed_count = indexed_count or 0
        application.state.index_checked_at = 0.0
        application.state.startup_error = None
        if initialize_database:
            repo = repo or PostgresRunRepository()
            application.state.run_repository = repo
            try:
                if config.RUN_SCHEMA_ON_STARTUP:
                    application.state.indexed_count = await asyncio.to_thread(_initialize_database, repo)
                else:
                    application.state.indexed_count = await asyncio.to_thread(_check_database)
                application.state.database_available = True
                application.state.index_checked_at = time.monotonic()
                application.state.db_ready = application.state.indexed_count > 0
            except vector_store.IndexModelMismatch as exc:
                application.state.database_available = True
                application.state.index_model_mismatch = True
                application.state.indexed_count = 0
                application.state.db_ready = False
                application.state.startup_error = "INDEX_MODEL_MISMATCH"
                logger.error("Creator index needs a reindex: %s", exc)
            except Exception as exc:
                application.state.database_available = False
                application.state.startup_error = type(exc).__name__
                logger.warning("API startup dependency check failed: %s", type(exc).__name__)
        else:
            application.state.database_available = repo is not None
            application.state.db_ready = application.state.database_available and application.state.indexed_count > 0
        if manager is None and repo is not None:
            # Jobs are in-process. The free tier cannot afford a worker, so a
            # restart loses an in-flight match; completed runs are persisted.
            manager = JobManager(
                repo,
                indexed_count_provider=lambda: application.state.indexed_count,
                max_jobs=config.MAX_MEMORY_JOBS,
            )
            application.state.job_manager = manager
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
    application.state.index_model_mismatch = False

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
        # CORSMiddleware already adds the allow-origin header on the way out for
        # permitted origins, so this response needs nothing extra.
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "INTERNAL_ERROR",
                    "message": "The API could not complete the request.",
                }
            },
        )

    @application.get("/health/live")
    def live():
        return {"status": "ok", "memory_rss_mb": _rss_mb()}

    @application.get("/health/ready")
    def ready(request: Request):
        _refresh_index_state(request)
        if not request.app.state.database_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "DATABASE_UNAVAILABLE", "message": "The creator database is unavailable."},
            )
        if request.app.state.index_model_mismatch:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "INDEX_MODEL_MISMATCH",
                    "message": (
                        f"The creator index was built with a different embedding model than "
                        f"{config.EMBED_MODEL}. It must be re-embedded before matching works."
                    ),
                },
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
            "embedding_model": config.EMBED_MODEL,
            "embed_dimensions": config.EMBED_DIMENSIONS,
            "memory_rss_mb": _rss_mb(),
        }

    @application.get("/api/v1/meta", response_model=MetaResponse)
    def meta(request: Request):
        _refresh_index_state(request)
        ready_state = request.app.state.db_ready
        return {
            "platforms": ["Any", *PLATFORMS],
            "defaults": {
                # Empty, not a sample brief: the Search page offers starter
                # prompts, and pre-filling would make it ambiguous whether the
                # user actually typed it. The key has to exist even when empty,
                # because the frontend reads it on every meta load.
                "goal": "",
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
                "goal_min_length": config.MIN_GOAL_LENGTH,
                "goal_max_length": config.MAX_GOAL_LENGTH,
            },
            "index": {
                "status": (
                    "reindex_required"
                    if request.app.state.index_model_mismatch
                    else "ready" if ready_state else "unavailable"
                ),
                "count": request.app.state.indexed_count,
                "embedding_model": config.EMBED_MODEL,
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
        _validate_brief(payload.brief.goal, payload.brief.platform)
        owner_id = current_user_id(request)
        if config.AUTH_REQUIRED and not owner_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AUTH_REQUIRED", "message": "Sign in before running a match."},
            )
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
                detail={"code": "MATCH_SERVICE_UNAVAILABLE", "message": "The match service is unavailable."},
            )
        if config.APP_ENV == "demo":
            try:
                ip_rate_limiter.check(_client_ip(request))
            except RateLimitExceeded as exc:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "MATCH_IP_RATE_LIMIT", "message": "The demo match limit has been reached for this network."},
                ) from exc
        try:
            brief = payload.brief.to_domain()
            if owner_id is None:
                return manager.submit(brief, payload.params)
            return manager.submit(brief, payload.params, owner_id=owner_id)
        except JobQueueFullError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "MATCH_QUEUE_FULL", "message": "The match queue is full. Try again shortly."},
            ) from exc

    @application.get("/api/v1/match-jobs/{job_id}", response_model=MatchJobResponse)
    def get_match_job(job_id: UUID, request: Request):
        owner_id = current_user_id(request)
        manager = request.app.state.job_manager
        if owner_id is None:
            job = manager.get(job_id) if manager else None
        else:
            job = manager.get(job_id, owner_id=owner_id) if manager else None
        if job is None:
            raise _not_found("MATCH_JOB_NOT_FOUND", "Match job not found.")
        return job

    @application.get("/api/v1/runs", response_model=RunListResponse)
    def list_runs(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = None,
    ):
        owner_id = current_user_id(request)
        try:
            repository = _repository(request)
            if owner_id is None:
                records, next_cursor = repository.list(limit=limit, cursor=cursor)
            else:
                records, next_cursor = repository.list(limit=limit, cursor=cursor, owner_id=owner_id)
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
        owner_id = current_user_id(request)
        repository = _repository(request)
        record = repository.get(run_id) if owner_id is None else repository.get(run_id, owner_id=owner_id)
        if record is None:
            raise _not_found("RUN_NOT_FOUND", "Run not found.")
        return Response(
            content=build_csv(record),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="shortlist-{run_id}.csv"'},
        )

    @application.get("/api/v1/runs/{run_id}", response_model=RunDetail)
    def get_run(run_id: UUID, request: Request):
        owner_id = current_user_id(request)
        repository = _repository(request)
        record = repository.get(run_id) if owner_id is None else repository.get(run_id, owner_id=owner_id)
        if record is None:
            raise _not_found("RUN_NOT_FOUND", "Run not found.")
        return run_detail(record)

    @application.delete("/api/v1/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_run(run_id: UUID, request: Request):
        owner_id = current_user_id(request)
        repository = _repository(request)
        deleted = repository.delete(run_id) if owner_id is None else repository.delete(run_id, owner_id=owner_id)
        if not deleted:
            raise _not_found("RUN_NOT_FOUND", "Run not found.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.post("/api/v1/comparisons", response_model=ComparisonResponse)
    def compare(payload: ComparisonRequest, request: Request):
        owner_id = current_user_id(request)
        repository = _repository(request)
        run_a = repository.get(payload.run_id_a) if owner_id is None else repository.get(payload.run_id_a, owner_id=owner_id)
        run_b = repository.get(payload.run_id_b) if owner_id is None else repository.get(payload.run_id_b, owner_id=owner_id)
        if run_a is None or run_b is None:
            raise _not_found("RUN_NOT_FOUND", "One or both runs were not found.")
        return compare_runs(run_a, run_b)

    return application


def _validate_public_configuration() -> None:
    missing = []
    if not config.AUTH_REQUIRED:
        missing.append("AUTH_REQUIRED=true")
    if not config.DATABASE_URL:
        missing.append("DATABASE_URL")
    if not config.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not config.SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not (config.SUPABASE_JWT_SECRET or config.SUPABASE_JWKS_URL):
        missing.append("SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL")
    if not os.environ.get("CORS_ALLOWED_ORIGINS", "").strip():
        missing.append("CORS_ALLOWED_ORIGINS")
    if missing:
        raise RuntimeError("Public deployment configuration is missing: " + ", ".join(missing))


def _initialize_database(repository) -> int:
    repository.ensure_schema()
    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)
        vector_store.assert_index_matches_config(conn)
        return vector_store.count_influencers(conn)


def _check_database() -> int:
    with vector_store.get_connection() as conn:
        vector_store.assert_index_matches_config(conn)
        return vector_store.count_influencers(conn)


def _rss_mb() -> float | None:
    """Current resident set size in MB, or None where /proc is unavailable.

    The free service dies at 512 MB, so the number that matters is what the
    process is holding right now, not its peak.
    """
    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        return round(resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)
    except (OSError, IndexError, ValueError):
        return None


def _refresh_index_state(request: Request) -> None:
    application = request.app
    if not application.state.uses_database:
        return
    now = time.monotonic()
    if application.state.index_checked_at and now - application.state.index_checked_at < 5:
        return
    try:
        with vector_store.get_connection() as conn:
            vector_store.assert_index_matches_config(conn)
            application.state.indexed_count = vector_store.count_influencers(conn)
        application.state.database_available = True
        application.state.index_checked_at = now
        application.state.startup_error = None
        application.state.index_model_mismatch = False
        application.state.db_ready = application.state.indexed_count > 0
    except vector_store.IndexModelMismatch:
        # Re-checked on every refresh so a reindex run against the live
        # database flips the service back to ready without a redeploy.
        application.state.database_available = True
        application.state.index_checked_at = now
        application.state.index_model_mismatch = True
        application.state.indexed_count = 0
        application.state.db_ready = False
        application.state.startup_error = "INDEX_MODEL_MISMATCH"
    except Exception as exc:
        application.state.database_available = False
        application.state.index_checked_at = now
        application.state.db_ready = False
        application.state.startup_error = type(exc).__name__


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        candidate = forwarded.split(",")[-1].strip()
        if candidate:
            return candidate
    return request.client.host if request.client else "unknown"


def _repository(request: Request):
    repository = request.app.state.run_repository
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "HISTORY_UNAVAILABLE", "message": "Run history is unavailable."},
        )
    return repository


def _validate_brief(goal: str, platform: str) -> None:
    """Free-text briefs are open-ended; only length and platform are checked.

    The old check rejected anything outside the generator's 30 verticals,
    which is what forced brief input to be a taxonomy value rather than a
    description of what the brand actually wants.
    """
    text = (goal or "").strip()
    if len(text) < config.MIN_GOAL_LENGTH:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "GOAL_TOO_SHORT",
                "message": f"Describe what you are promoting in at least {config.MIN_GOAL_LENGTH} characters.",
            },
        )
    if len(text) > config.MAX_GOAL_LENGTH:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "GOAL_TOO_LONG",
                "message": f"Keep the brief under {config.MAX_GOAL_LENGTH} characters.",
            },
        )
    if not any(char.isalnum() for char in text):
        raise HTTPException(
            status_code=422,
            detail={"code": "GOAL_EMPTY", "message": "Describe what you are promoting in words."},
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
