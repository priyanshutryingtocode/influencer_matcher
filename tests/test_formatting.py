"""Tests for src.formatting display helpers."""

from src.formatting import format_followers, match_evidence, niche_coverage
from src.models import Brief, Influencer


def make_influencer(id_=1, niche="Fitness", tags=None, bio=""):
    return Influencer(
        id=id_, handle=f"@c{id_}", niche=niche, platform="Instagram",
        city="Austin", followers=1000, engagement=5.0,
        tags=tags or [], bio=bio,
    )


def test_format_followers_boundaries():
    assert format_followers(999) == "999"
    assert format_followers(1_000) == "1K"
    assert format_followers(48_000) == "48K"
    assert format_followers(1_000_000) == "1.0M"
    assert format_followers(5_400_000) == "5.4M"


def test_niche_coverage_counts():
    candidates = [make_influencer(1), make_influencer(2, niche="Gaming"), make_influencer(3)]
    matches, total = niche_coverage(candidates, "Fitness")
    assert (matches, total) == (2, 3)


def test_match_evidence_exact_niche():
    evidence = " | ".join(match_evidence(Brief(niche="Fitness", platform="Any"), make_influencer(1)))
    assert "Exact niche match" in evidence


def test_match_evidence_shared_terms_from_tags_and_bio():
    brief = Brief(niche="Fitness", platform="Any", audience="", vibe="calm yoga stretching")
    inf = make_influencer(1, niche="Yoga", tags=["stretching"], bio="")
    evidence = " | ".join(match_evidence(brief, inf))
    assert "Shared brief/profile terms" in evidence or "Relevant profile tags" in evidence


def test_match_evidence_fallback_message():
    brief = Brief(niche="Fitness", platform="Any", audience="zzz qqq", vibe="xxx yyy")
    inf = make_influencer(1, niche="Gaming", tags=["fps"], bio="Shooter games.")
    evidence = " | ".join(match_evidence(brief, inf))
    assert "semantic similarity" in evidence
