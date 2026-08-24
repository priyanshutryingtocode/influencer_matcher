"""Tests for src.models dataclasses."""

from src.models import Brief, Influencer


def test_query_text_includes_niche_and_keywords():
    brief = Brief(niche="Fitness", platform="TikTok", audience="millennials", vibe="high energy")
    text = brief.query_text()
    assert "Fitness" in text
    assert "gym" in text  # topic keyword from NICHES["Fitness"]
    assert "millennials" in text
    assert "high energy" in text


def test_query_text_defaults_when_fields_empty():
    brief = Brief(niche="Books", platform="Any")
    text = brief.query_text()
    assert "general audiences" in text
    assert "versatile" in text


def test_query_text_unknown_niche_has_no_keywords_section():
    brief = Brief(niche="Nonexistent", platform="Any")
    text = brief.query_text()
    assert "Topics include:" not in text


def test_corpus_text_contains_profile_facts():
    inf = Influencer(
        id=1, handle="@fitpro", niche="Fitness", platform="TikTok",
        city="Austin", followers=1000, engagement=5.0,
        tags=["gym", "HIIT"], bio="Lifting daily.",
    )
    text = inf.corpus_text()
    for fragment in ("@fitpro", "TikTok", "Austin", "gym", "HIIT", "Lifting daily."):
        assert fragment in text
