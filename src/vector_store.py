"""Postgres + pgvector: the persistent home for influencer embeddings.

This replaces the old in-memory `.embedding` field approach. Embeddings are
computed once (embeddings.py) and upserted here; retrieval then runs as a
single SQL query that does the metadata filter (budget, platform) and the
vector similarity ranking together, instead of pulling everything into
Python and filtering/sorting by hand.

Requires the pgvector extension: CREATE EXTENSION vector; (init_schema
does this for you, given a role with sufficient privilege).
"""

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from . import config
from .models import Influencer

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS influencers (
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

-- HNSW index for fast approximate nearest-neighbor search on cosine distance.
-- Fine to build even on a near-empty table; pgvector will maintain it as
-- rows are added.
CREATE INDEX IF NOT EXISTS influencers_embedding_idx
    ON influencers USING hnsw (embedding vector_cosine_ops);

-- Metadata filters (budget, platform) run *before* the vector search in
-- every query below, so a plain b-tree index on the filter columns keeps
-- that part fast too.
CREATE INDEX IF NOT EXISTS influencers_rate_idx ON influencers (rate);
CREATE INDEX IF NOT EXISTS influencers_platform_idx ON influencers (platform);
"""


def get_connection() -> psycopg.Connection:
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and paste in "
            "your Supabase connection string (Project Settings -> Database -> "
            "Connection string -> Session pooler)."
        )
    # prepare_threshold=None disables psycopg's automatic prepared statements.
    # Supabase's connection pooler (Supavisor) runs in transaction mode by
    # default, which doesn't support prepared statements across queries --
    # without this you'll intermittently see "prepared statement does not
    # exist" errors. Harmless to leave on even against a direct connection.
    conn = psycopg.connect(config.DATABASE_URL, autocommit=True, prepare_threshold=None)
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)


def count_influencers(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM influencers").fetchone()[0]


def upsert_influencers(conn: psycopg.Connection, influencers: list[Influencer]) -> None:
    rows = [
        (
            inf.id, inf.handle, inf.niche, inf.platform, inf.city,
            inf.followers, inf.engagement, inf.rate, inf.tags, inf.bio,
            inf.embedding,
        )
        for inf in influencers
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO influencers
                (id, handle, niche, platform, city, followers, engagement, rate, tags, bio, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                embedding = EXCLUDED.embedding
            """,
            rows,
        )


def search(
    conn: psycopg.Connection,
    query_embedding: np.ndarray,
    budget_max: int,
    platform: str,
    top_k: int,
) -> list[Influencer]:
    """Metadata filter + vector similarity, pushed down into one query.
    `<=>` is pgvector's cosine distance operator (smaller = more similar)."""
    sql = """
        SELECT id, handle, niche, platform, city, followers, engagement, rate, tags, bio
        FROM influencers
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
