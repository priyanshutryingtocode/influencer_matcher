"""Tests for src.data_generator: determinism, invariants, seed propagation."""

import pytest

from src.data_generator import (
    NICHES,
    PLATFORMS,
    generate_balanced_influencers,
    generate_influencers,
)


def test_generate_influencers_count_and_ids():
    creators = generate_influencers(count=25, seed=7)
    assert len(creators) == 25
    assert sorted(c.id for c in creators) == list(range(25))


def test_generate_influencers_deterministic():
    a = [c.handle for c in generate_influencers(count=30, seed=11)]
    b = [c.handle for c in generate_influencers(count=30, seed=11)]
    assert a == b


def test_handles_unique():
    handles = [c.handle for c in generate_influencers(count=100)]
    assert len(handles) == len(set(handles))


def test_niche_and_platform_from_known_sets():
    for c in generate_influencers(count=50):
        assert c.niche in NICHES
        assert c.platform in PLATFORMS
        assert all(n in NICHES for n in c.secondary_niches)


def test_balanced_covers_every_combo_floor():
    floor = 2
    # Exact minimum: 30 niches x 9 platforms x floor
    creators = generate_balanced_influencers(
        count=540, seed=42, min_per_niche_platform=floor
    )
    counts: dict[tuple[str, str], int] = {}
    for c in creators:
        counts[(c.niche, c.platform)] = counts.get((c.niche, c.platform), 0) + 1
    combos = {(n, p) for n in NICHES for p in PLATFORMS}
    assert set(counts) >= combos
    assert min(counts[combo] for combo in combos) >= floor


def test_balanced_too_small_raises():
    # min viable = len(NICHES)=30 * len(PLATFORMS)=9 * floor=3 = 810
    with pytest.raises(ValueError, match="too small"):
        generate_balanced_influencers(count=10)


def test_balanced_respects_requested_fields():
    creators = generate_balanced_influencers(count=810, seed=42)
    assert len(creators) == 810
    assert sorted(c.id for c in creators) == list(range(810))


def test_balanced_seed_changes_output():
    """Regression: the Faker seeding inside balanced generation used to
    hardcode 42, so passing a different seed changed nothing."""
    a = [(c.name, c.handle) for c in generate_balanced_influencers(count=810, seed=42)]
    b = [(c.name, c.handle) for c in generate_balanced_influencers(count=810, seed=43)]
    assert a != b


def test_balanced_default_seed_stable():
    a = [c.handle for c in generate_balanced_influencers(count=810, seed=42)]
    b = [c.handle for c in generate_balanced_influencers(count=810, seed=42)]
    assert a == b
