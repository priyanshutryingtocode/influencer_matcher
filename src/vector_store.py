"""Postgres + pgvector: the persistent home for influencer embeddings."""

import hashlib

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from . import config
from .models import Influencer

DEFAULT_TABLE = "influencers"


def _schema_sql(table: str) -> str:
    _validate_identifier(table)
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {table} (
    id INTEGER PRIMARY KEY,
    handle TEXT NOT NULL,
    niche TEXT NOT NULL,
    platform TEXT NOT NULL,
    city TEXT NOT NULL,
    followers INTEGER NOT NULL,
    engagement NUMERIC NOT NULL,
    rate INTEGER NOT NULL,
    tags TEXT[] NOT NULL,
    bio TEXT NOT NULL,
    embedding VECTOR({config.EMBED_DIMENSIONS}) NOT NULL
);

ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embed_model TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE INDEX IF NOT EXISTS {table}_embedding_idx
    ON {table} USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS {table}_platform_idx ON {table} (platform);
"""


def _validate_identifier(name: str) -> None:
    if not name.replace("_", "").isalnum() or not name[0].isalpha():
        raise ValueError(f"Not a safe SQL identifier: {name!r}")


def get_connection() -> psycopg.Connection:
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and paste in "
            "your Supabase connection string (click Connect on your project's "
            "dashboard, then the Session pooler tab)."
        )
    conn = psycopg.connect(config.DATABASE_URL, autocommit=True, prepare_threshold=None)
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    conn.execute(_schema_sql(table))


def drop_table(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    _validate_identifier(table)
    conn.execute(f"DROP TABLE IF EXISTS {table}")


def clear_table(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    _validate_identifier(table)
    conn.execute(f"TRUNCATE {table}")


def count_influencers(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> int:
    _validate_identifier(table)
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_influencers(
    conn: psycopg.Connection, influencers: list[Influencer], table: str = DEFAULT_TABLE
) -> None:
    _validate_identifier(table)
    rows = [
        (
            inf.id, inf.handle, inf.niche, inf.platform, inf.city,
            inf.followers, inf.engagement, inf.rate, inf.tags, inf.bio,
            inf.embedding, config.EMBED_MODEL, _content_hash(inf.corpus_text()),
        )
        for inf in influencers
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {table}
                (id, handle, niche, platform, city, followers, engagement, rate, tags, bio,
                 embedding, embed_model, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                handle = EXCLUDED.handle, niche = EXCLUDED.niche, platform = EXCLUDED.platform,
                city = EXCLUDED.city, followers = EXCLUDED.followers, engagement = EXCLUDED.engagement,
                rate = EXCLUDED.rate, tags = EXCLUDED.tags, bio = EXCLUDED.bio,
                embedding = EXCLUDED.embedding, embed_model = EXCLUDED.embed_model,
                content_hash = EXCLUDED.content_hash
            """,
            rows,
        )


def replace_influencers(
    conn: psycopg.Connection, influencers: list[Influencer], table: str = DEFAULT_TABLE
) -> None:
    """Atomically swap the table's contents for a fresh set.

    Callers must fully generate + embed `influencers` *before* calling this
    -- nothing in here should ever run a Gemini call. The clear and the
    write both happen inside one transaction (conn.transaction(), which
    works even though get_connection() sets autocommit=True), so if the
    write fails partway through, the clear is rolled back too and the
    table is left exactly as it was, not empty.
    """
    _validate_identifier(table)
    with conn.transaction():
        conn.execute(f"TRUNCATE {table}")
        upsert_influencers(conn, influencers, table=table)


def search(
    conn: psycopg.Connection,
    query_embedding: np.ndarray,
    platform: str,
    top_k: int,
    table: str = DEFAULT_TABLE,
) -> list[Influencer]:
    _validate_identifier(table)

    try:
        conn.execute(f"SET hnsw.ef_search = {max(80, top_k * 8)}")
    except Exception:
        pass
    try:
        conn.execute("SET hnsw.iterative_scan = relaxed_order")
    except Exception:
        pass

    sql = f"""
        SELECT id, handle, niche, platform, city, followers, engagement, rate, tags, bio
        FROM {table}
    """
    params: list = []
    if platform != "Any":
        sql += " WHERE platform = %s"
        params.append(platform)
    sql += " ORDER BY embedding <=> %s LIMIT %s"
    params.extend([query_embedding, top_k])

    rows = conn.execute(sql, params).fetchall()
    return [
        Influencer(
            id=r[0], handle=r[1], niche=r[2], platform=r[3], city=r[4],
            followers=r[5], engagement=float(r[6]), rate=r[7], tags=list(r[8]), bio=r[9],
        )
        for r in rows
    ]