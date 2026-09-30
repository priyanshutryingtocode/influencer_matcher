"""Tests for the hosted embedder, the query-vector LRU cache, and the
on-disk vector cache used to make reindexing resumable.

No network: the Gemini client is replaced with a fake, and the per-request
floor is turned off so the tests do not sleep.
"""

import json

import numpy as np
import pytest

from src import config, embeddings


class FakeEmbedResponse:
    def __init__(self, values):
        self.embeddings = [type("Embedding", (), {"values": values})()]


class FakeModels:
    def __init__(self, recorder, dimensions=None, fail_times=0):
        self.recorder = recorder
        self.dimensions = dimensions or config.EMBED_DIMENSIONS
        self.fail_times = fail_times
        self.counter = 0

    def embed_content(self, model, contents, config=None):
        self.recorder.append({
            "model": model,
            "text": contents,
            "task_type": config.task_type,
            "output_dimensionality": config.output_dimensionality,
        })
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transient")
        self.counter += 1
        return FakeEmbedResponse([float(self.counter)] * self.dimensions)


class FakeClient:
    def __init__(self, models):
        self.models = models


@pytest.fixture(autouse=True)
def fast_and_clean(monkeypatch):
    monkeypatch.setattr(config, "EMBED_REQUEST_INTERVAL_SECONDS", 0.0)
    embeddings._query_cache.clear()
    embeddings._client = None
    yield
    embeddings._query_cache.clear()
    embeddings._client = None


@pytest.fixture
def recorder():
    return []


@pytest.fixture
def fake_api(monkeypatch, recorder):
    def install(dimensions=None, fail_times=0):
        models = FakeModels(recorder, dimensions=dimensions, fail_times=fail_times)
        monkeypatch.setattr(embeddings, "get_embedding_client", lambda: FakeClient(models))
        return models

    return install


def test_query_uses_retrieval_query_task_and_requested_width(fake_api, recorder):
    fake_api()
    vector = embeddings.embed_query("find me a fitness creator")

    assert vector.shape == (config.EMBED_DIMENSIONS,)
    assert recorder[0]["model"] == config.EMBED_MODEL
    assert recorder[0]["task_type"] == "RETRIEVAL_QUERY"
    assert recorder[0]["output_dimensionality"] == config.EMBED_DIMENSIONS


def test_documents_use_retrieval_document_task(fake_api, recorder):
    fake_api()
    embeddings.embed_documents(["doc one", "doc two"])

    assert [call["task_type"] for call in recorder] == ["RETRIEVAL_DOCUMENT"] * 2
    assert len(recorder) == 2  # one request per text


def test_vectors_are_l2_normalized(fake_api):
    fake_api()
    vector = embeddings.embed_query("anything")

    assert pytest.approx(1.0, abs=1e-5) == float(np.linalg.norm(vector))


def test_wrong_width_raises_actionable_error(fake_api):
    fake_api(dimensions=config.EMBED_DIMENSIONS + 8)

    with pytest.raises(RuntimeError, match="reindex"):
        embeddings.embed_query("anything")


def test_cache_hit_skips_api_call(fake_api, recorder):
    fake_api()
    first = embeddings.get_cached_query_vector("same brief")
    second = embeddings.get_cached_query_vector("same brief")

    assert len(recorder) == 1
    assert (first == second).all()


def test_different_briefs_embed_separately(fake_api, recorder):
    fake_api()
    embeddings.get_cached_query_vector("brief A")
    embeddings.get_cached_query_vector("brief B")

    assert len(recorder) == 2


def test_lru_eviction(monkeypatch, fake_api, recorder):
    fake_api()
    monkeypatch.setattr(embeddings, "_QUERY_CACHE_SIZE", 2)
    for text in ("one", "two", "three"):
        embeddings.get_cached_query_vector(text)
    assert len(embeddings._query_cache) == 2

    before = len(recorder)
    embeddings.get_cached_query_vector("three")
    assert len(recorder) == before  # still cached

    embeddings.get_cached_query_vector("one")
    assert len(recorder) == before + 1

    embeddings.get_cached_query_vector("three")
    assert len(recorder) == before + 1

    embeddings.get_cached_query_vector("two")
    assert len(recorder) == before + 2


