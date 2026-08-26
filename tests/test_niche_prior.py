"""Tests for the deterministic niche prior (src.retrieval)."""

from src.models import Influencer
from src.retrieval import niche_prior_sort


def make(id_, niche, secondary=None, similarity=0.9):
    return Influencer(
        id=id_, handle=f"@c{id_}", niche=niche, platform="Instagram",
        city="Austin", followers=10_000, engagement=5.0,
        secondary_niches=secondary or [], similarity=similarity,
    )


def test_on_niche_leads_off_niche():
    pool = [
        make(1, "Gaming", similarity=0.95),     # off-niche but most similar
        make(2, "Fitness", similarity=0.80),
        make(3, "Yoga", ["Fitness"], similarity=0.85),  # secondary match
    ]
    ordered = niche_prior_sort(pool, "Fitness")
    # on-niche group keeps similarity order: id3 (0.85) then id2 (0.80)
    assert [c.id for c in ordered] == [3, 2, 1]


def test_similarity_order_preserved_within_groups():
    pool = [
        make(1, "Fitness", similarity=0.70),
        make(2, "Fitness", similarity=0.90),
        make(3, "Gaming", similarity=0.99),
        make(4, "Gaming", similarity=0.60),
    ]
    ordered = niche_prior_sort(pool, "Fitness")
    assert [c.id for c in ordered] == [2, 1, 3, 4]


def test_none_similarity_treated_as_zero():
    pool = [
        make(1, "Fitness", similarity=None),
        make(2, "Fitness", similarity=0.5),
    ]
    ordered = niche_prior_sort(pool, "Fitness")
    assert [c.id for c in ordered] == [2, 1]


def test_input_not_mutated():
    pool = [make(1, "Gaming"), make(2, "Fitness")]
    ordered = niche_prior_sort(pool, "Fitness")
    assert ordered is not pool
    assert [c.id for c in pool] == [1, 2]
