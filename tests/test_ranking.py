"""Tests for src.ranking: response cleaning, fallbacks, fit capping.

The Gemini call is stubbed via monkeypatching
src.ranking.generate_content_throttled, so these tests are fully offline.
"""

import json

import pytest
from google.genai import errors as genai_errors

from src import ranking
from src.models import Brief, Influencer


class _FakeResponse:
    def __init__(self, payload):
        object.__setattr__(self, "_payload", json.dumps(payload))

    @property
    def text(self) -> str:
        return self._payload


def make_influencer(id_: int, niche: str, secondary=None) -> Influencer:
    return Influencer(
        id=id_, handle=f"@c{id_}", niche=niche,
        platform="Instagram", city="Austin",
        followers=10_000, engagement=5.0,
        secondary_niches=secondary or [],
    )


def install_stub(monkeypatch, payload=None, exc=None):
    """Replace the LLM call with a canned response or exception."""
    def fake_generate(client, model, contents, gen_config=None):
        if exc is not None:
            raise exc
        return _FakeResponse(payload)

    monkeypatch.setattr(ranking, "generate_content_throttled", fake_generate)


BRIEF = Brief(niche="Fitness", platform="TikTok")


# ---------------------------------------------------------------- happy path

def test_valid_response_cleaned(monkeypatch):
    install_stub(monkeypatch, {"ranked": [
        {"id": 1, "fit": "strong", "rationale": "r1"},
        {"id": 2, "fit": "weak", "rationale": "r2"},
    ]})
    candidates = [make_influencer(1, "Fitness"), make_influencer(2, "Gaming")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=2)
    assert [e["id"] for e in ranked] == [1, 2]
    assert all(e["source"] == "llm" for e in ranked)
    assert ranked[0]["fit"] == "strong"
    assert ranked[1]["fit"] == "weak"


def test_gen_config_pins_temperature_and_schema():
    cfg = ranking._gen_config()
    assert cfg.temperature == 0.0
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema == ranking.RANKING_SCHEMA
    if getattr(cfg, "thinking_config", None) is not None:
        assert cfg.thinking_config.thinking_budget == 0


# ----------------------------------------------------------------- fallbacks

def test_unparseable_json_falls_back(monkeypatch):
    def broken(client, model, contents, gen_config=None):
        resp = _FakeResponse({"ranked": []})
        object.__setattr__(resp, "_payload", "{not json")
        return resp

    monkeypatch.setattr(ranking, "generate_content_throttled", broken)
    candidates = [make_influencer(1, "Fitness")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert all(e["source"] == "fallback" for e in ranked)


def test_api_error_falls_back(monkeypatch):
    install_stub(monkeypatch, exc=genai_errors.APIError(500, {"message": "boom"}))
    candidates = [make_influencer(1, "Fitness")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert len(ranked) == 1
    assert ranked[0]["source"] == "fallback"
    assert ranked[0]["id"] == 1  # filled from retrieval order


def test_ranked_not_a_list_falls_back(monkeypatch):
    install_stub(monkeypatch, {"ranked": "invalid"})
    candidates = [make_influencer(1, "Fitness")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert all(e["source"] == "fallback" for e in ranked)


def test_no_valid_ids_falls_back(monkeypatch):
    install_stub(monkeypatch, {"ranked": [{"id": 99, "fit": "strong", "rationale": "x"}]})
    candidates = [make_influencer(1, "Fitness")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert all(e["source"] == "fallback" for e in ranked)


# ------------------------------------------------------------ entry cleaning

def test_non_dict_entries_skipped_without_crash(monkeypatch):
    install_stub(monkeypatch, {"ranked": ["garbage", 42, None,
                                           {"id": 2, "fit": "partial", "rationale": "ok"}]})
    candidates = [make_influencer(i, "Fitness") for i in (1, 2, 3)]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=3)
    assert len(ranked) == 3
    assert ranked[0]["id"] == 2 and ranked[0]["source"] == "llm"
    assert {e["source"] for e in ranked[1:]} == {"filled"}


def test_non_int_id_dropped_not_crash(monkeypatch):
    """A list-valued id would previously raise TypeError on set membership."""
    install_stub(monkeypatch, {"ranked": [
        {"id": [1], "fit": "strong", "rationale": "unhashable"},
        {"id": "1", "fit": "strong", "rationale": "string id"},
        {"id": True, "fit": "strong", "rationale": "bool id"},
        {"id": 1, "fit": "partial", "rationale": "real"},
    ]})
    candidates = [make_influencer(1, "Fitness")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert len(ranked) == 1
    assert ranked[0]["id"] == 1 and ranked[0]["source"] == "llm"


def test_duplicate_and_unknown_ids_dropped(monkeypatch):
    install_stub(monkeypatch, {"ranked": [
        {"id": 1, "fit": "partial", "rationale": "a"},
        {"id": 1, "fit": "partial", "rationale": "dup"},
        {"id": 77, "fit": "partial", "rationale": "hallucinated"},
        {"id": 2, "fit": "partial", "rationale": "b"},
    ]})
    candidates = [make_influencer(1, "Fitness"), make_influencer(2, "Yoga")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=4)
    ids = [e["id"] for e in ranked]
    assert ids.count(1) == 1
    # id 77 unknown -> dropped; slot filled from retrieval order (only cand 2 left)
    assert 2 in ids
    assert all(e["id"] != 77 for e in ranked)


def test_invalid_fit_coerced_to_partial(monkeypatch):
    install_stub(monkeypatch, {"ranked": [
        {"id": 1, "fit": "amazing", "rationale": "x"},
    ]})
    candidates = [make_influencer(1, "Fitness")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert ranked[0]["fit"] == "partial"


# ------------------------------------------------------------- fit capping

def test_strong_capped_when_niche_misses(monkeypatch):
    install_stub(monkeypatch, {"ranked": [
        {"id": 1, "fit": "strong", "rationale": "model overclaims"},
    ]})
    candidates = [make_influencer(1, "Gaming")]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=1)
    assert ranked[0]["fit"] == "partial"


def test_strong_allowed_for_secondary_niche(monkeypatch):
    """Regression: secondary-niche matches were previously capped at partial."""
    install_stub(monkeypatch, {"ranked": [
        {"id": 1, "fit": "strong", "rationale": "secondary match"},
    ]})
    candidates = [make_influencer(1, "Fashion", secondary=["Sustainable Fashion", "Fitness"])]
    fitness_brief = Brief(niche="Fitness", platform="Any")
    ranked = ranking.rank_candidates(object(), fitness_brief, candidates, top_n=1)
    assert ranked[0]["fit"] == "strong"


def test_short_list_filled_from_retrieval_order(monkeypatch):
    install_stub(monkeypatch, {"ranked": [
        {"id": 3, "fit": "partial", "rationale": "only this one"},
    ]})
    candidates = [make_influencer(i, "Fitness") for i in (1, 2, 3)]
    ranked = ranking.rank_candidates(object(), BRIEF, candidates, top_n=3)
    assert [e["id"] for e in ranked] == [3, 1, 2]
    assert ranked[0]["source"] == "llm"
    assert {e["source"] for e in ranked[1:]} == {"filled"}
