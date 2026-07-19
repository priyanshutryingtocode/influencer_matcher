"""Integration tests against a real Postgres + pgvector instance.

These need DATABASE_URL pointing at a running database (e.g. via
`docker compose up -d`) and are skipped automatically if it's not
reachable, so they won't break `pytest` for anyone who hasn't set the DB
up yet.
"""

import numpy as np
import pytest

from src import config, vector_store
from src.data_generator import generate_influencers

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    try:
        c = vector_store.get_connection()
        c.execute("SELECT 1")
    except Exception:
        pytest.skip("Postgres not reachable at DATABASE_URL; run `docker compose up -d` to enable this test")
    vector_store.init_schema(c)
    c.execute("TRUNCATE influencers")
    yield c
    c.execute("TRUNCATE influencers")
    c.close()


def _fake_embed(influencers, seed=0):
    rng = np.random.default_rng(seed)
    for inf in influencers:
        v = rng.normal(size=config.EMBED_DIMENSIONS)
        inf.embedding = v / np.linalg.norm(v)
    return influencers


def test_upsert_and_count(conn):
    influencers = _fake_embed(generate_influencers(count=10, seed=1))
    vector_store.upsert_influencers(conn, influencers)
    assert vector_store.count_influencers(conn) == 10


def test_upsert_is_idempotent(conn):
    influencers = _fake_embed(generate_influencers(count=10, seed=1))
    vector_store.upsert_influencers(conn, influencers)
    vector_store.upsert_influencers(conn, influencers)  # same ids again
    assert vector_store.count_influencers(conn) == 10


def test_search_respects_budget_filter(conn):
    influencers = _fake_embed(generate_influencers(count=20, seed=2))
    vector_store.upsert_influencers(conn, influencers)
    results = vector_store.search(conn, influencers[0].embedding, budget_max=1, platform="Any", top_k=5)
    assert results == []


def test_search_respects_platform_filter(conn):
    influencers = _fake_embed(generate_influencers(count=30, seed=3))
    vector_store.upsert_influencers(conn, influencers)
    results = vector_store.search(conn, influencers[0].embedding, budget_max=1_000_000, platform="TikTok", top_k=50)
    assert all(r.platform == "TikTok" for r in results)


def test_search_finds_nearest_vector(conn):
    influencers = _fake_embed(generate_influencers(count=25, seed=4))
    vector_store.upsert_influencers(conn, influencers)
    target = influencers[7]
    results = vector_store.search(conn, target.embedding, budget_max=1_000_000, platform="Any", top_k=1)
    assert results[0].id == target.id
