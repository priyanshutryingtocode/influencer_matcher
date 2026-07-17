"""Offline tests -- cover everything that doesn't require hitting the
Gemini API, so they run in CI without an API key."""

import numpy as np

from src.data_generator import generate_influencers
from src.embeddings import cosine_sim
from src.models import Brief
from src.retrieval import hybrid_retrieve


def test_generate_influencers_is_deterministic():
    a = generate_influencers(count=20, seed=1)
    b = generate_influencers(count=20, seed=1)
    assert [inf.handle for inf in a] == [inf.handle for inf in b]


def test_generate_influencers_respects_count():
    influencers = generate_influencers(count=15, seed=7)
    assert len(influencers) == 15


def test_cosine_sim_identical_vectors_is_one():
    v = np.array([0.1, 0.4, 0.9])
    assert abs(cosine_sim(v, v) - 1.0) < 1e-9


def test_cosine_sim_orthogonal_vectors_is_zero():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(cosine_sim(a, b)) < 1e-9


def test_hybrid_retrieve_returns_empty_when_budget_too_low(monkeypatch):
    influencers = generate_influencers(count=30, seed=3)
    brief = Brief(niche="Travel", platform="Any", budget_max=1)  # nothing costs $1
    # client is unused in this branch since the budget filter empties the
    # pool before any embedding call would happen
    result = hybrid_retrieve(client=None, brief=brief, influencers=influencers, top_k=5)
    assert result == []


def test_hybrid_retrieve_applies_platform_filter():
    influencers = generate_influencers(count=40, seed=9)
    brief = Brief(niche="Gaming", platform="YouTube", budget_max=1_000_000)

    class _StubClient:
        class models:
            @staticmethod
            def embed_content(model, contents, config):
                class _Emb:
                    values = [1.0, 0.0, 0.0]
                class _Result:
                    embeddings = [_Emb() for _ in contents]
                return _Result()

    for inf in influencers:
        inf.embedding = np.array([1.0, 0.0, 0.0])

    result = hybrid_retrieve(client=_StubClient(), brief=brief, influencers=influencers, top_k=50)
    assert all(inf.platform == "YouTube" for inf in result)
