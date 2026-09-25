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
        migration = Path(__file__).resolve().parents[2] / "migrations" / "001_create_match_runs.sql"
        with self._connection_factory() as conn:
            conn.execute(migration.read_text(encoding="utf-8"))

    def create(self, record: dict) -> dict:
        with self._connection_factory() as conn:
            row = conn.execute(
                """
                INSERT INTO match_runs
                    (id, brief, params, pipeline, result, warnings, summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, brief, params, pipeline, result, warnings, summary,
                          created_at, updated_at
                """,
                (
                    record["id"],
                    Jsonb(record["brief"]),
                    Jsonb(record["params"]),
                    Jsonb(record["pipeline"]),
                    Jsonb(record["result"]),
                    Jsonb(record["warnings"]),
                    Jsonb(record["summary"]),
                ),
            ).fetchone()
        return _record_from_row(row)

    def list(self, limit: int, cursor: str | None = None) -> tuple[list[dict], str | None]:
        where = ""
        params: list[Any] = []
        if cursor:
            created_at, run_id = _decode_cursor(cursor)
            where = "WHERE (created_at < %s OR (created_at = %s AND id < %s))"
            params.extend([created_at, created_at, run_id])
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

    def get(self, run_id: UUID) -> dict | None:
        with self._connection_factory() as conn:
            row = conn.execute(
                """
                SELECT id, brief, params, pipeline, result, warnings, summary,
                       created_at, updated_at
                FROM match_runs
                WHERE id = %s
                """,
                (run_id,),
            ).fetchone()
        return _record_from_row(row) if row else None

    def delete(self, run_id: UUID) -> bool:
        with self._connection_factory() as conn:
            row = conn.execute(
                "DELETE FROM match_runs WHERE id = %s RETURNING id",
                (run_id,),
            ).fetchone()
        return row is not None


def _record_from_row(row) -> dict:
    return {
        "id": row[0],
        "brief": row[1],
        "params": row[2],
        "pipeline": row[3],
        "result": row[4],
        "warnings": row[5],
        "summary": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


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
