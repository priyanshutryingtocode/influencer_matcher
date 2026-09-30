"""Tests for the shared Gemini quota-throttle policy (429 backoff + retry)."""

import pytest
from google.genai import errors

from src import config
from src.gemini_client import (
    DailyQuotaExhausted,
    _daily_quota,
    embed_content_throttled,
    generate_content_throttled,
)

# Shaped like the real free-tier daily-cap response: the human-readable message
# names only the metric, and the actionable per-day quota id lives in the
# structured QuotaFailure list.
_DAILY_PAYLOAD = {
    "error": {
        "code": 429,
        "message": (
            "You exceeded your current quota, please check your plan and billing "
            "details. Quota exceeded for metric: generativelanguage.googleapis.com/"
            "embed_content_free_tier_requests, limit: 1000, model: gemini-embedding-1.0"
        ),
        "status": "RESOURCE_EXHAUSTED",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{
                    "quotaMetric": "generativelanguage.googleapis.com/embed_content_free_tier_requests",
                    "quotaId": "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier",
                    "quotaValue": "1000",
                }],
            },
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "54s"},
        ],
    }
}

# A per-minute throttle carries a RetryInfo but no per-day quota id.
_MINUTE_PAYLOAD = {
    "error": {
        "code": 429,
        "message": "RESOURCE_EXHAUSTED: Quota exceeded. Please retry in 2s",
        "status": "RESOURCE_EXHAUSTED",
        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "2s"}],
    }
}


class ThrottleError(errors.ClientError):
    def __init__(self):
        super().__init__(429, _MINUTE_PAYLOAD)


class DailyQuotaError(errors.ClientError):
    def __init__(self):
        super().__init__(429, _DAILY_PAYLOAD)


class OtherError(errors.ClientError):
    def __init__(self):
        super().__init__(400, {"error": {
            "code": 400,
            "message": "bad request",
            "status": "INVALID_ARGUMENT",
        }})


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("src.gemini_client.time.sleep", slept.append)
    return slept


class FakeModels:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls: list[dict] = []

    def _record(self, method, model, contents, config):
        self.calls.append({"method": method, "model": model, "contents": contents, "config": config})
        if self.failures:
            raise self.failures.pop(0)
        return f"ok:{method}"

    def generate_content(self, model, contents, config=None):
        return self._record("generate_content", model, contents, config)

    def embed_content(self, model, contents, config):
        return self._record("embed_content", model, contents, config)


class FakeClient:
    def __init__(self, failures):
        self.models = FakeModels(failures)


def test_generate_content_retries_throttle_then_succeeds(no_real_sleep):
    client = FakeClient([ThrottleError(), ThrottleError()])

    result = generate_content_throttled(client, "gemini-x", "hello", attempts=3)

    assert result == "ok:generate_content"
    assert len(client.models.calls) == 3
    # The server-supplied delay is parsed out of the message, not guessed.
    assert no_real_sleep == [2.0, 2.0]


def test_generate_content_gives_up_after_attempts(no_real_sleep):
    client = FakeClient([ThrottleError(), ThrottleError()])

    with pytest.raises(ThrottleError):
        generate_content_throttled(client, "gemini-x", "hello", attempts=2)

    assert len(client.models.calls) == 2


def test_non_throttle_errors_are_not_retried(no_real_sleep):
    client = FakeClient([OtherError()])

    with pytest.raises(OtherError):
        generate_content_throttled(client, "gemini-x", "hello", attempts=3)

    assert len(client.models.calls) == 1
    assert no_real_sleep == []


def test_embed_content_passes_dimensions_and_task_type(no_real_sleep):
    client = FakeClient([])

    result = embed_content_throttled(
        client,
        config.EMBED_MODEL,
        "some text",
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=768,
    )

    assert result == "ok:embed_content"
    call = client.models.calls[0]
    assert call["method"] == "embed_content"
    assert call["model"] == config.EMBED_MODEL
    assert call["contents"] == "some text"
    assert call["config"].task_type == "RETRIEVAL_QUERY"
    assert call["config"].output_dimensionality == 768


def test_embed_content_retries_throttle(no_real_sleep):
    client = FakeClient([ThrottleError()])

    result = embed_content_throttled(
        client,
        config.EMBED_MODEL,
        "some text",
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=768,
        attempts=2,
    )

    assert result == "ok:embed_content"
    assert len(client.models.calls) == 2


def test_daily_quota_is_detected_from_the_structured_payload():
    quota_id, limit = _daily_quota(DailyQuotaError())

    assert quota_id == "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"
    assert limit == 1000


def test_per_minute_throttle_is_not_mistaken_for_a_daily_cap():
    assert _daily_quota(ThrottleError()) is None
    assert _daily_quota(OtherError()) is None


def test_daily_cap_raises_immediately_without_sleeping(no_real_sleep):
    client = FakeClient([DailyQuotaError()])

    with pytest.raises(DailyQuotaExhausted) as caught:
        embed_content_throttled(
            client,
            config.EMBED_MODEL,
            "some text",
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
            attempts=3,
        )

    # No backoff: the suggested 54s delay cannot refill a daily counter.
    assert no_real_sleep == []
    assert len(client.models.calls) == 1
    assert "1000 requests/day" in str(caught.value)
    assert "midnight Pacific" in str(caught.value)
    assert caught.value.quota_value == 1000


def test_daily_cap_is_reported_for_ranking_too(no_real_sleep):
    client = FakeClient([DailyQuotaError()])

    with pytest.raises(DailyQuotaExhausted):
        generate_content_throttled(client, config.GEN_MODEL, "hello", attempts=3)

    assert no_real_sleep == []


def test_daily_cap_on_the_last_attempt_is_still_classified(no_real_sleep):
    client = FakeClient([ThrottleError(), DailyQuotaError()])

    with pytest.raises(DailyQuotaExhausted):
        embed_content_throttled(
            client,
            config.EMBED_MODEL,
            "some text",
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
            attempts=2,
        )

    assert no_real_sleep == [2.0]
