from __future__ import annotations

from typing import Callable
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from api.repositories.postgres_run_repository import PostgresRunRepository
from src import vector_store
from api.schemas.models import MatchJobResponse, MatchParams
from src.models import Brief


class PostgresJobManager:
    def __init__(self, connection_factory: Callable | None = None):
        self._connection_factory = connection_factory or vector_store.get_connection
        self._run_repository = PostgresRunRepository(connection_factory=self._connection_factory)

    def shutdown(self) -> None:
        return None

    def ensure_schema(self) -> None:
        self._run_repository.ensure_schema()

    def submit(self, brief: Brief, params: MatchParams, owner_id: str) -> MatchJobResponse:
        job_id = uuid4()
        owner = UUID(owner_id)
        with self._connection_factory() as conn:
            row = conn.execute(
                """
                INSERT INTO match_jobs (id, owner_id, brief, params)
                VALUES (%s, %s, %s, %s)
                RETURNING id, owner_id, brief, params, status, stage, progress,
                          run_id, outcome, error, created_at, updated_at
                """,
                (
                    job_id,
                    owner,
                    Jsonb({
                        "niche": brief.niche,
                        "platform": brief.platform,
                        "audience": brief.audience,
                        "vibe": brief.vibe,
                    }),
                    Jsonb(params.model_dump(mode="json")),
                ),
            ).fetchone()
        return _job_from_row(row)

    def get(self, job_id: UUID, owner_id: str | None = None) -> MatchJobResponse | None:
        where = "id = %s"
        params: list = [job_id]
        if owner_id:
            where += " AND owner_id = %s"
            params.append(UUID(owner_id))
        with self._connection_factory() as conn:
            row = conn.execute(
                f"""
                SELECT id, owner_id, brief, params, status, stage, progress,
                       run_id, outcome, error, created_at, updated_at
                FROM match_jobs
                WHERE {where}
                """,
                params,
            ).fetchone()
        return _job_from_row(row) if row else None

    def recent_count(self, owner_id: str, since) -> int:
        with self._connection_factory() as conn:
            return conn.execute(
                """
                SELECT COUNT(*)
                FROM match_jobs
                WHERE owner_id = %s AND created_at >= %s
                """,
                (UUID(owner_id), since),
            ).fetchone()[0]

    def requeue_stale(self, seconds: int) -> int:
        with self._connection_factory() as conn:
            row = conn.execute(
                """
                UPDATE match_jobs
                SET status = 'queued', stage = 'queued', claimed_at = NULL, updated_at = NOW()
                WHERE status = 'running'
                  AND (claimed_at IS NULL OR claimed_at < NOW() - (%s * INTERVAL '1 second'))
                """,
                (seconds,),
            )
            return row.rowcount

    def claim_next(self) -> dict | None:
        with self._connection_factory() as conn:
            row = conn.execute(
                """
                UPDATE match_jobs
                SET status = 'running', stage = 'embedding', claimed_at = NOW(), updated_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM match_jobs
                    WHERE status = 'queued'
                    ORDER BY created_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, owner_id, brief, params, status, stage, progress,
                          run_id, outcome, error, created_at, updated_at
                """,
            ).fetchone()
        return _job_from_row_dict(row) if row else None

    def update(
        self,
        job_id: UUID,
        *,
        stage: str | None = None,
        status: str | None = None,
        progress: dict | None = None,
        error: str | None = None,
        outcome: str | None = None,
        run_id: UUID | None = None,
    ) -> None:
        fields = ["updated_at = NOW()"]
        if status in {"succeeded", "failed", "cancelled"}:
            fields.append("claimed_at = NULL")
        else:
            fields.append("claimed_at = NOW()")
        params: list = []
        if stage is not None:
            fields.append("stage = %s")
            params.append(stage)
        if status is not None:
            fields.append("status = %s")
            params.append(status)
        if progress is not None:
            fields.append("progress = %s")
            params.append(Jsonb(progress))
        if error is not None:
            fields.append("error = %s")
            params.append(error)
        if outcome is not None:
            fields.append("outcome = %s")
            params.append(outcome)
        if run_id is not None:
            fields.append("run_id = %s")
            params.append(run_id)
        params.append(job_id)
        with self._connection_factory() as conn:
            conn.execute(
                f"UPDATE match_jobs SET {', '.join(fields)} WHERE id = %s",
                params,
            )


def _job_from_row(row) -> MatchJobResponse:
    return MatchJobResponse(
        job_id=row[0],
        status=row[4],
        stage=row[5],
        progress=row[6] or {},
        run_id=row[7],
        outcome=row[8],
        error=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


def _job_from_row_dict(row) -> dict:
    return {
        "id": row[0],
        "owner_id": str(row[1]),
        "brief": row[2],
        "params": row[3],
        "status": row[4],
        "stage": row[5],
        "progress": row[6] or {},
        "run_id": row[7],
        "outcome": row[8],
        "error": row[9],
        "created_at": row[10],
        "updated_at": row[11],
    }
