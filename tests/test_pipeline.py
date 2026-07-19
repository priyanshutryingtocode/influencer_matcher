"""Offline tests -- cover everything that doesn't require API keys or a
live database, so they run in CI with no external services."""

import numpy as np

from src.data_generator import generate_influencers
from src.embeddings import cosine_sim


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
