"""Tests for src.vector_store SQL-safety helpers (offline, no database)."""

import pytest

from src.vector_store import _schema_sql, _validate_identifier


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
