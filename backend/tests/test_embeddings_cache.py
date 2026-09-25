"""Tests for the query-vector LRU cache and prefix handling (src.embeddings).

The SentenceTransformer itself is never loaded: embed_texts_local is
monkeypatched to return fixed vectors and record its inputs.
"""

import pytest

import numpy as np

from src import config, embeddings


@pytest.fixture(autouse=True)
def clean_cache():
    embeddings._query_cache.clear()
    yield
    embeddings._query_cache.clear()


@pytest.fixture
def fake_encode(monkeypatch):
    calls: list[list[str]] = []
    counter = {"n": 0}

    def fake(texts):
        calls.append(list(texts))
        rows = []
        for _ in texts:
            counter["n"] += 1
            rows.append(np.array([float(counter["n"])]))
        return rows

    monkeypatch.setattr(embeddings, "embed_texts_local", fake)
    return calls


def test_cache_hit_skips_reencode(fake_encode):
    a1 = embeddings.get_cached_query_vector("same brief")
    a2 = embeddings.get_cached_query_vector("same brief")
    assert len(fake_encode) == 1          # encoded once
    assert (a1 == a2).all()


def test_different_text_encodes_separately(fake_encode):
    embeddings.get_cached_query_vector("brief A")
    embeddings.get_cached_query_vector("brief B")
    assert len(fake_encode) == 2


def test_lru_eviction(monkeypatch, fake_encode):
    monkeypatch.setattr(embeddings, "_QUERY_CACHE_SIZE", 2)
    for text in ("one", "two", "three"):
        embeddings.get_cached_query_vector(text)
    # size 2 -> inserting "three" evicted "one"
    assert len(embeddings._query_cache) == 2

    before = len(fake_encode)  # == 3 encodes so far

    embeddings.get_cached_query_vector("three")
    assert len(fake_encode) == before          # still cached

    embeddings.get_cached_query_vector("one")  # miss -> +1; evicts "two"
    assert len(fake_encode) == before + 1

    embeddings.get_cached_query_vector("three")
    assert len(fake_encode) == before + 1      # survived the eviction

    embeddings.get_cached_query_vector("two")  # was evicted above -> +1
    assert len(fake_encode) == before + 2


def test_query_prefix_applied_to_queries_only(fake_encode, monkeypatch):
    monkeypatch.setattr(config, "EMBED_QUERY_PREFIX", "query: ")
    embeddings.get_cached_query_vector("find me")
    assert fake_encode[-1] == ["query: find me"]

    # Passage path goes through embed_texts -> EMBED_PASSAGE_PREFIX.
    monkeypatch.setattr(config, "EMBED_PASSAGE_PREFIX", "passage: ")
    embeddings.embed_texts(["doc body"])
    assert fake_encode[-1] == ["passage: doc body"]
