"""Postgres + pgvector: the persistent home for influencer embeddings."""

import hashlib
import logging
import threading

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from . import config
from .models import Influencer

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "influencers"

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()

_schema_ready_tables: set[str] = set()


def _configure_connection(conn: psycopg.Connection) -> None:
    """Runs once per new pooled connection: register pgvector adapters and
    pin the HNSW scan mode. Doing these here (instead of in search()) means
    each query saves two extra roundtrips."""
    register_vector(conn)
    try:
        conn.execute("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', false)")
    except psycopg.Error:
        logger.debug("hnsw.iterative_scan unavailable", exc_info=True)


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if not config.DATABASE_URL:
                    raise RuntimeError(
                        "DATABASE_URL is not set. Copy to .env and paste in "
                        "your Supabase connection string (click Connect on your "
                        "project's dashboard, then the Session pooler tab)."
                    )
                _pool = ConnectionPool(
                    conninfo=config.DATABASE_URL,
                    min_size=1,
                    max_size=4,
                    kwargs={"autocommit": True, "prepare_threshold": None},
                    configure=_configure_connection,
                    open=True,
                )
    return _pool


def _schema_sql(table: str) -> str:
    _validate_identifier(table)
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {table} (
    id INTEGER PRIMARY KEY,
    handle TEXT NOT NULL,
    platform TEXT NOT NULL,
    city TEXT NOT NULL,
    followers INTEGER NOT NULL,
    engagement NUMERIC NOT NULL,
    tags TEXT[] NOT NULL,
    bio TEXT NOT NULL,
    embedding VECTOR({config.EMBED_DIMENSIONS}) NOT NULL,
    name TEXT,
    country TEXT,
    language TEXT,
    average_views INTEGER,
    average_likes INTEGER,
    average_comments INTEGER,
    verified BOOLEAN,
    posts_per_week INTEGER,
    account_age_years INTEGER
);

ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embed_model TEXT;
ALTER TABLE {table} ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE {table} DROP COLUMN IF EXISTS rate;
-- The single-label taxonomy is gone; topic tags are the only topical signal.
-- DROP (not SET NULL) because nothing reads these columns any more.
ALTER TABLE {table} DROP COLUMN IF EXISTS niche;
ALTER TABLE {table} DROP COLUMN IF EXISTS secondary_niches;
-- Inferred characteristics live in creator_signals (migration 007), not here.
ALTER TABLE {table} DROP COLUMN IF EXISTS content_style;
ALTER TABLE {table} DROP COLUMN IF EXISTS audience_age;
ALTER TABLE {table} DROP COLUMN IF EXISTS audience_gender;
ALTER TABLE {table} DROP COLUMN IF EXISTS audience_country;
ALTER TABLE {table} DROP COLUMN IF EXISTS brand_collaborations;

CREATE INDEX IF NOT EXISTS {table}_embedding_idx
    ON {table} USING hnsw (embedding vector_cosine_ops);
-- Measured on the live 2,000-row index (2026-10-02), which is what the earlier TODO
-- asked for. Keeping it.
--
--   recall@10  1.000   recall@50  1.000   (20 sampled queries vs exact search)
--   planner    chooses this index; a real top-10 query runs 1.05ms
--   cost       index 16MB against a 936kB table -- 17x, which is the price
--
-- The ef_search tuning further down is what makes the recall numbers hold:
-- at the pgvector default of 40, recall@50 falls to 0.800. At top_k=50 the
-- unfiltered path raises it to 400 and recall returns to 1.000. Dropping the
-- index would mean a seq-scan over 2000 x 768 floats per query and would
-- re-introduce the crowding problem as the corpus grows.

