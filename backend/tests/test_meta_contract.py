"""The /api/v1/meta contract.

The response is typed rather than a bag of dicts. That is the point: a missing
`defaults.goal` shipped silently before, because `dict[str, Any]` validates
nothing and the frontend type promised a key the backend never sent. These
tests make a drift a failure here instead of a TypeError in someone's browser.
"""

import pytest
from pydantic import ValidationError

from api.schemas.models import MetaDefaults, MetaLimits, MetaResponse

VALID = {
    "platforms": ["Any", "Instagram"],
    "defaults": {"goal": "", "audience": "Gen Z", "vibe": "warm", "top_k": 10, "top_n": 5},
    "limits": {
        "top_k_min": 1, "top_k_max": 50, "top_n_min": 1, "top_n_max": 50,
        "goal_min_length": 8, "goal_max_length": 600,
        "audience_max_length": 300, "vibe_max_length": 500,
    },
    "index": {
        "status": "ready", "count": 500,
        "embedding_model": "gemini-embedding-001", "embed_dimensions": 768,
    },
    "ranking": {"model": "gemini-2.5-flash-lite", "fit_levels": ["strong", "weak"]},
}


def test_valid_payload_parses():
    parsed = MetaResponse(**VALID)
    assert parsed.defaults.goal == ""
    assert parsed.limits.goal_min_length == 8
    assert parsed.index.status == "ready"


def test_missing_goal_default_is_still_accepted():
    """Older stored state or a partial payload must not 500.

    `goal` defaults to empty so a payload written before the field existed
    still validates; the crash was the frontend reading it as undefined, not
    the backend omitting it.
    """
    payload = {**VALID, "defaults": {k: v for k, v in VALID["defaults"].items() if k != "goal"}}
    assert MetaResponse(**payload).defaults.goal == ""


@pytest.mark.parametrize("section", ["defaults", "limits", "index", "ranking"])
def test_dropping_a_required_section_is_rejected(section):
    """This is the check a bare dict could not give."""
    payload = {k: v for k, v in VALID.items() if k != section}
    with pytest.raises(ValidationError):
        MetaResponse(**payload)


def test_dropping_a_limits_key_is_rejected():
    limits = {k: v for k, v in VALID["limits"].items() if k != "goal_min_length"}
    with pytest.raises(ValidationError):
        MetaResponse(**{**VALID, "limits": limits})


def test_unknown_index_status_is_rejected():
    with pytest.raises(ValidationError):
        MetaResponse(**{**VALID, "index": {**VALID["index"], "status": "sort_of_ready"}})


def test_limits_and_defaults_are_not_open_dicts():
    """Guards against someone widening them back to dict[str, Any]."""
    assert MetaLimits.model_fields["goal_min_length"].is_required()
    assert MetaDefaults.model_fields["top_k"].annotation is int
