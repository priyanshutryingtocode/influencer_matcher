from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from psycopg.types.json import Jsonb

from src import vector_store


class InvalidCursor(ValueError):
    pass


class PostgresRunRepository:
    def __init__(self, connection_factory: Callable | None = None):
        self._connection_factory = connection_factory or vector_store.get_connection

    def ensure_schema(self) -> None:
        migration_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self._connection_factory() as conn:
            for migration in sorted(migration_dir.glob("*.sql")):
                conn.execute(migration.read_text(encoding="utf-8"))

    def check_schema(self) -> None:
        with self._connection_factory() as conn:
            conn.execute("SELECT 1 FROM match_runs LIMIT 1").fetchone()
            conn.execute("SELECT 1 FROM match_jobs LIMIT 1").fetchone()

    def create(self, record: dict, owner_id=None) -> dict:
        owner = _as_uuid(owner_id or record.get("owner_id"))
        with self._connection_factory() as conn:
            row = conn.execute(
                """
                INSERT INTO match_runs
                    (id, owner_id, brief, params, pipeline, result, warnings, summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, owner_id, brief, params, pipeline, result, warnings, summary,
                          created_at, updated_at
                """,
                (
                    record["id"],
                    owner,
                    Jsonb(record["brief"]),
                    Jsonb(record["params"]),
                    Jsonb(record["pipeline"]),
                    Jsonb(record["result"]),
                    Jsonb(record["warnings"]),
                    Jsonb(record["summary"]),
                ),
            ).fetchone()
        return _record_from_row(row)

    def list(self, limit: int, cursor: str | None = None, owner_id=None) -> tuple[list[dict], str | None]:
        conditions: list[str] = []
        params: list[Any] = []
        owner = _as_uuid(owner_id)
        if owner is not None:
            conditions.append("owner_id = %s")
            params.append(owner)
        if cursor:
            created_at, run_id = _decode_cursor(cursor)
            conditions.append("(created_at < %s OR (created_at = %s AND id < %s))")
            params.extend([created_at, created_at, run_id])
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit + 1)
        with self._connection_factory() as conn:
            rows = conn.execute(
                f"""
                SELECT id, created_at, brief, warnings, summary
                FROM match_runs
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        has_more = len(rows) > limit
        visible = rows[:limit]
        next_cursor = _encode_cursor(visible[-1][1], visible[-1][0]) if has_more and visible else None
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "brief": row[2],
                "warnings": row[3],
                "summary": row[4],
            }
            for row in visible
        ], next_cursor

    def get(self, run_id: UUID, owner_id=None) -> dict | None:
        owner = _as_uuid(owner_id)
        where = "id = %s"
        params: list[Any] = [run_id]
        if owner is not None:
            where += " AND owner_id = %s"
            params.append(owner)
        with self._connection_factory() as conn:
            row = conn.execute(
                f"""
                SELECT id, owner_id, brief, params, pipeline, result, warnings, summary,
                       created_at, updated_at
                FROM match_runs
                WHERE {where}
                """,
                params,
            ).fetchone()
        return _record_from_row(row) if row else None

    def delete(self, run_id: UUID, owner_id=None) -> bool:
        owner = _as_uuid(owner_id)
        where = "id = %s"
        params: list[Any] = [run_id]
        if owner is not None:
            where += " AND owner_id = %s"
            params.append(owner)
        with self._connection_factory() as conn:
            row = conn.execute(
                f"DELETE FROM match_runs WHERE {where} RETURNING id",
                params,
            ).fetchone()
        return row is not None


def _record_from_row(row) -> dict:
    return {
        "id": row[0],
        "owner_id": row[1],
        "brief": row[2],
        "params": row[3],
        "pipeline": row[4],
        "result": row[5],
        "warnings": row[6],
        "summary": row[7],
        "created_at": row[8],
        "updated_at": row[9],
    }


def _as_uuid(value):
    if value is None or value == "":
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _encode_cursor(created_at, run_id: UUID) -> str:
    value = f"{created_at.isoformat()}|{run_id}".encode("utf-8")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[Any, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        created_at, run_id = value.split("|", 1)
        from datetime import datetime

        return datetime.fromisoformat(created_at), UUID(run_id)
    except (ValueError, UnicodeError) as exc:
        raise InvalidCursor("Invalid history cursor") from exc