CREATE INDEX IF NOT EXISTS {table}_platform_idx ON {table} (platform);

ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
"""


def _validate_identifier(name: str) -> None:
    if not name.replace("_", "").isalnum() or not name[0].isalpha():
        raise ValueError(f"Not a safe SQL identifier: {name!r}")


def get_connection(timeout: float = 10):
    """Check a connection out of the pool as a context manager:

        with vector_store.get_connection() as conn:
            ...

    On exit the connection returns to the pool instead of being torn down,
    so repeat queries skip connection setup entirely. `timeout` bounds how
    long a caller waits for a healthy connection before PoolTimeout -- short
    enough that an unreachable database surfaces an error banner quickly,
    long enough to absorb transient Supabase pooler handoffs."""
    return _get_pool().connection(timeout=timeout)


def init_schema(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    """Create tables/indexes if missing. Idempotent DDL; skipped after the
    first successful run per table per process (cheap, but why pay it)."""
    if table in _schema_ready_tables:
        return
    conn.execute(_schema_sql(table))
    _schema_ready_tables.add(table)


def count_influencers(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> int:
    _validate_identifier(table)
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


class IndexModelMismatch(RuntimeError):
    """The stored creator index was built by a different embedding model.

    Raised instead of letting a search fail deep inside pgvector with an opaque
    "expected N dimensions, not M" error, so the API can report the actionable
    cause: the index needs a reindex.
    """


def _embedding_dimension(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> int | None:
    row = conn.execute(
        """
        SELECT format_type(att.atttypid, att.atttypmod)
        FROM pg_attribute AS att
        WHERE att.attrelid = to_regclass(%s)
          AND att.attname = 'embedding'
          AND NOT att.attisdropped
        """,
        (table,),
    ).fetchone()
    if not row or not row[0]:
        return None
    digits = "".join(char for char in str(row[0]) if char.isdigit())
    return int(digits) if digits else None


def assert_index_matches_config(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    """Fail fast when the index cannot answer queries for the configured model.

    A vector column of the wrong width, or rows labelled with another embedder,
    means every search would either error or silently compare incompatible
    vector spaces.
    """
    width = _embedding_dimension(conn, table)
    if width is not None and width != config.EMBED_DIMENSIONS:
        raise IndexModelMismatch(
            f"creator index is vector({width}) but EMBED_DIMENSIONS="
            f"{config.EMBED_DIMENSIONS}; reindex with `python main.py --reindex` "
            f"after changing the embedding model."
        )
    _validate_identifier(table)
    rows = conn.execute(
        f"SELECT DISTINCT embed_model FROM {table} WHERE embed_model IS NOT NULL LIMIT 5"
    ).fetchall()
    stale = {row[0] for row in rows} - {config.EMBED_MODEL}
    if stale:
        raise IndexModelMismatch(
            f"creator index was built with {sorted(stale)} but the service is "
            f"configured for {config.EMBED_MODEL!r}; reindex with "
            f"`python main.py --reindex`."
        )


def _refresh_stats(conn: psycopg.Connection, table: str = DEFAULT_TABLE) -> None:
    """Refresh planner statistics after a bulk replace. Without this the
    optimizer keeps stale estimates (often from an empty table) and falls
    back to seq-scans / cold HNSW walks, which shows up as multi-second
    latency on the first unfiltered (platform=Any) query."""
    try:
        conn.execute(f"ANALYZE {table}")
    except psycopg.Error:
        # Its absence only costs latency on the first unfiltered query.
        logger.debug("ANALYZE %s failed", table, exc_info=True)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_influencers(
    conn: psycopg.Connection, influencers: list[Influencer], table: str = DEFAULT_TABLE
) -> None:
    _validate_identifier(table)
    rows = [
        (
            inf.id, inf.handle, inf.platform, inf.city,
            inf.followers, inf.engagement, inf.tags, inf.bio,
            inf.embedding, config.EMBED_MODEL, _content_hash(inf.corpus_text()),
            inf.name, inf.country, inf.language,
            inf.average_views, inf.average_likes, inf.average_comments,
            inf.verified, inf.posts_per_week, inf.account_age_years,
        )
        for inf in influencers
    ]
    signal_rows = [
        (
            s.creator_id, s.content_style, s.audience_age, s.audience_gender,
            s.audience_country, s.brand_collaborations, s.reach_ratio,
            s.sponsored_ratio, s.growth_trend, s.audience_top_countries,
        )
        for s in (inf.signals() for inf in influencers)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"""
            INSERT INTO {table}
                (id, handle, platform, city, followers, engagement, tags, bio,
                 embedding, embed_model, content_hash, name, country, language,
                 average_views, average_likes, average_comments, verified, posts_per_week,
                 account_age_years)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                handle = EXCLUDED.handle, platform = EXCLUDED.platform,
                city = EXCLUDED.city, followers = EXCLUDED.followers, engagement = EXCLUDED.engagement,
                tags = EXCLUDED.tags, bio = EXCLUDED.bio,
                embedding = EXCLUDED.embedding, embed_model = EXCLUDED.embed_model,
                content_hash = EXCLUDED.content_hash, name = EXCLUDED.name,
                country = EXCLUDED.country,
                language = EXCLUDED.language, average_views = EXCLUDED.average_views,
                average_likes = EXCLUDED.average_likes, average_comments = EXCLUDED.average_comments,
                verified = EXCLUDED.verified, posts_per_week = EXCLUDED.posts_per_week,
                account_age_years = EXCLUDED.account_age_years
            """,
            rows,
        )
        cur.executemany(
            """
            INSERT INTO creator_signals
                (creator_id, content_style, audience_age, audience_gender,
                 audience_country, brand_collaborations, reach_ratio,
                 sponsored_ratio, growth_trend, audience_top_countries)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (creator_id) DO UPDATE SET
                content_style = EXCLUDED.content_style,
                audience_age = EXCLUDED.audience_age,
                audience_gender = EXCLUDED.audience_gender,
                audience_country = EXCLUDED.audience_country,
                brand_collaborations = EXCLUDED.brand_collaborations,
                reach_ratio = EXCLUDED.reach_ratio,
                sponsored_ratio = EXCLUDED.sponsored_ratio,
                growth_trend = EXCLUDED.growth_trend,
                audience_top_countries = EXCLUDED.audience_top_countries
            """,
            signal_rows,
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
        # CASCADE so the signals rows go with their creators; without it the
        # foreign key would block the truncate.
        conn.execute(f"TRUNCATE {table} CASCADE")
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
        conn.execute(
            "SELECT set_config('hnsw.ef_search', %s, false)", (str(ef_search),)
        )
    except psycopg.Error:
        logger.debug("hnsw.ef_search tuning failed", exc_info=True)

    # One LEFT JOIN, not a second query: retrieval returns top_k rows and a
    # per-row signal fetch would be top_k round trips. The join is on the
    # primary key, so it does not change the row set, and every signal is
    # COALESCEd so a creator with no signal row still reads back cleanly
    # rather than raising on a NULL.
    sql = f"""
        SELECT i.id, i.handle, i.platform, i.city, i.followers, i.engagement, i.tags, i.bio,
               1 - (i.embedding <=> %s) AS similarity,
               COALESCE(i.name, ''),
               COALESCE(i.country, ''), COALESCE(i.language, ''), COALESCE(i.average_views, 0),
               COALESCE(i.average_likes, 0), COALESCE(i.average_comments, 0), COALESCE(i.verified, FALSE),
               COALESCE(i.posts_per_week, 0), COALESCE(i.account_age_years, 0),
               COALESCE(s.content_style, ''), COALESCE(s.audience_age, ''),
               COALESCE(s.audience_gender, ''), COALESCE(s.audience_country, ''),
               COALESCE(s.brand_collaborations, ARRAY[]::TEXT[]),
               COALESCE(s.reach_ratio, 0), COALESCE(s.sponsored_ratio, 0),
               COALESCE(s.growth_trend, ''),
               COALESCE(s.audience_top_countries, ARRAY[]::TEXT[])
        FROM {table} AS i
        LEFT JOIN creator_signals AS s ON s.creator_id = i.id
    """
    params: list = [query_embedding]
    if platform != "Any":
        sql += " WHERE i.platform = %s"
        params.append(platform)
    sql += " ORDER BY (i.embedding <=> %s) LIMIT %s"
    params.append(query_embedding)
    params.append(top_k)

    rows = conn.execute(sql, params).fetchall()
    return [
        Influencer(
            id=r[0], handle=r[1], platform=r[2], city=r[3],
            followers=r[4], engagement=float(r[5]), tags=list(r[6]), bio=r[7],
            similarity=float(r[8]),
            name=r[9], country=r[10], language=r[11],
            average_views=r[12], average_likes=r[13], average_comments=r[14],
            verified=r[15], posts_per_week=r[16], account_age_years=r[17],
            content_style=r[18], audience_age=r[19], audience_gender=r[20],
            audience_country=r[21], brand_collaborations=list(r[22]),
            reach_ratio=float(r[23]), sponsored_ratio=float(r[24]),
            growth_trend=r[25], audience_top_countries=list(r[26]),
        )
        for r in rows
    ]