def test_query_cache_survives_a_failing_api_call(fake_api):
    fake_api(fail_times=1)
    with pytest.raises(RuntimeError):
        embeddings.get_cached_query_vector("brief")
    assert len(embeddings._query_cache) == 0


def test_embedding_cache_round_trips_and_resumes(tmp_path, fake_api):
    path = tmp_path / "vectors.jsonl"
    fake_api()

    first = embeddings.EmbeddingCache(path)
    first.put_many([("key-a", np.full(config.EMBED_DIMENSIONS, 0.5, dtype=np.float32))])
    assert len(first) == 1

    reopened = embeddings.EmbeddingCache(path)
    assert reopened.hits == 0
    assert reopened.get("key-a") is not None
    assert reopened.misses == 0
    assert pytest.approx(1.0, abs=1e-5) == float(np.linalg.norm(reopened.get("key-a")))


def test_embedding_cache_ignores_other_models_and_widths(tmp_path, fake_api):
    path = tmp_path / "vectors.jsonl"
    records = [
        {"key": "key-a", "model": "some-other-model",
         "dimensions": config.EMBED_DIMENSIONS, "values": [0.1] * config.EMBED_DIMENSIONS},
        {"key": "key-b", "model": config.EMBED_MODEL,
         "dimensions": config.EMBED_DIMENSIONS - 8, "values": [0.1] * (config.EMBED_DIMENSIONS - 8)},
    ]
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    fake_api()

    cache = embeddings.EmbeddingCache(path)
    assert len(cache) == 0
    assert cache.get("key-a") is None
    assert cache.get("key-b") is None


def test_embedding_cache_skips_a_truncated_final_line(tmp_path, fake_api):
    path = tmp_path / "vectors.jsonl"
    path.write_text(
        json.dumps({
            "key": "key-a",
            "model": config.EMBED_MODEL,
            "dimensions": config.EMBED_DIMENSIONS,
            "values": [0.1] * config.EMBED_DIMENSIONS,
        }) + "\n" + '{"key": "key-b", "val',
        encoding="utf-8",
    )
    fake_api()

    cache = embeddings.EmbeddingCache(path)
    assert len(cache) == 1
    assert cache.get("key-b") is None


def test_index_influencers_reuses_cached_vectors(tmp_path, fake_api, recorder):
    from src.data_generator import generate_influencers

    fake_api()
    influencers = generate_influencers(count=3)
    keys = [embeddings.text_key(influencer.corpus_text()) for influencer in influencers]

    cache = embeddings.EmbeddingCache(tmp_path / "vectors.jsonl")
    cache.put_many([(key, np.full(config.EMBED_DIMENSIONS, 0.25, dtype=np.float32)) for key in keys])
    requests_before = len(recorder)

    embeddings.index_influencers(influencers, cache=cache)

    assert len(recorder) == requests_before  # nothing re-billed
    assert all(influencer.embedding is not None for influencer in influencers)
    assert pytest.approx(1.0, abs=1e-5) == float(np.linalg.norm(influencers[0].embedding))


def test_index_influencers_embeds_only_cache_misses(tmp_path, fake_api, recorder):
    from src.data_generator import generate_influencers

    fake_api()
    influencers = generate_influencers(count=4)
    cache = embeddings.EmbeddingCache(tmp_path / "vectors.jsonl")
    cache.put_many([(
        embeddings.text_key(influencers[0].corpus_text()),
        np.full(config.EMBED_DIMENSIONS, 0.25, dtype=np.float32),
    )])
    requests_before = len(recorder)

    embeddings.index_influencers(influencers, cache=cache)

    assert len(recorder) == requests_before + 3
    assert cache.hits == 1
    assert cache.misses == 3


def test_request_floor_spaces_calls(monkeypatch):
    class FakeTime:
        def __init__(self):
            self.now = 100.0
            self.slept: list[float] = []

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.slept.append(seconds)
            self.now += seconds

    fake = FakeTime()
    monkeypatch.setattr(embeddings, "time", fake)
    monkeypatch.setattr(config, "EMBED_REQUEST_INTERVAL_SECONDS", 1.0)
    monkeypatch.setattr(embeddings, "_last_request_at", 100.0)

    embeddings._throttle()
    embeddings._throttle()

    assert fake.slept == [1.0, 1.0]

