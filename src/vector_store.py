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
    tags TEXT[] NOT NULL,
    bio TEXT NOT NULL,
    embedding VECTOR({config.EMBED_DIMENSIONS}) NOT NULL,
    name TEXT,
    secondary_niches TEXT[],
    country TEXT,
    language TEXT,
    average_views INTEGER,
    average_likes INTEGER,
    average_comments INTEGER,
    verified BOOLEAN,
    posts_per_week INTEGER,
    account_age_years INTEGER,
    content_style TEXT,
    audience_age TEXT,
    audience_gender TEXT,
    audience_country TEXT,
    brand_collaborations TEXT[]
);

ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embed_model TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE {table} DROP COLUMN IF EXISTS rate;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS secondary_niches TEXT[];
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS country TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS language TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS average_views INTEGER;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS average_likes INTEGER;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS average_comments INTEGER;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS verified BOOLEAN;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS posts_per_week INTEGER;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS account_age_years INTEGER;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS content_style TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS audience_age TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS audience_gender TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS audience_country TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS brand_collaborations TEXT[];

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
            "DATABASE_URL is not set. Copy to .env and paste in "
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


def _refresh_stats(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    """Refresh planner statistics after a bulk replace. Without this the
    optimizer keeps stale estimates (often from an empty table) and falls
    back to seq-scans / cold HNSW walks, which shows up as multi-second
    latency on the first unfiltered (platform=Any) query."""
    try:
        conn.execute(f"ANALYZE {table}")
    except Exception:
        pass


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_influencers(
    conn: psycopg.Connection, influencers: list[Influencer], table: str = DEFAULT_TABLE
) -> None:
    _validate_identifier(table)
    rows = [
        (
            inf.id, inf.handle, inf.niche, inf.platform, inf.city,
            inf.followers, inf.engagement, inf.tags, inf.bio,
            inf.embedding, config.EMBED_MODEL, _content_hash(inf.corpus_text()),
            inf.name, inf.secondary_niches, inf.country, inf.language,
            inf.average_views, inf.average_likes, inf.average_comments,
            inf.verified, inf.posts_per_week, inf.account_age_years,
            inf.content_style, inf.audience_age, inf.audience_gender,
            inf.audience_country, inf.brand_collaborations,
        )
        for inf in influencers
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {table}
                (id, handle, niche, platform, city, followers, engagement, tags, bio,
                 embedding, embed_model, content_hash, name, secondary_niches, country, language,
                 average_views, average_likes, average_comments, verified, posts_per_week,
                 account_age_years, content_style, audience_age, audience_gender, audience_country,
                 brand_collaborations)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                handle = EXCLUDED.handle, niche = EXCLUDED.niche, platform = EXCLUDED.platform,
                city = EXCLUDED.city, followers = EXCLUDED.followers, engagement = EXCLUDED.engagement,
                tags = EXCLUDED.tags, bio = EXCLUDED.bio,
                embedding = EXCLUDED.embedding, embed_model = EXCLUDED.embed_model,
                content_hash = EXCLUDED.content_hash, name = EXCLUDED.name,
                secondary_niches = EXCLUDED.secondary_niches, country = EXCLUDED.country,
                language = EXCLUDED.language, average_views = EXCLUDED.average_views,
                average_likes = EXCLUDED.average_likes, average_comments = EXCLUDED.average_comments,
                verified = EXCLUDED.verified, posts_per_week = EXCLUDED.posts_per_week,
                account_age_years = EXCLUDED.account_age_years, content_style = EXCLUDED.content_style,
                audience_age = EXCLUDED.audience_age, audience_gender = EXCLUDED.audience_gender,
                audience_country = EXCLUDED.audience_country,
                brand_collaborations = EXCLUDED.brand_collaborations
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
    _refresh_stats(conn, table)


def search(
    conn: psycopg.Connection,
    query_embedding: np.ndarray,
    platform: str,
    top_k: int,
    table: str = DEFAULT_TABLE,
) -> list[Influencer]:
    _validate_identifier(table)

    try:
        # Unfiltered (platform=Any) searches walk the whole HNSW graph, so
        # they get a larger ef_search to avoid under-fetching neighbors;
        # filtered searches need far fewer graph hops since they match a
        # smaller platform subset.
        ef_search = max(80, top_k * 8) if platform == "Any" else max(40, top_k * 4)
        conn.execute(f"SET hnsw.ef_search = {ef_search}")
    except Exception:
        pass
    try:
        conn.execute("SET hnsw.iterative_scan = relaxed_order")
    except Exception:
        pass

    sql = f"""
        SELECT id, handle, niche, platform, city, followers, engagement, tags, bio,
               1 - (embedding <=> %s) AS similarity,
               COALESCE(name, ''), COALESCE(secondary_niches, ARRAY[]::TEXT[]),
               COALESCE(country, ''), COALESCE(language, ''), COALESCE(average_views, 0),
               COALESCE(average_likes, 0), COALESCE(average_comments, 0), COALESCE(verified, FALSE),
               COALESCE(posts_per_week, 0), COALESCE(account_age_years, 0),
               COALESCE(content_style, ''), COALESCE(audience_age, ''),
               COALESCE(audience_gender, ''), COALESCE(audience_country, ''),
               COALESCE(brand_collaborations, ARRAY[]::TEXT[])
        FROM {table}
    """
    params: list = [query_embedding]
    if platform != "Any":
        sql += " WHERE platform = %s"
        params.append(platform)
    sql += " ORDER BY embedding <=> %s LIMIT %s"
    params.extend([query_embedding, top_k])

    rows = conn.execute(sql, params).fetchall()
    return [
        Influencer(
            id=r[0], handle=r[1], niche=r[2], platform=r[3], city=r[4],
            followers=r[5], engagement=float(r[6]), tags=list(r[7]), bio=r[8],
            similarity=float(r[9]),
            name=r[10], secondary_niches=list(r[11]), country=r[12], language=r[13],
            average_views=r[14], average_likes=r[15], average_comments=r[16],
            verified=r[17], posts_per_week=r[18], account_age_years=r[19],
            content_style=r[20], audience_age=r[21], audience_gender=r[22],
            audience_country=r[23], brand_collaborations=list(r[24]),
        )
        for r in rows
    ]
