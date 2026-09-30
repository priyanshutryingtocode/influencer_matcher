"""Tests for src.vector_store SQL-safety helpers and the index/model guard
(offline, no database)."""

import pytest

from src import config
from src.vector_store import (
    IndexModelMismatch,
    _embedding_dimension,
    _schema_sql,
    _validate_identifier,
    assert_index_matches_config,
)


class FakeConn:
    """Returns queued results in call order: one fetchone, one fetchall."""

    def __init__(self, dimension, models):
        self.results = [[dimension], [(model,) for model in models]]

    def execute(self, sql, params=None):
        return self

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)


@pytest.mark.parametrize("name", ["influencers", "t", "a_1", "Table_2"])
def test_valid_identifiers_accepted(name):
    _validate_identifier(name)  # must not raise


@pytest.mark.parametrize("name", ["", "1abc", "_leading", "bad name", "drop-table", 'x"; --'])
def test_invalid_identifiers_rejected(name):
    with pytest.raises(ValueError, match="safe SQL identifier"):
        _validate_identifier(name)


def test_schema_sql_rejects_unsafe_table():
    with pytest.raises(ValueError):
        _schema_sql('influencers"; DROP TABLE users')


def test_content_hash_stable_and_sensitive():
    from src.vector_store import _content_hash
    assert _content_hash("abc") == _content_hash("abc")
    assert _content_hash("abc") != _content_hash("abd")


def test_signal_columns_are_not_on_the_influencers_table():
    """Inferred fields live in creator_signals, not on the searched row."""
    sql = _schema_sql("influencers")
    body = sql.split("CREATE TABLE")[1]
    for column in ("content_style", "audience_age", "audience_gender",
                   "audience_country", "brand_collaborations"):
        assert f"{column} TEXT" not in body
        assert f"DROP COLUMN IF EXISTS {column}" in sql


def test_signals_are_read_with_a_join_and_coalesced():
    """A missing signal row must not break retrieval.

    Every signal column is COALESCEd, so a creator whose signals row is absent
    (or whose fields are NULL) still reads back as an empty string or zero
    rather than raising.
    """
    import inspect
    from src import vector_store

    sql = inspect.getsource(vector_store.search)
    assert "LEFT JOIN creator_signals" in sql
    assert "s.creator_id = i.id" in sql
    for column in ("content_style", "audience_age", "audience_gender",
                   "audience_country", "brand_collaborations", "reach_ratio",
                   "sponsored_ratio", "growth_trend", "audience_top_countries"):
        assert f"COALESCE(s.{column}" in sql, f"{column} is read without COALESCE"


def test_truncate_cascades_to_signals():
    """TRUNCATE without CASCADE would be blocked by the signals foreign key."""
    import inspect
    from src import vector_store

    assert "TRUNCATE {table} CASCADE" in inspect.getsource(vector_store.replace_influencers)


def test_embedding_dimension_parses_pgvector_type():
    assert _embedding_dimension(FakeConn(f"vector({config.EMBED_DIMENSIONS})", [])) == config.EMBED_DIMENSIONS


def test_embedding_dimension_none_when_column_missing():
    assert _embedding_dimension(FakeConn(None, [])) is None


def test_matching_index_passes_the_guard():
    assert_index_matches_config(FakeConn(f"vector({config.EMBED_DIMENSIONS})", [config.EMBED_MODEL]))


def test_empty_index_passes_the_guard():
    # A freshly migrated table has no rows to mislabel, so there is nothing to
    # reindex yet; the readiness check reports the empty count instead.
    assert_index_matches_config(FakeConn(f"vector({config.EMBED_DIMENSIONS})", []))


def test_wrong_width_reports_a_reindex():
    with pytest.raises(IndexModelMismatch, match="reindex"):
        assert_index_matches_config(FakeConn("vector(384)", [config.EMBED_MODEL]))


def test_stale_embed_model_reports_a_reindex():
    with pytest.raises(IndexModelMismatch, match="reindex"):
        assert_index_matches_config(
            FakeConn(f"vector({config.EMBED_DIMENSIONS})", ["sentence-transformers/all-MiniLM-L6-v2"])
        )
