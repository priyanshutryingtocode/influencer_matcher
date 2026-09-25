import numpy as np

from src import match_service
from src.models import Brief


class ConnectionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_retrieve_candidates_passes_precomputed_query_vector(monkeypatch):
    vector = np.array([0.1, 0.2])
    seen = {}

    def fake_retrieve(conn, brief, top_k, query_vec=None):
        seen["query_vec"] = query_vec
        return []

    monkeypatch.setattr(match_service.vector_store, "get_connection", ConnectionContext)
    monkeypatch.setattr(match_service, "hybrid_retrieve", fake_retrieve)
    result = match_service.retrieve_candidates(Brief(niche="Fitness", platform="Any"), 3, query_vec=vector)
    assert result == []
    assert seen["query_vec"] is vector


def test_run_match_returns_none_without_candidates(monkeypatch):
    monkeypatch.setattr(match_service, "retrieve_candidates", lambda brief, top_k: [])
    result = match_service.run_match(Brief(niche="Fitness", platform="Any"), 3, 1, client=object())
    assert result is None
