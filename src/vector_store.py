"""Postgres + pgvector: the persistent home for influencer embeddings.

Embeddings are computed once (embeddings.py) and upserted here; retrieval
runs as a single SQL query that does the metadata filter (budget, platform)
and the vector similarity ranking together.

Table name is a parameter (default "influencers") rather than hardcoded --
this lets tests run against an isolated table instead of ever touching real
data, which matters a lot once DATABASE_URL points at Supabase instead of a
disposable local database.
"""

import hashlib

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from . import config
from .models import Influencer

DEFAULT_TABLE = "influencers"


def _schema_sql(table: str) -> str:
    # Identifiers can't be parameterized in SQL, so we validate the table
    # name is a plain identifier before interpolating it, rather than
    # accepting arbitrary strings into a DDL statement.
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

-- Added after the initial release: which embedding model produced this
-- row's vector, and a hash of the text that was embedded. Lets a future
-- reindex job detect "this row's source text changed" or "this row was
-- embedded with an old model version" instead of blindly re-embedding
-- everything. ADD COLUMN IF NOT EXISTS so this is safe to run against a
-- table created before these columns existed.
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embed_model TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE INDEX IF NOT EXISTS {table}_embedding_idx
    ON {table} USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS {table}_rate_idx ON {table} (rate);
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
    # prepare_threshold=None disables psycopg's automatic prepared statements.
    # Supabase's connection pooler (Supavisor) runs in transaction mode by
    # default, which doesn't support prepared statements across queries --
    # without this you'll intermittently see "prepared statement does not
    # exist" errors. Harmless to leave on even against a direct connection.
    conn = psycopg.connect(config.DATABASE_URL, autocommit=True, prepare_threshold=None)
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    conn.execute(_schema_sql(table))


def drop_table(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    """Used by tests to clean up an isolated test table. Deliberately a
    separate, explicitly-named function from anything used in the app's
    normal flow, so it's never reachable by accident."""
    _validate_identifier(table)
    conn.execute(f"DROP TABLE IF EXISTS {table}")


def clear_table(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    """Empties the table without dropping it (keeps indexes in place).
    Used by 'rebuild database' flows so a rebuild with a smaller profile
    count doesn't leave stale rows behind from a previous, larger run."""
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
                handle = EXCLUDED.handle,
                niche = EXCLUDED.niche,
                platform = EXCLUDED.platform,
                city = EXCLUDED.city,
                followers = EXCLUDED.followers,
                engagement = EXCLUDED.engagement,
                rate = EXCLUDED.rate,
                tags = EXCLUDED.tags,
                bio = EXCLUDED.bio,
                embedding = EXCLUDED.embedding,
                embed_model = EXCLUDED.embed_model,
                content_hash = EXCLUDED.content_hash
            """,
            rows,
        )


def search(
    conn: psycopg.Connection,
    query_embedding: np.ndarray,
    budget_max: int,
    platform: str,
    top_k: int,
    table: str = DEFAULT_TABLE,
) -> list[Influencer]:
    """Metadata filter + vector similarity, pushed down into one query.
    `<=>` is pgvector's cosine distance operator (smaller = more similar).

    Caveat worth knowing: with an HNSW (approximate-nearest-neighbor) index,
    Postgres can retrieve the nearest vectors first and apply the WHERE
    filter afterward, so a selective filter (e.g. a low budget) can return
    fewer than `top_k` rows even when more would actually qualify. We widen
    the ANN search (ef_search) proportionally to top_k to make that less
    likely, and opt into iterative scanning on pgvector versions that
    support it (0.8+), which keeps scanning until enough post-filter
    results are found. Both are best-effort session settings -- guarded so
    this still works against older pgvector without them.
    """
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
        WHERE rate <= %s
    """
    params: list = [budget_max]
    if platform != "Any":
        sql += " AND platform = %s"
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