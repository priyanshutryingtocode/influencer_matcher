"""Tests for src.models dataclasses."""

from api.schemas.models import BriefPayload
from src.models import Brief, Influencer


def test_query_text_uses_free_text_goal_verbatim():
    """Free text is the query: nothing is rewritten or appended from a list."""
    brief = Brief(
        goal="a thrifted-vintage label for slow fashion", platform="TikTok",
        audience="millennials", vibe="high energy",
    )
    text = brief.query_text()
    assert text.startswith("a thrifted-vintage label for slow fashion")
    assert "millennials" in text
    assert "high energy" in text
    assert "Topics include:" not in text


def test_query_text_uses_goal_alone_when_refinements_empty():
    brief = Brief(goal="deep-dive coding tutorials", platform="Any")
    assert brief.query_text() == "deep-dive coding tutorials"


def test_legacy_niche_payload_is_accepted_as_goal():
    """Old clients still posting 'niche' keep working; it becomes the goal."""
    payload = BriefPayload.model_validate({"niche": "sourdough baking for beginners", "platform": "Any"})
    assert payload.goal == "sourdough baking for beginners"
    assert Brief(goal=payload.goal, platform=payload.platform).query_text() == "sourdough baking for beginners"


def test_corpus_text_contains_profile_facts():
    inf = Influencer(
        id=1, handle="@fitpro", platform="TikTok",
        city="Austin", followers=1000, engagement=5.0,
        tags=["gym", "HIIT"], bio="Lifting daily.",
    )
    text = inf.corpus_text()
    for fragment in ("@fitpro", "TikTok", "Austin", "gym", "HIIT", "Lifting daily."):
        assert fragment in text


def test_corpus_text_carries_every_field_a_reason_may_cite():
    """A grounded reason quotes a stored field, so the field has to be in the
    text retrieval actually searched. Anything a reason could cite but
    corpus_text omits is a claim the model cannot check honestly."""
    from src.ranking import GROUNDABLE_FIELDS

    inf = Influencer(
        id=1, handle="@fitpro", platform="TikTok", city="Austin",
        country="USA", followers=1000, engagement=5.0,
        tags=["gym", "HIIT"], bio="Lifting daily.",
        content_style="Tutorials", audience_age="25-34",
        audience_gender="60% Female", audience_country="USA",
        brand_collaborations=["Nike", "Gymshark"],
    )
    text = inf.corpus_text()
    for field in GROUNDABLE_FIELDS:
        for value in GROUNDABLE_FIELDS[field](inf):
            assert str(value) in text, f"{field}={value!r} missing from corpus_text"


def test_corpus_text_omits_empty_optional_fields():
    """No 'Audience: ,' placeholders, which would only dilute the vector."""
    inf = Influencer(
        id=1, handle="@a", platform="TikTok", city="Austin",
        followers=1000, engagement=5.0, tags=["gym"], bio="Tips.",
    )
    text = inf.corpus_text()
    assert "Content style" not in text
    assert "Audience" not in text
    assert "Past brand partners" not in text
